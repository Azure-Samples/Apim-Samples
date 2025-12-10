"""
Console output utilities for APIM samples.

This module provides formatted console output functions with ANSI color support,
thread-safe printing for parallel operations, and consistent message formatting.
"""

import datetime
import textwrap
import threading


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

CONSOLE_WIDTH = 175

# Thread-safe print lock
_print_lock = threading.Lock()


# ------------------------------
#    PRIVATE METHODS
# ------------------------------

def _print_log(message: str, prefix: str = '', color: str = '', output: str = '', duration: str = '', show_time: bool = False, blank_above: bool = False, blank_below: bool = False, wrap_lines: bool = False) -> None:
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
    time_str    = f' ⌚ {datetime.datetime.now().time()}' if show_time else ''
    output_str  = f' {output}' if output else ''

    if blank_above:
        print()

    # To preserve explicit newlines in the message (e.g., from print_val with val_below=True),
    # split the message on actual newlines and wrap each line separately, preserving blank lines and indentation.
    full_message = f'{prefix}{color}{message}{RESET}{time_str} {duration}{output_str}'
    lines = full_message.splitlines(keepends = False)

    for line in lines:
        if wrap_lines:
            wrapped = textwrap.fill(line, width = CONSOLE_WIDTH)
            print(wrapped)
        else:
            print(line)

    if blank_below:
        print()


# ------------------------------
#    PUBLIC METHODS
# ------------------------------

def print_command(cmd: str = '') -> None:
    """Print a command message."""
    _print_log(cmd, '⚙️ ', BOLD_B)


def print_error(msg: str, output: str = '', duration: str = '') -> None:
    """Print an error message."""
    _print_log(msg, '⛔ ', BOLD_R, output, duration, True)


def print_info(msg: str, blank_above: bool = False) -> None:
    """Print an informational message."""
    _print_log(msg, '👉🏽 ', BOLD_B, blank_above = blank_above)


def print_message(msg: str, output: str = '', duration: str = '', blank_above: bool = False) -> None:
    """Print a general message."""
    _print_log(msg, 'ℹ️ ', BOLD_G, output, duration, True, blank_above)


def print_ok(msg: str, output: str = '', duration: str = '', blank_above: bool = True) -> None:
    """Print an OK/success message."""
    _print_log(msg, '✅ ', BOLD_G, output, duration, True, blank_above)


def print_success(msg: str, output: str = '', duration: str = '', blank_above: bool = False) -> None:
    """Print a success message."""
    _print_log(msg, '✅ ', BOLD_G, output, duration, True, blank_above)


def print_warning(msg: str, output: str = '', duration: str = '') -> None:
    """Print a warning message."""
    _print_log(msg, '⚠️ ', BOLD_Y, output, duration, True)


def print_val(name: str, value: str, val_below: bool = False) -> None:
    """Print a key-value pair."""
    _print_log(f"{name:<25}:{'\n' if val_below else ' '}{value}", '👉🏽 ', BOLD_B)


def print_header(msg: str) -> None:
    """Print a header message."""
    _print_log(f"\n{'=' * len(msg)}\n{msg}\n{'=' * len(msg)}", '', BOLD_G, blank_above=True, blank_below=True)
