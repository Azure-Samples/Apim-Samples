#!/usr/bin/env python3
"""Serve the APIM Samples presentation with auto-browser launch."""

import sys
from datetime import datetime
from pathlib import Path

# APIM Samples imports
from dev_server import QuietRequestHandler, serve_directory

# Ensure UTF-8 encoding for console output on Windows
if sys.platform == 'win32':  # pragma: no cover
    sys.stdout.reconfigure(encoding='utf-8')


PRESENTATION_ENTRY_PATH = '/APIM-Samples-Slide-Deck.html'


def get_local_timestamp() -> str:
    """Return a local timestamp as mm/dd/yyyy hh:mm:ss.mmm."""
    current_time = datetime.now().astimezone()
    return f'{current_time:%m/%d/%Y %H:%M:%S}.{current_time.microsecond // 1000:03d}'


def get_presentation_dir():
    """Get the assets directory path."""
    repo_root = Path(__file__).parent.parent
    assets_dir = repo_root / 'assets'
    if not assets_dir.exists():
        raise FileNotFoundError(f'Assets directory not found: {assets_dir}')
    return assets_dir


class PresentationHandler(QuietRequestHandler):
    """HTTP handler that serves the presentation."""

    _last_polled_mtimes: dict[str, float] = {}
    _log_non_http_status = False

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


def serve_presentation(port: int = 7777) -> None:
    """Start the HTTP server and open browser."""
    serve_directory(
        get_presentation_dir(),
        PresentationHandler,
        port,
        title='APIM Samples Presentation Server',
        links=(('URL', ''), ('Presentation URL', PRESENTATION_ENTRY_PATH)),
        browser_path=PRESENTATION_ENTRY_PATH,
    )


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
