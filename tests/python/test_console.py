"""Unit tests for the console module."""

import logging
import threading

import console

# APIM Samples imports
from test_helpers import capture_console_output as capture_output


# ------------------------------
#    CONSTANTS TESTS
# ------------------------------

def test_ansi_color_constants():
    """Test that all ANSI color constants are properly defined."""
    assert console.BOLD_B == '\x1b[1;34m'
    assert console.BOLD_G == '\x1b[1;32m'
    assert console.BOLD_R == '\x1b[1;31m'
    assert console.BOLD_Y == '\x1b[1;33m'
    assert console.BOLD_C == '\x1b[1;36m'
    assert console.BOLD_M == '\x1b[1;35m'
    assert console.BOLD_W == '\x1b[1;37m'
    assert console.RESET == '\x1b[0m'


def test_thread_colors_list():
    """Test that thread colors list contains expected values."""
    assert len(console.THREAD_COLORS) == 6
    assert console.BOLD_B in console.THREAD_COLORS
    assert console.BOLD_G in console.THREAD_COLORS
    assert console.BOLD_Y in console.THREAD_COLORS


def test_console_width():
    """Test that console width is set to expected value."""
    assert console.CONSOLE_WIDTH == 220


def test_print_lock_exists():
    """Test that the print lock is properly initialized."""
    assert isinstance(console._print_lock, type(threading.Lock()))


# ------------------------------
#    print_command TESTS
# ------------------------------

def test_print_command_basic():
    """Test print_command with basic message."""
    output = capture_output(console.print_command, 'az login')
    assert '⚙️' in output
    assert 'az login' in output
    assert console.BOLD_B in output
    assert console.RESET in output


def test_print_command_empty():
    """Test print_command with empty string."""
    output = capture_output(console.print_command, '')
    assert '⚙️' in output


def test_print_command_multiline():
    """Test print_command with multiline message."""
    output = capture_output(console.print_command, 'line1\nline2\nline3')
    assert 'line1' in output
    assert 'line2' in output
    assert 'line3' in output


# ------------------------------
#    print_error TESTS
# ------------------------------

def test_print_error_basic():
    """Test print_error with basic message."""
    output = capture_output(console.print_error, 'Error occurred')
    assert '❌' in output
    assert 'Error occurred' in output
    assert console.BOLD_R in output
    assert '⌚' in output  # time should be shown


def test_print_error_with_output():
    """Test print_error with additional output."""
    output = capture_output(console.print_error, 'Failed', output='exit code 1')
    assert 'Failed' in output
    assert 'exit code 1' in output


def test_print_error_with_duration():
    """Test print_error with duration."""
    output = capture_output(console.print_error, 'Timeout', duration='30s')
    assert 'Timeout' in output
    assert '30s' in output


def test_print_error_with_all_options():
    """Test print_error with all optional parameters."""
    output = capture_output(console.print_error, 'Complete failure', output='details', duration='5s')
    assert 'Complete failure' in output
    assert 'details' in output
    assert '5s' in output


# ------------------------------
#    print_info TESTS
# ------------------------------

def test_print_info_basic():
    """Test print_info with basic message."""
    output = capture_output(console.print_info, 'Information message')
    assert 'ℹ️' in output
    assert 'Information message' in output
    assert console.BOLD_B in output


def test_print_info_blank_above():
    """Test print_info with blank line above."""
    output = capture_output(console.print_info, 'Info', blank_above=True)
    lines = output.split('\n')
    assert not lines[0]  # First line should be blank
    assert 'Info' in output


def test_print_info_no_blank_above():
    """Test print_info without blank line above (default)."""
    output = capture_output(console.print_info, 'Info')
    assert not output.startswith('\n')


# ------------------------------
#    print_message TESTS
# ------------------------------

def test_print_message_basic():
    """Test print_message with basic message."""
    output = capture_output(console.print_message, 'General message')
    assert 'ℹ️' in output
    assert 'General message' in output
    assert console.BOLD_G in output
    assert '⌚' in output


def test_print_message_with_output():
    """Test print_message with additional output."""
    output = capture_output(console.print_message, 'Processing', output='success')
    assert 'Processing' in output
    assert 'success' in output


def test_print_message_with_duration():
    """Test print_message with duration."""
    output = capture_output(console.print_message, 'Completed', duration='2.5s')
    assert 'Completed' in output
    assert '2.5s' in output


def test_print_message_blank_above():
    """Test print_message with blank line above."""
    output = capture_output(console.print_message, 'Message', blank_above=True)
    lines = output.split('\n')
    assert not lines[0]


# ------------------------------
#    print_ok TESTS
# ------------------------------

def test_print_ok_basic():
    """Test print_ok with basic message."""
    output = capture_output(console.print_ok, 'Operation successful')
    assert '✅' in output
    assert 'Operation successful' in output
    assert console.BOLD_G in output
    assert '⌚' in output


def test_print_ok_default_blank_above():
    """Test print_ok has no blank line above by default."""
    output = capture_output(console.print_ok, 'OK')
    assert not output.startswith('\n')


def test_print_ok_no_blank_above():
    """Test print_ok without blank line above."""
    output = capture_output(console.print_ok, 'OK', blank_above=False)
    assert not output.startswith('\n')


def test_print_ok_with_output_and_duration():
    """Test print_ok with all options."""
    output = capture_output(console.print_ok, 'Done', output='result', duration='1.2s')
    assert 'Done' in output
    assert 'result' in output
    assert '1.2s' in output


# NOTE: `print_success` was removed; `print_ok` covers success output.


# ------------------------------
#    print_warning TESTS
# ------------------------------

def test_print_warning_basic():
    """Test print_warning with basic message."""
    output = capture_output(console.print_warning, 'Warning message')
    assert '⚠️' in output
    assert 'Warning message' in output
    assert console.BOLD_Y in output
    assert '⌚' in output


def test_print_warning_with_output():
    """Test print_warning with additional output."""
    output = capture_output(console.print_warning, 'Deprecated', output='use v2 instead')
    assert 'Deprecated' in output
    assert 'use v2 instead' in output


def test_print_warning_with_duration():
    """Test print_warning with duration."""
    output = capture_output(console.print_warning, 'Slow operation', duration='45s')
    assert 'Slow operation' in output
    assert '45s' in output


# ------------------------------
#    print_debug TESTS
# ------------------------------


def test_print_debug_basic():
    """Test print_debug logs debug prefix."""
    output = capture_output(console.print_debug, 'Debug details')

    assert '🐞' in output
    assert 'Debug details' in output


def test_print_debug_blank_lines():
    """Test print_debug respects blank_above/below flags."""
    output = capture_output(console.print_debug, 'Wrapped', blank_above=True, blank_below=True)

    lines = output.split('\n')
    assert not lines[0]
    assert not lines[-1]


def test_print_debug_wrap_lines():
    """Test print_debug wraps long lines when requested."""
    long_msg = 'd' * 300
    output = capture_output(console.print_debug, long_msg, wrap_lines=True)

    assert 'd' in output
    assert '\n' in output


# ------------------------------
#    print_val TESTS
# ------------------------------

def test_print_val_inline():
    """Test print_val with value on same line."""
    output = capture_output(console.print_val, 'Name', 'John Doe')
    assert '👉' in output
    assert 'Name' in output
    assert 'John Doe' in output
    assert console.BOLD_B in output
    # Should have colon followed by space
    assert ': John Doe' in output


def test_print_val_below():
    """Test print_val with value on line below."""
    output = capture_output(console.print_val, 'Description', 'A long value', val_below=True)
    assert 'Description' in output
    assert 'A long value' in output
    # Should have colon followed by newline
    lines = output.split('\n')
    assert any('Description' in line and ':' in line for line in lines)


def test_print_val_alignment():
    """Test print_val formats name with proper alignment."""
    output = capture_output(console.print_val, 'Key', 'Value')
    # Name should be left-aligned in 25-char field
    assert 'Key' in output


def test_print_val_empty_value():
    """Test print_val with empty value."""
    output = capture_output(console.print_val, 'Empty', '')
    assert 'Empty' in output


# ------------------------------
#    _print_log TESTS
# ------------------------------

def test_print_log_basic():
    """Test _print_log with minimal parameters."""
    output = capture_output(console._print_log, 'Test message')
    assert 'Test message' in output


def test_print_log_with_prefix():
    """Test _print_log with prefix."""
    output = capture_output(console._print_log, 'Message', prefix='>> ')
    assert '>> Message' in output


def test_print_log_with_color():
    """Test _print_log with color."""
    output = capture_output(console._print_log, 'Colored', color=console.BOLD_R)
    assert console.BOLD_R in output
    assert console.RESET in output


def test_print_log_show_time():
    """Test _print_log with show_time enabled."""
    output = capture_output(console._print_log, 'Timed', show_time=True)
    assert '⌚' in output


def test_print_log_blank_above():
    """Test _print_log with blank line above."""
    output = capture_output(console._print_log, 'Message', blank_above=True)
    lines = output.split('\n')
    assert not lines[0]


def test_print_log_blank_below():
    """Test _print_log with blank line below."""
    output = capture_output(console._print_log, 'Message', blank_below=True)
    assert output.endswith('\n\n')


def test_print_log_multiline_preservation():
    """Test _print_log preserves explicit newlines in message."""
    output = capture_output(console._print_log, 'Line1\nLine2\nLine3')
    lines = [line for line in output.split('\n') if line]
    assert len(lines) >= 3
    assert 'Line1' in output
    assert 'Line2' in output
    assert 'Line3' in output


def test_print_log_wrap_lines():
    """Test _print_log with wrap_lines enabled."""
    long_message = 'x' * 200  # Longer than CONSOLE_WIDTH
    output = capture_output(console._print_log, long_message, wrap_lines=True)
    # Should wrap the line
    assert 'x' in output


# ------------------------------
#    THREAD SAFETY TESTS
# ------------------------------

def test_print_lock_thread_safety():
    """Test that print operations are thread-safe."""
    results = []

    def print_in_thread(msg):
        console.print_info(msg)
        results.append(msg)

    threads = []
    for i in range(10):
        thread = threading.Thread(target=print_in_thread, args=(f'Thread {i}',))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    assert len(results) == 10


def test_concurrent_prints():
    """Test multiple concurrent print operations."""
    def concurrent_print():
        console.print_command('command')
        console.print_info('info')
        console.print_ok('success')

    threads = [threading.Thread(target=concurrent_print) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # If we get here without deadlock, test passes


# ------------------------------
#    EDGE CASES
# ------------------------------

def test_empty_strings():
    """Test all print functions handle empty strings."""
    output = capture_output(console.print_command, '')
    assert output  # Should still print prefix

    output = capture_output(console.print_error, '')
    assert output

    output = capture_output(console.print_info, '')
    assert output


def test_special_characters():
    """Test handling of special characters."""
    special = '!@#$%^&*()[]{}|\\:;"\'<>,.?/~`'
    output = capture_output(console.print_info, special)
    # Most characters should appear (some might be processed by terminal)
    assert '!' in output or '@' in output


def test_unicode_characters():
    """Test handling of Unicode characters."""
    unicode_msg = '🚀 Deployment 成功 ✨'
    output = capture_output(console.print_info, unicode_msg)
    # Unicode should be preserved
    assert '🚀' in output or 'Deployment' in output


def test_very_long_message():
    """Test handling of very long messages."""
    long_msg = 'A' * 1000
    output = capture_output(console.print_info, long_msg)
    assert 'A' in output


def test_null_duration_and_output():
    """Test functions with None values for optional parameters."""
    output = capture_output(console.print_error, 'Error', output=None, duration=None)
    assert 'Error' in output


# ------------------------------
#    INTEGRATION TESTS
# ------------------------------

def test_mixed_function_calls():
    """Test calling multiple different print functions in sequence."""
    def run_all():
        console.print_command('az login')
        console.print_info('Starting test')
        console.print_ok('Step 1 complete')
        console.print_warning('Slow operation')
        console.print_error('Step 2 failed')
        console.print_ok('Recovery successful')
        console.print_val('Result', 'PASS')

    output_str = capture_output(run_all)
    assert 'az login' in output_str
    assert 'Starting test' in output_str
    assert 'Step 1 complete' in output_str
    assert 'Slow operation' in output_str
    assert 'Step 2 failed' in output_str
    assert 'Recovery successful' in output_str
    assert 'Result' in output_str
    assert 'PASS' in output_str
    functions_and_colors = [
        (console.print_command, console.BOLD_B),
        (console.print_error, console.BOLD_R),
        (console.print_info, console.BOLD_B),
        (console.print_message, console.BOLD_G),
        (console.print_ok, console.BOLD_G),
        (console.print_warning, console.BOLD_Y),
    ]

    for func, expected_color in functions_and_colors:
        output = capture_output(func, 'test')
        assert expected_color in output, f'{func.__name__} should use {expected_color}'


# ------------------------------
#    _WRAP_LINE TESTS
# ------------------------------


def test_wrap_line_short_text():
    """Test _wrap_line with text shorter than width."""
    result = console._wrap_line('short', 100)
    assert result == 'short'


def test_wrap_line_long_text():
    """Test _wrap_line with text longer than width."""
    result = console._wrap_line('this is a very long line that needs to be wrapped because it exceeds the width', 20)
    assert '\n' in result


def test_wrap_line_preserves_leading_whitespace():
    """Test _wrap_line preserves leading indentation."""
    text = '    indented text that is very long and should wrap properly'
    result = console._wrap_line(text, 30)
    lines = result.split('\n')
    for line in lines:
        if line:
            assert line.startswith('    ')


def test_wrap_line_empty_string():
    """Test _wrap_line with empty string."""
    result = console._wrap_line('', 100)
    assert not result


def test_wrap_line_only_whitespace():
    """Test _wrap_line with only whitespace."""
    result = console._wrap_line('    ', 100)
    assert result == '    '


def test_wrap_line_zero_width():
    """Test _wrap_line with zero width."""
    result = console._wrap_line('text', 0)
    assert result == 'text'


def test_wrap_line_negative_width():
    """Test _wrap_line with negative width."""
    result = console._wrap_line('text', -10)
    assert result == 'text'


# ------------------------------
#    _INFER_LEVEL_FROM_MESSAGE TESTS
# ------------------------------


def test_infer_level_emoji_error():
    """Test _infer_level_from_message with error emoji."""
    level = console._infer_level_from_message('❌ Something went wrong')
    assert level == logging.ERROR


def test_infer_level_emoji_warning():
    """Test _infer_level_from_message with warning emoji."""
    level = console._infer_level_from_message('⚠️ Be careful')
    assert level == logging.WARNING


def test_infer_level_emoji_success():
    """Test _infer_level_from_message with success emoji."""
    level = console._infer_level_from_message('✅ Operation succeeded')
    assert level == logging.INFO


def test_infer_level_emoji_celebration():
    """Test _infer_level_from_message with celebration emoji."""
    level = console._infer_level_from_message('🎉 Release shipped')
    assert level == logging.INFO


def test_infer_level_text_error():
    """Test _infer_level_from_message with 'error:' text."""
    level = console._infer_level_from_message('error: something failed')
    assert level == logging.ERROR


def test_infer_level_text_warning():
    """Test _infer_level_from_message with 'warning:' text."""
    level = console._infer_level_from_message('warning: be careful')
    assert level == logging.WARNING


def test_infer_level_debug_word():
    """Test _infer_level_from_message detects debug prefix."""
    level = console._infer_level_from_message('Debug output: enabled')
    assert level == logging.DEBUG


def test_infer_level_debug_emoji():
    """Test _infer_level_from_message detects debug emoji."""
    level = console._infer_level_from_message('🐞 Tracking issue')
    assert level == logging.DEBUG


def test_infer_level_command_output():
    """Test _infer_level_from_message detects command output prefix."""
    level = console._infer_level_from_message('Command Output: az version')
    assert level == logging.DEBUG


def test_infer_level_default():
    """Test _infer_level_from_message with unknown format."""
    level = console._infer_level_from_message('just a message')
    assert level == logging.INFO


def test_infer_level_empty_string():
    """Test _infer_level_from_message with empty string."""
    level = console._infer_level_from_message('')
    assert level == logging.INFO


def test_infer_level_empty_string_custom_default():
    """Test _infer_level_from_message uses provided default for blanks."""
    level = console._infer_level_from_message('', default=logging.DEBUG)
    assert level == logging.DEBUG


# ------------------------------
#    _GET_CONSOLE_WIDTH TESTS
# ------------------------------


def test_get_console_width_default(monkeypatch):
    """Test _get_console_width uses default when env var not set."""
    monkeypatch.delenv('APIM_SAMPLES_CONSOLE_WIDTH', raising=False)
    width = console._get_console_width()
    assert width == console._DEFAULT_CONSOLE_WIDTH


def test_get_console_width_custom(monkeypatch):
    """Test _get_console_width uses custom value from env."""
    monkeypatch.setenv('APIM_SAMPLES_CONSOLE_WIDTH', '150')
    width = console._get_console_width()
    assert width == 150


def test_get_console_width_invalid_value(monkeypatch):
    """Test _get_console_width falls back to default for invalid value."""
    monkeypatch.setenv('APIM_SAMPLES_CONSOLE_WIDTH', 'invalid')
    width = console._get_console_width()
    assert width == console._DEFAULT_CONSOLE_WIDTH


def test_get_console_width_too_small(monkeypatch):
    """Test _get_console_width falls back to default for too-small value."""
    monkeypatch.setenv('APIM_SAMPLES_CONSOLE_WIDTH', '10')
    width = console._get_console_width()
    assert width == console._DEFAULT_CONSOLE_WIDTH
