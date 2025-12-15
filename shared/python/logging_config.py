"""APIM Samples logging configuration.

This workspace historically used ad-hoc `print()` and a custom console helper.
This module centralizes standard-library logging configuration so that:
- log level can be controlled via environment configuration
- logging remains consistent across scripts, notebooks, and tests

Configuration is intentionally simple: a single stream handler with a formatter
that prints only the message text. Levels are still applied for filtering.
"""

from __future__ import annotations

import logging
import logging.config
import os
import threading
from pathlib import Path
from typing import Final

try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    load_dotenv = None


_LOG_LEVEL_ENV: Final[str] = 'APIM_SAMPLES_LOG_LEVEL'
_DEFAULT_LEVEL: Final[str] = 'INFO'

_ENV_FILE_NAME: Final[str] = '.env'

_config_lock = threading.Lock()
_state: dict[str, bool] = {'configured': False, 'dotenv_loaded': False}


def _find_env_file() -> Path | None:
    """Return the most likely .env file path for this repo, if it exists.

    We prioritize an explicit PROJECT_ROOT, then the current working directory,
    then a path derived from this module's location (shared/python -> repo root).
    """

    candidates: list[Path] = []

    project_root_env = os.getenv('PROJECT_ROOT')
    if project_root_env:
        candidates.append(Path(project_root_env) / _ENV_FILE_NAME)

    candidates.append(Path.cwd() / _ENV_FILE_NAME)

    # shared/python/logging_config.py -> shared/python -> shared -> repo root
    candidates.append(Path(__file__).resolve().parents[2] / _ENV_FILE_NAME)

    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue

    return None


def _load_dotenv_once() -> None:
    """Load environment variables from .env (if available), once per process."""

    with _config_lock:
        if _state['dotenv_loaded']:
            return

        _state['dotenv_loaded'] = True

    if load_dotenv is None:
        return

    env_path = _find_env_file()
    if not env_path:
        return

    # Do not override already-set env vars.
    load_dotenv(dotenv_path=env_path, override=False)


def _normalize_level_name(value: str | None) -> str:
    if not value:
        return _DEFAULT_LEVEL

    normalized = value.strip().upper()

    # Common aliases
    aliases = {
        'WARN': 'WARNING',
        'FATAL': 'CRITICAL',
    }

    normalized = aliases.get(normalized, normalized)

    if normalized not in {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}:
        return _DEFAULT_LEVEL

    return normalized


def get_configured_level_name() -> str:
    """Return the configured level name from env (normalized)."""
    _load_dotenv_once()
    return _normalize_level_name(os.getenv(_LOG_LEVEL_ENV))


def configure_logging(*, level: str | None = None, force: bool = False) -> None:
    """Configure process-wide logging.

    Args:
        level: Optional level override. If omitted, reads `APIM_SAMPLES_LOG_LEVEL`.
        force: If True, reconfigures logging even if already configured.
    """

    level_name = _normalize_level_name(level) if level is not None else get_configured_level_name()

    with _config_lock:
        root_logger = logging.getLogger()

        if _state['configured'] and not force:
            root_logger.setLevel(level_name)
            return

        # If something already configured logging, do not clobber handlers unless force=True.
        if root_logger.handlers and not force:
            root_logger.setLevel(level_name)
            _state['configured'] = True
            return

        logging.config.dictConfig(
            {
                'version': 1,
                'disable_existing_loggers': False,
                'formatters': {
                    'message_only': {
                        'format': '%(message)s',
                    }
                },
                'handlers': {
                    'console': {
                        'class': 'logging.StreamHandler',
                        'formatter': 'message_only',
                        'level': 'DEBUG',
                        'stream': 'ext://sys.stderr',
                    }
                },
                'root': {
                    'handlers': ['console'],
                    'level': level_name,
                },
            }
        )

        _state['configured'] = True


def ensure_configured() -> None:
    """Ensure logging is configured (idempotent)."""

    configure_logging(force=False)


def is_debug_enabled(logger: logging.Logger | None = None) -> bool:
    """Return True if DEBUG is enabled for the given logger (or root)."""

    target = logger if logger is not None else logging.getLogger()
    return target.isEnabledFor(logging.DEBUG)
