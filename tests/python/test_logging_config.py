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


def test_configure_logging_with_force_reconfigures(monkeypatch: pytest.MonkeyPatch) -> None:
    logging_config.configure_logging(level='INFO')
    assert logging_config._state['configured'] is True

    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO

    logging_config.configure_logging(level='DEBUG', force=True)
    assert root_logger.level == logging.DEBUG


def test_configure_logging_no_force_updates_level_only(monkeypatch: pytest.MonkeyPatch) -> None:
    logging_config.configure_logging(level='INFO')
    handler_count = len(logging.getLogger().handlers)

    logging_config.configure_logging(level='WARNING')
    assert logging.getLogger().level == logging.WARNING
    assert len(logging.getLogger().handlers) == handler_count


def test_is_debug_enabled_with_custom_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    logging_config.configure_logging(level='DEBUG')
    custom_logger = logging.getLogger('test_logger')
    custom_logger.setLevel(logging.INFO)

    assert logging_config.is_debug_enabled(custom_logger) is False
    assert logging_config.is_debug_enabled() is True


def test_is_debug_enabled_with_none_uses_root(monkeypatch: pytest.MonkeyPatch) -> None:
    logging_config.configure_logging(level='DEBUG')
    assert logging_config.is_debug_enabled(None) is True

    logging_config.configure_logging(level='INFO', force=True)
    assert logging_config.is_debug_enabled(None) is False


def test_find_env_file_returns_none_when_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Create a fresh directory that definitely has no .env
    empty_dir = tmp_path / 'empty'
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)
    monkeypatch.delenv('PROJECT_ROOT', raising=False)

    # Mock __file__ to point to a location without .env
    fake_module = empty_dir / 'shared' / 'python' / 'logging_config.py'
    fake_module.parent.mkdir(parents=True)
    monkeypatch.setattr(logging_config, '__file__', str(fake_module))

    found = logging_config._find_env_file()
    assert found is None


def test_load_dotenv_once_skips_when_no_dotenv_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(logging_config, 'load_dotenv', None)

    logging_config._state['dotenv_loaded'] = False
    logging_config._load_dotenv_once()

    assert logging_config._state['dotenv_loaded'] is True


def test_load_dotenv_once_returns_early_when_no_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that _load_dotenv_once returns early when no .env file is found."""

    # Create an empty directory with no .env file
    empty_dir = tmp_path / 'empty'
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)
    monkeypatch.delenv('PROJECT_ROOT', raising=False)

    # Mock __file__ to point to a location without .env
    fake_module = empty_dir / 'shared' / 'python' / 'logging_config.py'
    fake_module.parent.mkdir(parents=True)
    monkeypatch.setattr(logging_config, '__file__', str(fake_module))

    # Create a mock for load_dotenv to verify it's NOT called
    mock_load_dotenv = Mock()
    monkeypatch.setattr(logging_config, 'load_dotenv', mock_load_dotenv)

    logging_config._state['dotenv_loaded'] = False
    logging_config._load_dotenv_once()

    # load_dotenv should NOT have been called since no .env file exists
    mock_load_dotenv.assert_not_called()
    assert logging_config._state['dotenv_loaded'] is True


def test_get_configured_level_name_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('APIM_SAMPLES_LOG_LEVEL', 'ERROR')

    assert logging_config.get_configured_level_name() == 'ERROR'


def test_get_configured_level_name_defaults_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('APIM_SAMPLES_LOG_LEVEL', raising=False)

    assert logging_config.get_configured_level_name() == 'INFO'


def test_normalize_level_name_strips_whitespace() -> None:
    assert logging_config._normalize_level_name('  DEBUG  ') == 'DEBUG'


def test_normalize_level_name_accepts_all_valid_levels() -> None:
    for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        assert logging_config._normalize_level_name(level) == level
        assert logging_config._normalize_level_name(level.lower()) == level


def test_configure_logging_uses_override_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('APIM_SAMPLES_LOG_LEVEL', 'INFO')

    logging_config.configure_logging(level='DEBUG')

    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_uses_env_when_no_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('APIM_SAMPLES_LOG_LEVEL', 'ERROR')

    logging_config.configure_logging()

    assert logging.getLogger().level == logging.ERROR


def test_find_env_file_checks_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / '.env').write_text('APIM_SAMPLES_LOG_LEVEL=DEBUG\n', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('PROJECT_ROOT', raising=False)

    found = logging_config._find_env_file()

    assert found == tmp_path / '.env'


def test_find_env_file_checks_module_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock __file__ to point to tmp_path/shared/python/logging_config.py
    fake_module_path = tmp_path / 'shared' / 'python' / 'logging_config.py'
    fake_module_path.parent.mkdir(parents=True)
    fake_module_path.write_text('# fake', encoding='utf-8')

    (tmp_path / '.env').write_text('APIM_SAMPLES_LOG_LEVEL=DEBUG\n', encoding='utf-8')

    # Create the 'other' directory so chdir works
    other_dir = tmp_path / 'other'
    other_dir.mkdir()

    monkeypatch.setattr(logging_config, '__file__', str(fake_module_path))
    monkeypatch.chdir(other_dir)
    monkeypatch.delenv('PROJECT_ROOT', raising=False)

    found = logging_config._find_env_file()

    assert found == tmp_path / '.env'


def test_find_env_file_handles_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that _find_env_file handles OSError when checking if a path is a file."""

    # Create a valid .env file that will be found after the OSError
    (tmp_path / '.env').write_text('APIM_SAMPLES_LOG_LEVEL=DEBUG\n', encoding='utf-8')
    monkeypatch.chdir(tmp_path)

    # Mock Path.is_file to raise OSError on first call, then work normally
    original_is_file = Path.is_file
    call_count = [0]

    def mock_is_file(self: Path) -> bool:
        call_count[0] += 1
        if call_count[0] == 1:
            raise OSError('Permission denied')
        return original_is_file(self)

    monkeypatch.setattr(Path, 'is_file', mock_is_file)

    # Set PROJECT_ROOT to trigger checking a candidate that will raise OSError
    monkeypatch.setenv('PROJECT_ROOT', str(tmp_path / 'inaccessible'))

    found = logging_config._find_env_file()

    # Should still find the .env in cwd (second candidate)
    assert found == tmp_path / '.env'
