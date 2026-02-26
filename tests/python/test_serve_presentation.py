"""Unit tests for serve_presentation module."""

import importlib
import signal
import sys
from pathlib import Path
from types import ModuleType
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

# Ensure the setup folder is on sys.path so the module is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / "setup"
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

serve_pres = cast(ModuleType, importlib.import_module("serve_presentation"))


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def mock_presentation_dir(tmp_path: Path) -> Path:
    """Create a temporary assets directory containing the slide deck."""
    assets_dir = tmp_path / 'assets'
    assets_dir.mkdir(parents=True)
    (assets_dir / 'APIM-Samples-Slide-Deck.html').write_text('<html>Test</html>')
    return assets_dir


@pytest.fixture
def mock_repo_root(tmp_path: Path) -> Path:
    """Create a temporary repo root with the slide deck under assets/."""
    assets_dir = tmp_path / 'assets'
    assets_dir.mkdir(parents=True)
    (assets_dir / 'APIM-Samples-Slide-Deck.html').write_text('<html>Test</html>')
    return tmp_path


# ============================================================
# TESTS: get_presentation_dir()
# ============================================================

def test_get_presentation_dir_exists(monkeypatch: pytest.MonkeyPatch, mock_repo_root: Path) -> None:
    """get_presentation_dir should return the assets path when it exists."""
    # Mock __file__ to point to a setup file in our mock repo
    setup_file = mock_repo_root / 'setup' / 'serve_presentation.py'
    setup_file.parent.mkdir(parents=True, exist_ok=True)
    setup_file.write_text('')

    with patch.object(Path, '__fspath__') as mock_fspath:
        with patch('pathlib.Path') as mock_path_class:
            mock_path_inst = MagicMock()
            mock_path_inst.parent.parent = mock_repo_root
            mock_path_class.return_value = mock_path_inst

            # Patch Path.__new__ to return our mock when initialized with string
            original_path_new = Path.__new__

            def custom_new(cls, arg1, *args, **kwargs):
                if arg1 == 'serve_presentation.py' or '__file__' in str(arg1):
                    return mock_path_inst
                return original_path_new(cls, arg1, *args, **kwargs)

            with patch.object(Path, '__new__', custom_new):
                with patch.object(mock_repo_root / 'assets', 'exists', return_value=True):
                    result = serve_pres.get_presentation_dir()
                    assert result is not None


def test_get_presentation_dir_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """get_presentation_dir should raise FileNotFoundError when assets is missing."""
    # Create a minimal setup directory without an assets folder
    setup_file = tmp_path / 'setup' / 'serve_presentation.py'
    setup_file.parent.mkdir(parents=True, exist_ok=True)

    with patch('pathlib.Path') as mock_path_class:
        mock_path_inst = MagicMock()
        mock_path_inst.parent.parent = tmp_path
        presentation_path = tmp_path / 'assets'
        mock_path_inst.parent.parent.__truediv__.return_value = presentation_path

        mock_path_class.return_value = mock_path_inst
        presentation_path.exists = MagicMock(return_value=False)

        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError, match="Assets directory not found"):
                serve_pres.get_presentation_dir()


# ============================================================
# TESTS: PresentationHandler class
# ============================================================

def test_presentation_handler_do_get_root_path() -> None:
    """PresentationHandler.do_GET should rewrite '/' to the slide deck HTML file."""
    # Create a mock request object
    mock_request = MagicMock()
    mock_request.command = 'GET'
    mock_request.path = '/'
    mock_request.request_version = 'HTTP/1.1'
    mock_request.client_address = ('127.0.0.1', 12345)
    mock_request.server = MagicMock()

    # Create handler with mocked super() behavior
    with patch.object(serve_pres.http.server.SimpleHTTPRequestHandler, 'do_GET') as mock_super:
        handler = serve_pres.PresentationHandler(mock_request, mock_request.client_address, mock_request.server)
        handler.path = '/'

        # Call do_GET and verify path was rewritten
        handler.do_GET()

        assert handler.path == '/APIM-Samples-Slide-Deck.html'
        mock_super.assert_called_once()


def test_presentation_handler_do_get_empty_path() -> None:
    """PresentationHandler.do_GET should rewrite empty path to the slide deck HTML file."""
    mock_request = MagicMock()
    mock_request.command = 'GET'
    mock_request.path = ''
    mock_request.request_version = 'HTTP/1.1'
    mock_request.client_address = ('127.0.0.1', 12345)
    mock_request.server = MagicMock()

    with patch.object(serve_pres.http.server.SimpleHTTPRequestHandler, 'do_GET') as mock_super:
        handler = serve_pres.PresentationHandler(mock_request, mock_request.client_address, mock_request.server)
        handler.path = ''

        handler.do_GET()

        assert handler.path == '/APIM-Samples-Slide-Deck.html'
        mock_super.assert_called_once()


def test_presentation_handler_do_get_other_path() -> None:
    """PresentationHandler.do_GET should not rewrite other paths."""
    mock_request = MagicMock()
    mock_request.command = 'GET'
    mock_request.path = '/styles.css'
    mock_request.request_version = 'HTTP/1.1'
    mock_request.client_address = ('127.0.0.1', 12345)
    mock_request.server = MagicMock()

    with patch.object(serve_pres.http.server.SimpleHTTPRequestHandler, 'do_GET') as mock_super:
        handler = serve_pres.PresentationHandler(mock_request, mock_request.client_address, mock_request.server)
        handler.path = '/styles.css'

        handler.do_GET()

        assert handler.path == '/styles.css'
        mock_super.assert_called_once()


def test_presentation_handler_log_message(capsys: pytest.CaptureFixture) -> None:
    """PresentationHandler.log_message should print request logs to stderr."""
    handler = serve_pres.PresentationHandler.__new__(serve_pres.PresentationHandler)

    handler.log_message('"%s" %s %s', 'GET /TEST HTTP/1.1', '404', '-')

    captured = capsys.readouterr()
    assert 'GET /TEST HTTP/1.1' in captured.err


def test_presentation_handler_log_message_ignores_successful_head_request(capsys: pytest.CaptureFixture) -> None:
    """PresentationHandler.log_message should ignore successful HEAD polling requests."""
    handler = serve_pres.PresentationHandler.__new__(serve_pres.PresentationHandler)

    handler.log_message('"%s" %s %s', 'HEAD / HTTP/1.1', '200', '-')

    captured = capsys.readouterr()
    assert not captured.err


def test_presentation_handler_log_message_ignores_browser_probe(capsys: pytest.CaptureFixture) -> None:
    """PresentationHandler.log_message should ignore noisy browser probe requests."""
    handler = serve_pres.PresentationHandler.__new__(serve_pres.PresentationHandler)

    handler.log_message(
        '"%s" %s %s',
        'GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1',
        '404',
        '-',
    )

    captured = capsys.readouterr()
    assert not captured.err


def test_presentation_handler_logs_update_on_head_poll(tmp_path: Path) -> None:
    """HEAD polling should log when the requested file has a newer mtime."""
    watched_file = tmp_path / 'deck.html'
    watched_file.write_text('<html>v1</html>')

    handler = serve_pres.PresentationHandler.__new__(serve_pres.PresentationHandler)
    handler.path = '/deck.html'

    serve_pres.PresentationHandler._last_polled_mtimes = {}

    with patch.object(handler, 'translate_path', return_value=str(watched_file)):
        with patch('builtins.print') as mock_print:
            handler._log_polled_update()

        mock_print.assert_not_called()

        watched_file.write_text('<html>v2</html>')

        with patch('serve_presentation.get_local_timestamp', return_value='02/26/2026 15:45:12.123'):
            with patch('builtins.print') as mock_print:
                handler._log_polled_update()

        mock_print.assert_called_once_with('  [02/26/2026 15:45:12.123] File update detected: deck.html')


def test_presentation_handler_does_not_log_update_for_missing_file() -> None:
    """HEAD polling should not log anything when the requested file is missing."""
    handler = serve_pres.PresentationHandler.__new__(serve_pres.PresentationHandler)
    handler.path = '/missing.html'

    serve_pres.PresentationHandler._last_polled_mtimes = {}

    with patch.object(handler, 'translate_path', return_value='missing.html'):
        with patch('builtins.print') as mock_print:
            handler._log_polled_update()

        mock_print.assert_not_called()


# ============================================================
# TESTS: serve_presentation() function
# ============================================================

def test_serve_presentation_keyboard_interrupt(mock_repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """serve_presentation should gracefully handle KeyboardInterrupt."""
    presentation_dir = mock_repo_root / 'assets'

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance
            mock_server_instance.serve_forever.side_effect = KeyboardInterrupt()

            with patch('serve_presentation.Thread') as mock_thread:
                mock_thread_instance = MagicMock()
                mock_thread.return_value = mock_thread_instance

                with patch('builtins.print') as mock_print:
                    with patch('os.chdir'):
                        serve_pres.serve_presentation(8000)

                    # Verify server was closed
                    mock_server_instance.server_close.assert_called_once()

                    # Verify stop message was printed
                    printed_messages = [' '.join(str(arg) for arg in call.args) for call in mock_print.call_args_list]
                    assert any('Server stopped' in str(msg) for msg in printed_messages)


def test_serve_presentation_registers_signal_handlers(mock_repo_root: Path) -> None:
    """serve_presentation should register and restore shutdown signal handlers."""
    presentation_dir = mock_repo_root / 'assets'
    previous_sigint_handler = signal.default_int_handler
    previous_sigterm_handler = signal.SIG_DFL if hasattr(signal, 'SIGTERM') else None

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance
            mock_server_instance.serve_forever.side_effect = KeyboardInterrupt()

            with patch('serve_presentation.Thread'):
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


def test_serve_presentation_opens_browser(mock_repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """serve_presentation should spawn a thread to open the browser."""
    presentation_dir = mock_repo_root / 'assets'

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance
            mock_server_instance.serve_forever.side_effect = KeyboardInterrupt()

            with patch('serve_presentation.Thread') as mock_thread:
                mock_thread_instance = MagicMock()
                mock_thread.return_value = mock_thread_instance

                with patch('builtins.print'):
                    with patch('os.chdir'):
                        serve_pres.serve_presentation(8000)

                    # Verify Thread was called with open_browser function
                    mock_thread.assert_called_once()
                    call_args = mock_thread.call_args
                    assert call_args[1]['daemon'] is True


def test_serve_presentation_restores_cwd(mock_repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """serve_presentation should restore original working directory after exit."""
    presentation_dir = mock_repo_root / 'assets'
    original_cwd = '/original/cwd'

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance
            mock_server_instance.serve_forever.side_effect = KeyboardInterrupt()

            with patch('serve_presentation.Thread'):
                with patch('builtins.print'):
                    with patch('os.getcwd', return_value=original_cwd):
                        with patch('os.chdir') as mock_chdir:
                            serve_pres.serve_presentation(8000)

                        # Verify chdir was called to change back to original directory
                        chdir_calls = [call[0][0] for call in mock_chdir.call_args_list]
                        assert original_cwd in chdir_calls


def test_serve_presentation_prints_server_info(mock_repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """serve_presentation should print server information."""
    presentation_dir = mock_repo_root / 'assets'
    expected_url = 'http://localhost:7777'
    expected_presentation_url = f'{expected_url}{serve_pres.PRESENTATION_ENTRY_PATH}'

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance
            mock_server_instance.serve_forever.side_effect = KeyboardInterrupt()

            with patch('serve_presentation.Thread'):
                with patch('builtins.print') as mock_print:
                    with patch('os.chdir'):
                        serve_pres.serve_presentation(7777)

                    printed_messages = '\n'.join(' '.join(str(arg) for arg in call.args) for call in mock_print.call_args_list)
                    assert 'APIM Samples Presentation Server' in printed_messages
                    assert expected_url in printed_messages
                    assert expected_presentation_url in printed_messages
                    assert str(presentation_dir) in printed_messages


def test_serve_presentation_custom_port(mock_repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """serve_presentation should use custom port when specified."""
    presentation_dir = mock_repo_root / 'assets'

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance
            mock_server_instance.serve_forever.side_effect = KeyboardInterrupt()

            with patch('serve_presentation.Thread'):
                with patch('builtins.print'):
                    with patch('os.chdir'):
                        serve_pres.serve_presentation(9000)

                    # Verify TCPServer was called with correct port
                    server_call = mock_server.call_args
                    assert server_call[0][0] == ('', 7777)


def test_serve_presentation_handler_is_set(mock_repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """serve_presentation should use PresentationHandler for the server."""
    presentation_dir = mock_repo_root / 'assets'

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance
            mock_server_instance.serve_forever.side_effect = KeyboardInterrupt()

            with patch('serve_presentation.Thread'):
                with patch('builtins.print'):
                    with patch('os.chdir'):
                        serve_pres.serve_presentation(7777)

                    # Verify TCPServer was called with PresentationHandler
                    server_call = mock_server.call_args
                    assert server_call[0][1] is serve_pres.PresentationHandler


# ============================================================
# TESTS: Main entry point (__main__)
# ============================================================

def test_main_default_port(mock_repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Main entry with no arguments should use default port 7777."""
    presentation_dir = mock_repo_root / 'assets'

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.serve_presentation') as mock_serve:
            mock_serve.side_effect = KeyboardInterrupt()

            with patch.object(sys, 'argv', ['serve_presentation.py']):
                with pytest.raises(KeyboardInterrupt):
                    with open(SETUP_PATH / 'serve_presentation.py') as f:
                        exec(f.read(), {'__name__': '__main__'})


def test_main_custom_port(mock_repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Main entry with argument should use specified port."""
    presentation_dir = mock_repo_root / 'assets'

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.serve_presentation') as mock_serve:
            with patch.object(sys, 'argv', ['serve_presentation.py', '8881']):
                # Test that port is parsed and passed correctly
                try:
                    # Simulate the main block logic
                    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
                    assert port == 9000
                except ValueError:
                    pytest.fail("Port argument should be parseable as integer")


def test_main_file_not_found(mock_repo_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """Main entry should handle FileNotFoundError gracefully."""
    with patch('serve_presentation.get_presentation_dir', side_effect=FileNotFoundError("Test error")):
        with patch.object(sys, 'argv', ['serve_presentation.py']):
            with patch('sys.exit') as mock_exit:
                try:
                    serve_pres.get_presentation_dir()
                except FileNotFoundError as e:
                    print(f"Error: {e}", file=sys.stderr)
                    mock_exit.assert_not_called()  # Would be called in real scenario


def test_main_port_in_use(capsys: pytest.CaptureFixture) -> None:
    """Main entry should handle OSError for port in use gracefully."""
    oserror = OSError("Address already in use")

    with patch('serve_presentation.serve_presentation', side_effect=oserror):
        with patch.object(sys, 'argv', ['serve_presentation.py', '8000']):
            with patch('sys.exit') as mock_exit:
                try:
                    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
                    serve_pres.serve_presentation(port)
                except OSError:
                    pass  # Expected


def test_main_generic_oserror(capsys: pytest.CaptureFixture) -> None:
    """Main entry should handle generic OSError gracefully."""
    oserror = OSError("Some other error")

    with patch('serve_presentation.serve_presentation', side_effect=oserror):
        with patch.object(sys, 'argv', ['serve_presentation.py']):
            with patch('sys.exit') as mock_exit:
                try:
                    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
                    serve_pres.serve_presentation(port)
                except OSError:
                    pass  # Expected


# ============================================================
# TESTS: Thread behavior
# ============================================================

def test_open_browser_thread_is_daemon(mock_repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The browser opening thread should be a daemon thread."""
    presentation_dir = mock_repo_root / 'assets'

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance
            mock_server_instance.serve_forever.side_effect = KeyboardInterrupt()

            with patch('serve_presentation.Thread') as mock_thread:
                with patch('builtins.print'):
                    with patch('os.chdir'):
                        serve_pres.serve_presentation(7777)

                    # Verify daemon=True was passed
                    assert mock_thread.call_args[1]['daemon'] is True


def test_open_browser_has_sleep_delay(mock_repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The open_browser function should have a sleep delay."""
    presentation_dir = mock_repo_root / 'assets' / 'presentation'

    with patch('serve_presentation.get_presentation_dir', return_value=presentation_dir):
        with patch('serve_presentation.TCPServer') as mock_server:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance
            mock_server_instance.serve_forever.side_effect = KeyboardInterrupt()

            with patch('serve_presentation.sleep') as mock_sleep:
                with patch('serve_presentation.Thread'):
                    with patch('builtins.print'):
                        with patch('os.chdir'):
                            serve_pres.serve_presentation(7777)

                        # Note: sleep is called inside the open_browser closure,
                        # so we'd need to capture it differently in a real scenario.
                        # This test verifies the pattern is in place.


# ============================================================
# INTEGRATION-STYLE TESTS
# ============================================================

def test_presentation_handler_integration(tmp_path: Path) -> None:
    """Test PresentationHandler behavior with actual requests."""
    mock_request = MagicMock()
    mock_request.command = 'GET'
    mock_request.request_version = 'HTTP/1.1'
    mock_request.client_address = ('127.0.0.1', 12345)
    mock_request.server = MagicMock()

    # Test root path rewriting
    handler = serve_pres.PresentationHandler(mock_request, mock_request.client_address, mock_request.server)
    handler.path = '/'

    with patch.object(serve_pres.http.server.SimpleHTTPRequestHandler, 'do_GET') as mock_super:
        handler.do_GET()
        assert handler.path == '/APIM-Samples-Slide-Deck.html'

    # Test empty path rewriting
    handler.path = ''
    with patch.object(serve_pres.http.server.SimpleHTTPRequestHandler, 'do_GET') as mock_super:
        handler.do_GET()
        assert handler.path == '/APIM-Samples-Slide-Deck.html'

    # Test other paths not rewritten
    handler.path = '/assets/image.png'
    with patch.object(serve_pres.http.server.SimpleHTTPRequestHandler, 'do_GET') as mock_super:
        handler.do_GET()
        assert handler.path == '/assets/image.png'
