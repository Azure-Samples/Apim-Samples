"""Exercise the real IPython reload lifecycle without Azure, delays, or repository edits."""

import atexit
import importlib
import logging
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from IPython.core.interactiveshell import InteractiveShell
from traitlets.config import Config

# APIM Samples imports
import _runtime_locks
import apimtypes
import logging_config
import notebook_autoreload

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _source(body: str, policy: str = 'reload_safe') -> str:
    """Build a classified temporary module."""
    return f'"""Reload fixture.\n\nAutoreload: {policy}\nTest fixture with an explicit reload contract.\n"""\n{body}\n'


def _write(path: Path, source: str) -> None:
    """Advance source timestamps deterministically and invalidate bytecode without sleeps."""
    timestamp = path.stat().st_mtime + 2 if path.exists() else 1_800_000_000
    path.write_text(source, encoding='utf-8')
    os.utime(path, (timestamp, timestamp))
    Path(importlib.util.cache_from_source(str(path))).unlink(missing_ok=True)
    importlib.invalidate_caches()


def _run(shell: InteractiveShell, source: str) -> None:
    """Execute actual cell events and surface execution errors."""
    result = shell.run_cell(source)
    result.raise_error()


@pytest.fixture
def reload_shell(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[InteractiveShell]:
    """Isolate registrations, module mutations, and IPython history from other tests."""
    config = Config({'HistoryManager': {'hist_file': ':memory:'}, 'InteractiveShell': {'colors': 'nocolor'}})
    shell = InteractiveShell(config=config)
    before = set(sys.modules)
    monkeypatch.setattr(notebook_autoreload, 'get_ipython', lambda: shell)
    monkeypatch.setattr(notebook_autoreload, '_MODULE_ROOTS', (tmp_path,))
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        yield shell
    finally:
        watcher = notebook_autoreload._CONFIGURED_SHELLS.pop(shell, None)
        if watcher is not None:
            shell.events.unregister('post_run_cell', watcher.register_loaded_modules)
        for name in set(sys.modules) - before:
            module = sys.modules.get(name)
            filename = getattr(module, '__file__', None)
            if isinstance(filename, str) and Path(filename).is_relative_to(tmp_path):
                sys.modules.pop(name, None)
        atexit.unregister(shell.atexit_operations)
        shell.atexit_operations()
        shell.cleanup()


@pytest.mark.parametrize('policy', ['reload_safe', 'reload_conditional', 'reload_unsafe'])
def test_get_reload_policy(policy: str) -> None:
    module = ModuleType('classified')
    module.__doc__ = f'Example.\n\nAutoreload: {policy}\nReason.'
    assert notebook_autoreload.get_reload_policy(module) == policy


@pytest.mark.parametrize('docstring', [None, '', 'Autoreload: reload_typo', 'Autoreload: reload_safe\nAutoreload: reload_unsafe'])
def test_get_reload_policy_rejects_missing_invalid_or_duplicate_classification(docstring: str | None) -> None:
    module = ModuleType('unclassified')
    module.__doc__ = docstring
    with pytest.raises(ValueError, match='unclassified: expected one'):
        notebook_autoreload.get_reload_policy(module)


def test_configure_outside_ipython_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    warning = MagicMock()
    monkeypatch.setattr(notebook_autoreload, 'get_ipython', lambda: None)
    monkeypatch.setattr(notebook_autoreload, 'print_warning', warning)
    assert notebook_autoreload.configure_notebook_autoreload() is False
    warning.assert_called_once()


def test_changed_functions_methods_transitive_dependencies_and_state(reload_shell: InteractiveShell, tmp_path: Path) -> None:
    dependency = tmp_path / 'reload_dependency.py'
    helper = tmp_path / 'reload_helper.py'
    _write(dependency, _source('CONSTANT = 1\ndef value():\n    return 1'))
    _write(helper, _source(
        'import reload_dependency\n'
        'def value():\n    return reload_dependency.value()\n'
        'class Client:\n'
        '    def __init__(self):\n        self.saved = 42\n'
        '    def read(self):\n        return self.saved + 1',
        'reload_conditional',
    ))
    _run(reload_shell, 'import reload_helper\nfrom reload_dependency import CONSTANT, value as imported_value\n'
         'client = reload_helper.Client()\ndeployment_outputs = {"apim_name": "keep-me"}\ncomputed = reload_helper.value()')
    assert notebook_autoreload.configure_notebook_autoreload()
    saved_outputs = reload_shell.user_ns['deployment_outputs']
    _write(dependency, _source('CONSTANT = 2\ndef value():\n    return 20'))
    helper_body = helper.read_text(encoding='utf-8').split('"""\n', 1)[1]
    _write(helper, _source(helper_body.replace('self.saved + 1', 'self.saved + 2').replace('self.saved = 42', 'self.saved = 100'), 'reload_conditional'))
    _run(reload_shell, 'observed = (reload_helper.value(), imported_value(), client.read(), reload_helper.Client().read(), CONSTANT, reload_helper.reload_dependency.CONSTANT)')
    assert reload_shell.user_ns['observed'] == (20, 20, 44, 102, 1, 2)
    assert reload_shell.user_ns['client'].saved == 42
    assert reload_shell.user_ns['computed'] == 1
    assert reload_shell.user_ns['deployment_outputs'] is saved_outputs
    assert saved_outputs == {'apim_name': 'keep-me'}


def test_later_imports_register_transitive_modules_without_eager_imports(reload_shell: InteractiveShell, tmp_path: Path) -> None:
    _write(tmp_path / 'reload_unused.py', _source('raise AssertionError("Do not eagerly import this module")'))
    dependency = tmp_path / 'reload_later_dependency.py'
    _write(dependency, _source('def value():\n    return 2'))
    _write(tmp_path / 'reload_later.py', _source('import reload_later_dependency\ndef value():\n    return reload_later_dependency.value()'))
    notebook_autoreload.configure_notebook_autoreload()
    _run(reload_shell, 'import reload_later')
    _write(dependency, _source('def value():\n    return 30'))
    _run(reload_shell, 'observed = reload_later.value()')
    assert reload_shell.user_ns['observed'] == 30
    assert 'reload_unused' not in sys.modules
    assert 'reload_later_dependency' not in reload_shell.user_ns


def test_unchanged_modules_are_not_reexecuted(reload_shell: InteractiveShell, tmp_path: Path) -> None:
    marker = tmp_path / 'executions.txt'
    module = tmp_path / 'reload_unchanged.py'
    body = f'from pathlib import Path\nwith Path({str(marker)!r}).open("a") as output:\n    output.write("import\\n")\ndef value():\n    return 1'
    _write(module, _source(body))
    _run(reload_shell, 'import reload_unchanged')
    notebook_autoreload.configure_notebook_autoreload()
    # Force full reexecution on changed files so incremental reload cannot mask a timestamp regression.
    reload_shell.run_line_magic('autoreload', '1 --full')
    for _ in range(3):
        _run(reload_shell, 'observed = reload_unchanged.value()')
    assert marker.read_text(encoding='utf-8').splitlines() == ['import']
    _write(module, _source(body.replace('return 1', 'return 2')))
    _run(reload_shell, 'observed = reload_unchanged.value()')
    assert reload_shell.user_ns['observed'] == 2
    assert marker.read_text(encoding='utf-8').splitlines() == ['import', 'import']


def test_unsafe_enum_and_external_modules_are_excluded(reload_shell: InteractiveShell, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    owned = tmp_path / 'owned'
    owned.mkdir()
    monkeypatch.setattr(notebook_autoreload, '_MODULE_ROOTS', (owned,))
    monkeypatch.syspath_prepend(str(owned))
    unsafe = owned / 'reload_enum.py'
    external = tmp_path / 'reload_external.py'
    _write(unsafe, _source('from enum import Enum\nclass Choice(Enum):\n    FIRST = 1', 'reload_unsafe'))
    _write(external, _source('def value():\n    return 1'))
    _run(reload_shell, 'import reload_enum\nimport reload_external\nchoice = reload_enum.Choice.FIRST')
    original_enum = reload_shell.user_ns['reload_enum'].Choice
    notebook_autoreload.configure_notebook_autoreload()
    _write(unsafe, _source('from enum import Enum\nclass Choice(Enum):\n    FIRST = 1\n    SECOND = 2', 'reload_unsafe'))
    _write(external, _source('def value():\n    return 999'))
    _run(reload_shell, 'observed = (choice is reload_enum.Choice.FIRST, reload_external.value())')
    assert reload_shell.user_ns['observed'] == (True, 1)
    assert reload_shell.user_ns['reload_enum'].Choice is original_enum


def test_repeated_configuration_preserves_namespace_and_callbacks(reload_shell: InteractiveShell, tmp_path: Path) -> None:
    _write(tmp_path / 'reload_binding.py', _source('def value():\n    return 1'))
    importlib.import_module('reload_binding')
    sentinel = object()
    reload_shell.user_ns['reload_binding'] = sentinel
    notebook_autoreload.configure_notebook_autoreload()
    callbacks = list(reload_shell.events.callbacks['post_run_cell'])
    notebook_autoreload.configure_notebook_autoreload()
    assert reload_shell.user_ns['reload_binding'] is sentinel
    assert reload_shell.events.callbacks['post_run_cell'] == callbacks
    assert len(notebook_autoreload._CONFIGURED_SHELLS[reload_shell].policies) == 1


def test_missing_classification_surfaces_an_error(reload_shell: InteractiveShell, tmp_path: Path) -> None:
    _write(tmp_path / 'reload_missing.py', 'def value():\n    return 1\n')
    _run(reload_shell, 'import reload_missing')
    with pytest.raises(ValueError, match='reload_missing: expected one'):
        notebook_autoreload.configure_notebook_autoreload()


def test_syntax_errors_are_visible_and_corrected_source_recovers(
    reload_shell: InteractiveShell, tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture,
) -> None:
    module = tmp_path / 'reload_broken.py'
    _write(module, _source('def value():\n    return 1'))
    _run(reload_shell, 'import reload_broken')
    notebook_autoreload.configure_notebook_autoreload()
    _write(module, _source('def value(:\n    return 2'))
    _run(reload_shell, 'pass')
    captured = capsys.readouterr()
    assert 'SyntaxError' in captured.err + captured.out + caplog.text
    _write(module, _source('def value():\n    return 200'))
    _run(reload_shell, 'observed = reload_broken.value()')
    assert reload_shell.user_ns['observed'] == 200


def test_real_module_reloads_preserve_locks_logging_and_enum_identity(
    reload_shell: InteractiveShell, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = []
    for stem in ('console', 'azure_resources'):
        source = (PROJECT_ROOT / 'shared' / 'python' / f'{stem}.py').read_text(encoding='utf-8')
        path = tmp_path / f'reload_real_{stem}.py'
        _write(path, source + '\ndef reload_probe():\n    return 1\n')
        paths.append(path)
    _run(reload_shell, 'import reload_real_console\nimport reload_real_azure_resources')
    monkeypatch.setattr(logging.getLogger(), 'level', logging.WARNING)
    handlers = tuple(logging.getLogger().handlers)
    output_lock = _runtime_locks.PRINT_LOCK
    command_lock = _runtime_locks.AZ_CLI_LOCK
    log_state = logging_config._state
    sku = apimtypes.APIM_SKU.BASICV2
    notebook_autoreload.configure_notebook_autoreload()
    reload_shell.run_line_magic('autoreload', '1 --full')
    for path in paths:
        _write(path, path.read_text(encoding='utf-8').replace('def reload_probe():\n    return 1', 'def reload_probe():\n    return 200'))
    _run(reload_shell, 'observed = (reload_real_console.reload_probe(), reload_real_azure_resources.reload_probe())')
    assert reload_shell.user_ns['observed'] == (200, 200)
    assert reload_shell.user_ns['reload_real_console']._print_lock is output_lock
    assert reload_shell.user_ns['reload_real_azure_resources']._AZ_CLI_LOCK is command_lock
    assert logging_config._state is log_state
    assert logging.getLogger().level == logging.WARNING
    assert tuple(logging.getLogger().handlers) == handlers
    assert sku is apimtypes.APIM_SKU.BASICV2


def test_repository_default_classifies_loaded_shared_dependencies(reload_shell: InteractiveShell, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notebook_autoreload, '_MODULE_ROOTS', (PROJECT_ROOT / 'shared' / 'python',))
    notebook_autoreload.configure_notebook_autoreload()
    policies = notebook_autoreload._CONFIGURED_SHELLS[reload_shell].policies
    assert policies['apimtypes'] == 'reload_unsafe'
    assert policies['logging_config'] == 'reload_unsafe'
    assert policies['_runtime_locks'] == 'reload_unsafe'
    assert policies['notebook_autoreload'] == 'reload_unsafe'
    assert policies['utils'] == 'reload_conditional'
    assert policies['azure_resources'] == 'reload_conditional'
    assert policies['console'] == 'reload_conditional'
