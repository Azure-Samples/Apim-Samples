"""Unit tests for verify_local_setup script."""

from __future__ import annotations

import builtins
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import Mock, patch

import pytest

# Ensure the setup folder is on sys.path so the verification script is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / 'setup'
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

if TYPE_CHECKING:
    vls = cast(ModuleType, None)
else:
    vls = cast(ModuleType, importlib.import_module('verify_local_setup'))


def _fake_import_factory(overrides: dict[str, Any]):
    real_import = builtins.__import__

    def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name in overrides:
            value = overrides[name]
            if isinstance(value, Exception):
                raise value
            return value
        return real_import(name, *args, **kwargs)

    return _fake_import


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def temp_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Temporarily override Path.cwd to return tmp_path."""
    monkeypatch.setattr(Path, 'cwd', lambda: tmp_path)
    return tmp_path


@pytest.fixture
def suppress_print(monkeypatch: pytest.MonkeyPatch) -> None:
    """Suppress print output during tests."""
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)


@pytest.fixture
def mock_az_cli():
    """Patch shutil.which and subprocess.run for mocking az commands."""
    with patch('shutil.which') as mock_which, patch('subprocess.run') as mock_run:
        yield mock_which, mock_run


# ============================================================
# Tests for print_status
# ============================================================


def test_print_status_success():
    """print_status should tolerate success messages."""
    vls.print_status('ok', success=True)


def test_print_status_success_with_fix():
    """print_status should print success without fix when success=True."""
    vls.print_status('ok', success=True, fix='ignored')


def test_print_status_failure_with_fix():
    """print_status should print failure message with fix when success=False."""
    with patch('builtins.print') as mock_print:
        vls.print_status('bad', success=False, fix='do this')
        # Verify the status line and the fix line were printed
        assert mock_print.call_count == 2
        # First call is status line
        first_call = mock_print.call_args_list[0][0][0]
        assert 'FAIL' in first_call
        assert 'bad' in first_call
        # Second call is fix line (covers elif not success branch)
        second_call = mock_print.call_args_list[1][0][0]
        assert '👉 Fix:' in second_call
        assert 'do this' in second_call


def test_print_status_skipped():
    """print_status should tolerate skipped checks with note."""
    vls.print_status('skipped check', skipped=True, fix='reason for skip')


def test_print_status_skipped_with_note():
    """print_status should print skipped message with note when skipped=True."""
    with patch('builtins.print') as mock_print:
        vls.print_status('check', skipped=True, fix='reason')
        # Verify the status line and the note line were printed
        assert mock_print.call_count == 2
        # First call is status line
        first_call = mock_print.call_args_list[0][0][0]
        assert 'SKIPPED' in first_call
        # Second call is note line
        second_call = mock_print.call_args_list[1][0][0]
        assert 'ℹ️  Note:' in second_call
        assert 'reason' in second_call


# ============================================================
# Tests for check_virtual_environment
# ============================================================


def test_check_virtual_environment_success(temp_cwd: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Virtual environment check should pass when .venv exists and python resides inside it."""
    scripts_dir = temp_cwd / '.venv' / ('Scripts' if sys.platform.startswith('win') else 'bin')
    scripts_dir.mkdir(parents=True)
    venv_python = scripts_dir / 'python'
    venv_python.write_text('#!/usr/bin/env python')

    monkeypatch.setattr(sys, 'executable', str(venv_python))

    ok, fix = vls.check_virtual_environment()
    assert ok is True
    assert not fix


def test_check_virtual_environment_missing(temp_cwd: Path) -> None:
    """Virtual environment check should fail when .venv doesn't exist."""
    ok, fix = vls.check_virtual_environment()
    assert ok is False
    assert 'Create' in fix


def test_check_virtual_environment_wrong_python(temp_cwd: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Virtual environment check should fail when python is not from .venv."""
    (temp_cwd / '.venv').mkdir()
    monkeypatch.setattr(sys, 'executable', '/usr/bin/python')

    ok, fix = vls.check_virtual_environment()
    assert ok is False
    assert 'Activate' in fix


# ============================================================
# Tests for check_uv_sync
# ============================================================


def test_check_uv_sync_uv_not_installed() -> None:
    """UV sync check should fail when uv is not installed."""
    with patch('shutil.which') as mock_which:
        mock_which.return_value = None
        ok, fix = vls.check_uv_sync()
        assert ok is False
        assert 'Install uv' in fix
        assert 'https://docs.astral.sh/uv/' in fix


def test_check_uv_sync_success_venv_exists(temp_cwd: Path) -> None:
    """UV sync check should pass when uv syncs dependencies successfully."""
    (temp_cwd / '.venv').mkdir()

    with patch('shutil.which', return_value='/usr/bin/uv'), patch.object(vls, 'sync_dependencies') as mock_sync:
        ok, fix = vls.check_uv_sync()

    assert ok is True
    assert not fix
    mock_sync.assert_called_once_with(uv_path='/usr/bin/uv')


def test_check_uv_sync_fail_sync(temp_cwd: Path) -> None:
    """UV sync check should fail when uv sync fails."""
    (temp_cwd / '.venv').mkdir()

    with (
        patch('shutil.which', return_value='/usr/bin/uv'),
        patch.object(
            vls,
            'sync_dependencies',
            side_effect=subprocess.CalledProcessError(1, ['uv', 'sync']),
        ),
    ):
        ok, fix = vls.check_uv_sync()

    assert ok is False
    assert 'Failed to sync dependencies' in fix


def test_check_uv_sync_creates_venv_then_syncs(temp_cwd: Path) -> None:
    """UV sync check should create venv if missing then sync successfully."""
    with patch('shutil.which', return_value='/usr/bin/uv'), patch('subprocess.run', return_value=Mock(returncode=0)) as mock_run, patch.object(vls, 'sync_dependencies') as mock_sync:
        ok, fix = vls.check_uv_sync()

    assert ok is True
    assert not fix
    mock_run.assert_called_once()
    assert 'venv' in mock_run.call_args[0][0]
    mock_sync.assert_called_once_with(uv_path='/usr/bin/uv')


def test_check_uv_sync_fail_venv_creation(temp_cwd: Path) -> None:
    """UV sync check should fail when venv creation fails."""
    with patch('shutil.which', return_value='/usr/bin/uv'):
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, ['uv', 'venv'])):
            ok, fix = vls.check_uv_sync()
            assert ok is False
            assert 'Failed to create venv' in fix


def test_check_uv_sync_venv_created_but_sync_fails(temp_cwd: Path) -> None:
    """UV sync check should fail when venv is created but sync fails."""
    with (
        patch('shutil.which', return_value='/usr/bin/uv'),
        patch('subprocess.run', return_value=Mock(returncode=0)),
        patch.object(
            vls,
            'sync_dependencies',
            side_effect=subprocess.CalledProcessError(1, ['uv', 'sync']),
        ),
    ):
        ok, fix = vls.check_uv_sync()

    assert ok is False
    assert 'Failed to sync dependencies' in fix


# ============================================================
# Tests for check_required_packages
# ============================================================


def test_check_required_packages_all_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Package check should return True when all dependencies are available."""
    fake_import = _fake_import_factory(
        {
            'requests': SimpleNamespace(__name__='requests'),
            'ipykernel': SimpleNamespace(__name__='ipykernel'),
            'jupyter_client': SimpleNamespace(__name__='jupyter_client'),
            'dotenv': SimpleNamespace(__name__='dotenv'),
        }
    )
    monkeypatch.setattr('builtins.__import__', fake_import)

    ok, fix = vls.check_required_packages()
    assert ok is True
    assert not fix


def test_check_required_packages_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Package check should return False when any dependency fails to import."""
    fake_import = _fake_import_factory(
        {
            'requests': SimpleNamespace(__name__='requests'),
            'ipykernel': SimpleNamespace(__name__='ipykernel'),
            'jupyter_client': SimpleNamespace(__name__='jupyter_client'),
            'dotenv': ImportError('dotenv missing'),
        }
    )
    monkeypatch.setattr('builtins.__import__', fake_import)

    ok, fix = vls.check_required_packages()
    assert ok is False
    assert 'setup/sync_dependencies.py' in fix


def test_check_required_packages_requests_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Package check should return False when requests is missing."""
    fake_import = _fake_import_factory(
        {
            'requests': ImportError('requests missing'),
            'ipykernel': SimpleNamespace(__name__='ipykernel'),
            'jupyter': SimpleNamespace(__name__='jupyter'),
            'dotenv': SimpleNamespace(__name__='dotenv'),
        }
    )
    monkeypatch.setattr('builtins.__import__', fake_import)

    ok, fix = vls.check_required_packages()
    assert ok is False
    assert 'requests' in fix


# ============================================================
# Tests for check_shared_modules
# ============================================================


@pytest.mark.parametrize('checkout_state', ['missing', 'empty', 'init-only'])
def test_check_shared_modules_incomplete_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, checkout_state: str) -> None:
    """Reject absent shared modules without launching a vacuous import check."""
    monkeypatch.setattr(vls, '__file__', str(tmp_path / 'setup' / 'verify_local_setup.py'))
    shared_path = tmp_path / 'shared' / 'python'
    if checkout_state != 'missing':
        shared_path.mkdir(parents = True)
    if checkout_state == 'init-only':
        (shared_path / '__init__.py').write_text('', encoding = 'utf-8')

    with patch('subprocess.run') as run:
        ok, fix = vls.check_shared_modules()

    assert not ok
    assert str(shared_path) in fix
    assert 'Restore the repository checkout.' in fix
    run.assert_not_called()


def test_check_shared_modules_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use a fresh interpreter without injecting a path that notebooks might lack."""
    original_path = sys.path.copy()
    with patch('subprocess.run', return_value = Mock(returncode = 0)) as run:
        ok, fix = vls.check_shared_modules()

    assert ok is True
    assert not fix
    assert sys.path == original_path
    command = run.call_args.args[0]
    assert command[:2] == [sys.executable, '-c']
    assert "'charts'" in command[2]
    assert 'module.__file__' in command[2]
    assert 'sys.path.insert' not in command[2]
    assert 'env' not in run.call_args.kwargs
    assert run.call_args.kwargs['cwd'] == PROJECT_ROOT / 'samples'


@pytest.mark.parametrize('missing_module', ['utils', 'apimtypes', 'authfactory', 'auth_testing', 'apimrequests', 'charts'])
def test_check_shared_modules_missing(monkeypatch: pytest.MonkeyPatch, missing_module: str) -> None:
    """Shared modules check should fail when any module is missing."""
    with patch('subprocess.run', side_effect = subprocess.CalledProcessError(1, 'python', stderr = f'{missing_module} missing')):
        ok, fix = vls.check_shared_modules()

    assert ok is False
    assert missing_module in fix
    assert 'restart notebook kernels' in fix


@pytest.mark.parametrize('error', [subprocess.TimeoutExpired('python', 60), OSError('cannot start python')])
def test_check_shared_modules_process_error(error: Exception) -> None:
    """Shared import subprocess failures remain actionable failures."""
    with patch('subprocess.run', side_effect = error):
        ok, fix = vls.check_shared_modules()

    assert not ok
    assert str(error) in fix


# ============================================================
# Tests for check_jupyter_kernel
# ============================================================


@pytest.mark.parametrize(
    'stdout,should_pass',
    [
        ('Available kernels:\n  python-venv\n', True),
        ('Available kernels:\n  python3\n', True),
        ('Available kernels:\n  other-kernel\n', False),
    ],
)
def test_check_jupyter_kernel_found(stdout: str, should_pass: bool) -> None:
    """Jupyter kernel check should pass when a valid kernel is found."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(stdout=stdout, returncode=0)
        ok, fix = vls.check_jupyter_kernel()
        assert ok is should_pass
        if should_pass:
            assert not fix
        else:
            assert 'ipykernel' in fix or 'Register' in fix


@pytest.mark.parametrize(
    'exception,error_text',
    [
        (subprocess.CalledProcessError(1, 'jupyter'), 'eligible Jupyter'),
        (FileNotFoundError(), 'eligible Jupyter'),
        (subprocess.TimeoutExpired('jupyter', 10), 'timed out'),
    ],
)
def test_check_jupyter_kernel_errors(exception: Exception, error_text: str) -> None:
    """Jupyter kernel check should fail on various errors."""
    with patch('subprocess.run', side_effect=exception):
        ok, fix = vls.check_jupyter_kernel()
        assert ok is False
        assert error_text in fix


# ============================================================
# Tests for check_vscode_settings
# ============================================================


def test_check_vscode_settings_all_configured(temp_cwd: Path) -> None:
    """VS Code settings check should pass when all settings are present."""
    vscode_settings = temp_cwd / '.vscode' / 'settings.json'
    vscode_settings.parent.mkdir(parents=True)

    settings = {
        'python.defaultInterpreterPath': '${workspaceFolder}/.venv/Scripts/python.exe',
        'python.envFile': '${workspaceFolder}/.env',
        'python.terminal.activateEnvironment': True,
        'python.testing.pytestEnabled': True,
        'files.eol': '\n',
    }
    vscode_settings.write_text(json.dumps(settings), encoding='utf-8')

    ok, fix = vls.check_vscode_settings()
    assert ok is True
    assert not fix


def test_check_vscode_settings_not_found(temp_cwd: Path) -> None:
    """VS Code settings check should fail when settings.json is missing."""
    ok, fix = vls.check_vscode_settings()
    assert ok is False
    assert 'complete-setup' in fix


def test_check_vscode_settings_missing_interpreter_path(temp_cwd: Path) -> None:
    """VS Code settings check should fail when interpreter path is not set."""
    vscode_settings = temp_cwd / '.vscode' / 'settings.json'
    vscode_settings.parent.mkdir(parents=True)

    settings = {'python.envFile': '${workspaceFolder}/.env'}
    vscode_settings.write_text(json.dumps(settings), encoding='utf-8')

    ok, fix = vls.check_vscode_settings()
    assert ok is False
    assert 'complete-setup' in fix


def test_check_vscode_settings_missing_env_file(temp_cwd: Path) -> None:
    """VS Code settings check should fail when env file setting is missing."""
    vscode_settings = temp_cwd / '.vscode' / 'settings.json'
    vscode_settings.parent.mkdir(parents=True)

    settings = {'python.defaultInterpreterPath': '${workspaceFolder}/.venv/Scripts/python.exe'}
    vscode_settings.write_text(json.dumps(settings), encoding='utf-8')

    ok, fix = vls.check_vscode_settings()
    assert ok is False
    assert 'complete-setup' in fix


def test_check_vscode_settings_file_read_error(temp_cwd: Path) -> None:
    """VS Code settings check should fail on file read errors."""
    vscode_settings = temp_cwd / '.vscode' / 'settings.json'
    vscode_settings.parent.mkdir(parents=True)
    vscode_settings.write_text('', encoding='utf-8')

    with patch('builtins.open', side_effect=OSError('Permission denied')):
        ok, fix = vls.check_vscode_settings()
    assert ok is False
    assert 'Could not read' in fix


# ============================================================
# Tests for check_env_file
# ============================================================


def test_check_env_file_validation(temp_cwd: Path) -> None:
    """Environment file check should validate required keys."""
    env_path = temp_cwd / '.env'
    env_path.write_text('PYTHONPATH=/tmp\nPROJECT_ROOT=/repo\n', encoding='utf-8')

    ok, fix = vls.check_env_file()
    assert ok is True
    assert not fix


def test_check_env_file_missing_key(temp_cwd: Path) -> None:
    """Environment file check should fail when keys are missing."""
    env_path = temp_cwd / '.env'
    env_path.write_text('PYTHONPATH=/tmp\n', encoding='utf-8')

    ok, fix = vls.check_env_file()
    assert ok is False
    assert 'generate-env' in fix


def test_check_env_file_missing(temp_cwd: Path) -> None:
    """Environment file check should fail when .env is missing."""
    ok, fix = vls.check_env_file()
    assert ok is False
    assert 'generate-env' in fix


def test_check_env_file_with_comments(temp_cwd: Path) -> None:
    """Environment file check should ignore comment lines."""
    env_path = temp_cwd / '.env'
    env_path.write_text('# Comment\nPYTHONPATH=/tmp\nPROJECT_ROOT=/repo\n', encoding='utf-8')

    ok, fix = vls.check_env_file()
    assert ok is True
    assert not fix


def test_check_env_file_read_error(temp_cwd: Path) -> None:
    """Environment file check should handle read errors."""
    env_path = temp_cwd / '.env'
    env_path.write_text('PYTHONPATH=/tmp\n', encoding='utf-8')
    with patch('builtins.open', side_effect=OSError('Permission denied')):
        ok, fix = vls.check_env_file()
    assert ok is False
    assert 'Could not read' in fix


# ============================================================
# Tests for check_azure_cli
# ============================================================


def test_check_azure_cli_installed() -> None:
    """Azure CLI check should pass when az is found and has valid version."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(stdout='azure-cli                         2.81.0\n', returncode=0)
            ok, fix = vls.check_azure_cli()
            assert ok is True
            assert '2.81.0' in fix


def test_check_azure_cli_not_found() -> None:
    """Azure CLI check should fail when az is not found."""
    with patch('shutil.which', return_value=None):
        ok, fix = vls.check_azure_cli()
        assert ok is False
        assert 'Install Azure CLI' in fix


def test_check_azure_cli_subprocess_error() -> None:
    """Azure CLI check should fail on subprocess errors."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'az')):
            ok, fix = vls.check_azure_cli()
            assert ok is False
            assert 'Reinstall' in fix


def test_check_azure_cli_timeout() -> None:
    """Azure CLI check should fail instead of hanging when az does not respond."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('az --version', vls.AZURE_CLI_TIMEOUT_SECONDS)):
            ok, fix = vls.check_azure_cli()
            assert ok is False
            assert 'timed out' in fix


def test_check_azure_cli_empty_version() -> None:
    """Azure CLI check should handle empty version output."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', return_value=Mock(stdout='', returncode=0)):
            ok, fix = vls.check_azure_cli()
            assert ok is True
            assert 'Azure CLI' in fix


# ============================================================
# Tests for check_bicep_cli
# ============================================================


def test_check_bicep_cli_installed() -> None:
    """Bicep CLI check should pass when bicep is available."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', return_value=Mock(stdout='Bicep CLI version 0.39.26 (1e90b06e40)\n', returncode=0)):
            ok, fix = vls.check_bicep_cli()
            assert ok is True
            assert '0.39.26' in fix


@pytest.mark.parametrize('repair', [False, True])
def test_check_bicep_cli_not_found(repair: bool) -> None:
    """Bicep CLI check should fail when az is not found."""
    with patch('shutil.which', return_value=None):
        ok, fix = vls.check_bicep_cli(repair = repair)
        assert ok is False
        assert 'Install Azure CLI' in fix


def test_check_bicep_cli_subprocess_error() -> None:
    """Bicep CLI check should fail on subprocess errors."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'az')):
            ok, fix = vls.check_bicep_cli()
            assert ok is False
            assert 'Install Bicep' in fix


def test_check_bicep_cli_timeout() -> None:
    """Bicep CLI check should fail instead of hanging when az does not respond."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('az bicep version', vls.AZURE_CLI_TIMEOUT_SECONDS)):
            ok, fix = vls.check_bicep_cli()
            assert ok is False
            assert 'timed out' in fix


def test_bicep_repair_installs_pin_and_rechecks() -> None:
    """Repair a missing Bicep with the eligible pin, then verify it works."""
    with patch.object(vls, '_az_path', return_value = '/bin/az'), patch('subprocess.run') as run:
        run.side_effect = [
            subprocess.CalledProcessError(1, 'az bicep version'),
            Mock(returncode = 0),
            Mock(stdout = 'Bicep CLI version 0.44.1\n'),
        ]
        ok, detail = vls.check_bicep_cli(repair = True)

    assert ok
    assert '0.44.1' in detail
    assert [call.args[0] for call in run.call_args_list] == [
        ['/bin/az', 'bicep', 'version'],
        ['/bin/az', 'bicep', 'install', '--version', 'v0.44.1'],
        ['/bin/az', 'bicep', 'version'],
    ]
    assert run.call_args_list[1].kwargs['timeout'] == vls.INSTALL_TIMEOUT_SECONDS


@pytest.mark.parametrize('error', [
    subprocess.CalledProcessError(1, 'install', stderr = 'download refused'),
    subprocess.TimeoutExpired('install', 180),
    OSError('cannot start az'),
])
def test_bicep_repair_failure(error: Exception) -> None:
    """Installation errors and timeouts must not turn into a passing check."""
    with patch.object(vls, '_az_path', return_value = '/bin/az'), patch('subprocess.run') as run:
        run.side_effect = [subprocess.CalledProcessError(1, 'version'), error]
        ok, detail = vls.check_bicep_cli(repair = True)

    assert not ok
    assert 'Install Bicep failed' in detail
    assert run.call_count == 2


def test_bicep_repair_recheck_fails() -> None:
    """An installer exit code alone is not proof that Bicep works."""
    with patch.object(vls, '_az_path', return_value = '/bin/az'), patch('subprocess.run') as run:
        run.side_effect = [subprocess.CalledProcessError(1, 'version'), Mock(), subprocess.CalledProcessError(1, 'version')]
        ok, _ = vls.check_bicep_cli(repair = True)

    assert not ok
    assert run.call_count == 3


def test_bicep_repair_leaves_installed_version_alone() -> None:
    """Do not upgrade or reinstall an existing Bicep release."""
    with patch.object(vls, '_az_path', return_value = '/bin/az'), patch('subprocess.run', return_value = Mock(stdout = 'Bicep CLI version 0.39.26\n')) as run:
        ok, _ = vls.check_bicep_cli(repair = True)

    assert ok
    run.assert_called_once()


def test_bicep_repair_does_not_install_on_timeout() -> None:
    """An unresponsive CLI must not trigger installation."""
    with patch.object(vls, '_az_path', return_value = '/bin/az'), patch('subprocess.run', side_effect = subprocess.TimeoutExpired('az', 15)) as run:
        ok, _ = vls.check_bicep_cli(repair = True)

    assert not ok
    run.assert_called_once()


def test_bicep_repair_cli_disappears() -> None:
    """Do not crash or install if the Azure CLI executable cannot be launched."""
    with patch.object(vls, '_az_path', return_value = '/bin/az'), patch('subprocess.run', side_effect = FileNotFoundError('az disappeared')) as run:
        ok, detail = vls.check_bicep_cli(repair = True)

    assert not ok
    assert 'az disappeared' in detail
    run.assert_called_once()


@pytest.mark.parametrize(
    'stdout,expected_version,should_have_unknown',
    [
        ('', 'unknown', True),
        ('Bicep version', 'unknown', True),
        ('Welcome to Bicep CLI\nversion 9.9.9\n', 'unknown', True),
        ('BICEP VERSION 1.2.3\n', '1.2.3', False),
    ],
)
def test_check_bicep_cli_version_parsing(stdout: str, expected_version: str, should_have_unknown: bool) -> None:
    """Bicep CLI version parsing should handle various formats."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', return_value=Mock(stdout=stdout, returncode=0)):
            ok, fix = vls.check_bicep_cli()
            assert ok is True
            if should_have_unknown:
                assert 'unknown' in fix.lower()
            else:
                assert expected_version in fix


# ============================================================
# Tests for check_azure_login
# ============================================================


def test_check_azure_login_success() -> None:
    """Azure login check should pass when account show succeeds."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', return_value=Mock(stdout=json.dumps({'name': 'sub', 'tenantId': 't', 'id': 'id'}), returncode=0)):
            ok, fix = vls.check_azure_login()
            assert ok is True
            assert 'Logged in' in fix


def test_check_azure_login_not_logged_in() -> None:
    """Azure login check should fail when account show errors."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'az account show')):
            ok, fix = vls.check_azure_login()
            assert ok is False
            assert 'az login' in fix


def test_check_azure_login_timeout() -> None:
    """Azure login check should fail instead of hanging when az account show stalls."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('az account show', vls.AZURE_CLI_TIMEOUT_SECONDS)):
            ok, fix = vls.check_azure_login()
            assert ok is False
            assert 'timed out' in fix


def test_check_azure_login_no_cli() -> None:
    """Azure login check should fail when CLI missing."""
    with patch('shutil.which', return_value=None):
        ok, fix = vls.check_azure_login()
        assert ok is False
        assert 'Install Azure CLI' in fix


# ============================================================
# Tests for check_azure_providers
# ============================================================


def test_check_azure_providers_all_registered() -> None:
    """Azure providers check should pass when all required providers are registered."""
    providers_json = (
        '["Microsoft.ApiManagement", "Microsoft.App",'
        ' "Microsoft.Authorization", "Microsoft.CognitiveServices",'
        ' "Microsoft.ContainerRegistry", "Microsoft.CostManagementExports",'
        ' "Microsoft.KeyVault",'
        ' "Microsoft.Maps", "Microsoft.ManagedIdentity",'
        ' "Microsoft.Network", "Microsoft.OperationalInsights",'
        ' "Microsoft.Resources", "Microsoft.Storage"]'
    )
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', return_value=Mock(stdout=providers_json, returncode=0)):
            ok, fix = vls.check_azure_providers()
            assert ok is True
            assert not fix


def test_check_azure_providers_missing() -> None:
    """Azure providers check should fail when some providers are missing."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', return_value=Mock(stdout='["Microsoft.Storage"]', returncode=0)):
            ok, fix = vls.check_azure_providers()
            assert ok is False
            assert 'Register' in fix


def test_check_azure_providers_no_az() -> None:
    """Azure providers check should fail when az is not found."""
    with patch('shutil.which', return_value=None):
        ok, fix = vls.check_azure_providers()
        assert ok is False
        assert 'Install Azure CLI' in fix


@pytest.mark.parametrize(
    'exception',
    [
        subprocess.CalledProcessError(1, 'az'),
        subprocess.TimeoutExpired('az provider list', vls.AZURE_CLI_TIMEOUT_SECONDS),
    ],
)
def test_check_azure_providers_subprocess_error(exception: Exception) -> None:
    """Azure providers check should handle subprocess errors gracefully."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', side_effect=exception):
            ok, fix = vls.check_azure_providers()
            assert ok is False
            assert 'Log in' in fix or 'login' in fix.lower() or 'timed out' in fix


def test_check_azure_providers_json_error() -> None:
    """Azure providers check should handle JSON decode errors."""
    with patch('shutil.which', return_value='/usr/bin/az'):
        with patch('subprocess.run', return_value=Mock(stdout='invalid json', returncode=0)):
            ok, fix = vls.check_azure_providers()
            assert ok is False
            assert 'Log in' in fix or 'login' in fix.lower()


# ============================================================
# Tests for check_git_notebook_filter
# ============================================================


def _git_config_side_effect(clean: str | Exception, smudge: str | Exception):
    """Build a subprocess.run side_effect that answers git config --get calls."""

    def _run(cmd, **kwargs):
        key = cmd[-1]
        value = clean if key == 'filter.notebook-metadata.clean' else smudge
        if isinstance(value, Exception):
            raise value
        return Mock(stdout=f'{value}\n', returncode=0)

    return _run


def test_check_git_notebook_filter_git_missing() -> None:
    """Git notebook filter check should fail when git is not on PATH."""
    with patch('shutil.which', return_value=None):
        ok, fix = vls.check_git_notebook_filter()
        assert ok is False
        assert 'Install Git' in fix


def test_check_git_notebook_filter_configured() -> None:
    """Git notebook filter check should pass when clean and smudge match expected values."""
    side_effect = _git_config_side_effect(
        clean='python setup/normalize_notebook_metadata.py',
        smudge='cat',
    )
    with patch('shutil.which', return_value='/usr/bin/git'):
        with patch('subprocess.run', side_effect=side_effect):
            ok, fix = vls.check_git_notebook_filter()
            assert ok is True
            assert not fix


def test_check_git_notebook_filter_not_configured() -> None:
    """Git notebook filter check should fail when git config key is unset (exit 1)."""
    with patch('shutil.which', return_value='/usr/bin/git'):
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'git')):
            ok, fix = vls.check_git_notebook_filter()
            assert ok is False
            assert 'Complete environment setup' in fix


def test_check_git_notebook_filter_wrong_clean_value() -> None:
    """Git notebook filter check should fail when clean filter points to something unexpected."""
    side_effect = _git_config_side_effect(clean='nbstripout', smudge='cat')
    with patch('shutil.which', return_value='/usr/bin/git'):
        with patch('subprocess.run', side_effect=side_effect):
            ok, fix = vls.check_git_notebook_filter()
            assert ok is False
            assert 'nbstripout' in fix


def test_check_git_notebook_filter_wrong_smudge_value() -> None:
    """Git notebook filter check should fail when smudge filter is not 'cat'."""
    side_effect = _git_config_side_effect(
        clean='python setup/normalize_notebook_metadata.py',
        smudge='python something_else.py',
    )
    with patch('shutil.which', return_value='/usr/bin/git'):
        with patch('subprocess.run', side_effect=side_effect):
            ok, fix = vls.check_git_notebook_filter()
            assert ok is False
            assert 'something_else' in fix


def test_check_git_notebook_filter_git_exec_missing() -> None:
    """Git notebook filter check should fail gracefully when git disappears between which() and run()."""
    with patch('shutil.which', return_value='/usr/bin/git'):
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            ok, fix = vls.check_git_notebook_filter()
            assert ok is False
            assert 'Install Git' in fix


# ============================================================
# Tests for main function
# ============================================================


def _mock_all_checks(monkeypatch: pytest.MonkeyPatch, **overrides: tuple[bool, str]) -> None:
    """Helper to mock all check functions with optional overrides."""
    defaults = {
        'check_virtual_environment': (True, ''),
        'check_uv_sync': (True, ''),
        'check_required_packages': (True, ''),
        'check_shared_modules': (True, ''),
        'check_env_file': (True, ''),
        'check_azure_cli': (True, ''),
        'check_bicep_cli': (True, ''),
        'check_azure_login': (True, ''),
        'check_azure_providers': (True, ''),
        'check_jupyter_kernel': (True, ''),
        'check_vscode_settings': (True, ''),
        'check_git_notebook_filter': (True, ''),
    }
    defaults.update(overrides)
    for check_name, result in defaults.items():
        monkeypatch.setattr(vls, check_name, lambda result=result: result)


def test_main_all_pass(monkeypatch: pytest.MonkeyPatch):
    """Main function should return True when all checks pass."""
    _mock_all_checks(monkeypatch)
    result = vls.main()
    assert result is True


def test_main_skip_azure_providers_when_login_fails(monkeypatch: pytest.MonkeyPatch):
    """Main function should skip Azure Providers check when Azure Login fails."""
    azure_providers_called = []

    def check_azure_providers_mock():
        azure_providers_called.append(True)
        return (True, '')

    _mock_all_checks(monkeypatch, check_azure_login=(False, 'not logged in'))
    monkeypatch.setattr(vls, 'check_azure_providers', check_azure_providers_mock)

    result = vls.main()
    assert result is False
    assert not azure_providers_called


def test_main_run_azure_providers_when_login_succeeds(monkeypatch: pytest.MonkeyPatch):
    """Main function should run Azure Providers check when Azure Login succeeds."""
    azure_providers_called = []

    def check_azure_providers_mock():
        azure_providers_called.append(True)
        return (True, '')

    _mock_all_checks(monkeypatch)
    monkeypatch.setattr(vls, 'check_azure_providers', check_azure_providers_mock)

    result = vls.main()
    assert result is True
    assert len(azure_providers_called) == 1


def test_main_some_fail(monkeypatch: pytest.MonkeyPatch):
    """Main function should return False when some checks fail."""
    _mock_all_checks(monkeypatch, check_required_packages=(False, 'install'))
    result = vls.main()
    assert result is False


def test_main_skip_providers_and_fail_other(monkeypatch: pytest.MonkeyPatch):
    """Main function should return False when non-provider checks fail, even if providers skipped."""
    _mock_all_checks(monkeypatch, check_required_packages=(False, 'install'), check_azure_login=(False, 'not logged in'))
    result = vls.main()
    assert result is False


@pytest.mark.parametrize('check_name,option', [
    ('Shared Modules', '--setup-imports'),
    ('Environment File', '--generate-env'),
    ('Jupyter Kernel', '--setup-kernel'),
    ('VS Code Settings', '--setup-vscode'),
    ('Git Notebook Filter', '--setup-nb-filter'),
])
def test_repair_check_commands(check_name: str, option: str) -> None:
    """Local repairs reuse setup commands and the active interpreter."""
    with patch('subprocess.run') as run:
        assert vls.repair_check(check_name)

    assert run.call_args.args[0] == [sys.executable, str(SETUP_PATH / 'local_setup.py'), option]


@pytest.mark.parametrize('check_name', ['Azure CLI', 'Azure Login', 'Azure Providers', 'Virtual Environment', 'UV Sync', 'Required Packages'])
def test_repair_check_does_not_change_external_prerequisites(check_name: str) -> None:
    """Do not install OS tools or mutate the Azure account during repair."""
    with patch('subprocess.run') as run:
        assert not vls.repair_check(check_name)

    run.assert_not_called()


@pytest.mark.parametrize('error', [subprocess.CalledProcessError(1, 'setup'), subprocess.TimeoutExpired('setup', 180), OSError('denied')])
def test_repair_check_failure(error: Exception) -> None:
    """Repair command failures must remain failures."""
    with patch('subprocess.run', side_effect = error):
        assert not vls.repair_check('Shared Modules')


@pytest.mark.parametrize('after_repair', [True, False])
def test_main_rechecks_repairs(monkeypatch: pytest.MonkeyPatch, after_repair: bool) -> None:
    """Only the recheck, not the repair command's exit code, determines success."""
    _mock_all_checks(monkeypatch)
    check = Mock(side_effect = [(False, 'missing'), (after_repair, '')])
    monkeypatch.setattr(vls, 'check_shared_modules', check)
    monkeypatch.setattr(vls, 'check_bicep_cli', Mock(return_value = (True, '')))
    with patch.object(vls, 'repair_check', return_value = True) as repair:
        assert vls.main(repair = True) is after_repair

    assert check.call_count == 2
    repair.assert_called_once_with('Shared Modules')
