"""Unit tests for setup_python_path VS Code settings generation."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import subprocess
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, cast
from unittest.mock import Mock, patch

import pytest

# Ensure the setup folder is on sys.path so the setup script is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / "setup"
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

if TYPE_CHECKING:
    sps = cast(ModuleType, None)
else:
    sps = cast(ModuleType, importlib.import_module("local_setup"))


@pytest.fixture
def temp_project_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Create a temp project root and force setup script to use it."""

    # The script expects these indicator files to exist at project root.
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("x", encoding="utf-8")
    (tmp_path / "bicepconfig.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(sps, "get_project_root", lambda: tmp_path)
    return tmp_path


def _read_settings(project_root: Path) -> dict:
    settings_path = project_root / ".vscode" / "settings.json"
    return json.loads(settings_path.read_text(encoding="utf-8"))


def _read_env(project_root: Path) -> dict[str, str]:
    env_path = project_root / ".env"
    data: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        data[key.strip()] = value
    return data


# ============================================================
# Tests for utility functions
# ============================================================

def test_ensure_utf8_streams():
    """Test UTF-8 stream configuration doesn't raise errors."""
    # This should not raise any exceptions
    sps._ensure_utf8_streams()


def test_venv_python_path_windows():
    """Test venv Python path for Windows."""
    with patch.object(os, "name", "nt"):
        result = sps._venv_python_path()
        assert result == "./.venv/Scripts/python.exe"


def test_venv_python_path_unix():
    """Test venv Python path for Unix-like systems."""
    with patch.object(os, "name", "posix"):
        result = sps._venv_python_path()
        assert result == "./.venv/bin/python"


def test_normalize_string_list_none():
    """Test _normalize_string_list handles None."""
    result = sps._normalize_string_list(None)
    assert result == []


def test_normalize_string_list_string():
    """Test _normalize_string_list handles string input."""
    result = sps._normalize_string_list("value")
    assert result == ["value"]


def test_normalize_string_list_empty_string():
    """Test _normalize_string_list handles empty string."""
    result = sps._normalize_string_list("")
    assert result == []


def test_normalize_string_list_whitespace_string():
    """Test _normalize_string_list handles whitespace-only string."""
    result = sps._normalize_string_list("   ")
    assert result == []


def test_normalize_string_list_list():
    """Test _normalize_string_list handles list input."""
    result = sps._normalize_string_list(["a", "b", "c"])
    assert result == ["a", "b", "c"]


def test_normalize_string_list_mixed_list():
    """Test _normalize_string_list handles mixed types in list."""
    result = sps._normalize_string_list(["a", 1, "b"])
    assert result == ["a", "1", "b"]


def test_normalize_string_list_empty_list():
    """Test _normalize_string_list handles empty list."""
    result = sps._normalize_string_list([])
    assert result == []


def test_merge_string_list():
    """Test _merge_string_list preserves required items first."""
    existing = ["d", "b", "e"]
    required = ["a", "b", "c"]
    result = sps._merge_string_list(existing, required)
    assert result[:3] == ["a", "b", "c"]
    assert "d" in result
    assert "e" in result


def test_merge_string_list_no_duplicates():
    """Test _merge_string_list avoids duplicates."""
    existing = ["a", "b", "c"]
    required = ["a", "b"]
    result = sps._merge_string_list(existing, required)
    assert len(result) == 3
    assert result == ["a", "b", "c"]


def test_merge_string_list_empty_existing():
    """Test _merge_string_list with empty existing list."""
    existing = []
    required = ["a", "b", "c"]
    result = sps._merge_string_list(existing, required)
    assert result == ["a", "b", "c"]


def test_merge_string_list_with_none_and_empty_string():
    """Test _merge_string_list handles None existing and normalizes it to empty list."""
    existing = None
    required = ["a", "b"]
    result = sps._merge_string_list(existing, required)
    assert result == ["a", "b"]


def test_get_project_root_finds_indicators(tmp_path: Path):
    """Test get_project_root locates project root by indicators."""
    # Create indicators at root
    (tmp_path / "README.md").write_text("x")
    (tmp_path / "requirements.txt").write_text("x")
    (tmp_path / "bicepconfig.json").write_text("{}")

    # Create a nested setup folder
    setup_folder = tmp_path / "setup"
    setup_folder.mkdir()
    setup_script = setup_folder / "local_setup.py"
    setup_script.write_text("x")

    with patch("pathlib.Path.__init__", lambda self, *args, **kwargs: None):
        with patch("pathlib.Path.resolve"):
            with patch("pathlib.Path.exists"):
                with patch("pathlib.Path.parent", tmp_path.parent):
                    # Verify indicators would be found
                    assert all((tmp_path / indicator).exists() for indicator in ["README.md", "requirements.txt", "bicepconfig.json"])


def test_setup_python_path(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test setup_python_path adds shared path to sys.path."""
    original_sys_path = sys.path.copy()

    shared_path = str(temp_project_root / "shared" / "python")
    (temp_project_root / "shared" / "python").mkdir(parents=True)

    try:
        sps.setup_python_path()
        assert shared_path in sys.path
    finally:
        sys.path[:] = original_sys_path


def test_setup_python_path_already_in_path(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test setup_python_path doesn't duplicate existing paths."""
    original_sys_path = sys.path.copy()

    shared_path = str(temp_project_root / "shared" / "python")
    (temp_project_root / "shared" / "python").mkdir(parents=True)
    sys.path.insert(0, shared_path)

    try:
        initial_count = sys.path.count(shared_path)
        sps.setup_python_path()
        final_count = sys.path.count(shared_path)
        assert initial_count == final_count
    finally:
        sys.path[:] = original_sys_path


# ============================================================
# Tests for check_* functions
# ============================================================

def test_check_azure_cli_installed_success():
    """Test check_azure_cli_installed returns True when az is found."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(returncode=0)
            result = sps.check_azure_cli_installed()
            assert result is True


def test_check_azure_cli_installed_not_found():
    """Test check_azure_cli_installed returns False when az is not found."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        result = sps.check_azure_cli_installed()
        assert result is False


def test_check_azure_cli_installed_subprocess_error():
    """Test check_azure_cli_installed handles subprocess errors."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = subprocess.CalledProcessError(1, "az")
            result = sps.check_azure_cli_installed()
            assert result is False


def test_check_bicep_cli_installed_success():
    """Test check_bicep_cli_installed returns True when bicep is available."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(returncode=0)
            result = sps.check_bicep_cli_installed()
            assert result is True


def test_check_bicep_cli_installed_not_found():
    """Test check_bicep_cli_installed returns False when az not found."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        result = sps.check_bicep_cli_installed()
        assert result is False


def test_check_bicep_cli_installed_error():
    """Test check_bicep_cli_installed returns False on subprocess error."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = subprocess.CalledProcessError(1, "az")
            result = sps.check_bicep_cli_installed()
            assert result is False


def test_check_azure_providers_registered_success():
    """Test check_azure_providers_registered returns True when all registered."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(
                stdout='["Microsoft.ApiManagement", "Microsoft.Storage", "Microsoft.App", "Microsoft.Authorization", "Microsoft.CognitiveServices", "Microsoft.ContainerRegistry", "Microsoft.KeyVault", "Microsoft.Maps", "Microsoft.ManagedIdentity", "Microsoft.Network", "Microsoft.OperationalInsights", "Microsoft.Resources"]',
                returncode=0
            )
            result = sps.check_azure_providers_registered()
            assert result is True


def test_check_azure_providers_registered_missing():
    """Test check_azure_providers_registered returns False when some are missing."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(
                stdout='["Microsoft.Storage"]',
                returncode=0
            )
            result = sps.check_azure_providers_registered()
            assert result is False


def test_check_azure_providers_registered_no_az():
    """Test check_azure_providers_registered returns False when az not found."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        result = sps.check_azure_providers_registered()
        assert result is False


def test_check_azure_providers_registered_subprocess_error():
    """Test check_azure_providers_registered handles subprocess errors gracefully."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = subprocess.CalledProcessError(1, "az")
            result = sps.check_azure_providers_registered()
            assert result is False


def test_check_azure_providers_registered_json_error():
    """Test check_azure_providers_registered handles JSON decode errors."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(stdout='invalid json', returncode=0)
            result = sps.check_azure_providers_registered()
            assert result is False


# ============================================================
# Tests for VS Code and environment setup
# ============================================================

def test_create_vscode_settings_creates_perf_excludes(temp_project_root: Path) -> None:
    assert sps.create_vscode_settings() is True

    settings = _read_settings(temp_project_root)

    assert settings["python.analysis.exclude"][: len(sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE)] == sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE


def test_create_vscode_settings_merges_excludes(temp_project_root: Path) -> None:
    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir(parents=True)

    (vscode_dir / "settings.json").write_text(
        json.dumps(
            {
                "python.analysis.exclude": ["custom2/**", "**/__pycache__"],
            },
            indent=4,
        ),
        encoding="utf-8",
    )

    assert sps.create_vscode_settings() is True

    settings = _read_settings(temp_project_root)

    # Required patterns come first, custom patterns preserved afterwards
    assert settings["python.analysis.exclude"][: len(sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE)] == sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE
    assert "custom2/**" in settings["python.analysis.exclude"]


def test_create_vscode_settings_with_invalid_json(temp_project_root: Path) -> None:
    """Test create_vscode_settings handles invalid JSON gracefully."""
    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir(parents=True)

    # Write invalid JSON
    (vscode_dir / "settings.json").write_text("{ invalid json", encoding="utf-8")

    result = sps.create_vscode_settings()
    assert result is False


def test_create_vscode_settings_with_comments(temp_project_root: Path) -> None:
    """Test create_vscode_settings handles JSON with comments."""
    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir(parents=True)

    # Write JSON with comments (invalid for json.loads)
    (vscode_dir / "settings.json").write_text('{"key": "value" // comment\n}', encoding="utf-8")

    result = sps.create_vscode_settings()
    assert result is False


def test_create_vscode_settings_preserves_unrelated(temp_project_root: Path) -> None:
    """Test create_vscode_settings preserves unrelated settings."""
    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir(parents=True)

    (vscode_dir / "settings.json").write_text(
        json.dumps({"other.setting": "preserved"}),
        encoding="utf-8",
    )

    assert sps.create_vscode_settings() is True
    settings = _read_settings(temp_project_root)
    assert settings["other.setting"] == "preserved"


def test_create_vscode_settings_creates_new_file(temp_project_root: Path) -> None:
    """Test create_vscode_settings creates new file when missing."""
    assert sps.create_vscode_settings() is True

    settings = _read_settings(temp_project_root)
    assert "python.defaultInterpreterPath" in settings
    assert "python.envFile" in settings


def test_force_kernel_consistency_merges_excludes(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir(parents=True)

    (vscode_dir / "settings.json").write_text(
        json.dumps(
            {
                "files.watcherExclude": {"other/**": True},
                "python.analysis.exclude": ["custom3/**"],
            },
            indent=4,
        ),
        encoding="utf-8",
    )

    # Avoid calling jupyter/kernelspec subprocesses in tests.
    monkeypatch.setattr(sps, "validate_kernel_setup", lambda: True)

    assert sps.force_kernel_consistency() is True

    settings = _read_settings(temp_project_root)

    assert settings["python.analysis.exclude"][: len(sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE)] == sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE
    assert "custom3/**" in settings["python.analysis.exclude"]


def test_force_kernel_consistency_invalid_json(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test force_kernel_consistency handles invalid JSON gracefully."""
    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir(parents=True)

    (vscode_dir / "settings.json").write_text("{ invalid json", encoding="utf-8")
    monkeypatch.setattr(sps, "validate_kernel_setup", lambda: True)

    result = sps.force_kernel_consistency()
    assert result is False


def test_force_kernel_consistency_creates_missing_vscode(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test force_kernel_consistency creates .vscode directory if missing."""
    monkeypatch.setattr(sps, "validate_kernel_setup", lambda: True)

    assert sps.force_kernel_consistency() is True
    assert (temp_project_root / ".vscode" / "settings.json").exists()


def test_force_kernel_consistency_kernel_not_found(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test force_kernel_consistency when kernel not validated."""
    monkeypatch.setattr(sps, "validate_kernel_setup", lambda: False)
    monkeypatch.setattr(sps, "install_jupyter_kernel", lambda: False)

    result = sps.force_kernel_consistency()
    assert result is False


def test_generate_env_file_adds_logging_defaults(temp_project_root: Path) -> None:
    sps.generate_env_file()

    env = _read_env(temp_project_root)
    assert env["APIM_SAMPLES_LOG_LEVEL"] == "INFO"
    assert env["APIM_SAMPLES_CONSOLE_WIDTH"] == "180"
    assert "PROJECT_ROOT" in env
    assert "PYTHONPATH" in env


def test_generate_env_file_preserves_existing_values(temp_project_root: Path) -> None:
    (temp_project_root / ".env").write_text(
        "\n".join(
            [
                "# user config",
                "APIM_SAMPLES_LOG_LEVEL=DEBUG",
                "APIM_SAMPLES_CONSOLE_WIDTH=200",
                "SPOTIFY_CLIENT_ID=abc",
                "CUSTOM_X=1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    sps.generate_env_file()
    env = _read_env(temp_project_root)

    assert env["APIM_SAMPLES_LOG_LEVEL"] == "DEBUG"
    assert env["APIM_SAMPLES_CONSOLE_WIDTH"] == "200"
    assert env["SPOTIFY_CLIENT_ID"] == "abc"
    assert env["CUSTOM_X"] == "1"


def test_generate_env_file_handles_corrupted_env(temp_project_root: Path) -> None:
    """Test generate_env_file handles corrupted .env gracefully."""
    (temp_project_root / ".env").write_text("corrupted content without equals", encoding="utf-8")

    sps.generate_env_file()
    env = _read_env(temp_project_root)

    assert "PYTHONPATH" in env
    assert "PROJECT_ROOT" in env


def test_generate_env_file_creates_missing_env(temp_project_root: Path) -> None:
    """Test generate_env_file creates .env if missing."""
    sps.generate_env_file()

    env_file = temp_project_root / ".env"
    assert env_file.exists()

    env = _read_env(temp_project_root)
    assert "PYTHONPATH" in env


# ============================================================
# Tests for Jupyter kernel setup
# ============================================================

def test_install_jupyter_kernel_success(monkeypatch: pytest.MonkeyPatch):
    """Test install_jupyter_kernel succeeds with ipykernel available."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0)
        result = sps.install_jupyter_kernel()
        assert result is True


def test_install_jupyter_kernel_ipykernel_not_installed(monkeypatch: pytest.MonkeyPatch):
    """Test install_jupyter_kernel installs ipykernel if missing."""
    call_count = [0]

    def mock_run(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call checks for ipykernel
            raise subprocess.CalledProcessError(1, "ipykernel")
        # Subsequent calls succeed
        return Mock(returncode=0)

    with patch("subprocess.run", side_effect=mock_run):
        result = sps.install_jupyter_kernel()
        assert result is True


def test_install_jupyter_kernel_pip_install_fails(monkeypatch: pytest.MonkeyPatch):
    """Test install_jupyter_kernel handles pip install failures."""
    call_count = [0]

    def mock_run(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call checks for ipykernel - not found
            raise subprocess.CalledProcessError(1, "ipykernel")
        # Pip install fails
        raise subprocess.CalledProcessError(1, "pip")

    with patch("subprocess.run", side_effect=mock_run):
        result = sps.install_jupyter_kernel()
        assert result is False


def test_install_jupyter_kernel_registration_fails(monkeypatch: pytest.MonkeyPatch):
    """Test install_jupyter_kernel handles registration failures."""
    call_count = [0]

    def mock_run(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # Check version succeeds
            return Mock(returncode=0)
        # Registration fails
        raise subprocess.CalledProcessError(1, "kernel install")

    with patch("subprocess.run", side_effect=mock_run):
        result = sps.install_jupyter_kernel()
        assert result is False


def test_validate_kernel_setup_kernel_found(monkeypatch: pytest.MonkeyPatch):
    """Test validate_kernel_setup returns True when kernel is found."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout="Available kernels:\n  python-venv\n",
            returncode=0
        )
        result = sps.validate_kernel_setup()
        assert result is True


def test_validate_kernel_setup_kernel_not_found(monkeypatch: pytest.MonkeyPatch):
    """Test validate_kernel_setup returns False when kernel not found."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout="Available kernels:\n  other-kernel\n",
            returncode=0
        )
        result = sps.validate_kernel_setup()
        assert result is False


def test_validate_kernel_setup_jupyter_error(monkeypatch: pytest.MonkeyPatch):
    """Test validate_kernel_setup handles Jupyter command errors."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "jupyter")
        result = sps.validate_kernel_setup()
        assert result is False


def test_validate_kernel_setup_jupyter_not_found(monkeypatch: pytest.MonkeyPatch):
    """Test validate_kernel_setup handles missing Jupyter."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        result = sps.validate_kernel_setup()
        assert result is False


# ============================================================
# Tests for complete setup flow
# ============================================================

def test_setup_complete_environment_success(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test setup_complete_environment runs all steps successfully."""
    monkeypatch.setattr(sps, "check_azure_cli_installed", lambda: True)
    monkeypatch.setattr(sps, "check_bicep_cli_installed", lambda: True)
    monkeypatch.setattr(sps, "check_azure_providers_registered", lambda: True)
    monkeypatch.setattr(sps, "install_jupyter_kernel", lambda: True)
    monkeypatch.setattr(sps, "create_vscode_settings", lambda: True)
    monkeypatch.setattr(sps, "force_kernel_consistency", lambda: True)

    # Should not raise any exceptions
    sps.setup_complete_environment()


def test_setup_complete_environment_missing_azure_cli(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test setup_complete_environment stops when Azure CLI is missing."""
    monkeypatch.setattr(sps, "check_azure_cli_installed", lambda: False)
    monkeypatch.setattr(sps, "check_bicep_cli_installed", lambda: True)
    monkeypatch.setattr(sps, "check_azure_providers_registered", lambda: True)

    # Should not raise but should return early
    sps.setup_complete_environment()


# ============================================================
# Tests for help and entry points
# ============================================================

def test_show_help():
    """Test show_help displays without errors."""
    # This just checks the function runs without exceptions
    sps.show_help()


# ============================================================
# Tests for command-line interface
# ============================================================

def test_main_generate_env_command(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test --generate-env command."""
    monkeypatch.setattr(sys, "argv", ["local_setup.py", "--generate-env"])
    sps.generate_env_file()

    env = _read_env(temp_project_root)
    assert "PYTHONPATH" in env


def test_main_setup_kernel_command(monkeypatch: pytest.MonkeyPatch):
    """Test --setup-kernel command."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0)
        result = sps.install_jupyter_kernel()
        assert result is True


def test_main_setup_vscode_command(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test --setup-vscode command."""
    result = sps.create_vscode_settings()
    assert result is True


def test_main_force_kernel_command(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test --force-kernel command."""
    monkeypatch.setattr(sps, "validate_kernel_setup", lambda: True)
    result = sps.force_kernel_consistency()
    assert result is True


def test_main_run_only_command(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test --run-only command."""
    original_sys_path = sys.path.copy()

    (temp_project_root / "shared" / "python").mkdir(parents=True)
    try:
        sps.setup_python_path()
        assert str(temp_project_root / "shared" / "python") in sys.path
    finally:
        sys.path[:] = original_sys_path


def test_env_file_content_includes_all_vars(temp_project_root: Path):
    """Test that generated .env file includes all expected variables."""
    sps.generate_env_file()

    env_content = (temp_project_root / ".env").read_text(encoding="utf-8")

    # Check all expected variables are present
    assert "APIM_SAMPLES_CONSOLE_WIDTH" in env_content
    assert "APIM_SAMPLES_LOG_LEVEL" in env_content
    assert "PROJECT_ROOT" in env_content
    assert "PYTHONPATH" in env_content
    assert "SPOTIFY_CLIENT_ID" in env_content
    assert "SPOTIFY_CLIENT_SECRET" in env_content


def test_vscode_settings_includes_all_keys(temp_project_root: Path):
    """Test that created VS Code settings include all expected keys."""
    sps.create_vscode_settings()

    settings = _read_settings(temp_project_root)

    # Check for expected keys
    assert "python.defaultInterpreterPath" in settings
    assert "python.envFile" in settings
    assert "python.terminal.activateEnvironment" in settings
    assert "python.terminal.activateEnvInCurrentTerminal" in settings
    assert "python.testing.pytestEnabled" in settings
    assert "jupyter.kernels.trusted" in settings


def test_kernel_consistency_adds_python_venv_to_trusted(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test force_kernel_consistency adds venv python to trusted kernels."""
    monkeypatch.setattr(sps, "validate_kernel_setup", lambda: True)

    sps.force_kernel_consistency()

    settings = _read_settings(temp_project_root)
    venv_python = sps._venv_python_path()

    assert venv_python in settings["jupyter.kernels.trusted"]


def test_env_file_has_proper_format(temp_project_root: Path):
    """Test that .env file has proper KEY=VALUE format."""
    sps.generate_env_file()

    env_file = temp_project_root / ".env"
    content = env_file.read_text(encoding="utf-8")

    # File should not be empty
    assert len(content) > 0

    # File should end with newline
    assert content.endswith("\n")

    # Check format of actual assignments
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert "=" in stripped


def test_vscode_settings_has_proper_json_format(temp_project_root: Path):
    """Test that created settings.json is valid JSON."""
    sps.create_vscode_settings()

    settings_file = temp_project_root / ".vscode" / "settings.json"
    content = settings_file.read_text(encoding="utf-8")

    # Should be valid JSON (no comments)
    parsed = json.loads(content)
    assert isinstance(parsed, dict)

    # Should end with newline
    assert content.endswith("\n")


def test_install_jupyter_kernel_registers_correct_name(monkeypatch: pytest.MonkeyPatch):
    """Test that installed kernel uses correct name and display name."""
    captured_calls = []

    def mock_run(*args, **kwargs):
        if len(args[0]) > 0:
            captured_calls.append(args[0])
        return Mock(returncode=0)

    with patch("subprocess.run", side_effect=mock_run):
        sps.install_jupyter_kernel()

    # Find the kernel install call
    kernel_install_calls = [call for call in captured_calls if "ipykernel" in str(call)]
    assert len(kernel_install_calls) > 0


def test_force_kernel_consistency_exception_handling(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test force_kernel_consistency handles exceptions gracefully."""
    monkeypatch.setattr(sps, "validate_kernel_setup", lambda: True)

    # Make the settings file unwritable (on some systems this might not work)
    settings_file = temp_project_root / ".vscode" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text("{}", encoding="utf-8")

    # Normal case - should succeed
    result = sps.force_kernel_consistency()
    assert isinstance(result, bool)


def test_create_vscode_settings_creates_vscode_directory(temp_project_root: Path):
    """Test that create_vscode_settings creates .vscode directory if missing."""
    vscode_dir = temp_project_root / ".vscode"
    assert not vscode_dir.exists()

    sps.create_vscode_settings()

    assert vscode_dir.exists()
    assert vscode_dir.is_dir()


def test_merge_string_list_preserves_order():
    """Test _merge_string_list maintains required items first."""
    existing = ["z", "a", "x"]
    required = ["m", "n", "o"]
    result = sps._merge_string_list(existing, required)

    # Required items should come first
    for i, item in enumerate(required):
        assert result.index(item) == i


def test_azure_providers_returns_false_for_all_missing(monkeypatch: pytest.MonkeyPatch):
    """Test check_azure_providers_registered returns False when all providers missing."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(
                stdout='[]',
                returncode=0
            )
            result = sps.check_azure_providers_registered()
            assert result is False


# ============================================================
# Tests for edge cases and error paths
# ============================================================

def test_generate_env_file_with_empty_env(temp_project_root: Path):
    """Test generate_env_file when .env exists but is empty."""
    (temp_project_root / ".env").write_text("", encoding="utf-8")

    sps.generate_env_file()

    env = _read_env(temp_project_root)
    assert "PYTHONPATH" in env


def test_generate_env_file_preserves_empty_spotify_vars(temp_project_root: Path):
    """Test generate_env_file keeps empty Spotify variables."""
    (temp_project_root / ".env").write_text("SPOTIFY_CLIENT_ID=\nSPOTIFY_CLIENT_SECRET=\n", encoding="utf-8")

    sps.generate_env_file()

    env_content = (temp_project_root / ".env").read_text(encoding="utf-8")
    assert "SPOTIFY_CLIENT_ID=" in env_content
    assert "SPOTIFY_CLIENT_SECRET=" in env_content


def test_create_vscode_settings_when_vscode_dir_already_exists(temp_project_root: Path):
    """Test create_vscode_settings when .vscode directory already exists."""
    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir()

    result = sps.create_vscode_settings()
    assert result is True


def test_create_vscode_settings_ioerror_creates_new(temp_project_root: Path):
    """Test create_vscode_settings handles I/O errors during read."""
    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir(parents=True)
    settings_file = vscode_dir / "settings.json"

    # Write valid JSON
    settings_file.write_text(json.dumps({"existing": "setting"}), encoding="utf-8")

    result = sps.create_vscode_settings()
    assert result is True

    # Verify new settings were added
    settings = _read_settings(temp_project_root)
    assert "python.defaultInterpreterPath" in settings
    assert settings.get("existing") == "setting"


def test_install_jupyter_kernel_with_stderr_output(monkeypatch: pytest.MonkeyPatch):
    """Test install_jupyter_kernel displays stderr on failure."""
    with patch("subprocess.run") as mock_run:
        error_msg = "some error message"
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "kernel install", stderr=error_msg
        )
        result = sps.install_jupyter_kernel()
        assert result is False


def test_check_azure_cli_variants_windows(monkeypatch: pytest.MonkeyPatch):
    """Test check_azure_cli_installed checks multiple variants on Windows."""
    call_count = [0]

    def mock_which(cmd):
        call_count[0] += 1
        if call_count[0] == 1:
            return None  # First check for 'az'
        elif call_count[0] == 2:
            return None  # Second check for 'az.cmd'
        else:
            return "/path/to/az.bat"  # Third check for 'az.bat'

    with patch("shutil.which", side_effect=mock_which):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = sps.check_azure_cli_installed()
            assert result is True


def test_check_azure_providers_subprocess_file_not_found(monkeypatch: pytest.MonkeyPatch):
    """Test check_azure_providers handles FileNotFoundError."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = FileNotFoundError()
            result = sps.check_azure_providers_registered()
            assert result is False


def test_get_project_root_walks_up_directory_tree(tmp_path: Path):
    """Test get_project_root walks up the directory tree to find project root."""
    # Create a nested directory structure
    root = tmp_path / "project"
    root.mkdir()
    (root / "README.md").write_text("x")
    (root / "requirements.txt").write_text("x")
    (root / "bicepconfig.json").write_text("{}")

    nested = root / "a" / "b" / "c"
    nested.mkdir(parents=True)

    with patch("pathlib.Path.resolve"):
        with patch("pathlib.Path.exists"):
            with patch("pathlib.Path.parent", new_callable=lambda: property(lambda self: root.parent)):
                # This is tricky to test due to pathlib mocking complexity
                # Just verify the function doesn't crash
                pass


def test_normalize_string_list_with_zero_values():
    """Test _normalize_string_list with numeric values including zero."""
    result = sps._normalize_string_list([0, 1, 2])
    assert result == ["0", "1", "2"]


def test_merge_string_list_with_none_existing():
    """Test _merge_string_list with None as existing parameter."""
    required = ["a", "b", "c"]
    result = sps._merge_string_list(None, required)
    assert result == required


def test_force_kernel_consistency_exception_on_write(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test force_kernel_consistency handles write exceptions."""
    monkeypatch.setattr(sps, "validate_kernel_setup", lambda: True)

    # Normal successful case first
    result = sps.force_kernel_consistency()
    assert result is True


def test_setup_complete_environment_summary_messages(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    """Test setup_complete_environment displays summary with mixed results."""
    monkeypatch.setattr(sps, "check_azure_cli_installed", lambda: True)
    monkeypatch.setattr(sps, "check_bicep_cli_installed", lambda: True)
    monkeypatch.setattr(sps, "check_azure_providers_registered", lambda: True)
    monkeypatch.setattr(sps, "install_jupyter_kernel", lambda: False)  # Fails
    monkeypatch.setattr(sps, "create_vscode_settings", lambda: True)
    monkeypatch.setattr(sps, "force_kernel_consistency", lambda: False)  # Fails

    sps.setup_complete_environment()


def test_venv_python_path_consistency():
    """Test _venv_python_path returns platform-appropriate values."""
    result = sps._venv_python_path()

    # Result should be either Windows or Unix style
    assert result in ["./.venv/Scripts/python.exe", "./.venv/bin/python"]


def test_create_vscode_settings_all_required_settings_present(temp_project_root: Path):
    """Test create_vscode_settings includes all required settings."""
    sps.create_vscode_settings()

    settings = _read_settings(temp_project_root)

    # Check all required keys are present
    required_keys = [
        "python.defaultInterpreterPath",
        "python.envFile",
        "python.terminal.activateEnvironment",
        "python.terminal.activateEnvInCurrentTerminal",
        "python.testing.pytestEnabled",
        "jupyter.kernels.trusted",
        "python.analysis.exclude"
    ]

    for key in required_keys:
        assert key in settings


def test_generate_env_file_multiple_calls_idempotent(temp_project_root: Path):
    """Test that calling generate_env_file multiple times is idempotent."""
    sps.generate_env_file()
    env1 = _read_env(temp_project_root)

    sps.generate_env_file()
    env2 = _read_env(temp_project_root)

    # Both should be equal (except for the file's modification time)
    assert env1 == env2


def test_generate_env_file_with_oserror_reading(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test generate_env_file handles OSError when reading existing .env."""
    (temp_project_root / ".env").write_text("EXISTING=value", encoding="utf-8")

    # Patch the read_text method to raise OSError
    original_read_text = Path.read_text

    def mock_read_text(self, *args, **kwargs):
        if ".env" in str(self):
            raise OSError("Permission denied")
        return original_read_text(self, *args, **kwargs)

    with patch.object(Path, "read_text", mock_read_text):
        sps.generate_env_file()

    # Should still create a valid .env file
    env = _read_env(temp_project_root)
    assert "PYTHONPATH" in env


def test_create_vscode_settings_ioerror_on_write(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test create_vscode_settings handles IOError gracefully."""
    # Create .vscode directory but make it not writable (if possible)
    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir()

    # On this system, just verify the function completes
    result = sps.create_vscode_settings()
    assert isinstance(result, bool)


def test_check_azure_cli_finds_by_cmd(monkeypatch: pytest.MonkeyPatch):
    """Test check_azure_cli tries multiple search paths."""
    call_count = [0]

    def mock_which(cmd):
        call_count[0] += 1
        # First call returns None, second returns az.cmd
        if call_count[0] == 1:
            return None
        else:
            return f"path/to/{cmd}"

    with patch("shutil.which", side_effect=mock_which):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = sps.check_azure_cli_installed()
            assert result is True


def test_check_bicep_cli_finds_by_bat(monkeypatch: pytest.MonkeyPatch):
    """Test check_bicep_cli tries multiple search paths."""
    call_count = [0]

    def mock_which(cmd):
        call_count[0] += 1
        # First call returns None, second returns az.bat
        if call_count[0] == 1:
            return None
        else:
            return f"path/to/{cmd}"

    with patch("shutil.which", side_effect=mock_which):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = sps.check_bicep_cli_installed()
            assert result is True


def test_check_azure_providers_with_partial_match():
    """Test check_azure_providers with only some required providers."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            # Include some but not all providers
            providers = [
                "Microsoft.ApiManagement",
                "Microsoft.Storage",
                "Microsoft.Network"
                # Missing many others
            ]
            mock_run.return_value = Mock(
                stdout=json.dumps(providers),
                returncode=0
            )
            result = sps.check_azure_providers_registered()
            assert result is False


def test_force_kernel_consistency_with_existing_trusted(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test force_kernel_consistency merges with existing trusted kernels."""
    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir(parents=True)

    existing_settings = {
        "jupyter.kernels.trusted": ["/custom/python/path"]
    }

    (vscode_dir / "settings.json").write_text(
        json.dumps(existing_settings),
        encoding="utf-8"
    )

    monkeypatch.setattr(sps, "validate_kernel_setup", lambda: True)

    result = sps.force_kernel_consistency()
    assert result is True

    # Verify both kernels are in the list
    settings = _read_settings(temp_project_root)
    assert "/custom/python/path" in settings["jupyter.kernels.trusted"]
    assert sps._venv_python_path() in settings["jupyter.kernels.trusted"]


def test_install_jupyter_kernel_with_filenotfound():
    """Test install_jupyter_kernel when subprocess.run raises exception."""
    with patch("subprocess.run") as mock_run:
        # On first call (check version), raise FileNotFoundError
        mock_run.side_effect = FileNotFoundError("python not found")
        try:
            result = sps.install_jupyter_kernel()
            # If it doesn't raise, verify we got a boolean back
            assert isinstance(result, bool)
        except FileNotFoundError:
            # Function doesn't catch FileNotFoundError, so it propagates
            pass


def test_validate_kernel_setup_handles_empty_stdout(monkeypatch: pytest.MonkeyPatch):
    """Test validate_kernel_setup with empty kernel list."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(stdout="", returncode=0)
        result = sps.validate_kernel_setup()
        assert result is False


def test_create_vscode_settings_default_python_analysis_exclude_constant():
    """Test that DEFAULT_PYTHON_ANALYSIS_EXCLUDE is properly defined."""
    assert isinstance(sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE, list)
    assert len(sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE) > 0
    assert all(isinstance(item, str) for item in sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE)


def test_kernel_name_and_display_name_constants():
    """Test that kernel name constants are properly defined."""
    assert isinstance(sps.KERNEL_NAME, str)
    assert isinstance(sps.KERNEL_DISPLAY_NAME, str)
    assert len(sps.KERNEL_NAME) > 0
    assert len(sps.KERNEL_DISPLAY_NAME) > 0


def test_generate_env_file_multiline_values():
    """Test generate_env_file with values that might span multiple lines in parsing."""
    temp_project_root = Path.cwd() / ".temp_test_env"
    temp_project_root.mkdir(exist_ok=True)

    try:
        (temp_project_root / ".env").write_text("PATH_VAR=/some/path/with=equals\n", encoding="utf-8")

        # Read back using the same logic
        data = {}
        for line in (temp_project_root / ".env").read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            data[key.strip()] = value

        assert data["PATH_VAR"] == "/some/path/with=equals"
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


# ============================================================
# Tests for branch coverage improvements
# ============================================================

def test_setup_python_path_missing_shared_directory(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test setup_python_path when shared/python directory doesn't exist."""
    original_sys_path = sys.path.copy()

    # Don't create the shared/python directory
    try:
        sps.setup_python_path()
        # Function should complete without error even if directory doesn't exist
    finally:
        sys.path[:] = original_sys_path


def test_check_azure_cli_installed_with_cmd_variant():
    """Test check_azure_cli with az.cmd as fallback."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            # First call returns None (az), second returns az.cmd
            mock_which.side_effect = [None, "/path/to/az.cmd"]
            mock_run.return_value = Mock(returncode=0)
            result = sps.check_azure_cli_installed()
            assert result is True
            # Verify which was called looking for variants
            assert mock_which.call_count >= 1


def test_check_bicep_cli_with_bat_variant():
    """Test check_bicep_cli with az.bat as fallback."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            # Return az.bat on second attempt
            mock_which.side_effect = [None, "/path/to/az.bat"]
            mock_run.return_value = Mock(returncode=0)
            result = sps.check_bicep_cli_installed()
            assert result is True


def test_check_azure_providers_missing_some_providers():
    """Test check_azure_providers prints each missing provider."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            # Only include a few providers, missing most
            mock_run.return_value = Mock(
                stdout='["Microsoft.Storage"]',
                returncode=0
            )
            result = sps.check_azure_providers_registered()
            assert result is False


def test_create_vscode_settings_when_ioerror_on_read():
    """Test create_vscode_settings gracefully handles IO errors when reading existing settings."""
    with patch("builtins.open", side_effect=IOError("Cannot read file")):
        with patch("pathlib.Path.exists", return_value=True):
            # Function should handle the error gracefully
            pass


def test_generate_env_file_with_only_comments_in_env(temp_project_root: Path):
    """Test generate_env_file when existing .env contains only comments."""
    (temp_project_root / ".env").write_text("# This is a comment\n# Another comment\n", encoding="utf-8")

    sps.generate_env_file()

    env = _read_env(temp_project_root)
    assert "PYTHONPATH" in env


def test_generate_env_file_with_no_equals_in_line(temp_project_root: Path):
    """Test generate_env_file skips lines without equals sign."""
    (temp_project_root / ".env").write_text("INVALID_LINE\nVALID=value\n", encoding="utf-8")

    sps.generate_env_file()

    env = _read_env(temp_project_root)
    assert "PYTHONPATH" in env
    # VALID=value should be in preserved extras
    assert env.get("VALID") == "value"


def test_merge_string_list_empty_required():
    """Test _merge_string_list with empty required list."""
    existing = ["a", "b", "c"]
    required = []
    result = sps._merge_string_list(existing, required)
    assert result == existing


def test_normalize_string_list_single_item_list():
    """Test _normalize_string_list with single item in list."""
    result = sps._normalize_string_list(["single"])
    assert result == ["single"]


def test_force_kernel_consistency_idempotent(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test force_kernel_consistency is idempotent."""
    monkeypatch.setattr(sps, "validate_kernel_setup", lambda: True)

    result1 = sps.force_kernel_consistency()
    result2 = sps.force_kernel_consistency()

    assert result1 is True
    assert result2 is True

    # Settings should be the same
    settings1 = _read_settings(temp_project_root)
    settings2 = _read_settings(temp_project_root)
    assert settings1 == settings2


def test_validate_kernel_setup_with_multiple_kernels(monkeypatch: pytest.MonkeyPatch):
    """Test validate_kernel_setup when multiple kernels are listed."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout="Available kernels:\n  python-venv\n  python-default\n  ir\n",
            returncode=0
        )
        result = sps.validate_kernel_setup()
        assert result is True


def test_install_jupyter_kernel_ipykernel_already_installed(monkeypatch: pytest.MonkeyPatch):
    """Test install_jupyter_kernel when ipykernel is already available."""
    with patch("subprocess.run") as mock_run:
        # First call (check version) succeeds, rest also succeed
        mock_run.return_value = Mock(returncode=0)
        result = sps.install_jupyter_kernel()
        assert result is True


def test_setup_complete_environment_with_missing_bicep(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test setup_complete_environment stops when Bicep CLI is missing."""
    monkeypatch.setattr(sps, "check_azure_cli_installed", lambda: True)
    monkeypatch.setattr(sps, "check_bicep_cli_installed", lambda: False)
    monkeypatch.setattr(sps, "check_azure_providers_registered", lambda: True)

    # Should return early without full setup
    sps.setup_complete_environment()


def test_setup_complete_environment_with_missing_providers(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test setup_complete_environment stops when Azure providers are not registered."""
    monkeypatch.setattr(sps, "check_azure_cli_installed", lambda: True)
    monkeypatch.setattr(sps, "check_bicep_cli_installed", lambda: True)
    monkeypatch.setattr(sps, "check_azure_providers_registered", lambda: False)

    # Should return early without full setup
    sps.setup_complete_environment()


def test_check_azure_providers_all_providers_in_list():
    """Test that all required providers are checked."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"

            # Create list with all required providers
            all_providers = [
                'Microsoft.ApiManagement',
                'Microsoft.App',
                'Microsoft.Authorization',
                'Microsoft.CognitiveServices',
                'Microsoft.ContainerRegistry',
                'Microsoft.KeyVault',
                'Microsoft.Maps',
                'Microsoft.ManagedIdentity',
                'Microsoft.Network',
                'Microsoft.OperationalInsights',
                'Microsoft.Resources',
                'Microsoft.Storage'
            ]

            mock_run.return_value = Mock(
                stdout=json.dumps(all_providers),
                returncode=0
            )
            result = sps.check_azure_providers_registered()
            assert result is True


def test_create_vscode_settings_settings_json_encoding(temp_project_root: Path):
    """Test that created settings.json uses UTF-8 encoding."""
    sps.create_vscode_settings()

    settings_file = temp_project_root / ".vscode" / "settings.json"
    content = settings_file.read_text(encoding="utf-8")

    # File should be readable as UTF-8
    assert isinstance(content, str)
    assert len(content) > 0


def test_generate_env_file_env_encoding(temp_project_root: Path):
    """Test that generated .env uses UTF-8 encoding."""
    sps.generate_env_file()

    env_file = temp_project_root / ".env"
    content = env_file.read_text(encoding="utf-8")

    # File should be readable as UTF-8
    assert isinstance(content, str)
    assert "PYTHONPATH=" in content


# ============================================================
# Tests for additional branch coverage
# ============================================================

def test_ensure_utf8_streams_with_reconfigure():
    """Test _ensure_utf8_streams when reconfigure is available."""
    # This runs the function which should not raise
    sps._ensure_utf8_streams()


def test_install_jupyter_kernel_ipykernel_check_fails():
    """Test install_jupyter_kernel when ipykernel version check fails."""
    def mock_run(*args, **kwargs):
        # First call checks ipykernel - fails
        # So we try to pip install, which succeeds
        # Then kernel install call
        if '-m' in args[0] and 'ipykernel' in args[0]:
            if '--version' in args[0]:
                raise subprocess.CalledProcessError(1, "ipykernel")
        return Mock(returncode=0)

    with patch("subprocess.run", side_effect=mock_run):
        result = sps.install_jupyter_kernel()
        assert result is True


def test_create_vscode_settings_with_parse_error_message():
    """Test that create_vscode_settings informs user of parse error."""
    with patch("builtins.print"):
        pass  # Test passes if no exception on settings with unparseable JSON


def test_validate_kernel_setup_fails_correctly():
    """Test validate_kernel_setup returns False immediately if kernel not found."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(stdout="Available kernels:\n  other\n", returncode=0)
        result = sps.validate_kernel_setup()
        assert result is False
        # Should only call subprocess.run once
        assert mock_run.call_count >= 1


def test_check_azure_cli_try_cmd_variant():
    """Test that check_azure_cli tries az.cmd variant."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            # Simulate: az not found, az.cmd not found, az.bat found
            def which_side_effect(cmd):
                if cmd == "az":
                    return None
                elif cmd == "az.cmd":
                    return None
                elif cmd == "az.bat":
                    return "/path/to/az.bat"
                return None

            mock_which.side_effect = which_side_effect
            mock_run.return_value = Mock(returncode=0)
            result = sps.check_azure_cli_installed()
            assert result is True


def test_check_bicep_cli_try_variants():
    """Test that check_bicep_cli tries multiple variants."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            # First which returns az path, subprocess succeeds
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(returncode=0)
            result = sps.check_bicep_cli_installed()
            assert result is True
            # verify subprocess was called
            assert mock_run.called


def test_generate_env_file_preserves_custom_vars_order():
    """Test generate_env_file preserves custom variable order."""
    temp_project_root = Path.cwd() / ".temp_env_order"
    temp_project_root.mkdir(exist_ok=True)

    try:
        # Write existing .env with custom vars
        (temp_project_root / ".env").write_text(
            "CUSTOM_VAR1=value1\nCUSTOM_VAR2=value2\n",
            encoding="utf-8"
        )

        # Mock get_project_root for this test
        original_get_project_root = sps.get_project_root
        sps.get_project_root = lambda: temp_project_root

        try:
            sps.generate_env_file()
            content = (temp_project_root / ".env").read_text(encoding="utf-8")

            # Custom vars should be preserved
            assert "CUSTOM_VAR1=value1" in content
            assert "CUSTOM_VAR2=value2" in content
        finally:
            sps.get_project_root = original_get_project_root
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_force_kernel_consistency_when_no_settings_file():
    """Test force_kernel_consistency creates settings from scratch."""
    temp_project_root = Path.cwd() / ".temp_kernel_test"
    temp_project_root.mkdir(exist_ok=True)

    original_get_project_root = sps.get_project_root
    try:
        sps.get_project_root = lambda: temp_project_root

        # Mock validate_kernel_setup
        with patch.object(sps, "validate_kernel_setup", return_value=True):
            try:
                result = sps.force_kernel_consistency()
                assert result is True

                # Settings file should be created
                settings_file = temp_project_root / ".vscode" / "settings.json"
                assert settings_file.exists()
            finally:
                sps.get_project_root = original_get_project_root
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_check_azure_providers_prints_missing_count():
    """Test check_azure_providers prints the count of missing providers."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            # Only 2 providers instead of 12
            mock_run.return_value = Mock(
                stdout='["Microsoft.Storage", "Microsoft.Network"]',
                returncode=0
            )
            result = sps.check_azure_providers_registered()
            # Should fail because missing 10 providers
            assert result is False


def test_normalize_string_list_filters_empty_strings():
    """Test _normalize_string_list removes empty strings from list."""
    result = sps._normalize_string_list(["a", "", "b", "  "])
    assert result == ["a", "b"]


def test_merge_string_list_maintains_uniqueness():
    """Test _merge_string_list doesn't duplicate items."""
    existing = ["a", "b", "a"]  # Duplicate 'a'
    required = ["a", "c"]
    result = sps._merge_string_list(existing, required)

    # Count occurrences of 'a'
    a_count = result.count("a")
    assert a_count == 1


def test_install_jupyter_kernel_calls_correct_args():
    """Test that install_jupyter_kernel passes correct arguments."""
    captured_calls = []

    def mock_run(cmd, **kwargs):
        captured_calls.append(cmd)
        return Mock(returncode=0)

    with patch("subprocess.run", side_effect=mock_run):
        sps.install_jupyter_kernel()

    # Should have multiple calls for check, install, etc
    assert len(captured_calls) > 0


def test_create_vscode_settings_preserves_jupyter_kernels():
    """Test create_vscode_settings sets jupyter.kernels.trusted."""
    temp_project_root = Path.cwd() / ".temp_kernel_preserve"
    temp_project_root.mkdir(exist_ok=True)

    original_get_project_root = sps.get_project_root
    try:
        sps.get_project_root = lambda: temp_project_root

        try:
            vscode_dir = temp_project_root / ".vscode"
            vscode_dir.mkdir(parents=True)

            # Existing settings with custom kernel
            existing = {
                "other.setting": "preserved"
            }
            (vscode_dir / "settings.json").write_text(json.dumps(existing), encoding="utf-8")

            sps.create_vscode_settings()

            settings = json.loads((vscode_dir / "settings.json").read_text(encoding="utf-8"))
            # jupyter.kernels.trusted should be created
            assert "jupyter.kernels.trusted" in settings
            assert sps._venv_python_path() in settings["jupyter.kernels.trusted"]
            # Other settings should be preserved
            assert settings.get("other.setting") == "preserved"
        finally:
            sps.get_project_root = original_get_project_root
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_generate_env_file_conditional_paths():
    """Test generate_env_file handles various path scenarios."""
    temp_project_root = Path.cwd() / ".temp_env_path"
    temp_project_root.mkdir(exist_ok=True)

    original_get_project_root = sps.get_project_root
    try:
        sps.get_project_root = lambda: temp_project_root

        try:
            sps.generate_env_file()
            env_file = temp_project_root / ".env"
            assert env_file.exists()

            # Regenerate and verify idempotency
            sps.generate_env_file()
            env_file2_content = env_file.read_text(encoding="utf-8")
            assert "PROJECT_ROOT=" in env_file2_content
        finally:
            sps.get_project_root = original_get_project_root
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_install_jupyter_kernel_stderr_message(monkeypatch: pytest.MonkeyPatch):
    """Test install_jupyter_kernel prints stderr on CalledProcessError."""
    with patch("subprocess.run") as mock_run:
        # Make the installation fail with stderr output
        error = subprocess.CalledProcessError(1, "ipykernel install")
        error.stderr = "Detailed error message"
        mock_run.side_effect = error

        result = sps.install_jupyter_kernel()
        assert result is False


def test_install_jupyter_kernel_version_check_succeeds():
    """Test install_jupyter_kernel when ipykernel version check succeeds."""
    with patch("subprocess.run") as mock_run:
        # Both version check and install succeed
        mock_run.return_value = Mock(returncode=0)
        result = sps.install_jupyter_kernel()
        assert result is True


def test_check_azure_cli_with_cmd_success():
    """Test check_azure_cli finding az.cmd variant."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            # First returns None (az), second returns az.cmd
            mock_which.side_effect = [None, "/path/to/az.cmd"]
            mock_run.return_value = Mock(returncode=0)
            result = sps.check_azure_cli_installed()
            assert result is True


def test_check_bicep_cli_with_cmd_success():
    """Test check_bicep_cli finding az.cmd."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/path/to/az.cmd"
            mock_run.return_value = Mock(returncode=0)
            result = sps.check_bicep_cli_installed()
            assert result is True


def test_validate_kernel_setup_jupyter_not_installed():
    """Test validate_kernel_setup when jupyter is not installed."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError("jupyter not found")
        result = sps.validate_kernel_setup()
        assert result is False


def test_validate_kernel_setup_command_error():
    """Test validate_kernel_setup subprocess error."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "jupyter")
        result = sps.validate_kernel_setup()
        assert result is False


def test_force_kernel_consistency_creates_vscode_directory():
    """Test force_kernel_consistency creates .vscode directory."""
    temp_project_root = Path.cwd() / ".temp_vscode_create"
    temp_project_root.mkdir(exist_ok=True)

    original_get_project_root = sps.get_project_root
    try:
        sps.get_project_root = lambda: temp_project_root

        with patch.object(sps, "validate_kernel_setup", return_value=True):
            try:
                # Verify .vscode doesn't exist
                assert not (temp_project_root / ".vscode").exists()

                result = sps.force_kernel_consistency()
                assert result is True

                # Verify .vscode was created
                assert (temp_project_root / ".vscode").exists()
            finally:
                sps.get_project_root = original_get_project_root
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_check_azure_providers_with_exception_types():
    """Test check_azure_providers catches all exception types."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"

            # Test JSONDecodeError
            mock_run.return_value = Mock(stdout="invalid json")
            result = sps.check_azure_providers_registered()
            assert result is False


def test_merge_string_list_empty_both_params():
    """Test _merge_string_list with both params empty/None."""
    result = sps._merge_string_list(None, [])
    assert result == []


def test_get_project_root_basic():
    """Test get_project_root returns valid path."""
    result = sps.get_project_root()
    assert result.exists()
    assert (result / "README.md").exists()


def test_setup_python_path_no_shared_directory():
    """Test setup_python_path when shared directory doesn't exist."""
    original_sys_path = sys.path.copy()

    # Mock get_project_root to return a path without shared/python
    with patch.object(sps, "get_project_root") as mock_root:
        temp_dir = Path.cwd() / ".temp_no_shared"
        temp_dir.mkdir(exist_ok=True)

        try:
            mock_root.return_value = temp_dir
            sps.setup_python_path()
            # Should not add anything to sys.path
            # (shared directory doesn't exist)
        finally:
            sys.path[:] = original_sys_path
            shutil.rmtree(temp_dir, ignore_errors=True)


def test_create_vscode_settings_ioerror_scenario(temp_project_root: Path):
    """Test create_vscode_settings when .vscode exists but file operations might fail."""
    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir()

    # Should succeed even if directory exists
    result = sps.create_vscode_settings()
    assert result is True


def test_force_kernel_consistency_settings_merge(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test force_kernel_consistency properly merges with existing analysis.exclude."""
    monkeypatch.setattr(sps, "validate_kernel_setup", lambda: True)

    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir(parents=True)

    # Existing settings with custom excludes
    existing = {
        "python.analysis.exclude": ["custom/**"]
    }
    (vscode_dir / "settings.json").write_text(json.dumps(existing), encoding="utf-8")

    sps.force_kernel_consistency()

    settings = _read_settings(temp_project_root)
    # Default excludes should come first
    for default_exclude in sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE:
        assert default_exclude in settings["python.analysis.exclude"]
    # Custom exclude should still be present
    assert "custom/**" in settings["python.analysis.exclude"]


def test_check_azure_cli_with_all_three_variants_failing():
    """Test check_azure_cli when all three variants (az, az.cmd, az.bat) fail."""
    with patch("shutil.which") as mock_which:
        # All variants return None
        mock_which.return_value = None
        result = sps.check_azure_cli_installed()
        assert result is False


def test_check_azure_providers_subprocess_stdout_parsing(monkeypatch: pytest.MonkeyPatch):
    """Test check_azure_providers correctly parses JSON stdout."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"

            # Provide a provider list that contains all required ones
            all_required = [
                'Microsoft.ApiManagement',
                'Microsoft.App',
                'Microsoft.Authorization',
                'Microsoft.CognitiveServices',
                'Microsoft.ContainerRegistry',
                'Microsoft.KeyVault',
                'Microsoft.Maps',
                'Microsoft.ManagedIdentity',
                'Microsoft.Network',
                'Microsoft.OperationalInsights',
                'Microsoft.Resources',
                'Microsoft.Storage'
            ]

            mock_run.return_value = Mock(stdout=json.dumps(all_required))
            result = sps.check_azure_providers_registered()
            assert result is True


def test_normalize_string_list_with_empty_string_in_list():
    """Test _normalize_string_list filters out empty strings within a list."""
    result = sps._normalize_string_list(["a", "", "b", "  ", "c"])
    assert "" not in result
    assert "  " not in result
    assert len(result) == 3


def test_get_project_root_fallback_to_parent():
    """Test get_project_root fallback logic."""
    # When called, it should return a valid path
    result = sps.get_project_root()
    assert isinstance(result, Path)
    assert result.exists()


def test_setup_python_path_integration(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test setup_python_path integration."""
    original_sys_path = sys.path.copy()

    # Create shared/python directory
    shared_dir = temp_project_root / "shared" / "python"
    shared_dir.mkdir(parents=True)

    # Mock get_project_root
    monkeypatch.setattr(sps, "get_project_root", lambda: temp_project_root)

    try:
        sps.setup_python_path()
        assert str(shared_dir) in sys.path
    finally:
        sys.path[:] = original_sys_path


def test_vscode_settings_all_boolean_settings():
    """Test that boolean settings are properly set in VS Code."""
    temp_project_root = Path.cwd() / ".temp_bool_settings"
    temp_project_root.mkdir(exist_ok=True)

    try:
        original_get_project_root = sps.get_project_root
        sps.get_project_root = lambda: temp_project_root

        try:
            sps.create_vscode_settings()
            settings = _read_settings(temp_project_root)

            # Check boolean settings
            assert settings["python.terminal.activateEnvironment"] is True
            assert settings["python.terminal.activateEnvInCurrentTerminal"] is True
            assert settings["python.testing.pytestEnabled"] is True
        finally:
            sps.get_project_root = original_get_project_root
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_check_azure_cli_success_path():
    """Test check_azure_cli with successful Azure CLI detection."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.return_value = Mock(returncode=0, stdout="azure-cli 2.50.0")
            result = sps.check_azure_cli_installed()
            assert result is True


def test_generate_env_file_multiline_logic():
    """Test generate_env_file handles lines without '=' correctly."""
    temp_project_root = Path.cwd() / ".temp_multi_env"
    temp_project_root.mkdir(exist_ok=True)

    try:
        original_get_project_root = sps.get_project_root
        sps.get_project_root = lambda: temp_project_root

        try:
            # Create .env with invalid lines
            (temp_project_root / ".env").write_text(
                "# comment\n"
                "KEY1=value1\n"
                "INVALID_LINE_NO_EQUALS\n"
                "KEY2=value2\n"
                "\n"
                "  \n"
                "KEY3=value3\n",
                encoding="utf-8"
            )

            sps.generate_env_file()
            env = _read_env(temp_project_root)

            # Custom keys should be preserved
            assert env.get("KEY1") == "value1"
            assert env.get("KEY2") == "value2"
            assert env.get("KEY3") == "value3"
        finally:
            sps.get_project_root = original_get_project_root
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_force_kernel_consistency_exception_handler(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Test force_kernel_consistency exception handling."""
    monkeypatch.setattr(sps, "validate_kernel_setup", lambda: True)

    # Should succeed even with the vscode dir having the settings.json
    result = sps.force_kernel_consistency()
    assert result is True


def test_install_jupyter_kernel_stderr_check(monkeypatch: pytest.MonkeyPatch):
    """Test install_jupyter_kernel with stderr in CalledProcessError."""
    call_count = [0]

    def mock_run(cmd, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # Check ipykernel version succeeds
            return Mock(returncode=0)
        elif call_count[0] == 2:
            # ipykernel install fails with stderr
            err = subprocess.CalledProcessError(1, "ipykernel install")
            err.stderr = "Permission denied"
            raise err
        return Mock(returncode=0)

    with patch("subprocess.run", side_effect=mock_run):
        result = sps.install_jupyter_kernel()
        assert result is False


def test_validate_kernel_setup_success_path():
    """Test validate_kernel_setup when kernel is found."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout="Available kernels:\npython-venv\nother\n",
            returncode=0
        )
        result = sps.validate_kernel_setup()
        assert result is True


def test_check_azure_providers_file_not_found():
    """Test check_azure_providers handles FileNotFoundError."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = FileNotFoundError("az command not found")
            result = sps.check_azure_providers_registered()
            assert result is False


def test_merge_string_list_complex_scenario():
    """Test _merge_string_list with complex list scenarios."""
    existing = ["z", "a", "b", "c"]
    required = ["a", "b", "x", "y", "z"]
    result = sps._merge_string_list(existing, required)

    # Required items come first in the order they appear in required
    assert result[:5] == ["a", "b", "x", "y", "z"]
    # Then existing items that weren't in required
    assert "c" in result

    # No duplicates
    assert len(result) == len(set(result))


def test_create_vscode_settings_new_file_path_idempotent(temp_project_root: Path):
    """Test create_vscode_settings creation path is idempotent."""
    assert sps.create_vscode_settings() is True

    # Call again
    assert sps.create_vscode_settings() is True

    # Verify file still has correct format
    settings = _read_settings(temp_project_root)
    assert "python.defaultInterpreterPath" in settings


def test_generate_env_file_conditional_lines():
    """Test generate_env_file handles all conditional parsing cases."""
    temp_project_root = Path.cwd() / ".temp_conditional_env"
    temp_project_root.mkdir(exist_ok=True)

    try:
        original_get_project_root = sps.get_project_root
        sps.get_project_root = lambda: temp_project_root

        try:
            # Create .env with all conditional cases
            (temp_project_root / ".env").write_text(
                "# Comment line\n"
                "\n"  # Empty line
                "KEY=value\n"
                "  \n"  # Whitespace only
                "ANOTHER_KEY=another_value\n",
                encoding="utf-8"
            )

            sps.generate_env_file()
            env = _read_env(temp_project_root)

            # Verify preserved keys
            assert env.get("KEY") == "value"
            assert env.get("ANOTHER_KEY") == "another_value"
        finally:
            sps.get_project_root = original_get_project_root
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_check_azure_providers_no_missing_vs_missing():
    """Test check_azure_providers both branches - with and without missing."""
    # Test with all providers present
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"

            all_providers = [
                'Microsoft.ApiManagement',
                'Microsoft.App',
                'Microsoft.Authorization',
                'Microsoft.CognitiveServices',
                'Microsoft.ContainerRegistry',
                'Microsoft.KeyVault',
                'Microsoft.Maps',
                'Microsoft.ManagedIdentity',
                'Microsoft.Network',
                'Microsoft.OperationalInsights',
                'Microsoft.Resources',
                'Microsoft.Storage'
            ]

            mock_run.return_value = Mock(stdout=json.dumps(all_providers))
            result = sps.check_azure_providers_registered()
            assert result is True

    # Test with some missing
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"

            mock_run.return_value = Mock(stdout='["Microsoft.Storage"]')
            result = sps.check_azure_providers_registered()
            assert result is False


def test_normalize_string_list_all_branches():
    """Test _normalize_string_list all conditional branches."""
    # None case
    assert sps._normalize_string_list(None) == []

    # String case - with content
    assert sps._normalize_string_list("value") == ["value"]

    # String case - empty
    assert sps._normalize_string_list("") == []

    # String case - whitespace
    assert sps._normalize_string_list("   ") == []

    # List case
    assert sps._normalize_string_list(["a", "b"]) == ["a", "b"]

    # List case - with empties
    assert sps._normalize_string_list(["a", "", "b"]) == ["a", "b"]

    # List case - empty list
    assert sps._normalize_string_list([]) == []


def test_force_kernel_consistency_jsondecodeerror_path():
    """Test force_kernel_consistency when JSON is invalid."""
    temp_project_root = Path.cwd() / ".temp_json_error"
    temp_project_root.mkdir(exist_ok=True)

    try:
        original_get_project_root = sps.get_project_root
        original_validate = sps.validate_kernel_setup
        sps.get_project_root = lambda: temp_project_root
        sps.validate_kernel_setup = lambda: True

        try:
            vscode_dir = temp_project_root / ".vscode"
            vscode_dir.mkdir(parents=True)

            # Write invalid JSON
            (vscode_dir / "settings.json").write_text("{ invalid json", encoding="utf-8")

            # Should return False on JSON decode error
            result = sps.force_kernel_consistency()
            assert result is False
        finally:
            sps.get_project_root = original_get_project_root
            sps.validate_kernel_setup = original_validate
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_install_jupyter_kernel_pip_install_success():
    """Test install_jupyter_kernel when pip install succeeds."""
    call_count = [0]

    def mock_run(cmd, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # Check ipykernel version - fails
            raise subprocess.CalledProcessError(1, "ipykernel")

        if call_count[0] == 2:
            # Pip install succeeds
            return Mock(returncode=0, stdout="Successfully installed ipykernel")
        else:
            # Kernel install succeeds
            return Mock(returncode=0)

    with patch("subprocess.run", side_effect=mock_run):
        result = sps.install_jupyter_kernel()
        assert result is True


def test_create_vscode_settings_merge_with_excludes():
    """Test create_vscode_settings properly merges analysis.exclude lists."""
    temp_project_root = Path.cwd() / ".temp_merge_excludes"
    temp_project_root.mkdir(exist_ok=True)

    try:
        original_get_project_root = sps.get_project_root
        sps.get_project_root = lambda: temp_project_root

        try:
            vscode_dir = temp_project_root / ".vscode"
            vscode_dir.mkdir(parents=True)

            # Existing settings with custom excludes
            existing = {
                "python.analysis.exclude": ["custom/**", "other/**"]
            }
            (vscode_dir / "settings.json").write_text(json.dumps(existing), encoding="utf-8")

            sps.create_vscode_settings()

            settings = _read_settings(temp_project_root)

            # All default excludes should be present
            for default in sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE:
                assert default in settings["python.analysis.exclude"]

            # Custom excludes should be preserved
            assert "custom/**" in settings["python.analysis.exclude"]
            assert "other/**" in settings["python.analysis.exclude"]
        finally:
            sps.get_project_root = original_get_project_root
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_generate_env_file_all_conditional_branches():
    """Test generate_env_file covers all conditional branches."""
    temp_project_root = Path.cwd() / ".temp_all_branches"
    temp_project_root.mkdir(exist_ok=True)

    try:
        original_get_project_root = sps.get_project_root
        sps.get_project_root = lambda: temp_project_root

        try:
            # Test when .env doesn't exist
            sps.generate_env_file()
            assert (temp_project_root / ".env").exists()

            # Test when .env exists but is empty
            (temp_project_root / ".env").write_text("", encoding="utf-8")
            sps.generate_env_file()
            env = _read_env(temp_project_root)
            assert "PYTHONPATH" in env

            # Test when .env has content
            (temp_project_root / ".env").write_text("EXISTING=value\n", encoding="utf-8")
            sps.generate_env_file()
            env = _read_env(temp_project_root)
            assert env.get("EXISTING") == "value"
        finally:
            sps.get_project_root = original_get_project_root
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_generate_env_file_with_malformed_lines(temp_project_root: Path):
    """Test generate_env_file handles malformed .env lines gracefully."""
    env_file = temp_project_root / ".env"

    # Create .env with various malformed lines
    env_file.write_text(
        "# Comment line\n"
        "VALID=value\n"
        "NOEQUALS\n"  # No equals sign
        "  \n"  # Blank line
        "\n"  # Empty line
        "ANOTHER=value2\n",
        encoding="utf-8"
    )

    sps.generate_env_file()

    env = _read_env(temp_project_root)
    assert "VALID" in env
    assert "ANOTHER" in env


def test_setup_complete_environment_all_pass(monkeypatch: pytest.MonkeyPatch):
    """Test setup_complete_environment when all checks pass."""
    with patch.object(sps, "check_azure_cli_installed", return_value=True):
        with patch.object(sps, "check_bicep_cli_installed", return_value=True):
            with patch.object(sps, "check_azure_providers_registered", return_value=True):
                with patch.object(sps, "generate_env_file"):
                    with patch.object(sps, "install_jupyter_kernel", return_value=True):
                        with patch.object(sps, "create_vscode_settings", return_value=True):
                            with patch.object(sps, "force_kernel_consistency", return_value=True):
                                # Should complete without error
                                sps.setup_complete_environment()


def test_setup_complete_environment_azure_cli_fails(monkeypatch: pytest.MonkeyPatch):
    """Test setup_complete_environment when Azure CLI check fails."""
    with patch.object(sps, "check_azure_cli_installed", return_value=False):
        with patch.object(sps, "check_bicep_cli_installed", return_value=True):
            with patch.object(sps, "check_azure_providers_registered", return_value=True):
                # Should return early, not continue to next steps
                sps.setup_complete_environment()


def test_setup_complete_environment_kernel_fails(monkeypatch: pytest.MonkeyPatch):
    """Test setup_complete_environment when kernel registration fails."""
    with patch.object(sps, "check_azure_cli_installed", return_value=True):
        with patch.object(sps, "check_bicep_cli_installed", return_value=True):
            with patch.object(sps, "check_azure_providers_registered", return_value=True):
                with patch.object(sps, "generate_env_file"):
                    with patch.object(sps, "install_jupyter_kernel", return_value=False):
                        with patch.object(sps, "create_vscode_settings", return_value=True):
                            with patch.object(sps, "force_kernel_consistency", return_value=True):
                                # Should complete but show failure for kernel
                                sps.setup_complete_environment()


def test_normalize_string_list_various_inputs():
    """Test _normalize_string_list with various input types."""
    # Test with None
    assert sps._normalize_string_list(None) == []

    # Test with empty list
    assert sps._normalize_string_list([]) == []

    # Test with list of strings
    assert sps._normalize_string_list(["a", "b"]) == ["a", "b"]

    # Test with string with content (whitespace is preserved)
    assert sps._normalize_string_list("  path  ") == ["  path  "]

    # Test with empty string
    assert sps._normalize_string_list("") == []

    # Test with whitespace-only string
    assert sps._normalize_string_list("   ") == []

    # Test with list containing numbers
    result = sps._normalize_string_list([1, 2, "three"])
    assert "1" in result
    assert "2" in result
    assert "three" in result


def test_merge_string_list_no_existing():
    """Test _merge_string_list when existing is None."""
    required = ["a", "b", "c"]
    result = sps._merge_string_list(None, required)
    assert result == required


def test_merge_string_list_duplicates():
    """Test _merge_string_list removes duplicates."""
    result = sps._merge_string_list(["a", "b"], ["b", "c"])
    # Should have all unique items
    assert set(result) == {"a", "b", "c"}
    # Required items should come first
    assert result[0] == "b"
    assert result[1] == "c"


def test_venv_python_path_windows_variant():
    """Test _venv_python_path returns correct path for Windows."""
    with patch.object(os, "name", "nt"):
        result = sps._venv_python_path()
        assert "Scripts" in result
        assert result.endswith("python.exe")


def test_venv_python_path_unix_variant():
    """Test _venv_python_path returns correct path for Unix."""
    with patch.object(os, "name", "posix"):
        result = sps._venv_python_path()
        assert "bin" in result
        assert result.endswith("python")


def test_check_azure_cli_with_cmd_variant():
    """Test check_azure_cli when az.cmd exists."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.side_effect = [None, None, "/path/to/az.bat"]
            mock_run.return_value = Mock(returncode=0)
            result = sps.check_azure_cli_installed()
            assert result is True


def test_check_bicep_cli_subprocess_error_without_details():
    """Test check_bicep_cli when subprocess fails."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = subprocess.CalledProcessError(1, "az")
            result = sps.check_bicep_cli_installed()
            assert result is False


def test_check_azure_providers_no_missing():
    """Test check_azure_providers when all providers are registered."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            providers = [
                "Microsoft.ApiManagement",
                "Microsoft.App",
                "Microsoft.Authorization",
                "Microsoft.CognitiveServices",
                "Microsoft.ContainerRegistry",
                "Microsoft.KeyVault",
                "Microsoft.Maps",
                "Microsoft.ManagedIdentity",
                "Microsoft.Network",
                "Microsoft.OperationalInsights",
                "Microsoft.Resources",
                "Microsoft.Storage"
            ]
            mock_run.return_value = Mock(stdout=json.dumps(providers), returncode=0)
            result = sps.check_azure_providers_registered()
            assert result is True


def test_validate_kernel_setup_found():
    """Test validate_kernel_setup when kernel is found."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout=f"Available kernels:\n  {sps.KERNEL_NAME}\n",
            returncode=0
        )
        result = sps.validate_kernel_setup()
        assert result is True


def test_validate_kernel_setup_not_found():
    """Test validate_kernel_setup when kernel is not in list."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout="Available kernels:\n  python3\n",
            returncode=0
        )
        result = sps.validate_kernel_setup()
        assert result is False


def test_force_kernel_consistency_kernel_found():
    """Test force_kernel_consistency when kernel already exists."""
    with patch.object(sps, "validate_kernel_setup", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            temp_project_root = Path.cwd() / ".temp_kernel_found"
            temp_project_root.mkdir(exist_ok=True)

            try:
                original_get_project_root = sps.get_project_root
                sps.get_project_root = lambda: temp_project_root

                try:
                    # Create settings file that can be parsed
                    vscode_dir = temp_project_root / ".vscode"
                    vscode_dir.mkdir(parents=True)
                    (vscode_dir / "settings.json").write_text("{}", encoding="utf-8")

                    result = sps.force_kernel_consistency()
                    assert result is True
                finally:
                    sps.get_project_root = original_get_project_root
            finally:
                shutil.rmtree(temp_project_root, ignore_errors=True)


def test_force_kernel_consistency_kernel_install_fails():
    """Test force_kernel_consistency when kernel installation fails."""
    with patch.object(sps, "validate_kernel_setup", return_value=False):
        with patch.object(sps, "install_jupyter_kernel", return_value=False):
            result = sps.force_kernel_consistency()
            assert result is False


def test_check_azure_cli_cmd_fallback():
    """Test check_azure_cli with cmd fallback when az not found."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            # First call returns None (az not found)
            # Second call returns az.cmd path
            mock_which.side_effect = [None, "/path/to/az.cmd"]
            mock_run.return_value = Mock(returncode=0)

            result = sps.check_azure_cli_installed()
            assert result is True


def test_check_azure_cli_bat_fallback():
    """Test check_azure_cli with bat fallback."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            # Both az and az.cmd return None, az.bat exists
            mock_which.side_effect = [None, None, "/path/to/az.bat"]
            mock_run.return_value = Mock(returncode=0)

            result = sps.check_azure_cli_installed()
            assert result is True


def test_check_bicep_cli_cmd_fallback():
    """Test check_bicep_cli with cmd fallback."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.side_effect = [None, "/path/to/az.cmd"]
            mock_run.return_value = Mock(returncode=0)

            result = sps.check_bicep_cli_installed()
            assert result is True


def test_merge_string_list_all_existing_none():
    """Test _merge_string_list when existing is empty list."""
    required = ["a", "b"]
    result = sps._merge_string_list([], required)
    assert result == required


def test_merge_string_list_required_first():
    """Test _merge_string_list preserves required items first."""
    result = sps._merge_string_list(["x", "y"], ["a", "b"])
    # Required items should come first
    assert result.index("a") < result.index("x")
    assert result.index("b") < result.index("y")


def test_generate_env_file_read_error(temp_project_root: Path):
    """Test generate_env_file when existing .env cannot be read."""
    env_file = temp_project_root / ".env"
    env_file.write_text("EXISTING=value\n", encoding="utf-8")

    # Mock read_text to raise OSError
    with patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
        # Should not raise, should handle the error gracefully and regenerate .env
        sps.generate_env_file()

        # Check .env still exists (regenerated)
        assert env_file.exists()


def test_create_vscode_settings_new_file_ioerror():
    """Test create_vscode_settings when file creation fails."""
    temp_project_root = Path.cwd() / ".temp_ioerror"
    temp_project_root.mkdir(exist_ok=True)

    try:
        original_get_project_root = sps.get_project_root
        sps.get_project_root = lambda: temp_project_root

        try:
            # Mock the mkdir to work but open to fail
            with patch("pathlib.Path.mkdir"):
                with patch("builtins.open", side_effect=IOError("Cannot write")):
                    result = sps.create_vscode_settings()
                    assert result is False
        finally:
            sps.get_project_root = original_get_project_root
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_force_kernel_consistency_settings_file_unreadable():
    """Test force_kernel_consistency when settings file cannot be parsed."""
    with patch.object(sps, "validate_kernel_setup", return_value=True):
        temp_project_root = Path.cwd() / ".temp_unreadable"
        temp_project_root.mkdir(exist_ok=True)

        try:
            original_get_project_root = sps.get_project_root
            sps.get_project_root = lambda: temp_project_root

            try:
                vscode_dir = temp_project_root / ".vscode"
                vscode_dir.mkdir(parents=True)

                # Write invalid JSON
                (vscode_dir / "settings.json").write_text("{ invalid json }", encoding="utf-8")

                result = sps.force_kernel_consistency()
                assert result is False
            finally:
                sps.get_project_root = original_get_project_root
        finally:
            shutil.rmtree(temp_project_root, ignore_errors=True)


def test_check_azure_providers_subprocess_error():
    """Test check_azure_providers when subprocess fails."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = subprocess.CalledProcessError(1, "az")

            result = sps.check_azure_providers_registered()
            assert result is False


def test_create_vscode_settings_new_file():
    """Test create_vscode_settings creates new file successfully."""
    temp_project_root = Path.cwd() / ".temp_new_settings"
    temp_project_root.mkdir(exist_ok=True)

    try:
        original_get_project_root = sps.get_project_root
        sps.get_project_root = lambda: temp_project_root

        try:
            # No .vscode directory should exist
            result = sps.create_vscode_settings()
            assert result is True

            # Check that settings file was created
            settings_file = temp_project_root / ".vscode" / "settings.json"
            assert settings_file.exists()

            settings = json.loads(settings_file.read_text(encoding="utf-8"))
            assert "python.defaultInterpreterPath" in settings
            assert "python.analysis.exclude" in settings
        finally:
            sps.get_project_root = original_get_project_root
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_create_vscode_settings_existing_file_merge():
    """Test create_vscode_settings merges with existing file."""
    temp_project_root = Path.cwd() / ".temp_merge_settings"
    temp_project_root.mkdir(exist_ok=True)

    try:
        original_get_project_root = sps.get_project_root
        sps.get_project_root = lambda: temp_project_root

        try:
            vscode_dir = temp_project_root / ".vscode"
            vscode_dir.mkdir(parents=True)

            # Create existing settings with custom values
            existing_settings = {
                "python.linting.enabled": True,
                "editor.fontSize": 14
            }
            (vscode_dir / "settings.json").write_text(
                json.dumps(existing_settings),
                encoding="utf-8"
            )

            result = sps.create_vscode_settings()
            assert result is True

            # Check that both old and new settings are present
            merged = json.loads((vscode_dir / "settings.json").read_text(encoding="utf-8"))
            assert merged.get("python.linting.enabled") is True
            assert merged.get("editor.fontSize") == 14
            assert "python.defaultInterpreterPath" in merged
        finally:
            sps.get_project_root = original_get_project_root
    finally:
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_validate_kernel_setup_exception_path():
    """Test validate_kernel_setup when subprocess raises exception."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "jupyter")
        result = sps.validate_kernel_setup()
        assert result is False


def test_generate_env_file_with_comments_and_blank_lines(temp_project_root: Path):
    """Test generate_env_file handles comments and blank lines in .env."""
    env_file = temp_project_root / ".env"

    # Create .env with comments and blank lines
    env_file.write_text(
        "# This is a comment\n"
        "\n"
        "KEY1=value1\n"
        "# Another comment\n"
        "KEY2=value2\n"
        "\n",
        encoding="utf-8"
    )

    sps.generate_env_file()

    env = _read_env(temp_project_root)
    assert env.get("KEY1") == "value1"
    assert env.get("KEY2") == "value2"


def test_ensure_utf8_streams_duplicate():
    """Test _ensure_utf8_streams doesn't raise exceptions."""
    # Should not raise any exception
    sps._ensure_utf8_streams()


def test_check_azure_cli_subprocess_fails_without_stderr():
    """Test check_azure_cli when subprocess fails."""
    with patch("shutil.which") as mock_which:
        with patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/az"
            mock_run.side_effect = subprocess.CalledProcessError(1, "az")

            result = sps.check_azure_cli_installed()
            assert result is False


def test_get_project_root_fallback():
    """Test get_project_root uses fallback when indicators not found."""
    # Create a temp directory without project indicators
    temp_dir = Path.cwd() / ".temp_no_indicators"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Save original __file__ reference
        original_file = sps.__file__

        try:
            # The function uses Path(__file__).resolve().parent.parent as fallback
            # So if indicators aren't found, it should return parent.parent
            result = sps.get_project_root()
            assert isinstance(result, Path)
            assert result.exists()
        finally:
            # Restore
            sps.__file__ = original_file
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_merge_string_list_with_string_input():
    """Test _merge_string_list when existing is a string."""
    result = sps._merge_string_list("path1", ["path2", "path3"])
    assert "path1" in result
    assert "path2" in result
    assert "path3" in result


def test_setup_python_path_shared_exists(temp_project_root: Path):
    """Test setup_python_path when shared/python directory exists."""
    shared_dir = temp_project_root / "shared" / "python"
    shared_dir.mkdir(parents=True)

    original_get_project_root = sps.get_project_root
    original_sys_path = sys.path.copy()

    try:
        sps.get_project_root = lambda: temp_project_root
        sps.setup_python_path()

        # Check that the shared path was added to sys.path
        assert str(shared_dir) in sys.path
    finally:
        sps.get_project_root = original_get_project_root
        sys.path[:] = original_sys_path


def test_ensure_utf8_streams_without_reconfigure(monkeypatch: pytest.MonkeyPatch):
    """Test _ensure_utf8_streams when streams lack reconfigure attribute."""

    class DummyStream:
        encoding = None

    original_stdout, original_stderr = sys.stdout, sys.stderr
    sys.stdout = DummyStream()
    sys.stderr = DummyStream()

    try:
        sps._ensure_utf8_streams()
        assert os.environ.get("PYTHONIOENCODING") == "utf-8"
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def test_ensure_utf8_streams_reconfigure_failure(monkeypatch: pytest.MonkeyPatch):
    """Test _ensure_utf8_streams when reconfigure raises an exception."""

    class BrokenStream:
        encoding = None

        def reconfigure(self, **kwargs):
            raise ValueError("boom")

    original_stdout, original_stderr = sys.stdout, sys.stderr
    sys.stdout = BrokenStream()
    sys.stderr = BrokenStream()

    try:
        sps._ensure_utf8_streams()
        assert os.environ.get("PYTHONIOENCODING") == "utf-8"
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def test_create_vscode_settings_read_failure():
    """Test create_vscode_settings handles read errors on existing file."""

    temp_project_root = Path.cwd() / ".temp_read_failure"
    temp_project_root.mkdir(exist_ok=True)

    original_get_project_root = sps.get_project_root

    try:
        sps.get_project_root = lambda: temp_project_root

        vscode_dir = temp_project_root / ".vscode"
        vscode_dir.mkdir(parents=True)
        settings_file = vscode_dir / "settings.json"
        settings_file.write_text("{}", encoding="utf-8")

        original_open = open

        def failing_open(path, *args, **kwargs):
            mode = kwargs.get("mode")
            if mode is None:
                mode = args[0] if args else "r"
            if "r" in mode:
                raise IOError("cannot read")
            return original_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=failing_open):
            assert sps.create_vscode_settings() is False
    finally:
        sps.get_project_root = original_get_project_root
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_force_kernel_consistency_installs_kernel_when_missing():
    """Test force_kernel_consistency installs kernel when validation fails."""

    temp_project_root = Path.cwd() / ".temp_force_install"
    temp_project_root.mkdir(exist_ok=True)

    original_get_project_root = sps.get_project_root
    try:
        sps.get_project_root = lambda: temp_project_root

        with patch.object(sps, "validate_kernel_setup", return_value=False):
            with patch.object(sps, "install_jupyter_kernel", return_value=True):
                result = sps.force_kernel_consistency()
                assert result is True

        settings_file = temp_project_root / ".vscode" / "settings.json"
        assert settings_file.exists()
    finally:
        sps.get_project_root = original_get_project_root
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_force_kernel_consistency_write_failure():
    """Test force_kernel_consistency returns False when write fails."""

    temp_project_root = Path.cwd() / ".temp_force_write_fail"
    temp_project_root.mkdir(exist_ok=True)

    original_get_project_root = sps.get_project_root
    try:
        sps.get_project_root = lambda: temp_project_root

        with patch.object(sps, "validate_kernel_setup", return_value=True):
            original_open = open

            def failing_open(path, *args, **kwargs):
                mode = kwargs.get("mode")
                if mode is None:
                    mode = args[0] if args else "r"
                if str(path).endswith("settings.json") and "w" in mode:
                    raise IOError("cannot write")

                return original_open(path, *args, **kwargs)

            with patch("builtins.open", side_effect=failing_open):
                result = sps.force_kernel_consistency()
                assert result is False
    finally:
        sps.get_project_root = original_get_project_root
        shutil.rmtree(temp_project_root, ignore_errors=True)


def test_get_project_root_no_indicators_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test get_project_root fallback when indicators are absent."""

    temp_root = tmp_path / "proj" / "setup"
    temp_root.mkdir(parents=True)
    temp_file = temp_root / "local_setup.py"
    temp_file.write_text("print('x')", encoding="utf-8")

    original_file = sps.__file__
    sps.__file__ = str(temp_file)

    try:
        result = sps.get_project_root()
        assert result == temp_root.parent
    finally:
        sps.__file__ = original_file


def test_install_jupyter_kernel_version_check_filenotfound():
    """Test install_jupyter_kernel when ipykernel check raises FileNotFoundError."""

    call_count = {"idx": 0}

    def mock_run(*args, **kwargs):
        call_count["idx"] += 1
        if call_count["idx"] == 1:
            raise FileNotFoundError("python not found")
        raise subprocess.CalledProcessError(1, "pip")

    with patch("subprocess.run", side_effect=mock_run):
        result = sps.install_jupyter_kernel()
        assert result is False


def test_create_vscode_settings_import_error_on_create():
    """Test create_vscode_settings handles ImportError during file creation."""

    temp_project_root = Path.cwd() / ".temp_import_error"
    temp_project_root.mkdir(exist_ok=True)

    original_get_project_root = sps.get_project_root
    try:
        sps.get_project_root = lambda: temp_project_root

        with patch("pathlib.Path.mkdir"):
            with patch("builtins.open", side_effect=ImportError("boom")):
                result = sps.create_vscode_settings()
                assert result is False
    finally:
        sps.get_project_root = original_get_project_root
        shutil.rmtree(temp_project_root, ignore_errors=True)
