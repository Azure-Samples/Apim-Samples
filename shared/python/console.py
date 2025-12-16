"""Console output utilities for APIM samples.

Historically, this repo used `print()` plus a small helper layer for consistent
console output. This module keeps that public API, but now emits messages via
standard-library `logging` so that output can be filtered/configured by log
level.
"""

from __future__ import annotations

import datetime
import logging
import os
import textwrap
import threading

from logging_config import configure_logging
configure_logging()

# ------------------------------
#    CONSTANTS
# ------------------------------

# ANSI escape code constants for colored console output
BOLD_B = '\x1b[1;34m'   # blue
BOLD_G = '\x1b[1;32m'   # green
BOLD_R = '\x1b[1;31m'   # red
BOLD_Y = '\x1b[1;33m'   # yellow
BOLD_C = '\x1b[1;36m'   # cyan
BOLD_M = '\x1b[1;35m'   # magenta
BOLD_W = '\x1b[1;37m'   # white
RESET  = '\x1b[0m'

# Thread colors for parallel operations
THREAD_COLORS = [BOLD_B, BOLD_G, BOLD_Y, BOLD_C, BOLD_M, BOLD_W]

CONSOLE_WIDTH = 220

_CONSOLE_WIDTH_ENV = 'APIM_SAMPLES_CONSOLE_WIDTH'
_DEFAULT_CONSOLE_WIDTH = 220

# Thread-safe print lock
_print_lock = threading.Lock()

_logger = logging.getLogger(__name__)

# ------------------------------
#    PRIVATE METHODS
# ------------------------------

def _get_console_width() -> int:
    """Return configured console width for line wrapping."""

    raw = os.getenv(_CONSOLE_WIDTH_ENV)
    if not raw:
        return _DEFAULT_CONSOLE_WIDTH
    try:
        value = int(raw)
        return value if value > 20 else _DEFAULT_CONSOLE_WIDTH
    except ValueError:
        return _DEFAULT_CONSOLE_WIDTH

def _infer_level_from_message(message: str, default: int = logging.INFO) -> int:
    stripped = message.lstrip()
    if not stripped:
        return default

    # Heuristic mappings for existing emoji/prefix styles.
    if stripped.startswith('❌'):
        return logging.ERROR
    if stripped.startswith('⚠️'):
        return logging.WARNING
    if stripped.startswith(('✅', '🎉')):
        return logging.INFO
    if stripped.lower().startswith('debug') or stripped.startswith(('🐞')):
        return logging.DEBUG

    lowered = stripped.lower()
    if lowered.startswith('error:'):
        return logging.ERROR
    if lowered.startswith('warning:'):
        return logging.WARNING
    if lowered.startswith('command output:'):
        return logging.DEBUG

    # Default
    return default

def _wrap_line(line: str, width: int) -> str:
    if not line or width <= 0:
        return line

    # Preserve leading whitespace for tables/indented output.
    leading_len = len(line) - len(line.lstrip(' '))
    leading = line[:leading_len]
    content = line[leading_len:]
    if not content:
        return line

    return textwrap.fill(
        content,
        width=width,
        initial_indent=leading,
        subsequent_indent=leading,
        break_long_words=False,
        break_on_hyphens=False,
    )

def _print_log(message: str, prefix: str = '', color: str = '', output: str = '', duration: str = '', show_time: bool = False, blank_above: bool = False, blank_below: bool = False, wrap_lines: bool = False, level: int | None = None) -> None:
    """
    Print a formatted log message with optional prefix, color, output, duration, and time.
    Handles blank lines above and below the message for readability.

    Args:
        message (str): The message to print.
        prefix (str, optional): Prefix for the message.
        color (str, optional): ANSI color code.
        output (str, optional): Additional output to append.
        duration (str, optional): Duration string to append.
        show_time (bool, optional): Whether to show the current time.
        blank_above (bool, optional): Whether to print a blank line above.
        blank_below (bool, optional): Whether to print a blank line below.
        wrap_lines (bool, optional): Whether to wrap lines to fit console width.
    """

    time_str = f' ⌚ {datetime.datetime.now().time()}' if show_time else ''
    output_str = f' {output}' if output else ''

    resolved_level = level if level is not None else _infer_level_from_message(message)

    if blank_above:
        _logger.log(resolved_level, '')

    # To preserve explicit newlines in the message (e.g., from print_val with val_below=True),
    # split the message on actual newlines and wrap each line separately, preserving blank lines and indentation.
    full_message = f'{prefix}{color}{message}{RESET}{time_str} {duration}{output_str}'.rstrip()
    lines = full_message.splitlines(keepends = False)

    width = _get_console_width()

    for line in lines:
        if wrap_lines:
            wrapped = _wrap_line(line, width)
            for wrapped_line in wrapped.splitlines() or ['']:
                _logger.log(resolved_level, wrapped_line)
        else:
            _logger.log(resolved_level, line)

    if blank_below:
        _logger.log(resolved_level, '')


# ------------------------------
#    PUBLIC METHODS
# ------------------------------

def print_command(cmd: str = '') -> None:
    """Print a command message."""
    _print_log(cmd, '⚙️ ', BOLD_B, blank_above = True, blank_below = True, level = logging.INFO)

def print_error(msg: str, output: str = '', duration: str = '') -> None:
    """Print an error message."""
    _print_log(msg, '❌ ', BOLD_R, output, duration, True, True, True, wrap_lines = True, level = logging.ERROR)

def print_info(msg: str, blank_above: bool = False) -> None:
    """Print an informational message."""
    _print_log(msg, 'ℹ️ ', BOLD_B, blank_above = blank_above, level = logging.INFO)

def print_message(msg: str, output: str = '', duration: str = '', blank_above: bool = False, blank_below: bool = False) -> None:
    """Print a general message."""
    _print_log(msg, 'ℹ️ ', BOLD_G, output, duration, True, blank_above, blank_below, level = logging.INFO)

def print_ok(msg: str, output: str = '', duration: str = '', blank_above: bool = False) -> None:
    """Print an OK/success message."""
    _print_log(msg, '✅ ', BOLD_G, output, duration, True, blank_above, level = logging.INFO)

def print_warning(msg: str, output: str = '', duration: str = '') -> None:
    """Print a warning message."""
    _print_log(msg, '⚠️ ', BOLD_Y, output, duration, True, wrap_lines = True, level = logging.WARNING)

def print_val(name: str, value: str, val_below: bool = False) -> None:
    """Print a key-value pair."""
    _print_log(f"{name:<25}:{'\n' if val_below else ' '}{value}", '👉🏽 ', BOLD_B, wrap_lines = True, level = logging.INFO)

def print_plain(msg: str = '', *, level: int | None = None, wrap_lines: bool = True, blank_above: bool = False, blank_below: bool = False) -> None:
    """Log a message without any icon/prefix.

    Useful for tables, separators, and other formatted output where adding an
    icon would be distracting.
    """

    resolved_level = level if level is not None else _infer_level_from_message(msg, default=logging.INFO)
    _print_log(msg, prefix='', color = '', blank_above = blank_above, blank_below=blank_below, wrap_lines = wrap_lines, level = resolved_level)

def print_debug(msg: str = '', *, wrap_lines: bool = True, blank_above: bool = False, blank_below: bool = False) -> None:
    """Log a debug message."""

    _print_log(msg, prefix='🐞 ', color = '', blank_above = blank_above, blank_below=blank_below, wrap_lines = wrap_lines, level = logging.DEBUG)
