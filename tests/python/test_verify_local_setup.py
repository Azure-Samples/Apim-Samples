"""Unit tests for verify_local_setup script."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, TYPE_CHECKING, cast

import pytest

# Ensure the setup folder is on sys.path so the verification script is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / "setup"
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

if TYPE_CHECKING:  # pragma: no cover - placeholder for type inference
    vls = cast(ModuleType, None)
else:
    vls = cast(ModuleType, importlib.import_module("verify_local_setup"))


# ------------------------------
#    FIXTURES
# ------------------------------

@pytest.fixture
def temp_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Temporarily override Path.cwd to return tmp_path."""

    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    return tmp_path


# ------------------------------
#    TESTS
# ------------------------------


def test_check_virtual_environment_success(temp_cwd: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Virtual environment check should pass when .venv exists and python resides inside it."""

    scripts_dir = temp_cwd / ".venv" / ("Scripts" if sys.platform.startswith("win") else "bin")
    scripts_dir.mkdir(parents=True)
    venv_python = scripts_dir / "python"
    venv_python.write_text("#!/usr/bin/env python")

    monkeypatch.setattr(sys, "executable", str(venv_python))

    assert vls.check_virtual_environment() is True


def test_check_required_packages_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Package check should return False when any dependency fails to import."""

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "dotenv":
            raise ImportError("dotenv missing")

        # Return a lightweight placeholder for expected modules.
        return SimpleNamespace(__name__=name)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert vls.check_required_packages() is False


def test_check_vscode_settings_success(temp_cwd: Path) -> None:
    """VS Code settings check should succeed when required keys are present."""

    settings_dir = temp_cwd / ".vscode"
    settings_dir.mkdir(parents=True)
    (settings_dir / "settings.json").write_text(
        '{\n'
        '  "jupyter.defaultKernel": "apim-samples",\n'
        '  "python.defaultInterpreterPath": ".venv/",\n'
        '  "notebook.defaultLanguage": "python"\n'
        '}\n',
        encoding="utf-8",
    )

    assert vls.check_vscode_settings() is True


def test_check_env_file_validation(temp_cwd: Path) -> None:
    """Environment file check should validate required keys."""

    env_path = temp_cwd / ".env"
    env_path.write_text("PYTHONPATH=/tmp\nPROJECT_ROOT=/repo\n", encoding="utf-8")

    assert vls.check_env_file() is True


def test_check_env_file_missing_key(temp_cwd: Path) -> None:
    """Environment file check should fail when keys are missing."""

    env_path = temp_cwd / ".env"
    env_path.write_text("PYTHONPATH=/tmp\n", encoding="utf-8")

    assert vls.check_env_file() is False
