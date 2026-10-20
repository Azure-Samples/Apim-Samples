"""Discover installed Python interpreters and bootstrap the local environment."""

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PythonInstallation:
    """An installed interpreter and its user-visible identity."""

    key: str
    version: str
    path: Path


def _report_discovery_diagnostics(stderr: str) -> None:
    """Report uv diagnostics except known warnings about missing launcher targets."""

    for block in re.split(r'(?=^\S)', stderr, flags=re.MULTILINE):
        diagnostic = block.strip()
        if not diagnostic:
            continue
        lines = diagnostic.splitlines()
        missing_launcher = lines[0].startswith('warning: Failed to inspect Python interpreter from ') and any(
            line.strip().startswith('Cannot find file at ') and line.strip().endswith('This usually indicates a missing or moved file.') for line in lines[1:]
        )
        if not missing_launcher:
            print(diagnostic, file=sys.stderr)


def discover_python_installations(uv_path: str, requirement: str) -> list[PythonInstallation]:
    """Use uv's cross-platform discovery without downloading any interpreters."""

    result = subprocess.run(
        [uv_path, 'python', 'list', requirement, '--only-installed', '--output-format', 'json', '--offline'],
        capture_output=True,
        text=True,
        check=True,
    )
    _report_discovery_diagnostics(result.stderr)
    entries = json.loads(result.stdout)
    if not isinstance(entries, list):
        raise ValueError('uv returned an invalid installed-Python list.')

    installations: dict[str, PythonInstallation] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not all(isinstance(entry.get(field), str) and entry[field] for field in ('key', 'version', 'path')):
            raise ValueError('uv returned an invalid installed-Python entry.')
        installation = PythonInstallation(entry['key'], entry['version'], Path(entry['path']))
        # uv lists launcher aliases separately; retain one path per runtime.
        installations.setdefault(installation.key, installation)

    return list(installations.values())


def select_python_installation(installations: list[PythonInstallation], venv_python: Path | None) -> Path:
    """Prompt for an installed runtime, defaulting to keeping an existing venv."""

    if not installations and venv_python is None:
        raise ValueError('No compatible installed Python was found. Install a version matching requires-python in pyproject.toml and retry.')

    print('\nChoose the Python interpreter for .venv:\n')
    rows: list[tuple[int, str, str, Path]] = []
    if venv_python is not None:
        result = subprocess.run([str(venv_python), '--version'], capture_output=True, text=True, check=True)
        rows.append((0, result.stdout.strip(), '[Keep existing environment]', venv_python))
    rows.extend((index, f'Python {installation.version}', f'[{installation.key}]', installation.path) for index, installation in enumerate(installations, start=1))
    option_width = max(len(str(row[0])) for row in rows)
    version_width = max(len(row[1]) for row in rows)
    identity_width = max(len(row[2]) for row in rows)
    default_index = 0 if venv_python is not None else 1
    for index, version, identity, path in rows:
        default = ' (default)' if index == default_index else ''
        print(f'  {index:>{option_width}}) {version:<{version_width}} {identity:<{identity_width}} - {path}{default}')
    print(f'\n  {"q":>{option_width}}) Cancel setup\n')

    while True:
        choice = input('Select an option: ').strip().lower()
        if choice == 'q':
            raise KeyboardInterrupt
        if not choice:
            choice = '0' if venv_python is not None else '1'
        if choice == '0' and venv_python is not None:
            return venv_python
        if choice.isascii() and choice.isdecimal() and 1 <= int(choice) <= len(installations):
            return installations[int(choice) - 1].path
        print('Invalid selection. Enter a listed number or q to cancel.')


def setup_python_environment() -> int:
    """Create/sync the selected venv, then configure it using its own Python."""

    try:
        root = Path(__file__).resolve().parents[1]
        uv_path = shutil.which('uv')
        if uv_path is None:
            raise FileNotFoundError('uv is required for complete setup. Install it using the instructions in setup/README.md.')
        with (root / 'pyproject.toml').open('rb') as project_file:
            requirement = tomllib.load(project_file)['project']['requires-python']
        print(f'\nDetecting installed Python interpreters matching {requirement}...')
        installations = discover_python_installations(uv_path, requirement)
        venv = root / '.venv'
        venv_python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        existing_python = venv_python if venv_python.is_file() else None
        selected_python = select_python_installation(installations, existing_python)
        if selected_python != existing_python:
            if venv.exists():
                confirmation = input('Replace .venv and its installed packages? [y/N]: ').strip().lower()
                if confirmation not in ('y', 'yes'):
                    print('Setup cancelled; the existing environment was not changed.')
                    return 0
                if sys.prefix != sys.base_prefix and Path(sys.prefix).resolve() == venv.resolve():
                    raise ValueError('Cannot replace the environment running setup. Deactivate it and retry using the Developer CLI or a system Python.')
            command = [uv_path, 'venv', '--python', str(selected_python), '--no-python-downloads']
            if venv.exists():
                command.append('--clear')
            subprocess.run([*command, str(venv)], cwd=root, check=True)

        environment = os.environ.copy()
        environment.pop('VIRTUAL_ENV', None)
        environment['UV_PROJECT_ENVIRONMENT'] = str(venv)
        environment['UV_PYTHON'] = str(venv_python)
        environment['UV_PYTHON_DOWNLOADS'] = 'never'
        subprocess.run(
            [str(venv_python), str(root / 'setup' / 'sync_dependencies.py')],
            cwd=root,
            env=environment,
            check=True,
        )
        subprocess.run(
            [str(venv_python), str(root / 'setup' / 'local_setup.py'), '--configure-workspace'],
            cwd=root,
            env=environment,
            check=True,
        )
        return 0
    except (EOFError, KeyboardInterrupt):
        print('\nSetup cancelled.')
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f'Python environment setup failed: {error}', file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        return 1
