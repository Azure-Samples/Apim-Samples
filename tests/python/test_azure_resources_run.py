"""Focused tests for azure_resources.run behavior.

These tests validate the command-runner semantics (debug flag injection, stdout/stderr
handling, and Azure CLI locking) without requiring live Azure.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

# APIM Samples imports
import azure_resources as az


class _FakeLock:
    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0

    def __enter__(self) -> None:
        self.entered += 1

    def __exit__(self, exc_type, exc, tb) -> None:
        self.exited += 1


@pytest.fixture
def _quiet_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """Silence console facade functions so tests don't emit output."""

    monkeypatch.setattr(az, 'print_command', Mock())
    monkeypatch.setattr(az, 'print_plain', Mock())
    monkeypatch.setattr(az, 'print_ok', Mock())
    monkeypatch.setattr(az, 'print_error', Mock())


def test_run_adds_az_debug_flag_and_keeps_stdout_clean_when_success(_quiet_console: None) -> None:
    completed = SimpleNamespace(stdout='{"ok": true}', stderr='DEBUG: noisy stderr', returncode=0)

    with patch.object(az, 'is_debug_enabled', return_value=True), patch.object(az.subprocess, 'run', return_value=completed) as sp_run:
        output = az.run('az group list -o json')

    assert output.success is True
    assert output.text == '{"ok": true}'

    called_command = sp_run.call_args.args[0]
    assert called_command.startswith('az group list')
    assert '--debug' in called_command

    assert sp_run.call_args.kwargs['check'] is False
    assert sp_run.call_args.kwargs['capture_output'] is True
    assert sp_run.call_args.kwargs['text'] is True

    # stderr debug noise should still be logged at DEBUG.
    assert any(call.kwargs.get('level') == logging.DEBUG for call in az.print_plain.call_args_list)


def test_run_does_not_add_debug_flag_when_not_debug_enabled(_quiet_console: None) -> None:
    completed = SimpleNamespace(stdout='[]', stderr='', returncode=0)

    with patch.object(az, 'is_debug_enabled', return_value=False), patch.object(az.subprocess, 'run', return_value=completed) as sp_run:
        output = az.run('az group list -o json')

    assert output.success is True
    assert output.text == '[]'
    assert '--debug' not in sp_run.call_args.args[0]


def test_run_inserts_debug_flag_before_pipe_operator(_quiet_console: None) -> None:
    completed = SimpleNamespace(stdout='[]', stderr='debug', returncode=0)

    with patch.object(az, 'is_debug_enabled', return_value=True), patch.object(az.subprocess, 'run', return_value=completed) as sp_run:
        az.run('az group list -o json | jq .')

    assert sp_run.call_args.args[0] == 'az group list -o json --debug | jq .'


def test_run_combines_stdout_and_stderr_on_failure(_quiet_console: None) -> None:
    completed = SimpleNamespace(stdout='partial', stderr='ERROR: failed', returncode=1)

    with patch.object(az, 'is_debug_enabled', return_value=False), patch.object(az.subprocess, 'run', return_value=completed):
        output = az.run('az group list -o json', error_message='failed')

    assert output.success is False
    assert 'partial' in output.text
    assert 'ERROR: failed' in output.text


def test_run_uses_az_cli_lock_only_for_az_commands(_quiet_console: None, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_lock = _FakeLock()
    monkeypatch.setattr(az, '_AZ_CLI_LOCK', fake_lock)

    completed = SimpleNamespace(stdout='ok', stderr='', returncode=0)

    with patch.object(az, 'is_debug_enabled', return_value=False), patch.object(az.subprocess, 'run', return_value=completed):
        az.run('az group list')

    assert fake_lock.entered == 1
    assert fake_lock.exited == 1

    # Non-az command should not use the lock.
    fake_lock.entered = 0
    fake_lock.exited = 0

    with patch.object(az, 'is_debug_enabled', return_value=False), patch.object(az.subprocess, 'run', return_value=completed):
        az.run('echo hello')

    assert not fake_lock.entered
    assert not fake_lock.exited
