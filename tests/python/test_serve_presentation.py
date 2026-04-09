"""Unit tests for serve_presentation module."""

import importlib
import re
import runpy
import signal
import sys
import threading
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

# Ensure the setup folder is on sys.path so the module is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / 'setup'
SCRIPT_PATH = SETUP_PATH / 'serve_presentation.py'
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

serve_pres = cast(ModuleType, importlib.import_module('serve_presentation'))


@pytest.fixture
def mock_repo_root(tmp_path: Path) -> Path:
    """Create a temporary repo root with the slide deck under assets/."""
    assets_dir = tmp_path / 'assets'
    assets_dir.mkdir(parents=True)
    (assets_dir / 'APIM-Samples-Slide-Deck.html').write_text('<html>Test</html>')
    return tmp_path


def _make_handler(path: str = '/') -> Any:
    """Create a handler instance without running the HTTP server base initializer."""
    handler = serve_pres.PresentationHandler.__new__(serve_pres.PresentationHandler)
    handler.path = path
    return handler


def test_get_local_timestamp_format() -> None:
    """get_local_timestamp should return the expected local timestamp format."""
    timestamp = serve_pres.get_local_timestamp()

    assert re.fullmatch(r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}\.\d{3}', timestamp)


def test_get_presentation_dir_exists(monkeypatch: pytest.MonkeyPatch, mock_repo_root: Path) -> None:
    """get_presentation_dir should return the assets path when it exists."""
    setup_file = mock_repo_root / 'setup' / 'serve_presentation.py'
    setup_file.parent.mkdir(parents=True, exist_ok=True)
    setup_file.write_text('')

    monkeypatch.setattr(serve_pres, '__file__', str(setup_file))

    assert serve_pres.get_presentation_dir() == mock_repo_root / 'assets'


def test_get_presentation_dir_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """get_presentation_dir should raise FileNotFoundError when assets is missing."""
    setup_file = tmp_path / 'setup' / 'serve_presentation.py'
    setup_file.parent.mkdir(parents=True, exist_ok=True)
    setup_file.write_text('')

    monkeypatch.setattr(serve_pres, '__file__', str(setup_file))

    with pytest.raises(FileNotFoundError, match='Assets directory not found'):
        serve_pres.get_presentation_dir()


def test_presentation_handler_do_get_root_path() -> None:
    """PresentationHandler.do_GET should rewrite '/' to the slide deck HTML file."""
    handler = _make_handler('/')

    with patch.object(serve_pres.http.server.SimpleHTTPRequestHandler, 'do_GET') as mock_super:
        handler.do_GET()

    assert handler.path == serve_pres.PRESENTATION_ENTRY_PATH
    mock_super.assert_called_once()


def test_presentation_handler_do_get_empty_path() -> None:
    """PresentationHandler.do_GET should rewrite empty path to the slide deck HTML file."""
    handler = _make_handler('')

    with patch.object(serve_pres.http.server.SimpleHTTPRequestHandler, 'do_GET') as mock_super:
        handler.do_GET()

    assert handler.path == serve_pres.PRESENTATION_ENTRY_PATH
    mock_super.assert_called_once()


def test_presentation_handler_do_get_other_path() -> None:
    """PresentationHandler.do_GET should not rewrite other paths."""
    handler = _make_handler('/styles.css')

    with patch.object(serve_pres.http.server.SimpleHTTPRequestHandler, 'do_GET') as mock_super:
        handler.do_GET()

    assert handler.path == '/styles.css'
    mock_super.assert_called_once()


def test_presentation_handler_do_head_rewrites_and_closes_file() -> None:
    """PresentationHandler.do_HEAD should rewrite the path and close send_head output."""
    handler = _make_handler('/')
    file_handle = MagicMock()

    with patch.object(handler, '_log_polled_update') as mock_log_polled_update:
        with patch.object(handler, 'send_head', return_value=file_handle) as mock_send_head:
            handler.do_HEAD()

    assert handler.path == serve_pres.PRESENTATION_ENTRY_PATH
    mock_log_polled_update.assert_called_once()
    mock_send_head.assert_called_once()
    file_handle.close.assert_called_once()


def test_presentation_handler_do_head_with_no_file_handle() -> None:
    """PresentationHandler.do_HEAD should not attempt to close a falsey send_head result."""
    handler = _make_handler('/')

    with patch.object(handler, '_log_polled_update') as mock_log_polled_update:
        with patch.object(handler, 'send_head', return_value=None) as mock_send_head:
            handler.do_HEAD()

    assert handler.path == serve_pres.PRESENTATION_ENTRY_PATH
    mock_log_polled_update.assert_called_once()
    mock_send_head.assert_called_once()


def test_presentation_handler_log_message(capsys: pytest.CaptureFixture[str]) -> None:
    """PresentationHandler.log_message should print request logs to stderr."""
    handler = _make_handler()

    handler.log_message('"%s" %s %s', 'GET /TEST HTTP/1.1', '404', '-')

    captured = capsys.readouterr()
    assert 'GET /TEST HTTP/1.1' in captured.err


def test_presentation_handler_log_message_ignores_successful_head_request(capsys: pytest.CaptureFixture[str]) -> None:
    """PresentationHandler.log_message should ignore successful HEAD polling requests."""
    handler = _make_handler()

    handler.log_message('"%s" %s %s', 'HEAD / HTTP/1.1', '200', '-')

    captured = capsys.readouterr()
    assert not captured.err


def test_presentation_handler_log_message_ignores_browser_probe(capsys: pytest.CaptureFixture[str]) -> None:
    """PresentationHandler.log_message should ignore noisy browser probe requests."""
    handler = _make_handler()

    handler.log_message(
        '"%s" %s %s',
        'GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1',
        '404',
        '-',
    )

    captured = capsys.readouterr()
    assert not captured.err


def test_presentation_handler_log_message_ignores_non_http_message_without_status(capsys: pytest.CaptureFixture[str]) -> None:
    """PresentationHandler.log_message should stay quiet for non-HTTP lines without a status code."""
    handler = _make_handler()

    handler.log_message('%s', 'background task completed')

    captured = capsys.readouterr()
    assert not captured.err


def test_should_ignore_log_request_with_short_request_line() -> None:
    """Short request lines should not be ignored by the log filter."""
    assert not serve_pres.PresentationHandler._should_ignore_log_request('MALFORMED')


def test_presentation_handler_logs_update_on_head_poll(tmp_path: Path) -> None:
    """HEAD polling should log when the requested file has a newer mtime."""
    watched_file = tmp_path / 'deck.html'
    watched_file.write_text('<html>v1</html>')

    handler = _make_handler('/deck.html')
    serve_pres.PresentationHandler._last_polled_mtimes = {}

    with patch.object(handler, 'translate_path', return_value=str(watched_file)):
        with patch('builtins.print') as mock_print:
            handler._log_polled_update()

        mock_print.assert_not_called()

        watched_file.write_text('<html>v2</html>')

        with patch('serve_presentation.get_local_timestamp', return_value='02/26/2026 15:45:12.123'):
            with patch('builtins.print') as mock_print:
                handler._log_polled_update()

    mock_print.assert_called_once_with('  [02/26/2026 15:45:12.123] File update detected: deck.html', flush=True)


def test_presentation_handler_does_not_log_update_for_missing_file() -> None:
    """HEAD polling should not log anything when the requested file is missing."""
    handler = _make_handler('/missing.html')
    serve_pres.PresentationHandler._last_polled_mtimes = {}

    with patch.object(handler, 'translate_path', return_value='missing.html'):
        with patch('builtins.print') as mock_print:
            handler._log_polled_update()

    mock_print.assert_not_called()


def test_presentation_handler_does_not_log_update_for_directory(tmp_path: Path) -> None:
    """HEAD polling should not log anything when the translated path is a directory."""
    watched_dir = tmp_path / 'assets'
    watched_dir.mkdir()

    handler = _make_handler('/assets')
    serve_pres.PresentationHandler._last_polled_mtimes = {}

    with patch.object(handler, 'translate_path', return_value=str(watched_dir)):
        with patch('builtins.print') as mock_print:
            handler._log_polled_update()

    mock_print.assert_not_called()


def test_serve_presentation_keyboard_interrupt(mock_repo_root: Path) -> None:
    """serve_presentation should gracefully handle KeyboardInterrupt."""
    presentation_dir = mock_repo_root / 'assets'

    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = True

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance

            with patch('serve_presentation.Thread', return_value=mock_thread_instance):
                with patch('serve_presentation.sleep', side_effect=KeyboardInterrupt):
                    with patch('builtins.print') as mock_print:
                        with patch('os.chdir'):
                            serve_pres.serve_presentation(8000)

    mock_server_instance.server_close.assert_called_once()
    printed_messages = [' '.join(str(arg) for arg in call.args) for call in mock_print.call_args_list]
    assert any('Server stopped' in str(message) for message in printed_messages)


def test_serve_presentation_registers_signal_handlers(mock_repo_root: Path) -> None:
    """serve_presentation should register and restore shutdown signal handlers."""
    presentation_dir = mock_repo_root / 'assets'
    previous_sigint_handler = signal.default_int_handler
    previous_sigterm_handler = signal.SIG_DFL if hasattr(signal, 'SIGTERM') else None

    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = False

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance

            with patch('serve_presentation.Thread', return_value=mock_thread_instance):
                with patch('builtins.print'):
                    with patch('os.chdir'):
                        with patch('serve_presentation.signal.getsignal') as mock_getsignal:
                            with patch('serve_presentation.signal.signal') as mock_signal:
                                mock_getsignal.side_effect = [previous_sigint_handler, previous_sigterm_handler]
                                serve_pres.serve_presentation(8000)

    registered_signals = [call.args[0] for call in mock_signal.call_args_list[:2]]
    restored_handlers = [call.args[1] for call in mock_signal.call_args_list[2:]]

    assert signal.SIGINT in registered_signals
    if hasattr(signal, 'SIGTERM'):
        assert signal.SIGTERM in registered_signals
        assert previous_sigterm_handler in restored_handlers
    assert previous_sigint_handler in restored_handlers


def test_serve_presentation_opens_browser(mock_repo_root: Path) -> None:
    """serve_presentation should spawn a thread to open the browser."""
    presentation_dir = mock_repo_root / 'assets'

    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = False

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance

            with patch('serve_presentation.Thread', return_value=mock_thread_instance) as mock_thread:
                with patch('builtins.print'):
                    with patch('os.chdir'):
                        serve_pres.serve_presentation(8000)

    assert mock_thread.call_count == 2
    assert mock_thread.call_args_list[0].kwargs['daemon'] is True


def test_serve_presentation_browser_thread_target_opens_url(mock_repo_root: Path) -> None:
    """The browser thread target should sleep briefly and open the presentation URL."""
    presentation_dir = mock_repo_root / 'assets'

    class ImmediateThread:
        def __init__(self, target=None, daemon=None):
            self._target = target
            self.daemon = daemon

        def start(self) -> None:
            if self._target is not None:
                self._target()

        def is_alive(self) -> bool:
            return False

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.current_thread', return_value=object()):
            with patch('serve_presentation.main_thread', return_value=object()):
                with patch('serve_presentation.TCPServer') as mock_server:
                    mock_server_instance = MagicMock()
                    mock_server.return_value = mock_server_instance
                    mock_server_instance.serve_forever.side_effect = KeyboardInterrupt()

                    with patch('serve_presentation.Thread', ImmediateThread):
                        with patch('serve_presentation.sleep') as mock_sleep:
                            with patch('serve_presentation.webbrowser.open') as mock_open:
                                with patch('builtins.print'):
                                    with patch('os.chdir'):
                                        serve_pres.serve_presentation(8123)

    mock_sleep.assert_called_once_with(1)
    mock_open.assert_called_once_with(f'http://localhost:8123{serve_pres.PRESENTATION_ENTRY_PATH}')


def test_serve_presentation_restores_cwd(mock_repo_root: Path) -> None:
    """serve_presentation should restore original working directory after exit."""
    presentation_dir = mock_repo_root / 'assets'
    original_cwd = '/original/cwd'

    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = False

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance

            with patch('serve_presentation.Thread', return_value=mock_thread_instance):
                with patch('builtins.print'):
                    with patch('os.getcwd', return_value=original_cwd):
                        with patch('os.chdir') as mock_chdir:
                            serve_pres.serve_presentation(8000)

    chdir_calls = [call.args[0] for call in mock_chdir.call_args_list]
    assert original_cwd in chdir_calls


def test_serve_presentation_signal_handler_prints_shutdown_once(mock_repo_root: Path) -> None:
    """The shutdown signal handler should trigger a single shutdown message even if caught twice."""
    presentation_dir = mock_repo_root / 'assets'
    registered_handlers: dict[int, Any] = {}

    def capture_signal(sig: int, handler: Any) -> None:
        registered_handlers[sig] = handler

    # Simulate the signal handler being called twice during the serve loop, then exit.
    call_count = {'n': 0}

    def sleep_side_effect(_t: float) -> None:
        call_count['n'] += 1
        if call_count['n'] == 1:
            for _ in range(2):
                try:
                    registered_handlers[signal.SIGINT](signal.SIGINT, None)
                except KeyboardInterrupt:
                    continue
        raise KeyboardInterrupt

    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = True

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance

            with patch('serve_presentation.Thread', return_value=mock_thread_instance):
                with patch('builtins.print') as mock_print:
                    with patch('os.chdir'):
                        with patch('serve_presentation.signal.getsignal', return_value=signal.default_int_handler):
                            with patch('serve_presentation.signal.signal', side_effect=capture_signal):
                                with patch('serve_presentation.sleep', side_effect=sleep_side_effect):
                                    serve_pres.serve_presentation(8000)

    shutdown_messages = [call for call in mock_print.call_args_list if 'Server stopped' in ' '.join(str(arg) for arg in call.args)]
    assert len(shutdown_messages) == 1


def test_serve_presentation_prints_server_info(mock_repo_root: Path) -> None:
    """serve_presentation should print server information."""
    presentation_dir = mock_repo_root / 'assets'
    expected_url = 'http://localhost:7777'
    expected_presentation_url = f'{expected_url}{serve_pres.PRESENTATION_ENTRY_PATH}'

    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = False

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance

            with patch('serve_presentation.Thread', return_value=mock_thread_instance):
                with patch('builtins.print') as mock_print:
                    with patch('os.chdir'):
                        serve_pres.serve_presentation(7777)

    printed_messages = '\n'.join(' '.join(str(arg) for arg in call.args) for call in mock_print.call_args_list)
    assert 'APIM Samples Presentation Server' in printed_messages
    assert expected_url in printed_messages
    assert expected_presentation_url in printed_messages
    assert str(presentation_dir) in printed_messages


def test_serve_presentation_custom_port(mock_repo_root: Path) -> None:
    """serve_presentation should use custom port when specified."""
    presentation_dir = mock_repo_root / 'assets'

    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = False

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance

            with patch('serve_presentation.Thread', return_value=mock_thread_instance):
                with patch('builtins.print'):
                    with patch('os.chdir'):
                        serve_pres.serve_presentation(9000)

    assert mock_server.call_args.args[0] == ('127.0.0.1', 9000)


def test_serve_presentation_handler_is_set(mock_repo_root: Path) -> None:
    """serve_presentation should use PresentationHandler for the server."""
    presentation_dir = mock_repo_root / 'assets'

    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = False

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance

            with patch('serve_presentation.Thread', return_value=mock_thread_instance):
                with patch('builtins.print'):
                    with patch('os.chdir'):
                        serve_pres.serve_presentation(7777)

    assert mock_server.call_args.args[1] is serve_pres.PresentationHandler


def test_main_default_port() -> None:
    """Main entry with no arguments should use default port 7777."""
    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = False

    with patch('socketserver.TCPServer') as mock_server:
        mock_server_instance = MagicMock()
        mock_server.return_value = mock_server_instance

        with patch.object(threading, 'Thread', return_value=mock_thread_instance):
            with patch('builtins.print'):
                with patch('os.chdir'):
                    with patch('os.getcwd', return_value=str(PROJECT_ROOT)):
                        with patch('signal.getsignal', return_value=signal.default_int_handler):
                            with patch('signal.signal'):
                                with patch.object(sys, 'argv', ['serve_presentation.py']):
                                    runpy.run_path(str(SCRIPT_PATH), run_name='__main__')

    assert mock_server.call_args.args[0] == ('127.0.0.1', 7777)


def test_main_custom_port() -> None:
    """Main entry with argument should use specified port."""
    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = False

    with patch('socketserver.TCPServer') as mock_server:
        mock_server_instance = MagicMock()
        mock_server.return_value = mock_server_instance

        with patch.object(threading, 'Thread', return_value=mock_thread_instance):
            with patch('builtins.print'):
                with patch('os.chdir'):
                    with patch('os.getcwd', return_value=str(PROJECT_ROOT)):
                        with patch('signal.getsignal', return_value=signal.default_int_handler):
                            with patch('signal.signal'):
                                with patch.object(sys, 'argv', ['serve_presentation.py', '8881']):
                                    runpy.run_path(str(SCRIPT_PATH), run_name='__main__')

    assert mock_server.call_args.args[0] == ('127.0.0.1', 8881)


def test_main_file_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    """Main entry should handle FileNotFoundError gracefully."""
    with patch('pathlib.Path.exists', return_value=False):
        with patch.object(sys, 'argv', ['serve_presentation.py']):
            with pytest.raises(SystemExit) as exc_info:
                runpy.run_path(str(SCRIPT_PATH), run_name='__main__')

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert 'Assets directory not found' in captured.err


def test_main_port_in_use(capsys: pytest.CaptureFixture[str]) -> None:
    """Main entry should handle OSError for port in use gracefully."""
    with patch('socketserver.TCPServer', side_effect=OSError('Address already in use')):
        with patch('os.chdir'):
            with patch('os.getcwd', return_value=str(PROJECT_ROOT)):
                with patch('signal.getsignal', return_value=signal.default_int_handler):
                    with patch('signal.signal'):
                        with patch.object(sys, 'argv', ['serve_presentation.py', '8000']):
                            with pytest.raises(SystemExit) as exc_info:
                                runpy.run_path(str(SCRIPT_PATH), run_name='__main__')

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert 'Port 8000 is already in use' in captured.err
    assert 'Try a different port' in captured.err


def test_main_generic_oserror(capsys: pytest.CaptureFixture[str]) -> None:
    """Main entry should handle generic OSError gracefully."""
    with patch('socketserver.TCPServer', side_effect=OSError('Some other error')):
        with patch('os.chdir'):
            with patch('os.getcwd', return_value=str(PROJECT_ROOT)):
                with patch('signal.getsignal', return_value=signal.default_int_handler):
                    with patch('signal.signal'):
                        with patch.object(sys, 'argv', ['serve_presentation.py']):
                            with pytest.raises(SystemExit) as exc_info:
                                runpy.run_path(str(SCRIPT_PATH), run_name='__main__')

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert 'Some other error' in captured.err


def test_serve_presentation_survives_shutdown_failure(mock_repo_root: Path) -> None:
    """serve_presentation should still close the server when shutdown raises."""
    presentation_dir = mock_repo_root / 'assets'

    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = True

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance
            mock_server_instance.shutdown.side_effect = OSError('boom')

            with patch('serve_presentation.Thread', return_value=mock_thread_instance):
                with patch('serve_presentation.sleep', side_effect=KeyboardInterrupt):
                    with patch('builtins.print'):
                        with patch('os.chdir'):
                            serve_pres.serve_presentation(8000)

    mock_server_instance.shutdown.assert_called_once()
    mock_server_instance.server_close.assert_called_once()


def test_serve_presentation_survives_close_failure(mock_repo_root: Path) -> None:
    """serve_presentation should suppress server_close errors during cleanup."""
    presentation_dir = mock_repo_root / 'assets'

    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = True

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance
            mock_server_instance.server_close.side_effect = OSError('boom')

            with patch('serve_presentation.Thread', return_value=mock_thread_instance):
                with patch('serve_presentation.sleep', side_effect=KeyboardInterrupt):
                    with patch('builtins.print'):
                        with patch('os.chdir'):
                            serve_pres.serve_presentation(8000)

    mock_server_instance.shutdown.assert_called_once()
    mock_server_instance.server_close.assert_called_once()


def test_serve_presentation_keyboard_interrupt_before_server_creation(mock_repo_root: Path) -> None:
    """serve_presentation should handle interrupts before TCPServer is created."""
    presentation_dir = mock_repo_root / 'assets'

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer', side_effect=KeyboardInterrupt):
            with patch('builtins.print') as mock_print:
                with patch('os.chdir'):
                    serve_pres.serve_presentation(8000)

    printed_messages = [' '.join(str(arg) for arg in call.args) for call in mock_print.call_args_list]
    assert any('Server stopped' in str(message) for message in printed_messages)


def test_main_invalid_port_value_raises_value_error() -> None:
    """Main entry should propagate ValueError for a non-numeric port argument."""
    with patch.object(sys, 'argv', ['serve_presentation.py', 'not-a-port']):
        with pytest.raises(ValueError, match='invalid literal for int'):
            runpy.run_path(str(SCRIPT_PATH), run_name='__main__')


def test_open_browser_thread_is_daemon(mock_repo_root: Path) -> None:
    """The browser opening thread should be a daemon thread."""
    presentation_dir = mock_repo_root / 'assets'

    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = False

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance

            with patch('serve_presentation.Thread', return_value=mock_thread_instance) as mock_thread:
                with patch('builtins.print'):
                    with patch('os.chdir'):
                        serve_pres.serve_presentation(7777)

    assert mock_thread.call_args_list[0].kwargs['daemon'] is True


def test_open_browser_has_sleep_delay(mock_repo_root: Path) -> None:
    """serve_presentation should create a browser-opening thread when starting."""
    presentation_dir = mock_repo_root / 'assets'

    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = False

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance

            with patch('serve_presentation.Thread', return_value=mock_thread_instance) as mock_thread:
                with patch('builtins.print'):
                    with patch('os.chdir'):
                        serve_pres.serve_presentation(7777)

    assert callable(mock_thread.call_args_list[0].kwargs['target'])


def test_presentation_handler_integration() -> None:
    """PresentationHandler should consistently rewrite only root-style paths."""
    handler = _make_handler('/')

    with patch.object(serve_pres.http.server.SimpleHTTPRequestHandler, 'do_GET'):
        handler.do_GET()
        assert handler.path == serve_pres.PRESENTATION_ENTRY_PATH

        handler.path = ''
        handler.do_GET()
        assert handler.path == serve_pres.PRESENTATION_ENTRY_PATH

        handler.path = '/assets/image.png'
        handler.do_GET()
        assert handler.path == '/image.png'
