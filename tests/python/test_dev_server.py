"""Regression tests for shared preview logging and resource cleanup."""

import importlib
import os
import signal
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SETUP_PATH = Path(__file__).resolve().parents[2] / 'setup'
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

dev_server = importlib.import_module('dev_server')
serve_presentation = importlib.import_module('serve_presentation')


@pytest.fixture
def preview_server(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Isolate sockets, threads, and signal registration from cleanup tests."""
    server = MagicMock()
    thread = MagicMock()
    thread.is_alive.return_value = False
    monkeypatch.setattr(dev_server, 'TCPServer', MagicMock(return_value=server))
    monkeypatch.setattr(dev_server, 'Thread', MagicMock(return_value=thread))
    monkeypatch.setattr(dev_server.signal, 'signal', MagicMock())

    return server


def _serve(directory: Path) -> None:
    """Exercise the shared lifecycle with a minimal preview configuration."""
    dev_server.serve_directory(
        directory,
        dev_server.QuietRequestHandler,
        7800,
        title='Test preview',
        links=(('Landing page', '/'),),
        browser_path='/',
    )


@pytest.mark.parametrize(
    ('handler_type', 'args', 'expected'),
    [
        (dev_server.QuietRequestHandler, (), ''),
        (dev_server.QuietRequestHandler, ('not an HTTP request', '500'), 'not an HTTP request 500'),
        (serve_presentation.PresentationHandler, ('background task', '500'), ''),
        (dev_server.QuietRequestHandler, ('GET / HTTP/1.1', '302'), ''),
    ],
)
def test_handler_preserves_logging_contract(handler_type: type, args: tuple[str, ...], expected: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Retain the existing distinction between presentation and website logs."""
    handler = handler_type.__new__(handler_type)
    handler.log_message(' '.join('%s' for _ in args), *args)

    assert capsys.readouterr().err.strip() == expected


def test_bind_failure_restores_cwd_and_signal_handlers(tmp_path: Path, preview_server: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed listener must not leave process-global preview state behind."""
    original_dir = os.getcwd()
    previous_sigint = signal.getsignal(signal.SIGINT)
    dev_server.TCPServer.side_effect = OSError('port in use')

    with pytest.raises(OSError, match='port in use'):
        _serve(tmp_path)

    assert os.getcwd() == original_dir
    assert any(call.args == (signal.SIGINT, previous_sigint) for call in dev_server.signal.signal.call_args_list)
    preview_server.shutdown.assert_not_called()


@pytest.mark.parametrize('failed_thread', [0, 1])
def test_thread_start_failure_closes_unstarted_server(tmp_path: Path, preview_server: MagicMock, failed_thread: int) -> None:
    """Do not deadlock by shutting down a server whose loop never started."""
    threads = [MagicMock(), MagicMock()]
    threads[failed_thread].start.side_effect = RuntimeError('thread start failed')
    dev_server.Thread.side_effect = threads
    original_dir = os.getcwd()

    with pytest.raises(RuntimeError, match='thread start failed'):
        _serve(tmp_path)

    preview_server.shutdown.assert_not_called()
    preview_server.server_close.assert_called_once()
    assert os.getcwd() == original_dir


@pytest.mark.parametrize(
    ('operation', 'message'),
    [('shutdown', 'Error stopping preview server'), ('server_close', 'Error closing preview server')],
)
def test_cleanup_oserror_is_reported(tmp_path: Path, preview_server: MagicMock, operation: str, message: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Report recoverable socket cleanup failures while restoring state."""
    getattr(preview_server, operation).side_effect = OSError('socket failure')
    original_dir = os.getcwd()

    _serve(tmp_path)

    assert f'{message}: socket failure' in capsys.readouterr().err
    preview_server.server_close.assert_called_once()
    assert os.getcwd() == original_dir


def test_unexpected_shutdown_failure_still_closes_server(tmp_path: Path, preview_server: MagicMock) -> None:
    """Unexpected errors propagate after closing the socket and restoring cwd."""
    preview_server.shutdown.side_effect = RuntimeError('unexpected failure')
    original_dir = os.getcwd()

    with pytest.raises(RuntimeError, match='unexpected failure'):
        _serve(tmp_path)

    preview_server.server_close.assert_called_once()
    assert os.getcwd() == original_dir


def test_signal_restore_failure_still_restores_cwd(tmp_path: Path, preview_server: MagicMock) -> None:
    """A signal restoration error must not strand the caller in the preview."""
    signal_count = 2 if hasattr(signal, 'SIGTERM') else 1
    dev_server.signal.signal.side_effect = [None] * signal_count + [ValueError('signal restore failed')]
    original_dir = os.getcwd()

    with pytest.raises(ValueError, match='signal restore failed'):
        _serve(tmp_path)

    preview_server.server_close.assert_called_once()
    assert os.getcwd() == original_dir
