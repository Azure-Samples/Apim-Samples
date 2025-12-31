"""Unit tests for verify_local_setup script."""

from __future__ import annotations

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
# Tests for print_status and print_section
# ============================================================

def test_print_status_success(capsys, suppress_print):
    """Test print_status with success message."""
    vls.print_status("Test message", success=True)
    # Just verify it doesn't raise an exception


def test_print_status_failure(capsys, suppress_print):
    """Test print_status with failure message."""
    vls.print_status("Test message", success=False)
    # Just verify it doesn't raise an exception


def test_print_section(capsys, suppress_print):
    """Test print_section displays header."""
    vls.print_section("Test Section")
    # Just verify it doesn't raise an exception


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

    assert vls.check_virtual_environment() is True


def test_check_virtual_environment_missing(temp_cwd: Path, suppress_print) -> None:
    """Virtual environment check should fail when .venv doesn't exist."""
    assert vls.check_virtual_environment() is False


def test_check_virtual_environment_wrong_python(temp_cwd: Path, monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Virtual environment check should fail when python is not from .venv."""
    (temp_cwd / ".venv").mkdir()
    monkeypatch.setattr(sys, "executable", "/usr/bin/python")

    assert vls.check_virtual_environment() is False


# ============================================================
# Tests for check_required_packages
# ============================================================

def test_check_required_packages_all_present(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Package check should return True when all dependencies are available."""

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(__name__=name)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert vls.check_required_packages() is True


def test_check_required_packages_missing(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Package check should return False when any dependency fails to import."""

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "dotenv":
            raise ImportError("dotenv missing")

        # Return a lightweight placeholder for expected modules.
        return SimpleNamespace(__name__=name)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert vls.check_required_packages() is False


def test_check_required_packages_requests_missing(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Package check should return False when requests is missing."""

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "requests":
            raise ImportError("requests missing")
        return SimpleNamespace(__name__=name)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert vls.check_required_packages() is False


def test_check_required_packages_ipykernel_missing(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Package check should return False when ipykernel is missing."""

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "ipykernel":
            raise ImportError("ipykernel missing")
        return SimpleNamespace(__name__=name)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert vls.check_required_packages() is False


def test_check_required_packages_jupyter_missing(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Package check should return False when jupyter is missing."""

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "jupyter":
            raise ImportError("jupyter missing")
        return SimpleNamespace(__name__=name)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert vls.check_required_packages() is False


# ============================================================
# Tests for check_shared_modules
# ============================================================

def test_check_shared_modules_success(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Shared modules check should pass when imports succeed."""

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(__name__=name)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert vls.check_shared_modules() is True


def test_check_shared_modules_missing_utils(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Shared modules check should fail when utils module is missing."""

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "utils":
            raise ImportError("utils missing")
        return SimpleNamespace(__name__=name)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert vls.check_shared_modules() is False


def test_check_shared_modules_missing_apimtypes(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Shared modules check should fail when apimtypes module is missing."""

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "apimtypes":
            raise ImportError("apimtypes missing")
        return SimpleNamespace(__name__=name)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert vls.check_shared_modules() is False


def test_check_shared_modules_missing_authfactory(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Shared modules check should fail when authfactory module is missing."""

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "authfactory":
            raise ImportError("authfactory missing")
        return SimpleNamespace(__name__=name)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert vls.check_shared_modules() is False


def test_check_shared_modules_missing_apimrequests(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Shared modules check should fail when apimrequests module is missing."""

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "apimrequests":
            raise ImportError("apimrequests missing")
        return SimpleNamespace(__name__=name)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert vls.check_shared_modules() is False


# ============================================================
# Tests for check_jupyter_kernel
# ============================================================

def test_check_jupyter_kernel_found(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Jupyter kernel check should pass when kernel is found."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout="Available kernels:\n  apim-samples\n",
            returncode=0
        )
        assert vls.check_jupyter_kernel() is True


def test_check_jupyter_kernel_not_found(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Jupyter kernel check should fail when kernel is not found."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout="Available kernels:\n  other-kernel\n",
            returncode=0
        )
        assert vls.check_jupyter_kernel() is False


def test_check_jupyter_kernel_subprocess_error(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Jupyter kernel check should fail on subprocess errors."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "jupyter")
        assert vls.check_jupyter_kernel() is False


def test_check_jupyter_kernel_file_not_found(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Jupyter kernel check should fail when jupyter is not found."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        assert vls.check_jupyter_kernel() is False


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
        "files.eol": "\n"
    }
    vscode_settings.write_text(json.dumps(settings), encoding="utf-8")

    assert vls.check_vscode_settings() is True


def test_check_vscode_settings_not_found(temp_cwd: Path, suppress_print) -> None:
    """VS Code settings check should fail when settings.json is missing."""
    assert vls.check_vscode_settings() is False


def test_check_vscode_settings_missing_interpreter_path(temp_cwd: Path, suppress_print) -> None:
    """VS Code settings check should fail when interpreter path is not set."""
    vscode_settings = temp_cwd / ".vscode" / "settings.json"
    vscode_settings.parent.mkdir(parents=True)

    settings = {
        "python.envFile": "${workspaceFolder}/.env"
    }
    vscode_settings.write_text(json.dumps(settings), encoding="utf-8")

    assert vls.check_vscode_settings() is False


def test_check_vscode_settings_missing_env_file(temp_cwd: Path, suppress_print) -> None:
    """VS Code settings check should fail when env file setting is missing."""
    vscode_settings = temp_cwd / ".vscode" / "settings.json"
    vscode_settings.parent.mkdir(parents=True)

    settings = {
        "python.defaultInterpreterPath": ".venv/Scripts/python.exe"
    }
    vscode_settings.write_text(json.dumps(settings), encoding="utf-8")

    assert vls.check_vscode_settings() is False


def test_check_vscode_settings_file_read_error(temp_cwd: Path, suppress_print) -> None:
    """VS Code settings check should fail on file read errors."""
    vscode_settings = temp_cwd / ".vscode" / "settings.json"
    vscode_settings.parent.mkdir(parents=True)
    vscode_settings.write_text("", encoding="utf-8")

    # Mock file open to raise exception
    with patch("builtins.open", side_effect=OSError("Permission denied")):
        result = vls.check_vscode_settings()
        assert result is False


# ============================================================
# Tests for check_env_file
# ============================================================

def test_check_env_file_validation(temp_cwd: Path, suppress_print) -> None:
    """Environment file check should validate required keys."""

    env_path = temp_cwd / ".env"
    env_path.write_text("PYTHONPATH=/tmp\nPROJECT_ROOT=/repo\n", encoding="utf-8")

    assert vls.check_env_file() is True


def test_check_env_file_missing_key(temp_cwd: Path, suppress_print) -> None:
    """Environment file check should fail when keys are missing."""

    env_path = temp_cwd / ".env"
    env_path.write_text("PYTHONPATH=/tmp\n", encoding="utf-8")

    assert vls.check_env_file() is False


def test_check_env_file_missing(temp_cwd: Path, suppress_print) -> None:
    """Environment file check should fail when .env is missing."""
    assert vls.check_env_file() is False


def test_check_env_file_with_comments(temp_cwd: Path, suppress_print) -> None:
    """Environment file check should ignore comment lines."""
    env_path = temp_cwd / ".env"
    env_path.write_text("# Comment\nPYTHONPATH=/tmp\nPROJECT_ROOT=/repo\n", encoding="utf-8")

    assert vls.check_env_file() is True


def test_check_env_file_read_error(temp_cwd: Path, suppress_print) -> None:
    """Environment file check should handle read errors."""
    env_path = temp_cwd / ".env"
    env_path.write_text("PYTHONPATH=/tmp\n", encoding="utf-8")
    with patch("builtins.open", side_effect=OSError("Permission denied")):
        result = vls.check_env_file()
    assert result is False


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
                returncode=0
            )
            assert vls.check_azure_cli() is True


def test_check_azure_cli_not_found(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure CLI check should fail when az is not found."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        assert vls.check_azure_cli() is False


def test_check_azure_cli_subprocess_error(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure CLI check should fail on subprocess errors."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = subprocess.CalledProcessError(1, "az")
            assert vls.check_azure_cli() is False


def test_check_azure_cli_empty_version(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure CLI check should handle empty version output."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(stdout="", returncode=0)
            assert vls.check_azure_cli() is True


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
                returncode=0
            )
            assert vls.check_bicep_cli() is True


def test_check_bicep_cli_not_found(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Bicep CLI check should fail when az is not found."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        assert vls.check_bicep_cli() is False


def test_check_bicep_cli_subprocess_error(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Bicep CLI check should fail on subprocess errors."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = subprocess.CalledProcessError(1, "az")
            assert vls.check_bicep_cli() is False


def test_check_bicep_cli_empty_version(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Bicep CLI check should handle empty version output."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(stdout="", returncode=0)
            assert vls.check_bicep_cli() is True


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
                returncode=0
            )
            assert vls.check_azure_providers() is True


def test_check_azure_providers_missing(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure providers check should fail when some providers are missing."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(
                stdout='["Microsoft.Storage"]',
                returncode=0
            )
            assert vls.check_azure_providers() is False


def test_check_azure_providers_no_az(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure providers check should fail when az is not found."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        assert vls.check_azure_providers() is False


def test_check_azure_providers_subprocess_error(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure providers check should handle subprocess errors gracefully."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = subprocess.CalledProcessError(1, "az")
            assert vls.check_azure_providers() is False


def test_check_azure_providers_json_error(monkeypatch: pytest.MonkeyPatch, suppress_print) -> None:
    """Azure providers check should handle JSON decode errors."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(stdout="invalid json", returncode=0)
            assert vls.check_azure_providers() is False


# ============================================================
# Tests for main function
# ============================================================

def test_main_all_pass(monkeypatch: pytest.MonkeyPatch, suppress_print):
    """Main function should return True when all checks pass."""
    monkeypatch.setattr(vls, "check_virtual_environment", lambda: True)
    monkeypatch.setattr(vls, "check_required_packages", lambda: True)
    monkeypatch.setattr(vls, "check_shared_modules", lambda: True)
    monkeypatch.setattr(vls, "check_env_file", lambda: True)
    monkeypatch.setattr(vls, "check_azure_cli", lambda: True)
    monkeypatch.setattr(vls, "check_bicep_cli", lambda: True)
    monkeypatch.setattr(vls, "check_azure_providers", lambda: True)
    monkeypatch.setattr(vls, "check_jupyter_kernel", lambda: True)
    monkeypatch.setattr(vls, "check_vscode_settings", lambda: True)

    result = vls.main()
    assert result is True


def test_main_some_fail(monkeypatch: pytest.MonkeyPatch, suppress_print):
    """Main function should return False when some checks fail."""
    monkeypatch.setattr(vls, "check_virtual_environment", lambda: True)
    monkeypatch.setattr(vls, "check_required_packages", lambda: False)
    monkeypatch.setattr(vls, "check_shared_modules", lambda: True)
    monkeypatch.setattr(vls, "check_env_file", lambda: True)
    monkeypatch.setattr(vls, "check_azure_cli", lambda: True)
    monkeypatch.setattr(vls, "check_bicep_cli", lambda: True)
    monkeypatch.setattr(vls, "check_azure_providers", lambda: True)
    monkeypatch.setattr(vls, "check_jupyter_kernel", lambda: True)
    monkeypatch.setattr(vls, "check_vscode_settings", lambda: True)

    result = vls.main()
    assert result is False
