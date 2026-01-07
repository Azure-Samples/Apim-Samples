"""Tests for Azure CLI error parsing helpers in azure_resources."""

from __future__ import annotations

# APIM Samples imports
import azure_resources as az


def test_extract_az_cli_error_message_prefers_json_error_message() -> None:
    text = "Some noise\n{\"error\": {\"message\": \"Inner error\"}}\nMore noise"

    assert az._extract_az_cli_error_message(text) == 'Inner error'


def test_extract_az_cli_error_message_handles_json_top_level_message() -> None:
    text = '{"message": "Top-level message"}'

    assert az._extract_az_cli_error_message(text) == 'Top-level message'


def test_extract_az_cli_error_message_parses_error_prefix() -> None:
    text = "ERROR: Something bad happened\nDetails: ignored"

    assert az._extract_az_cli_error_message(text) == 'Something bad happened'


def test_extract_az_cli_error_message_parses_az_error_prefix() -> None:
    text = "az: error: Invalid value for --name"

    assert az._extract_az_cli_error_message(text) == 'Invalid value for --name'


def test_extract_az_cli_error_message_parses_code_message_pair() -> None:
    text = "Code: AuthorizationFailed\nMessage: Not authorized"

    assert az._extract_az_cli_error_message(text) == 'AuthorizationFailed: Not authorized'


def test_extract_az_cli_error_message_strips_ansi() -> None:
    text = "\x1b[31mERROR: Red text\x1b[0m"

    assert az._extract_az_cli_error_message(text) == 'Red text'


def test_extract_az_cli_error_message_skips_warnings_and_avoids_traceback() -> None:
    text = "WARNING: some warning\nActual failure\nTraceback (most recent call last):\n  ..."

    assert az._extract_az_cli_error_message(text) == 'Actual failure'


def test_extract_az_cli_error_message_empty_string() -> None:
    """Test with empty string input."""
    assert not az._extract_az_cli_error_message('')


def test_extract_az_cli_error_message_whitespace_only() -> None:
    """Test with whitespace-only input."""
    assert not az._extract_az_cli_error_message('   \n  \t  ')


def test_extract_az_cli_error_message_json_with_non_dict_payload() -> None:
    """Test JSON array (non-dict) is skipped."""
    text = "[1, 2, 3]\nERROR: Fallback message"
    assert az._extract_az_cli_error_message(text) == 'Fallback message'


def test_extract_az_cli_error_message_json_with_nested_error_dict() -> None:
    """Test JSON with error.message extraction."""
    text = '{"error": {"message": "Nested error message"}}'
    assert az._extract_az_cli_error_message(text) == 'Nested error message'


def test_extract_az_cli_error_message_json_error_not_dict() -> None:
    """Test JSON where error field is not a dict (skips to next extraction)."""
    text = '{"error": "string value"}\nERROR: Fallback'
    assert az._extract_az_cli_error_message(text) == 'Fallback'


def test_extract_az_cli_error_message_json_message_not_string() -> None:
    """Test JSON where message is not a string (skips to next extraction)."""
    text = '{"message": 123}\nERROR: Fallback'
    assert az._extract_az_cli_error_message(text) == 'Fallback'


def test_extract_az_cli_error_message_error_prefix_with_empty_suffix() -> None:
    """Test ERROR: prefix with nothing after colon."""
    text = "ERROR:\nSome other line"
    # Empty suffix after colon falls back to full line
    assert az._extract_az_cli_error_message(text) == 'ERROR:'


def test_extract_az_cli_error_message_az_error_prefix_with_empty_suffix() -> None:
    """Test az: error: prefix with nothing after second colon."""
    text = "az: error:\nSome other line"
    # Empty suffix falls back to full line
    assert az._extract_az_cli_error_message(text) == 'az: error:'


def test_extract_az_cli_error_message_code_and_message_together() -> None:
    """Test both Code and Message lines present."""
    text = "Code: AuthorizationFailed\nMessage: User is not authorized"
    assert az._extract_az_cli_error_message(text) == 'AuthorizationFailed: User is not authorized'


def test_extract_az_cli_error_message_multiple_code_lines() -> None:
    """Test multiple Code lines - only first is used."""
    text = "Code: FirstError\nCode: SecondError\nMessage: Details"
    assert az._extract_az_cli_error_message(text) == 'FirstError: Details'


def test_extract_az_cli_error_message_multiple_message_lines() -> None:
    """Test multiple Message lines - only first is used."""
    text = "Message: First message\nMessage: Second message"
    assert az._extract_az_cli_error_message(text) == 'First message'


def test_extract_az_cli_error_message_code_without_message() -> None:
    """Test Code: line without corresponding Message: line."""
    text = "Code: AuthorizationFailed\nSome other content"
    # Code alone without message falls through to first non-warning, non-traceback line
    assert az._extract_az_cli_error_message(text) == 'Code: AuthorizationFailed'


def test_extract_az_cli_error_message_message_without_code() -> None:
    """Test Message: line without corresponding Code: line."""
    text = "Message: Not authorized\nOther content"
    # Message without Code returns just the message value
    assert az._extract_az_cli_error_message(text) == 'Not authorized'


def test_extract_az_cli_error_message_traceback_at_start() -> None:
    """Test when traceback is the first line."""
    text = "Traceback (most recent call last):\n  File ...\n  Error details"
    assert not az._extract_az_cli_error_message(text)


def test_extract_az_cli_error_message_all_empty_lines_before_traceback() -> None:
    """Test when all lines before traceback are empty."""
    text = "\n\n\nTraceback (most recent call last):\n  Error"
    assert not az._extract_az_cli_error_message(text)


def test_extract_az_cli_error_message_empty_lines_with_traceback() -> None:
    """Test multiple empty lines mixed with non-empty lines."""
    text = "WARNING: warning\n\nActual message\n\nTraceback (...):\n  ..."
    assert az._extract_az_cli_error_message(text) == 'Actual message'


def test_extract_az_cli_error_message_only_warnings() -> None:
    """Test output containing only warnings."""
    text = "WARNING: first warning\nWARNING: second warning"
    assert not az._extract_az_cli_error_message(text)


def test_extract_az_cli_error_message_multiple_json_payloads() -> None:
    """Test multiple JSON payloads in output (first valid one is used)."""
    text = '{"error": {"message": "First error"}}\n{"error": {"message": "Second error"}}'
    assert az._extract_az_cli_error_message(text) == 'First error'


def test_extract_az_cli_error_message_malformed_json_then_error_prefix() -> None:
    """Test malformed JSON followed by ERROR: prefix."""
    text = '{invalid json\nERROR: Valid error message'
    assert az._extract_az_cli_error_message(text) == 'Valid error message'
