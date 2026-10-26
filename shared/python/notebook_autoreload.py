"""Configure change-triggered autoreload for repository-owned notebook dependencies.

Autoreload: reload_unsafe
Restart the kernel after editing this module; it owns persistent IPython callbacks.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Literal

from IPython import get_ipython
from IPython.core.interactiveshell import ExecutionResult, InteractiveShell

# APIM Samples imports
from console import print_info, print_warning

ReloadPolicy = Literal['reload_safe', 'reload_conditional', 'reload_unsafe']
_POLICY_PATTERN = re.compile(r'^Autoreload: (reload_safe|reload_conditional|reload_unsafe)$', re.MULTILINE)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MODULE_ROOTS = (_PROJECT_ROOT / 'shared' / 'python', _PROJECT_ROOT / 'samples', _PROJECT_ROOT / 'infrastructure')
_CONFIGURED_SHELLS: dict[InteractiveShell, _NotebookAutoreload] = {}


def get_reload_policy(module: ModuleType) -> ReloadPolicy:
    """Read the required, unique reload classification from a module docstring."""
    matches = _POLICY_PATTERN.findall(module.__doc__ or '')
    if len(matches) != 1:
        raise ValueError(
            f'{module.__name__}: expected one module-docstring declaration: '
            'Autoreload: reload_safe, Autoreload: reload_conditional, or Autoreload: reload_unsafe.'
        )

    policy = matches[0]
    if policy == 'reload_safe':
        return 'reload_safe'
    if policy == 'reload_conditional':
        return 'reload_conditional'
    return 'reload_unsafe'


class _NotebookAutoreload:
    """Register newly imported dependencies without eagerly importing other modules."""

    def __init__(self, shell: InteractiveShell) -> None:
        self.shell = shell
        self.seen: dict[str, ModuleType] = {}
        self.policies: dict[str, ReloadPolicy] = {}

    def register_loaded_modules(self, result: ExecutionResult | None = None) -> None:
        """Watch eligible modules, including dependencies imported by later cells."""
        for name, module in tuple(sys.modules.items()):
            if not isinstance(module, ModuleType) or self.seen.get(name) is module:
                continue
            filename = getattr(module, '__file__', None)
            if name in {'__main__', '__mp_main__'} or not isinstance(filename, str):
                self.seen[name] = module
                continue
            path = Path(filename).resolve()
            if path.suffix != '.py' or not any(path.is_relative_to(root) for root in _MODULE_ROOTS):
                self.seen[name] = module
                continue

            policy = get_reload_policy(module)
            self._register(name, policy)
            self.policies[name] = policy
            self.seen[name] = module

    def _register(self, name: str, policy: ReloadPolicy) -> None:
        """Use IPython's public magic without changing notebook name bindings."""
        if policy == 'reload_unsafe':
            self.shell.run_line_magic('aimport', f'-{name}')
            return

        top_name = name.split('.', 1)[0]
        had_binding = top_name in self.shell.user_ns
        previous_binding = self.shell.user_ns.get(top_name)
        try:
            self.shell.run_line_magic('aimport', name)
        finally:
            if had_binding:
                self.shell.user_ns[top_name] = previous_binding
            else:
                self.shell.user_ns.pop(top_name, None)


def configure_notebook_autoreload() -> bool:
    """Enable selective, timestamp-triggered reload without resetting notebook state.

    Call once after the first cell's imports, before constructing helper objects.
    Newly imported repository dependencies are registered after subsequent cells.
    Unsafe modules, third-party packages, and ordinary Python scripts are not reloaded.
    """
    shell = get_ipython()
    if shell is None:
        print_warning('Notebook autoreload is available only in an IPython or Jupyter session.')
        return False

    shell.extension_manager.load_extension('autoreload')
    shell.run_line_magic('autoreload', '1')
    watcher = _CONFIGURED_SHELLS.get(shell)
    if watcher is None:
        watcher = _NotebookAutoreload(shell)
        watcher.register_loaded_modules()
        shell.events.register('post_run_cell', watcher.register_loaded_modules)
        _CONFIGURED_SHELLS[shell] = watcher
        print_info('Notebook autoreload enabled: changed repository modules only; reload_unsafe modules excluded.')
    else:
        watcher.register_loaded_modules()

    return True
