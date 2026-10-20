"""Tests for interactive interpreter discovery and environment bootstrapping."""

import importlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / 'setup'
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

python_environment = importlib.import_module('python_environment')

MISSING_LAUNCHER_WARNING = (
    'warning: Failed to inspect Python interpreter from first executable in the search path at '
    '`C:\\ProgramData\\chocolatey\\bin\\python3.13.exe`\n'
    '  cause: Querying Python failed with exit status exit code: 0xffffffff\n'
    '\n'
    '         [stdout]\n'
    "         Cannot find file at 'c:\\python313\\python.exe' (c:\\python313\\python.exe). "
    'This usually indicates a missing or moved file.\n'
)


def test_discovery_filters_compatibility_and_deduplicates_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep distinct architectures/runtimes, but not repeated launcher aliases."""

    entries = [
        {'key': 'cpython-3.14-x64', 'version': '3.14.8', 'path': '/python 3.14/python'},
        {'key': 'cpython-3.14-x64', 'version': '3.14.8', 'path': '/bin/python3.14'},
        {'key': 'cpython-3.14-arm64', 'version': '3.14.8', 'path': '/arm/python'},
        {'key': 'cpython-3.12-x64', 'version': '3.12.10', 'path': '/python3.12'},
    ]
    run = Mock(return_value = subprocess.CompletedProcess([], 0, stdout = json.dumps(entries), stderr = ''))
    monkeypatch.setattr(python_environment.subprocess, 'run', run)

    installations = python_environment.discover_python_installations('uv', '>=3.12')

    assert [str(item.path) for item in installations] == [str(Path(entry['path'])) for entry in (entries[0], entries[2], entries[3])]
    run.assert_called_once_with(
        ['uv', 'python', 'list', '>=3.12', '--only-installed', '--output-format', 'json', '--offline'],
        capture_output = True, text = True, check = True,
    )


@pytest.mark.parametrize('output', ['invalid JSON', '{}', '[{}]', '[null]', '[{"key": "python", "path": null, "version": "3.12"}]'])
def test_discovery_rejects_malformed_results(output: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not turn invalid discovery output into a successful empty result."""

    monkeypatch.setattr(python_environment.subprocess, 'run', Mock(return_value = subprocess.CompletedProcess([], 0, stdout = output, stderr = '')))

    with pytest.raises(ValueError):
        python_environment.discover_python_installations('uv', '>=3.12')


def test_discovery_reports_warnings(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Surface broken interpreters reported by uv while keeping valid results."""

    monkeypatch.setattr(python_environment.subprocess, 'run', Mock(return_value = subprocess.CompletedProcess([], 0, stdout = '[]', stderr = 'Broken interpreter')))

    assert python_environment.discover_python_installations('uv', '>=3.12') == []
    assert 'Broken interpreter' in capsys.readouterr().err


@pytest.mark.parametrize('has_installation', [False, True])
@pytest.mark.parametrize('first_executable', [False, True])
def test_discovery_silently_skips_missing_launchers(
    has_installation: bool, first_executable: bool, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing launcher targets are silent without changing valid discovery results."""

    entries = [{'key': 'cpython-3.14-x64', 'version': '3.14.8', 'path': '/python314'}] if has_installation else []
    warning = MISSING_LAUNCHER_WARNING if first_executable else MISSING_LAUNCHER_WARNING.replace('first executable in the ', '')
    monkeypatch.setattr(
        python_environment.subprocess, 'run',
        Mock(return_value = subprocess.CompletedProcess([], 0, stdout = json.dumps(entries), stderr = warning)),
    )

    installations = python_environment.discover_python_installations('uv', '>=3.12')

    assert [installation.path for installation in installations] == ([Path('/python314')] if has_installation else [])
    captured = capsys.readouterr()
    assert captured.err == ''
    assert captured.out == ''


@pytest.mark.parametrize('placement', ['before', 'after'])
def test_discovery_preserves_other_diagnostics(
    placement: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Filtering a missing launcher warning must not hide adjacent diagnostics."""

    other = 'warning: Another interpreter could not be inspected\n  cause: Access denied\n'
    warning = other + MISSING_LAUNCHER_WARNING if placement == 'before' else MISSING_LAUNCHER_WARNING + other
    monkeypatch.setattr(
        python_environment.subprocess, 'run',
        Mock(return_value = subprocess.CompletedProcess([], 0, stdout = '[]', stderr = warning)),
    )

    assert python_environment.discover_python_installations('uv', '>=3.12') == []
    assert capsys.readouterr().err == other


@pytest.mark.parametrize('warning', [
    MISSING_LAUNCHER_WARNING.replace('This usually indicates a missing or moved file.', 'Access denied.'),
    MISSING_LAUNCHER_WARNING.replace('warning: Failed to inspect Python interpreter from ', 'error: Failed to inspect Python interpreter from '),
])
def test_discovery_keeps_unrecognized_launcher_diagnostics(
    warning: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Do not suppress other launcher problems or diagnostics marked as errors."""

    monkeypatch.setattr(
        python_environment.subprocess, 'run',
        Mock(return_value = subprocess.CompletedProcess([], 0, stdout = '[]', stderr = warning)),
    )

    assert python_environment.discover_python_installations('uv', '>=3.12') == []
    assert capsys.readouterr().err == warning


def test_discovery_propagates_command_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even a recognized missing-launcher message cannot mask a failing uv command."""

    error = subprocess.CalledProcessError(1, 'uv', stderr = MISSING_LAUNCHER_WARNING)
    monkeypatch.setattr(python_environment.subprocess, 'run', Mock(side_effect = error))

    with pytest.raises(subprocess.CalledProcessError) as raised:
        python_environment.discover_python_installations('uv', '>=3.12')
    assert raised.value is error


@pytest.mark.parametrize('choice, expected', [('', '/python314'), ('1', '/python314'), ('2', '/python312')])
def test_selection_uses_numbered_choice(choice: str, expected: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Use the selected executable, including paths not on PATH."""

    installations = [
        python_environment.PythonInstallation('3.14', '3.14.8', Path('/python314')),
        python_environment.PythonInstallation('3.12', '3.12.10', Path('/python312')),
    ]
    monkeypatch.setattr('builtins.input', lambda _: choice)

    assert python_environment.select_python_installation(installations, None) == Path(expected)


def test_selection_reprompts_invalid_input(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Out-of-range, negative, nonnumeric and non-ASCII numbers cannot select."""

    choices = iter(['text', '-1', '0', '2', '\u00b2', '1'])
    monkeypatch.setattr('builtins.input', lambda _: next(choices))
    installation = python_environment.PythonInstallation('3.12', '3.12.10', Path('/python312'))

    assert python_environment.select_python_installation([installation], None) == installation.path
    assert capsys.readouterr().out.count('Invalid selection') == 5


@pytest.mark.parametrize('choice', ['', '0'])
def test_selection_keeps_existing_environment(choice: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keeping an existing environment is the safe default, even if uv finds none."""

    monkeypatch.setattr('builtins.input', lambda _: choice)
    run = Mock(return_value = subprocess.CompletedProcess([], 0, stdout = 'Python 3.14.8\n'))
    monkeypatch.setattr(python_environment.subprocess, 'run', run)
    existing = Path('/project/.venv/python')

    assert python_environment.select_python_installation([], existing) == existing
    run.assert_called_once_with([str(existing), '--version'], capture_output = True, text = True, check = True)


@pytest.mark.parametrize('has_existing', [False, True])
def test_selection_aligns_menu_columns(has_existing: bool, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Align versions, identities, separators and paths, including two-digit options."""

    installations = [
        python_environment.PythonInstallation(f'cpython-3.12.{index}-x64', f'3.12.{index}', Path(f'/Python {index}/python'))
        for index in range(1, 12)
    ]
    existing = Path('/project/.venv/python') if has_existing else None
    monkeypatch.setattr('builtins.input', lambda _: '')
    monkeypatch.setattr(
        python_environment.subprocess, 'run',
        Mock(return_value = subprocess.CompletedProcess([], 0, stdout = 'Python 3.14.8\n')),
    )

    selected = python_environment.select_python_installation(installations, existing)

    assert selected == (existing if has_existing else installations[0].path)
    lines = capsys.readouterr().out.splitlines()
    rows = [line for line in lines if ') Python ' in line]
    assert len(rows) == len(installations) + int(has_existing)
    for marker in (')', 'Python ', '[', ' - '):
        assert len({row.index(marker) for row in rows}) == 1
    for row, installation in zip(rows[int(has_existing):], installations, strict = True):
        assert row.split(' - ', 1)[1].removesuffix(' (default)') == str(installation.path)
    assert sum(row.endswith(' (default)') for row in rows) == 1
    if has_existing:
        assert 'Python 3.14.8' in rows[0]
        assert '[Keep existing environment]' in rows[0]
        assert rows[0].endswith(f' - {existing} (default)')
    cancel_index = next(index for index, line in enumerate(lines) if ') Cancel setup' in line)
    assert lines[cancel_index - 1] == ''
    assert lines[cancel_index + 1] == ''
    assert lines[cancel_index].index(')') == rows[0].index(')')


def test_selection_requires_installed_python() -> None:
    """An empty discovery result cannot cause an automatic interpreter download."""

    with pytest.raises(ValueError, match = 'No compatible installed Python'):
        python_environment.select_python_installation([], None)


@pytest.fixture
def bootstrap_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate setup so tests never touch the real virtual environment."""

    setup = tmp_path / 'setup'
    setup.mkdir()
    (tmp_path / 'pyproject.toml').write_text('[project]\nrequires-python = ">=3.12"\n', encoding = 'utf-8')
    monkeypatch.setattr(python_environment, '__file__', str(setup / 'python_environment.py'))
    monkeypatch.setattr(python_environment.shutil, 'which', lambda _: 'uv')
    monkeypatch.setattr(
        python_environment, 'discover_python_installations',
        lambda *args: [python_environment.PythonInstallation('3.12', '3.12.10', tmp_path / 'Python 3.12' / 'python')],
    )
    monkeypatch.setattr('builtins.input', lambda _: '1')
    return tmp_path


def _existing_python(project: Path) -> Path:
    """Create a placeholder with the platform's expected venv interpreter path."""

    path = project / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    path.parent.mkdir(parents = True)
    path.touch()
    return path


def test_bootstrap_creates_syncs_and_configures_selected_python(bootstrap_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Propagate the chosen runtime through creation, guarded install and kernel setup."""

    run = Mock()
    monkeypatch.setattr(python_environment.subprocess, 'run', run)
    monkeypatch.setenv('VIRTUAL_ENV', '/unrelated/environment')
    monkeypatch.setenv('UV_PYTHON', 'wrong-python')
    monkeypatch.setenv('UV_PROJECT_ENVIRONMENT', '/unrelated/environment')
    monkeypatch.setenv('UV_PYTHON_DOWNLOADS', 'automatic')

    assert python_environment.setup_python_environment() == 0

    create, sync, configure = run.call_args_list
    assert create.args[0] == ['uv', 'venv', '--python', str(bootstrap_project / 'Python 3.12' / 'python'), '--no-python-downloads', str(bootstrap_project / '.venv')]
    venv_python = bootstrap_project / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    assert sync.args[0] == [str(venv_python), str(bootstrap_project / 'setup' / 'sync_dependencies.py')]
    assert configure.args[0] == [str(venv_python), str(bootstrap_project / 'setup' / 'local_setup.py'), '--configure-workspace']
    for call in (sync, configure):
        assert call.kwargs['cwd'] == bootstrap_project
        assert call.kwargs['check'] is True
        assert call.kwargs['env']['UV_PYTHON'] == str(venv_python)
        assert call.kwargs['env']['UV_PROJECT_ENVIRONMENT'] == str(bootstrap_project / '.venv')
        assert call.kwargs['env']['UV_PYTHON_DOWNLOADS'] == 'never'
        assert 'VIRTUAL_ENV' not in call.kwargs['env']


def test_bootstrap_reuses_existing_environment(bootstrap_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the existing interpreter without calling uv venv."""

    existing = _existing_python(bootstrap_project)
    monkeypatch.setattr('builtins.input', lambda _: '')
    run = Mock(return_value = subprocess.CompletedProcess([], 0, stdout = 'Python 3.14.8\n'))
    monkeypatch.setattr(python_environment.subprocess, 'run', run)

    assert python_environment.setup_python_environment() == 0
    assert len(run.call_args_list) == 3
    assert run.call_args_list[1].args[0][0] == str(existing)
    assert all(call.args[0][1] != 'venv' for call in run.call_args_list)


@pytest.mark.parametrize('confirmation, replaced', [('', False), ('n', False), ('yes', True), ('Y', True)])
def test_bootstrap_requires_replacement_confirmation(
    bootstrap_project: Path, monkeypatch: pytest.MonkeyPatch, confirmation: str, replaced: bool,
) -> None:
    """Only an explicit affirmative answer permits clearing an existing venv."""

    _existing_python(bootstrap_project)
    choices = iter(['1', confirmation])
    monkeypatch.setattr('builtins.input', lambda _: next(choices))
    run = Mock(return_value = subprocess.CompletedProcess([], 0, stdout = 'Python 3.14.8\n'))
    monkeypatch.setattr(python_environment.subprocess, 'run', run)

    assert python_environment.setup_python_environment() == 0
    creates = [call.args[0] for call in run.call_args_list if call.args[0][1] == 'venv']
    assert bool(creates) == replaced
    if replaced:
        assert creates[0][-2:] == ['--clear', str(bootstrap_project / '.venv')]
    else:
        assert run.call_count == 1


def test_bootstrap_refuses_to_replace_running_environment(bootstrap_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid deleting an interpreter which is currently running setup."""

    _existing_python(bootstrap_project)
    monkeypatch.setattr(sys, 'prefix', str(bootstrap_project / '.venv'))
    choices = iter(['1', 'y'])
    monkeypatch.setattr('builtins.input', lambda _: next(choices))
    run = Mock(return_value = subprocess.CompletedProcess([], 0, stdout = 'Python 3.14.8\n'))
    monkeypatch.setattr(python_environment.subprocess, 'run', run)

    assert python_environment.setup_python_environment() == 1
    assert run.call_count == 1


@pytest.mark.parametrize('error', [EOFError(), KeyboardInterrupt()])
def test_bootstrap_cancels_on_interrupted_input(bootstrap_project: Path, monkeypatch: pytest.MonkeyPatch, error: BaseException) -> None:
    """Cancellation before selection creates and installs nothing."""

    monkeypatch.setattr('builtins.input', Mock(side_effect = error))
    run = Mock()
    monkeypatch.setattr(python_environment.subprocess, 'run', run)

    assert python_environment.setup_python_environment() == 0
    run.assert_not_called()


def test_bootstrap_quit_preserves_environment(bootstrap_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The menu's quit option exits before any mutation."""

    monkeypatch.setattr('builtins.input', lambda _: 'q')
    run = Mock()
    monkeypatch.setattr(python_environment.subprocess, 'run', run)

    assert python_environment.setup_python_environment() == 0
    run.assert_not_called()


@pytest.mark.parametrize('failing_step', [0, 1, 2])
def test_bootstrap_stops_on_subprocess_failure(bootstrap_project: Path, monkeypatch: pytest.MonkeyPatch, failing_step: int) -> None:
    """Creation, dependency verification/sync and workspace failures must propagate."""

    run = Mock(side_effect = [*[None] * failing_step, subprocess.CalledProcessError(1, 'setup', stderr = 'failure details')])
    monkeypatch.setattr(python_environment.subprocess, 'run', run)

    assert python_environment.setup_python_environment() == 1
    assert run.call_count == failing_step + 1


def test_bootstrap_requires_uv(bootstrap_project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Missing uv produces actionable guidance rather than installing it implicitly."""

    monkeypatch.setattr(python_environment.shutil, 'which', lambda _: None)

    assert python_environment.setup_python_environment() == 1
    assert 'uv is required' in capsys.readouterr().err
