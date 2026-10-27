"""Opt-in Azure SDK logging overrides for the current Python process only.

Autoreload: reload_unsafe
Restart after edits: wrappers retain references to the original SDK logging methods.
Only logging is changed; HTTP headers, authentication, and transport are untouched.
"""

import importlib
import logging
import os
from functools import wraps
from types import ModuleType
from typing import Any, Callable

_SETTING = 'APIM_SAMPLES_UNMASK_SENSITIVE_HEADERS'


def _enabled() -> bool:
    return os.getenv(_SETTING, 'false').strip().lower() == 'true'


def _optional_module(name: str) -> ModuleType | None:
    """Load an installed SDK, but do not hide missing transitive dependencies."""
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name and (name == error.name or name.startswith(error.name + '.')):
            logging.getLogger(__name__).debug('Optional logging integration not installed: %s', name)
            return None
        raise


def _wrap(owner: Any, name: str, replacement: Callable) -> None:
    """Install each logging wrapper once, preserving its original implementation."""
    original = getattr(owner, name)
    if getattr(original, '_apim_unmasked_logging', False):
        return

    @wraps(original)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if _enabled():
            return replacement(*args, **kwargs)
        return original(*args, **kwargs)

    setattr(wrapped, '_apim_unmasked_logging', True)
    setattr(owner, name, wrapped)


def _raw_value(_policy: Any, _key: str, value: str) -> str:
    return value


def _log_request(logger: logging.Logger, request: Any) -> None:
    """Log the original request without substituting credentials or query values."""
    logger.debug('Request URL: %r', request.url)
    logger.debug('Request method: %r', request.method)
    logger.debug('Request headers:')
    for key, value in request.headers.items():
        logger.debug('    %r: %r', key, value)
    logger.debug('Request body: %r', request.body)


def enable_unmasked_logging() -> None:
    """Override Python SDK redactors, leaving Azure CLI subprocesses unchanged."""
    policies = _optional_module('azure.core.pipeline.policies')
    if policies is not None:
        _wrap(policies.HttpLoggingPolicy, '_redact_header', _raw_value)
        _wrap(policies.HttpLoggingPolicy, '_redact_query_param', _raw_value)

    legacy = _optional_module('msrest.http_logger')
    if legacy is not None:
        _wrap(legacy, 'log_request', lambda _unused, request, *args, **kwargs: _log_request(legacy._LOGGER, request))
