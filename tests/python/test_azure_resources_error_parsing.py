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
