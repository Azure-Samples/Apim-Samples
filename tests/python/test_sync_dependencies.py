"""Tests for guarded uv dependency synchronization."""

from __future__ import annotations

import importlib
import runpy
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / 'setup'
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

dependency_sync = importlib.import_module('sync_dependencies')


def test_user_config_paths_uses_platform_locations_without_duplicates(tmp_path: Path) -> None:
    paths = dependency_sync._user_config_paths(
        {
            'APPDATA': str(tmp_path / 'appdata'),
            'XDG_CONFIG_HOME': str(tmp_path / 'xdg'),
            'HOME': str(tmp_path / 'home'),
            'USERPROFILE': str(tmp_path / 'ignored-profile'),
        }
    )

    assert paths == [tmp_path / 'appdata' / 'uv' / 'uv.toml', tmp_path / 'xdg' / 'uv' / 'uv.toml', tmp_path / 'home' / '.config' / 'uv' / 'uv.toml']
    assert dependency_sync._user_config_paths({'HOME': str(tmp_path), 'XDG_CONFIG_HOME': str(tmp_path / '.config')}) == [tmp_path / '.config' / 'uv' / 'uv.toml']


def test_configured_index_prefers_environment(tmp_path: Path) -> None:
    config_path = tmp_path / 'uv' / 'uv.toml'
    config_path.parent.mkdir()
    config_path.write_text('index-url = "https://config.example/simple/"\n', encoding='utf-8')

    index = dependency_sync._configured_index(
        {
            'APPDATA': str(tmp_path),
            'UV_DEFAULT_INDEX': 'https://environment.example/simple/',
        }
    )

    assert index == 'https://environment.example/simple/'


def test_configured_index_reads_each_supported_config_key(tmp_path: Path) -> None:
    appdata_config = tmp_path / 'appdata' / 'uv' / 'uv.toml'
    appdata_config.parent.mkdir(parents=True)
    appdata_config.write_text('unrelated = true\n', encoding='utf-8')
    xdg_config = tmp_path / 'xdg' / 'uv' / 'uv.toml'
    xdg_config.parent.mkdir(parents=True)
    xdg_config.write_text('default-index = "https://default.example/simple/"\n', encoding='utf-8')

    assert dependency_sync._configured_index({'APPDATA': str(tmp_path / 'appdata'), 'XDG_CONFIG_HOME': str(tmp_path / 'xdg')}) == 'https://default.example/simple/'

    xdg_config.write_text('index-url = "https://legacy.example/simple/"\n', encoding='utf-8')
    assert dependency_sync._configured_index({'XDG_CONFIG_HOME': str(tmp_path / 'xdg')}) == 'https://legacy.example/simple/'
    assert dependency_sync._configured_index({'UV_INDEX_URL': 'https://environment.example/simple/'}) == 'https://environment.example/simple/'
    assert dependency_sync._configured_index({}) == dependency_sync.PYPI_INDEX
    assert dependency_sync._configured_index({'APPDATA': str(tmp_path / 'missing')}) == dependency_sync.PYPI_INDEX

    xdg_config.write_text('default-index = 7\nindex-url = "https://fallback.example/simple/"\n', encoding='utf-8')
    assert dependency_sync._configured_index({'XDG_CONFIG_HOME': str(tmp_path / 'xdg')}) == 'https://fallback.example/simple/'

    xdg_config.write_text('default-index = ""\n', encoding='utf-8')
    assert dependency_sync._configured_index({'XDG_CONFIG_HOME': str(tmp_path / 'xdg')}) == dependency_sync.PYPI_INDEX


def test_index_validation_and_canonical_detection() -> None:
    canonical = 'https://pypi.org/simple/'

    assert dependency_sync._validate_index(canonical) == canonical
    assert dependency_sync._uses_canonical_pypi(canonical)
    assert not dependency_sync._uses_canonical_pypi('http://pypi.org/simple/')
    assert not dependency_sync._uses_canonical_pypi('https://mirror.example/simple/')
    assert not dependency_sync._uses_canonical_pypi('https://pypi.org:443/simple/')
    assert not dependency_sync._uses_canonical_pypi('https://pypi.org/other/')


def test_canonical_artifact_url_handles_missing_and_unusable_entries(tmp_path: Path) -> None:
    lock_path = tmp_path / 'uv.lock'

    assert dependency_sync._canonical_artifact_url(lock_path) is None

    lock_path.write_text(
        """
[[package]]
name = "example"
version = "1.0.0"
sdist = "invalid"
wheels = [
  { hash = "sha256:missing-url" },
  { url = 7 },
  { url = "http://files.pythonhosted.org/example.whl" },
  { url = "https://files.pythonhosted.org:443/example.whl" },
  { url = "https://mirror.example/example.whl" },
  { url = "https://files.pythonhosted.org/example.whl" },
]
""",
        encoding='utf-8',
    )

    assert dependency_sync._canonical_artifact_url(lock_path) == 'https://files.pythonhosted.org/example.whl'

    lock_path.write_text('[[package]]\nwheels = [{ url = "https://mirror.example/example.whl" }]\n[[package]]\nwheels = []\n', encoding='utf-8')
    assert dependency_sync._canonical_artifact_url(lock_path) is None


def test_canonical_artifact_availability_handles_all_outcomes(tmp_path: Path) -> None:
    lock_path = tmp_path / 'uv.lock'
    lock_path.write_text('package = []\n', encoding='utf-8')
    assert dependency_sync._canonical_artifacts_available(lock_path)

    lock_path.write_text('[[package]]\nwheels = [{ url = "https://files.pythonhosted.org/example.whl" }]\n', encoding='utf-8')
    response = MagicMock()
    response.__enter__.return_value = response
    with patch.object(dependency_sync, 'urlopen', return_value=response) as urlopen:
        assert dependency_sync._canonical_artifacts_available(lock_path)
    assert urlopen.call_args.args[0].method == 'HEAD'
    assert urlopen.call_args.kwargs == {'timeout': 10}

    for error in (OSError('offline'), URLError('offline')):
        with patch.object(dependency_sync, 'urlopen', side_effect=error):
            assert not dependency_sync._canonical_artifacts_available(lock_path)


def test_run_delegates_to_subprocess() -> None:
    with patch.object(dependency_sync.subprocess, 'run') as subprocess_run:
        dependency_sync._run(['uv', '--version'])

    subprocess_run.assert_called_once_with(['uv', '--version'], check=True)


def test_sync_dependencies_uses_locked_sync_for_canonical_pypi(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    with patch.object(dependency_sync, '_run', side_effect=lambda command: commands.append(list(command))):
        dependency_sync.sync_dependencies(tmp_path, 'uv', {'UV_DEFAULT_INDEX': 'https://pypi.org/simple/'})

    assert commands[0][1:] == [str(tmp_path / 'setup' / 'verify_dependency_age.py'), '--scope', 'python']
    assert commands[1] == ['uv', 'sync', '--locked']


def test_sync_dependencies_exports_hashes_for_mirror_and_cleans_up(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    with patch.object(dependency_sync, '_run', side_effect=lambda command: commands.append(list(command))):
        dependency_sync.sync_dependencies(tmp_path, 'uv', {'UV_DEFAULT_INDEX': 'https://mirror.example/simple/'})

    export_command = commands[1]
    sync_command = commands[2]
    requirements_path = Path(export_command[-1])

    assert export_command[1:6] == ['export', '--frozen', '--no-emit-project', '--no-header', '--no-annotate']
    assert sync_command[:3] == ['uv', 'pip', 'sync']
    assert sync_command[3] == str(requirements_path)
    assert sync_command[4:] == [
        '--no-config',
        '--default-index',
        'https://mirror.example/simple/',
        '--require-hashes',
        '--system-certs',
        '--strict',
    ]
    assert not requirements_path.exists()


def test_sync_dependencies_cleans_up_after_failed_mirror_sync(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fail_sync(command: list[str]) -> None:
        commands.append(list(command))
        if command[1:3] == ['pip', 'sync']:
            raise RuntimeError('sync failed')

    with patch.object(dependency_sync, '_run', side_effect=fail_sync):
        with pytest.raises(RuntimeError, match='sync failed'):
            dependency_sync.sync_dependencies(tmp_path, 'uv', {'UV_DEFAULT_INDEX': 'https://mirror.example/simple/'})

    assert not Path(commands[1][-1]).exists()


def test_sync_dependencies_propagates_temporary_file_creation_failure(tmp_path: Path) -> None:
    with (
        patch.object(dependency_sync, '_run'),
        patch.object(dependency_sync.tempfile, 'NamedTemporaryFile', side_effect=OSError('temporary storage unavailable')),
        pytest.raises(OSError, match='temporary storage unavailable'),
    ):
        dependency_sync.sync_dependencies(tmp_path, 'uv', {'UV_DEFAULT_INDEX': 'https://mirror.example/simple/'})


@pytest.mark.parametrize('operation', [dependency_sync.sync_dependencies, dependency_sync.upgrade_and_sync_dependencies])
def test_dependency_operations_require_uv(tmp_path: Path, operation) -> None:
    with patch.object(dependency_sync.shutil, 'which', return_value=None), pytest.raises(FileNotFoundError, match='uv is not installed'):
        operation(tmp_path)


def test_upgrade_uses_canonical_pypi_then_syncs_through_mirror(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    with patch.object(dependency_sync, '_run', side_effect=lambda command: commands.append(list(command))):
        dependency_sync.upgrade_and_sync_dependencies(tmp_path, 'uv', {'UV_DEFAULT_INDEX': 'https://mirror.example/simple/'})

    assert commands[0] == [
        'uv',
        'lock',
        '--upgrade',
        '--no-config',
        '--default-index',
        'https://pypi.org/simple',
        '--exclude-newer',
        '7 days',
        '--system-certs',
        '--project',
        str(tmp_path),
    ]
    assert commands[1][1:] == [str(tmp_path / 'setup' / 'verify_dependency_age.py'), '--scope', 'python']
    assert commands[2][1] == 'export'
    assert commands[3][:3] == ['uv', 'pip', 'sync']


def test_upgrade_preserves_lock_and_syncs_when_canonical_artifacts_are_unreachable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commands: list[list[str]] = []

    with (
        patch.object(dependency_sync, '_canonical_artifacts_available', return_value=False),
        patch.object(dependency_sync, '_run', side_effect=lambda command: commands.append(list(command))),
    ):
        dependency_sync.upgrade_and_sync_dependencies(tmp_path, 'uv', {'UV_DEFAULT_INDEX': 'https://mirror.example/simple/'})

    assert commands[0][1:] == [str(tmp_path / 'setup' / 'verify_dependency_age.py'), '--scope', 'python']
    assert commands[1][1] == 'export'
    assert commands[2][:3] == ['uv', 'pip', 'sync']
    assert all('lock' not in command for command in commands)
    assert 'preserving uv.lock' in capsys.readouterr().err


def test_upgrade_stops_before_sync_when_lock_fails(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fail_lock(command: list[str]) -> None:
        commands.append(list(command))
        raise RuntimeError('lock failed')

    with patch.object(dependency_sync, '_run', side_effect=fail_lock):
        with pytest.raises(RuntimeError, match='lock failed'):
            dependency_sync.upgrade_and_sync_dependencies(tmp_path, 'uv')

    assert len(commands) == 1


@pytest.mark.parametrize('index_url', ['http://mirror.example/simple/', 'not-a-url'])
def test_sync_dependencies_rejects_insecure_or_invalid_index(tmp_path: Path, index_url: str) -> None:
    with patch.object(dependency_sync, '_run') as run:
        with pytest.raises(ValueError, match='must use HTTPS'):
            dependency_sync.sync_dependencies(tmp_path, 'uv', {'UV_DEFAULT_INDEX': index_url})

    run.assert_called_once()


@pytest.mark.parametrize('upgrade', [False, True])
def test_main_dispatches_requested_operation(monkeypatch: pytest.MonkeyPatch, upgrade: bool) -> None:
    sync = MagicMock()
    upgrade_and_sync = MagicMock()
    arguments = ['sync_dependencies.py']
    if upgrade:
        arguments.append('--upgrade')
    monkeypatch.setattr(sys, 'argv', arguments)
    monkeypatch.setattr(dependency_sync, 'sync_dependencies', sync)
    monkeypatch.setattr(dependency_sync, 'upgrade_and_sync_dependencies', upgrade_and_sync)

    assert dependency_sync.main() == 0
    assert sync.call_count == (0 if upgrade else 1)
    assert upgrade_and_sync.call_count == (1 if upgrade else 0)


@pytest.mark.parametrize(
    'error',
    [
        FileNotFoundError('missing uv'),
        ValueError('invalid index'),
        dependency_sync.tomllib.TOMLDecodeError('invalid TOML', '!', 0),
        subprocess.CalledProcessError(1, ['uv', 'sync']),
    ],
)
def test_main_reports_expected_failures(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], error: Exception) -> None:
    monkeypatch.setattr(sys, 'argv', ['sync_dependencies.py'])
    monkeypatch.setattr(dependency_sync, 'sync_dependencies', MagicMock(side_effect=error))

    assert dependency_sync.main() == 1
    assert 'Dependency sync failed:' in capsys.readouterr().err


def test_script_entry_point_exits_with_main_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'argv', [str(SETUP_PATH / 'sync_dependencies.py')])
    monkeypatch.setenv('UV_DEFAULT_INDEX', 'not-a-url')
    monkeypatch.setattr(subprocess, 'run', MagicMock())

    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(SETUP_PATH / 'sync_dependencies.py'), run_name='__main__')

    assert raised.value.code == 1
