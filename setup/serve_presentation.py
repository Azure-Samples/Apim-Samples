#!/usr/bin/env python3
"""Serve the APIM Samples presentation with auto-browser launch."""

import http.server
import os
import signal
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from socketserver import TCPServer
from threading import Thread, current_thread, main_thread
from time import sleep

# Ensure UTF-8 encoding for console output on Windows
if sys.platform == 'win32':  # pragma: no cover
    sys.stdout.reconfigure(encoding='utf-8')


PRESENTATION_ENTRY_PATH = '/APIM-Samples-Slide-Deck.html'


def get_local_timestamp() -> str:
    """Return a local timestamp as mm/dd/yyyy hh:mm:ss.mmm."""
    current_time = datetime.now().astimezone()
    return f'{current_time:%m/%d/%Y %H:%M:%S}.{current_time.microsecond // 1000:03d}'


def print_shutdown_message() -> None:
    """Print a consistent shutdown message for the presentation server."""
    print('\n\n✓ Server stopped', flush=True)


def get_presentation_dir():
    """Get the assets directory path."""
    repo_root = Path(__file__).parent.parent
    assets_dir = repo_root / 'assets'
    if not assets_dir.exists():
        raise FileNotFoundError(f'Assets directory not found: {assets_dir}')
    return assets_dir


class PresentationHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that serves the presentation."""

    _last_polled_mtimes: dict[str, float] = {}
    _ignored_log_path_prefixes = ('/.well-known/appspecific/',)

    def _rewrite_path(self):
        """Rewrite root path to presentation file.

        Also strips the leading /assets/ prefix from paths such as
        /assets/site.webmanifest and /assets/favicon-*.png.  The HTML file
        uses ./assets/... references that resolve correctly on the exported
        GitHub-Pages site (where the deck sits next to an assets/ folder),
        but when served locally from the assets/ directory itself those
        references would point one level too deep.  Stripping the prefix
        makes them resolve to the correct files without modifying the HTML.
        """
        if self.path in {'/', ''}:
            self.path = PRESENTATION_ENTRY_PATH
        elif self.path.startswith('/assets/'):
            self.path = self.path[len('/assets') :]

    def do_GET(self):
        """Handle GET requests."""
        self._rewrite_path()
        return super().do_GET()

    def do_HEAD(self):
        """Handle HEAD requests (for live reload with Last-Modified header)."""
        self._rewrite_path()
        self._log_polled_update()
        # Use send_head() which properly sets Last-Modified header
        f = self.send_head()
        if f:
            f.close()

    def _log_polled_update(self):
        """Log when polling notices that a served file has been updated."""
        file_path = Path(self.translate_path(self.path))
        if not file_path.exists() or not file_path.is_file():
            return

        current_mtime = file_path.stat().st_mtime
        file_key = str(file_path.resolve())
        previous_mtime = self._last_polled_mtimes.get(file_key)

        if previous_mtime is not None and current_mtime > previous_mtime:
            rel_path = self.path.lstrip('/') or file_path.name
            print(f'  [{get_local_timestamp()}] File update detected: {rel_path}', flush=True)

        self._last_polled_mtimes[file_key] = current_mtime

    @classmethod
    def _should_ignore_log_request(cls, request_line: str) -> bool:
        """Suppress noisy browser-originated probes that are not actionable."""
        request_parts = request_line.split()
        if len(request_parts) < 2:
            return False

        request_path = request_parts[1]
        return request_path.startswith(cls._ignored_log_path_prefixes)

    def log_message(self, format, *args):
        """Customize logging."""
        request_line = str(args[0]) if args else ''
        if self._should_ignore_log_request(request_line):
            return

        status_code = str(args[1]) if len(args) > 1 else ''

        # Keep successful polling and file-serving requests quiet.
        if status_code.isdigit() and int(status_code) < 400:
            return

        if 'HTTP' in request_line:
            print(f'  {format % args}', file=sys.stderr)


def serve_presentation(port: int = 7777):
    """Start the HTTP server and open browser."""
    pres_dir = get_presentation_dir()
    httpd = None
    shutdown_message_printed = False
    previous_signal_handlers: dict[int, object] = {}

    def print_shutdown_once() -> None:
        """Ensure the shutdown message is only printed once."""
        nonlocal shutdown_message_printed
        if shutdown_message_printed:
            return

        print_shutdown_message()
        shutdown_message_printed = True

    def handle_shutdown_signal(signum, frame) -> None:
        """Handle external shutdown signals with a visible terminal message."""
        del signum, frame
        print_shutdown_once()
        raise KeyboardInterrupt

    # Change to presentation directory
    original_dir = os.getcwd()
    os.chdir(pres_dir)

    try:
        if current_thread() is main_thread():
            handled_signals = [signal.SIGINT]
            if hasattr(signal, 'SIGTERM'):  # pragma: no branch
                handled_signals.append(signal.SIGTERM)

            for handled_signal in handled_signals:
                previous_signal_handlers[handled_signal] = signal.getsignal(handled_signal)
                signal.signal(handled_signal, handle_shutdown_signal)

        server_address = ('127.0.0.1', port)
        httpd = TCPServer(server_address, PresentationHandler)

        # URL to open
        url = f'http://localhost:{port}'
        presentation_url = f'{url}{PRESENTATION_ENTRY_PATH}'

        # Print server info
        print('\n✨ APIM Samples Presentation Server')
        print(f'   Serving from       : {pres_dir}')
        print(f'   URL                : {url}')
        print(f'   Presentation URL   : {presentation_url}')
        print()
        print('   🌐 Browser opening in 1 second...')
        print()
        print('   To stop the server : Press Ctrl+C')
        print(flush=True)

        # Open browser in a background thread
        def open_browser():
            sleep(1)  # Give server time to start
            print(f'   ✓ Opening browser to {presentation_url}', flush=True)
            webbrowser.open(presentation_url)

        Thread(target=open_browser, daemon=True).start()

        # Run the server in a daemon thread so the main thread remains free.
        # On Windows, serve_forever() blocks inside select() which cannot be
        # interrupted by Ctrl+C.  Keeping the main thread in a sleep() loop
        # lets Python's signal machinery raise KeyboardInterrupt reliably.
        server_thread = Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

        while server_thread.is_alive():
            sleep(1)

    except KeyboardInterrupt:
        print_shutdown_once()
    finally:
        for handled_signal, previous_handler in previous_signal_handlers.items():
            signal.signal(handled_signal, previous_handler)

        os.chdir(original_dir)
        if httpd is not None:
            try:
                httpd.shutdown()
            except Exception:  # noqa: BLE001
                pass
            try:
                httpd.server_close()
            except Exception:  # noqa: BLE001
                pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7777
    try:
        serve_presentation(port)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        if 'Address already in use' in str(e):
            print(f'Error: Port {port} is already in use', file=sys.stderr)
            print('Try a different port: python serve_presentation.py 7778', file=sys.stderr)
        else:
            print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
