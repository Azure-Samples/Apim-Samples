"""Tests for logging_config module."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import Mock

import pytest

# APIM Samples imports
import logging_config


@pytest.fixture(autouse=True)
def _reset_logging_config_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset logging state between tests to avoid cross-test interference."""

    logging_config._state['configured'] = False
    logging_config._state['dotenv_loaded'] = False
    logging_config._state['warnings_configured'] = False

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Remove env vars we commonly set in tests.
    monkeypatch.delenv('APIM_SAMPLES_LOG_LEVEL', raising=False)
    monkeypatch.delenv('PROJECT_ROOT', raising=False)


def test_normalize_level_name_defaults_to_info() -> None:
    assert logging_config._normalize_level_name(None) == 'INFO'
    assert logging_config._normalize_level_name('') == 'INFO'


def test_normalize_level_name_aliases_and_invalid_values() -> None:
    assert logging_config._normalize_level_name('warn') == 'WARNING'
    assert logging_config._normalize_level_name('fatal') == 'CRITICAL'
    assert logging_config._normalize_level_name('verbose') == 'INFO'


def test_find_env_file_prefers_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    (project_root / '.env').write_text('APIM_SAMPLES_LOG_LEVEL=DEBUG\n', encoding='utf-8')

    monkeypatch.setenv('PROJECT_ROOT', str(project_root))

    found = logging_config._find_env_file()

    assert found == project_root / '.env'


def test_load_dotenv_once_calls_loader_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / '.env').write_text('APIM_SAMPLES_LOG_LEVEL=DEBUG\n', encoding='utf-8')
    monkeypatch.chdir(tmp_path)

    mock_loader = Mock()
    monkeypatch.setattr(logging_config, 'load_dotenv', mock_loader)

    logging_config._load_dotenv_once()
    logging_config._load_dotenv_once()

    mock_loader.assert_called_once()
    assert mock_loader.call_args.kwargs.get('override') is False


def test_configure_logging_does_not_clobber_existing_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    root_logger = logging.getLogger()
    existing = logging.StreamHandler()
    root_logger.addHandler(existing)

    handlers_before = list(root_logger.handlers)

    logging_config.configure_logging(level='WARNING', force=False)

    assert existing in root_logger.handlers
    # Pytest's logging capture can attach additional handlers; we only verify that
    # logging_config didn't remove or replace any of the existing handlers.
    assert list(root_logger.handlers) == handlers_before
    assert root_logger.level == logging.WARNING


@pytest.mark.parametrize(
    ('level', 'expected'),
    [
        ('INFO', False),
        ('ERROR', True),
        ('DEBUG', True),
        ('WARNING', False),
    ],
)
def test_should_print_traceback_from_env(level: str, expected: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('APIM_SAMPLES_LOG_LEVEL', level)

    assert logging_config.should_print_traceback() is expected
