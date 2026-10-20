"""Shared HTTP logging and lifecycle for local repository previews."""

import http.server
import os
import signal
import sys
import webbrowser
from pathlib import Path
from socketserver import TCPServer
from threading import Thread, current_thread, main_thread
from time import sleep


class QuietRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Suppress successful requests and browser probes, but retain errors."""

    _ignored_log_path_prefixes = ('/.well-known/appspecific/',)
    _log_non_http_status = True

    @classmethod
    def _should_ignore_log_request(cls, request_line: str) -> bool:
        """Identify browser probes that do not need a terminal message."""
        parts = request_line.split()
        if len(parts) < 2:
            return False

        return parts[1].startswith(cls._ignored_log_path_prefixes)

    def log_message(self, format: str, *args: object) -> None:
        """Log unsuccessful requests without routine polling noise."""
        request_line = str(args[0]) if args else ''
        if self._should_ignore_log_request(request_line):
            return

        status_code = str(args[1]) if len(args) > 1 else ''
        if status_code.isdigit() and int(status_code) < 400:
            return

        if 'HTTP' in request_line or (self._log_non_http_status and status_code):
            print(f'  {format % args}', file=sys.stderr)


def serve_directory(
    directory: Path,
    handler: type[http.server.SimpleHTTPRequestHandler],
    port: int,
    *,
    title: str,
    links: tuple[tuple[str, str], ...],
    browser_path: str,
) -> None:
    """Serve a local preview and restore process state on exit."""
    original_dir = os.getcwd()
    httpd = None
    server_started = False
    shutdown_printed = False
    previous_handlers = {}

    def print_shutdown_once() -> None:
        """Print one shutdown message across signal and interrupt handling."""
        nonlocal shutdown_printed
        if not shutdown_printed:
            print('\n\n✓ Server stopped', flush=True)
            shutdown_printed = True

    def handle_shutdown_signal(signum: int, frame: object) -> None:
        """Translate external shutdown signals into a normal interrupt."""
        print_shutdown_once()
        raise KeyboardInterrupt

    os.chdir(directory)
    try:
        if current_thread() is main_thread():
            signals_to_handle = [signal.SIGINT]
            if hasattr(signal, 'SIGTERM'):  # pragma: no branch
                signals_to_handle.append(signal.SIGTERM)

            for sig in signals_to_handle:
                previous_handlers[sig] = signal.getsignal(sig)
                signal.signal(sig, handle_shutdown_signal)

        httpd = TCPServer(('127.0.0.1', port), handler)
        url = f'http://localhost:{port}'
        browser_url = f'{url}{browser_path}'

        print(f'\n✨ {title}')
        print(f'   Serving from       : {directory}')
        for label, path in links:
            print(f'   {label:<19}: {url}{path}')
        print()
        print('   🌐 Browser opening in 1 second...')
        print()
        print('   To stop the server : Press Ctrl+C')
        print(flush=True)

        def open_browser() -> None:
            """Open the preview once the server has had time to start."""
            sleep(1)
            print(f'   ✓ Opening browser to {browser_url}', flush=True)
            webbrowser.open(browser_url)

        Thread(target=open_browser, daemon=True).start()

        # Windows cannot interrupt serve_forever's select on the main thread.
        server_thread = Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        server_started = True
        while server_thread.is_alive():
            sleep(1)
    except KeyboardInterrupt:
        print_shutdown_once()
    finally:
        try:
            if httpd is not None:
                try:
                    if server_started:
                        httpd.shutdown()
                except OSError as error:
                    print(f'Error stopping preview server: {error}', file=sys.stderr)
                finally:
                    try:
                        httpd.server_close()
                    except OSError as error:
                        print(f'Error closing preview server: {error}', file=sys.stderr)
        finally:
            try:
                for sig, previous_handler in previous_handlers.items():
                    signal.signal(sig, previous_handler)
            finally:
                os.chdir(original_dir)
