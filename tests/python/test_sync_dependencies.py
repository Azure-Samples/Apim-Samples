"""Tests for guarded uv dependency synchronization."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / 'setup'
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

dependency_sync = importlib.import_module('sync_dependencies')


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
