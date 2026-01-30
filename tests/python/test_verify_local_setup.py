"""Unit tests for verify_local_setup script."""

from __future__ import annotations

import builtins
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, TYPE_CHECKING, cast
from unittest.mock import Mock, patch

import pytest

# Ensure the setup folder is on sys.path so the verification script is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / "setup"
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

if TYPE_CHECKING:
    vls = cast(ModuleType, None)
else:
    vls = cast(ModuleType, importlib.import_module("verify_local_setup"))


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

    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def suppress_print(monkeypatch: pytest.MonkeyPatch) -> None:
    """Suppress print output during tests."""
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)


# ============================================================
# Tests for print_status
# ============================================================

def test_print_status_success(capsys, suppress_print):
    """print_status should tolerate success messages."""
    vls.print_status("ok", success=True)


def test_print_status_failure_with_fix(capsys, suppress_print):
    """print_status should tolerate failure messages with fix text."""
    vls.print_status("bad", success=False, fix="do this")


def test_print_status_skipped(capsys, suppress_print):
    """print_status should tolerate skipped checks with note."""
    vls.print_status("skipped check", skipped=True, fix="reason for skip")


# ============================================================
# Tests for check_virtual_environment
# ============================================================

def test_check_virtual_environment_success(temp_cwd: Path, monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Virtual environment check should pass when .venv exists and python resides inside it."""

    scripts_dir = temp_cwd / ".venv" / ("Scripts" if sys.platform.startswith("win") else "bin")
    scripts_dir.mkdir(parents=True)
    venv_python = scripts_dir / "python"
    venv_python.write_text("#!/usr/bin/env python")

    monkeypatch.setattr(sys, "executable", str(venv_python))

    ok, fix = vls.check_virtual_environment()
    assert ok is True
    assert not fix


def test_check_virtual_environment_missing(temp_cwd: Path, suppress_print) -> None:
    """Virtual environment check should fail when .venv doesn't exist."""
    ok, fix = vls.check_virtual_environment()
    assert ok is False
    assert "Create" in fix


def test_check_virtual_environment_wrong_python(temp_cwd: Path, monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Virtual environment check should fail when python is not from .venv."""
    (temp_cwd / ".venv").mkdir()
    monkeypatch.setattr(sys, "executable", "/usr/bin/python")

    ok, fix = vls.check_virtual_environment()
    assert ok is False
    assert "Activate" in fix


# ============================================================
# Tests for check_uv_sync
# ============================================================

def test_check_uv_sync_uv_not_installed(suppress_print) -> None:
    """UV sync check should fail when uv is not installed."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        ok, fix = vls.check_uv_sync()
        assert ok is False
        assert "Install uv" in fix
        assert "https://docs.astral.sh/uv/" in fix


def test_check_uv_sync_success_venv_exists(temp_cwd: Path, suppress_print) -> None:
    """UV sync check should pass when uv syncs dependencies successfully with existing venv."""
    (temp_cwd / ".venv").mkdir()

    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/uv"
            mock_run.return_value = Mock(returncode=0)

            ok, fix = vls.check_uv_sync()
            assert ok is True
            assert not fix
            # Verify sync was called
            mock_run.assert_called_once()
            assert "sync" in mock_run.call_args[0][0]


def test_check_uv_sync_fail_sync(temp_cwd: Path, suppress_print) -> None:
    """UV sync check should fail when uv sync fails."""
    (temp_cwd / ".venv").mkdir()

    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/uv"
            mock_run.side_effect = subprocess.CalledProcessError(1, ["uv", "sync"])

            ok, fix = vls.check_uv_sync()
            assert ok is False
            assert "Failed to sync dependencies" in fix


def test_check_uv_sync_creates_venv_then_syncs(temp_cwd: Path, suppress_print) -> None:
    """UV sync check should create venv if missing then sync successfully."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/uv"
            mock_run.return_value = Mock(returncode=0)

            ok, fix = vls.check_uv_sync()
            assert ok is True
            assert not fix
            # Verify both venv creation and sync were called
            assert mock_run.call_count == 2
            assert "venv" in mock_run.call_args_list[0][0][0]
            assert "sync" in mock_run.call_args_list[1][0][0]


def test_check_uv_sync_fail_venv_creation(temp_cwd: Path, suppress_print) -> None:
    """UV sync check should fail when venv creation fails."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/uv"
            mock_run.side_effect = subprocess.CalledProcessError(1, ["uv", "venv"])

            ok, fix = vls.check_uv_sync()
            assert ok is False
            assert "Failed to create venv" in fix


def test_check_uv_sync_venv_created_but_sync_fails(temp_cwd: Path, suppress_print) -> None:
    """UV sync check should fail when venv is created but sync fails."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/uv"

            def run_side_effect(cmd, **kwargs):
                if "venv" in cmd:
                    return Mock(returncode=0)
                if "sync" in cmd:
                    raise subprocess.CalledProcessError(1, ["uv", "sync"])
                return Mock(returncode=0)

            mock_run.side_effect = run_side_effect

            ok, fix = vls.check_uv_sync()
            assert ok is False
            assert "Failed to sync dependencies" in fix


# ============================================================
# Tests for check_required_packages
# ============================================================

def test_check_required_packages_all_present(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Package check should return True when all dependencies are available."""

    fake_import = _fake_import_factory(
        {
            "requests": SimpleNamespace(__name__="requests"),
            "ipykernel": SimpleNamespace(__name__="ipykernel"),
            "jupyter": SimpleNamespace(__name__="jupyter"),
            "dotenv": SimpleNamespace(__name__="dotenv"),
        }
    )

    monkeypatch.setattr("builtins.__import__", fake_import)

    ok, fix = vls.check_required_packages()
    assert ok is True
    assert not fix


def test_check_required_packages_missing(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Package check should return False when any dependency fails to import."""

    fake_import = _fake_import_factory(
        {
            "requests": SimpleNamespace(__name__="requests"),
            "ipykernel": SimpleNamespace(__name__="ipykernel"),
            "jupyter": SimpleNamespace(__name__="jupyter"),
            "dotenv": ImportError("dotenv missing"),
        }
    )

    monkeypatch.setattr("builtins.__import__", fake_import)

    ok, fix = vls.check_required_packages()
    assert ok is False
    assert "uv sync" in fix


def test_check_required_packages_requests_missing(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Package check should return False when requests is missing."""

    fake_import = _fake_import_factory(
        {
            "requests": ImportError("requests missing"),
            "ipykernel": SimpleNamespace(__name__="ipykernel"),
            "jupyter": SimpleNamespace(__name__="jupyter"),
            "dotenv": SimpleNamespace(__name__="dotenv"),
        }
    )

    monkeypatch.setattr("builtins.__import__", fake_import)

    ok, fix = vls.check_required_packages()
    assert ok is False
    assert "requests" in fix


# ============================================================
# Tests for check_shared_modules
# ============================================================

def test_check_shared_modules_success(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Shared modules check should pass when imports succeed."""

    fake_import = _fake_import_factory(
        {
            "utils": SimpleNamespace(__name__="utils"),
            "apimtypes": SimpleNamespace(__name__="apimtypes"),
            "authfactory": SimpleNamespace(__name__="authfactory"),
            "apimrequests": SimpleNamespace(__name__="apimrequests"),
        }
    )

    monkeypatch.setattr("builtins.__import__", fake_import)

    ok, fix = vls.check_shared_modules()
    assert ok is True
    assert not fix


def test_check_shared_modules_missing_utils(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Shared modules check should fail when utils module is missing."""

    fake_import = _fake_import_factory({"utils": ImportError("utils missing")})

    monkeypatch.setattr("builtins.__import__", fake_import)

    ok, fix = vls.check_shared_modules()
    assert ok is False
    assert "generate-env" in fix


def test_check_shared_modules_missing_apimtypes(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Shared modules check should fail when apimtypes module is missing."""

    fake_import = _fake_import_factory({"apimtypes": ImportError("apimtypes missing")})

    monkeypatch.setattr("builtins.__import__", fake_import)

    ok, fix = vls.check_shared_modules()
    assert ok is False
    assert "generate-env" in fix


def test_check_shared_modules_missing_authfactory(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Shared modules check should fail when authfactory module is missing."""

    fake_import = _fake_import_factory({"authfactory": ImportError("authfactory missing")})

    monkeypatch.setattr("builtins.__import__", fake_import)

    ok, _ = vls.check_shared_modules()
    assert ok is False


def test_check_shared_modules_missing_apimrequests(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Shared modules check should fail when apimrequests module is missing."""

    fake_import = _fake_import_factory({"apimrequests": ImportError("apimrequests missing")})

    monkeypatch.setattr("builtins.__import__", fake_import)

    ok, _ = vls.check_shared_modules()
    assert ok is False


# ============================================================
# Tests for check_jupyter_kernel
# ============================================================

def test_check_jupyter_kernel_found(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Jupyter kernel check should pass when kernel is found."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout="Available kernels:\n  python-venv\n",
            returncode=0,
        )
        ok, fix = vls.check_jupyter_kernel()
        assert ok is True
        assert not fix


def test_check_jupyter_kernel_found_python3(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Jupyter kernel check should pass when kernel is found."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout="Available kernels:\n  python3\n",
            returncode=0,
        )
        ok, fix = vls.check_jupyter_kernel()
        assert ok is True
        assert not fix


def test_check_jupyter_kernel_not_found(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Jupyter kernel check should fail when kernel is not found."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout="Available kernels:\n  other-kernel\n",
            returncode=0,
        )
        ok, fix = vls.check_jupyter_kernel()
        assert ok is False
        assert "ipykernel" in fix or "Register" in fix


def test_check_jupyter_kernel_subprocess_error(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Jupyter kernel check should fail on subprocess errors."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "jupyter")
        ok, fix = vls.check_jupyter_kernel()
        assert ok is False
        assert "Install Jupyter" in fix


def test_check_jupyter_kernel_file_not_found(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Jupyter kernel check should fail when jupyter is not found."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        ok, fix = vls.check_jupyter_kernel()
        assert ok is False
        assert "Install Jupyter" in fix


def test_check_jupyter_kernel_timeout(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Jupyter kernel check should fail when subprocess times out."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired("jupyter", 10)
        ok, fix = vls.check_jupyter_kernel()
        assert ok is False
        assert "timed out" in fix


# ============================================================
# Tests for check_vscode_settings
# ============================================================

def test_check_vscode_settings_all_configured(temp_cwd: Path, suppress_print) -> None:
    """VS Code settings check should pass when all settings are present."""
    vscode_settings = temp_cwd / ".vscode" / "settings.json"
    vscode_settings.parent.mkdir(parents=True)

    settings = {
        "python.defaultInterpreterPath": ".venv/Scripts/python.exe",
        "python.envFile": "${workspaceFolder}/.env",
        "python.terminal.activateEnvironment": True,
        "python.testing.pytestEnabled": True,
        "files.eol": "\n",
    }
    vscode_settings.write_text(json.dumps(settings), encoding="utf-8")

    ok, fix = vls.check_vscode_settings()
    assert ok is True
    assert not fix


def test_check_vscode_settings_not_found(temp_cwd: Path, suppress_print) -> None:
    """VS Code settings check should fail when settings.json is missing."""
    ok, fix = vls.check_vscode_settings()
    assert ok is False
    assert "complete-setup" in fix


def test_check_vscode_settings_missing_interpreter_path(temp_cwd: Path, suppress_print) -> None:
    """VS Code settings check should fail when interpreter path is not set."""
    vscode_settings = temp_cwd / ".vscode" / "settings.json"
    vscode_settings.parent.mkdir(parents=True)

    settings = {
        "python.envFile": "${workspaceFolder}/.env"
    }
    vscode_settings.write_text(json.dumps(settings), encoding="utf-8")

    ok, fix = vls.check_vscode_settings()
    assert ok is False
    assert "complete-setup" in fix


def test_check_vscode_settings_missing_env_file(temp_cwd: Path, suppress_print) -> None:
    """VS Code settings check should fail when env file setting is missing."""
    vscode_settings = temp_cwd / ".vscode" / "settings.json"
    vscode_settings.parent.mkdir(parents=True)

    settings = {
        "python.defaultInterpreterPath": ".venv/Scripts/python.exe"
    }
    vscode_settings.write_text(json.dumps(settings), encoding="utf-8")

    ok, fix = vls.check_vscode_settings()
    assert ok is False
    assert "complete-setup" in fix


def test_check_vscode_settings_file_read_error(temp_cwd: Path, suppress_print) -> None:
    """VS Code settings check should fail on file read errors."""
    vscode_settings = temp_cwd / ".vscode" / "settings.json"
    vscode_settings.parent.mkdir(parents=True)
    vscode_settings.write_text("", encoding="utf-8")

    with patch("builtins.open", side_effect=OSError("Permission denied")):
        ok, fix = vls.check_vscode_settings()
    assert ok is False
    assert "Could not read" in fix


# ============================================================
# Tests for check_env_file
# ============================================================

def test_check_env_file_validation(temp_cwd: Path, suppress_print) -> None:
    """Environment file check should validate required keys."""

    env_path = temp_cwd / ".env"
    env_path.write_text("PYTHONPATH=/tmp\nPROJECT_ROOT=/repo\n", encoding="utf-8")

    ok, fix = vls.check_env_file()
    assert ok is True
    assert not fix


def test_check_env_file_missing_key(temp_cwd: Path, suppress_print) -> None:
    """Environment file check should fail when keys are missing."""

    env_path = temp_cwd / ".env"
    env_path.write_text("PYTHONPATH=/tmp\n", encoding="utf-8")

    ok, fix = vls.check_env_file()
    assert ok is False
    assert "generate-env" in fix


def test_check_env_file_missing(temp_cwd: Path, suppress_print) -> None:
    """Environment file check should fail when .env is missing."""
    ok, fix = vls.check_env_file()
    assert ok is False
    assert "generate-env" in fix


def test_check_env_file_with_comments(temp_cwd: Path, suppress_print) -> None:
    """Environment file check should ignore comment lines."""
    env_path = temp_cwd / ".env"
    env_path.write_text("# Comment\nPYTHONPATH=/tmp\nPROJECT_ROOT=/repo\n", encoding="utf-8")

    ok, fix = vls.check_env_file()
    assert ok is True
    assert not fix


def test_check_env_file_read_error(temp_cwd: Path, suppress_print) -> None:
    """Environment file check should handle read errors."""
    env_path = temp_cwd / ".env"
    env_path.write_text("PYTHONPATH=/tmp\n", encoding="utf-8")
    with patch("builtins.open", side_effect=OSError("Permission denied")):
        ok, fix = vls.check_env_file()
    assert ok is False
    assert "Could not read" in fix


# ============================================================
# Tests for check_azure_cli
# ============================================================

def test_check_azure_cli_installed(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure CLI check should pass when az is found and has valid version."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(
                stdout="azure-cli                         2.81.0\n",
                returncode=0,
            )
            ok, fix = vls.check_azure_cli()
            assert ok is True
            assert "2.81.0" in fix


def test_check_azure_cli_not_found(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure CLI check should fail when az is not found."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        ok, fix = vls.check_azure_cli()
        assert ok is False
        assert "Install Azure CLI" in fix


def test_check_azure_cli_subprocess_error(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure CLI check should fail on subprocess errors."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = subprocess.CalledProcessError(1, "az")
            ok, fix = vls.check_azure_cli()
            assert ok is False
            assert "Reinstall" in fix


def test_check_azure_cli_empty_version(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure CLI check should handle empty version output."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(stdout="", returncode=0)
            ok, fix = vls.check_azure_cli()
            assert ok is True
            assert "Azure CLI" in fix


# ============================================================
# Tests for check_bicep_cli
# ============================================================

def test_check_bicep_cli_installed(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Bicep CLI check should pass when bicep is available."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(
                stdout="Bicep CLI version 0.39.26 (1e90b06e40)\n",
                returncode=0,
            )
            ok, fix = vls.check_bicep_cli()
            assert ok is True
            assert "0.39.26" in fix


def test_check_bicep_cli_not_found(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Bicep CLI check should fail when az is not found."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        ok, fix = vls.check_bicep_cli()
        assert ok is False
        assert "Install Azure CLI" in fix


def test_check_bicep_cli_subprocess_error(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Bicep CLI check should fail on subprocess errors."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = subprocess.CalledProcessError(1, "az")
            ok, fix = vls.check_bicep_cli()
            assert ok is False
            assert "Install Bicep" in fix


def test_check_bicep_cli_empty_version(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Bicep CLI check should handle empty version output."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(stdout="", returncode=0)
            ok, fix = vls.check_bicep_cli()
            assert ok is True
            assert "Bicep" in fix


def test_check_bicep_cli_case_insensitive_version(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Bicep CLI parsing should be case-insensitive for the word 'version'."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(
                stdout="BICEP VERSION 1.2.3\n",
                returncode=0,
            )
            ok, fix = vls.check_bicep_cli()
            assert ok is True
            assert "1.2.3" in fix


def test_check_bicep_cli_version_token_without_value(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """If 'version' is the last token, fallback should report unknown."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(
                stdout="Bicep version\n",
                returncode=0,
            )
            ok, fix = vls.check_bicep_cli()
            assert ok is True
            assert "unknown" in fix.lower()


def test_check_bicep_cli_uses_first_line_only(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """When version isn't on the first line, parser should return unknown."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(
                stdout="Welcome to Bicep CLI\nversion 9.9.9\n",
                returncode=0,
            )
            ok, fix = vls.check_bicep_cli()
            assert ok is True
            assert "unknown" in fix.lower()


# ============================================================
# Tests for check_azure_login
# ============================================================


def test_check_azure_login_success(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure login check should pass when account show succeeds."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(
                stdout=json.dumps({"name": "sub", "tenantId": "t", "id": "id"}),
                returncode=0,
            )
            ok, fix = vls.check_azure_login()
            assert ok is True
            assert "Logged in" in fix


def test_check_azure_login_not_logged_in(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure login check should fail when account show errors."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = subprocess.CalledProcessError(1, "az account show")
            ok, fix = vls.check_azure_login()
            assert ok is False
            assert "az login" in fix


def test_check_azure_login_no_cli(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure login check should fail when CLI missing."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        ok, fix = vls.check_azure_login()
        assert ok is False
        assert "Install Azure CLI" in fix


# ============================================================
# Tests for check_azure_providers
# ============================================================

def test_check_azure_providers_all_registered(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure providers check should pass when all required providers are registered."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(
                stdout='["Microsoft.ApiManagement", "Microsoft.App", "Microsoft.Authorization", "Microsoft.CognitiveServices", "Microsoft.ContainerRegistry", "Microsoft.KeyVault", "Microsoft.Maps", "Microsoft.ManagedIdentity", "Microsoft.Network", "Microsoft.OperationalInsights", "Microsoft.Resources", "Microsoft.Storage"]',
                returncode=0,
            )
            ok, fix = vls.check_azure_providers()
            assert ok is True
            assert not fix


def test_check_azure_providers_missing(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure providers check should fail when some providers are missing."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(
                stdout='["Microsoft.Storage"]',
                returncode=0,
            )
            ok, fix = vls.check_azure_providers()
            assert ok is False
            assert "Register" in fix


def test_check_azure_providers_no_az(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure providers check should fail when az is not found."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        ok, fix = vls.check_azure_providers()
        assert ok is False
        assert "Install Azure CLI" in fix


def test_check_azure_providers_subprocess_error(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure providers check should handle subprocess errors gracefully."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = subprocess.CalledProcessError(1, "az")
            ok, fix = vls.check_azure_providers()
            assert ok is False
            assert "Log in" in fix or "Login" in fix


def test_check_azure_providers_json_error(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure providers check should handle JSON decode errors."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(stdout="invalid json", returncode=0)
            ok, fix = vls.check_azure_providers()
            assert ok is False
            assert "Log in" in fix or "Login" in fix


# ============================================================
# Tests for main function
# ============================================================

def test_main_all_pass(monkeypatch: pytest.MonkeyPatch, suppress_print):
    """Main function should return True when all checks pass."""
    monkeypatch.setattr(vls, "check_virtual_environment", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_uv_sync", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_required_packages", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_shared_modules", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_env_file", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_azure_cli", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_bicep_cli", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_azure_login", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_azure_providers", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_jupyter_kernel", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_vscode_settings", lambda: (True, ""))

    result = vls.main()
    assert result is True


def test_main_skip_azure_providers_when_login_fails(monkeypatch: pytest.MonkeyPatch, suppress_print):
    """Main function should skip Azure Providers check when Azure Login fails."""
    monkeypatch.setattr(vls, "check_virtual_environment", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_uv_sync", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_required_packages", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_shared_modules", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_env_file", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_azure_cli", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_bicep_cli", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_azure_login", lambda: (False, "not logged in"))
    azure_providers_called = []

    def check_azure_providers_mock():
        azure_providers_called.append(True)
        return (True, "")

    monkeypatch.setattr(vls, "check_azure_providers", check_azure_providers_mock)
    monkeypatch.setattr(vls, "check_jupyter_kernel", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_vscode_settings", lambda: (True, ""))

    result = vls.main()
    # Should fail because azure_login failed (even though providers are skipped)
    assert result is False
    # Verify Azure Providers check was NOT called because login failed
    assert not azure_providers_called


def test_main_run_azure_providers_when_login_succeeds(monkeypatch: pytest.MonkeyPatch, suppress_print):
    """Main function should run Azure Providers check when Azure Login succeeds."""
    monkeypatch.setattr(vls, "check_virtual_environment", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_uv_sync", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_required_packages", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_shared_modules", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_env_file", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_azure_cli", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_bicep_cli", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_azure_login", lambda: (True, "logged in"))
    azure_providers_called = []

    def check_azure_providers_mock():
        azure_providers_called.append(True)
        return (True, "")

    monkeypatch.setattr(vls, "check_azure_providers", check_azure_providers_mock)
    monkeypatch.setattr(vls, "check_jupyter_kernel", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_vscode_settings", lambda: (True, ""))

    result = vls.main()
    assert result is True
    # Verify Azure Providers check WAS called
    assert len(azure_providers_called) == 1


def test_main_some_fail(monkeypatch: pytest.MonkeyPatch, suppress_print):
    """Main function should return False when some checks fail."""
    monkeypatch.setattr(vls, "check_virtual_environment", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_required_packages", lambda: (False, "install"))
    monkeypatch.setattr(vls, "check_shared_modules", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_env_file", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_azure_cli", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_bicep_cli", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_azure_login", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_azure_providers", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_jupyter_kernel", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_vscode_settings", lambda: (True, ""))

    result = vls.main()
    assert result is False


def test_main_skip_providers_and_fail_other(monkeypatch: pytest.MonkeyPatch, suppress_print):
    """Main function should return False when non-provider checks fail, even if providers skipped."""
    monkeypatch.setattr(vls, "check_virtual_environment", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_required_packages", lambda: (False, "install"))
    monkeypatch.setattr(vls, "check_shared_modules", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_env_file", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_azure_cli", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_bicep_cli", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_azure_login", lambda: (False, "not logged in"))
    monkeypatch.setattr(vls, "check_jupyter_kernel", lambda: (True, ""))
    monkeypatch.setattr(vls, "check_vscode_settings", lambda: (True, ""))

    result = vls.main()
    # Should fail because check_required_packages fails
    assert result is False
