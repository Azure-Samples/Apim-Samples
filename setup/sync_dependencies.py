"""Install uv dependencies while preserving lock, hash, and age guarantees."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

PYPI_ARTIFACT_HOST = 'files.pythonhosted.org'
PYPI_HOST = 'pypi.org'
PYPI_INDEX = 'https://pypi.org/simple'
WAITING_PERIOD = '7 days'


def _user_config_paths(environment: Mapping[str, str]) -> list[Path]:
    """Return uv user configuration paths in platform preference order."""

    paths: list[Path] = []
    app_data = environment.get('APPDATA')
    if app_data:
        paths.append(Path(app_data) / 'uv' / 'uv.toml')

    xdg_config = environment.get('XDG_CONFIG_HOME')
    if xdg_config:
        paths.append(Path(xdg_config) / 'uv' / 'uv.toml')

    home = environment.get('HOME') or environment.get('USERPROFILE')
    if home:
        paths.append(Path(home) / '.config' / 'uv' / 'uv.toml')

    return list(dict.fromkeys(paths))


def _configured_index(environment: Mapping[str, str] | None = None) -> str:
    """Return the configured default package index or canonical PyPI."""

    active_environment = os.environ if environment is None else environment
    for variable in ('UV_DEFAULT_INDEX', 'UV_INDEX_URL'):
        value = active_environment.get(variable)
        if value:
            return value

    for config_path in _user_config_paths(active_environment):
        if not config_path.is_file():
            continue
        config = tomllib.loads(config_path.read_text(encoding='utf-8'))
        for key in ('default-index', 'index-url'):
            value = config.get(key)
            if isinstance(value, str) and value:
                return value

    return PYPI_INDEX


def _validate_index(index_url: str) -> str:
    """Require a secure package index URL with an explicit hostname."""

    parsed = urlsplit(index_url)
    if parsed.scheme != 'https' or not parsed.hostname:
        raise ValueError('The configured uv package index must use HTTPS and include a hostname.')
    return index_url


def _uses_canonical_pypi(index_url: str) -> bool:
    """Return whether an index URL points to canonical public PyPI."""

    parsed = urlsplit(index_url)
    return parsed.scheme == 'https' and parsed.hostname == PYPI_HOST and parsed.port is None and parsed.path.rstrip('/') == '/simple'


def _canonical_artifact_url(lock_path: Path) -> str | None:
    """Return one validated canonical artifact URL from an existing uv lock."""

    if not lock_path.is_file():
        return None

    lock_data = tomllib.loads(lock_path.read_text(encoding='utf-8'))
    for package in lock_data.get('package', []):
        artifacts = [package.get('sdist'), *package.get('wheels', [])]
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            artifact_url = artifact.get('url')
            if not isinstance(artifact_url, str):
                continue
            parsed = urlsplit(artifact_url)
            if parsed.scheme == 'https' and parsed.hostname == PYPI_ARTIFACT_HOST and parsed.port is None:
                return artifact_url

    return None


def _canonical_artifacts_available(lock_path: Path) -> bool:
    """Return whether the canonical PyPI artifact host is reachable."""

    artifact_url = _canonical_artifact_url(lock_path)
    if artifact_url is None:
        return True

    try:
        with urlopen(Request(artifact_url, method='HEAD'), timeout=10):
            return True
    except (OSError, URLError):
        return False


def _run(command: Sequence[str]) -> None:
    """Run one dependency command and fail on a nonzero exit code."""

    subprocess.run(command, check=True)


def sync_dependencies(repo_root: Path | None = None, uv_path: str | None = None, environment: Mapping[str, str] | None = None) -> None:
    """Verify and install the lock through canonical PyPI or a configured mirror."""

    root = Path(__file__).resolve().parents[1] if repo_root is None else repo_root.resolve()
    uv_command = uv_path or shutil.which('uv')
    if not uv_command:
        raise FileNotFoundError('uv is not installed or not on PATH.')

    _run([sys.executable, str(root / 'setup' / 'verify_dependency_age.py'), '--scope', 'python'])

    index_url = _validate_index(_configured_index(environment))
    if _uses_canonical_pypi(index_url):
        _run([uv_command, 'sync', '--locked'])
        return

    requirements_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix='apim-samples-', suffix='.requirements.txt', delete=False) as requirements_file:
            requirements_path = Path(requirements_file.name)

        _run(
            [
                uv_command,
                'export',
                '--frozen',
                '--no-emit-project',
                '--no-header',
                '--no-annotate',
                '--output-file',
                str(requirements_path),
            ]
        )
        _run(
            [
                uv_command,
                'pip',
                'sync',
                str(requirements_path),
                '--no-config',
                '--default-index',
                index_url,
                '--require-hashes',
                '--system-certs',
                '--strict',
            ]
        )
    finally:
        if requirements_path is not None:
            requirements_path.unlink(missing_ok=True)


def upgrade_and_sync_dependencies(
    repo_root: Path | None = None,
    uv_path: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> None:
    """Upgrade the lock through canonical PyPI, then verify and install it."""

    root = Path(__file__).resolve().parents[1] if repo_root is None else repo_root.resolve()
    uv_command = uv_path or shutil.which('uv')
    if not uv_command:
        raise FileNotFoundError('uv is not installed or not on PATH.')

    if not _canonical_artifacts_available(root / 'uv.lock'):
        print(
            'Canonical PyPI artifacts are unreachable; preserving uv.lock and syncing its verified packages through the configured index.',
            file=sys.stderr,
        )
        sync_dependencies(root, uv_command, environment)
        return

    _run(
        [
            uv_command,
            'lock',
            '--upgrade',
            '--no-config',
            '--default-index',
            PYPI_INDEX,
            '--exclude-newer',
            WAITING_PERIOD,
            '--system-certs',
            '--project',
            str(root),
        ]
    )
    sync_dependencies(root, uv_command, environment)


def main() -> int:
    """Run the guarded dependency synchronization command."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upgrade', action='store_true', help='Upgrade uv.lock from canonical PyPI before syncing dependencies.')
    arguments = parser.parse_args()

    try:
        if arguments.upgrade:
            upgrade_and_sync_dependencies()
        else:
            sync_dependencies()
    except (FileNotFoundError, ValueError, tomllib.TOMLDecodeError, subprocess.CalledProcessError) as error:
        print(f'Dependency sync failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
