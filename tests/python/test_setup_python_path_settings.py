"""Unit tests for setup_python_path VS Code settings generation."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, cast

import pytest

# Ensure the setup folder is on sys.path so the setup script is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / "setup"
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

if TYPE_CHECKING:  # pragma: no cover
    sps = cast(ModuleType, None)
else:
    sps = cast(ModuleType, importlib.import_module("setup_python_path"))


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


def test_create_vscode_settings_creates_perf_excludes(temp_project_root: Path) -> None:
    assert sps.create_vscode_settings() is True

    settings = _read_settings(temp_project_root)

    assert settings["search.exclude"]["**/.venv"] is True
    assert settings["search.exclude"]["**/.venv/**"] is True
    assert settings["files.watcherExclude"]["**/.venv/**"] is True
    assert settings["files.exclude"]["**/.venv"] is True

    assert settings["python.analysis.exclude"][: len(sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE)] == sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE


def test_create_vscode_settings_merges_excludes(temp_project_root: Path) -> None:
    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir(parents=True)

    (vscode_dir / "settings.json").write_text(
        json.dumps(
            {
                "search.exclude": {"custom/**": True, "**/.venv": False},
                "python.analysis.exclude": ["custom2/**", "**/__pycache__"],
            },
            indent=4,
        ),
        encoding="utf-8",
    )

    assert sps.create_vscode_settings() is True

    settings = _read_settings(temp_project_root)

    # Required keys forced on, custom preserved
    assert settings["search.exclude"]["custom/**"] is True
    assert settings["search.exclude"]["**/.venv"] is True
    assert settings["search.exclude"]["**/.venv/**"] is True

    # Required patterns come first, custom patterns preserved afterwards
    assert settings["python.analysis.exclude"][: len(sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE)] == sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE
    assert "custom2/**" in settings["python.analysis.exclude"]


def test_force_kernel_consistency_merges_excludes(temp_project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vscode_dir = temp_project_root / ".vscode"
    vscode_dir.mkdir(parents=True)

    (vscode_dir / "settings.json").write_text(
        json.dumps(
            {
                "search.exclude": {"**/.venv/**": False},
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

    assert settings["search.exclude"]["**/.venv"] is True
    assert settings["search.exclude"]["**/.venv/**"] is True
    assert settings["files.watcherExclude"]["**/.venv/**"] is True
    assert settings["files.watcherExclude"]["other/**"] is True

    assert settings["python.analysis.exclude"][: len(sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE)] == sps.DEFAULT_PYTHON_ANALYSIS_EXCLUDE
    assert "custom3/**" in settings["python.analysis.exclude"]


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
