#!/usr/bin/env python3
"""Stage and serve the APIM Samples GitHub Pages landing page locally.

This script replicates the 'Stage site artifact' step from
.github/workflows/github-pages.yml into a fresh _site/ directory,
builds a self-contained slide deck alongside index.html, and
serves the result with an auto-opening browser.

The staging logic here is the single local source of truth. If the
workflow's staging step changes, update stage_site() to match.
"""

import http.server
import os
import shutil
import signal
import sys
import webbrowser
from pathlib import Path
from socketserver import TCPServer
from threading import Thread, current_thread, main_thread
from time import sleep

from export_presentation import inline_images, strip_live_reload

# Ensure UTF-8 encoding for console output on Windows
if sys.platform == 'win32':  # pragma: no cover
    sys.stdout.reconfigure(encoding='utf-8')


REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / 'docs'
ASSETS_DIR = REPO_ROOT / 'assets'
SITE_DIR = REPO_ROOT / '_site'

# Mirrors the cp lines in .github/workflows/github-pages.yml.
# source filename (under assets/diagrams/) -> staged slug filename
DIAGRAM_SLUG_MAP = {
    'Simple API Management Architecture.svg': 'simple-apim.svg',
    'API Management & Container Apps Architecture.svg': 'apim-aca.svg',
    'Azure Front Door, API Management & Container Apps Architecture.svg': 'afd-apim-pe.svg',
    'Azure Application Gateway, API Management & Container Apps Architecture.svg': 'appgw-apim-pe.svg',
    'Azure Application Gateway, API Management & Container Apps Architecture VNet.svg': 'appgw-apim.svg',
}

# Mirrors the favicon block in .github/workflows/github-pages.yml.
# All six land flat in _site/assets/. site.webmanifest resolves its icon
# src paths relative to the manifest URL, so the android-chrome PNGs must
# sit as siblings of the manifest file.
FAVICON_FILES = (
    'apple-touch-icon.png',
    'favicon-32x32.png',
    'favicon-16x16.png',
    'site.webmanifest',
    'android-chrome-192x192.png',
    'android-chrome-512x512.png',
)

SLIDE_DECK_SOURCE = ASSETS_DIR / 'APIM-Samples-Slide-Deck.html'
SLIDE_DECK_STAGED = 'slide-deck.html'


def _copy(src: Path, dest: Path) -> None:
    """Copy a file and print a short confirmation."""
    shutil.copy2(src, dest)
    print(f'  ✓ {dest.relative_to(SITE_DIR)}')


def stage_site() -> None:
    """Replicate the workflow's staging step into a fresh _site/ directory."""
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)

    diagrams_out = SITE_DIR / 'assets' / 'diagrams'
    diagrams_out.mkdir(parents=True)

    print(f'📦 Staging site into {SITE_DIR.relative_to(REPO_ROOT)}/\n')

    # Page + crawler files
    _copy(DOCS_DIR / 'index.html', SITE_DIR / 'index.html')
    _copy(DOCS_DIR / 'styles.css', SITE_DIR / 'styles.css')
    _copy(DOCS_DIR / 'robots.txt', SITE_DIR / 'robots.txt')
    _copy(DOCS_DIR / 'sitemap.xml', SITE_DIR / 'sitemap.xml')

    # Brand assets (renamed to match index.html <img src> paths)
    _copy(ASSETS_DIR / 'APIM-Samples.png', SITE_DIR / 'assets' / 'apim-samples-logo.png')

    # Favicon set + web app manifest
    for name in FAVICON_FILES:
        _copy(ASSETS_DIR / name, SITE_DIR / 'assets' / name)

    # Architecture diagrams (slugified to match index.html <img src> paths)
    for src_name, slug in DIAGRAM_SLUG_MAP.items():
        _copy(ASSETS_DIR / 'diagrams' / src_name, diagrams_out / slug)

    (SITE_DIR / '.nojekyll').touch()


def build_slide_deck() -> None:
    """Inline the slide deck's images and stage it as a self-contained file.

    Reuses the same inlining logic as setup/export_presentation.py so
    the locally staged deck is identical to the one the 'e' menu option
    writes to build/.
    """
    if not SLIDE_DECK_SOURCE.exists():
        print(f'  ⚠️  Slide deck not found at {SLIDE_DECK_SOURCE}, skipping')

        return

    html = SLIDE_DECK_SOURCE.read_text(encoding='utf-8')
    html = inline_images(html, ASSETS_DIR)
    html = strip_live_reload(html)

    out = SITE_DIR / SLIDE_DECK_STAGED
    out.write_text(html, encoding='utf-8')

    size_mb = out.stat().st_size / (1024 * 1024)
    print(f'  ✓ {out.relative_to(SITE_DIR)} (self-contained, {size_mb:.2f} MB)')


def cleanup_site() -> None:
    """Remove _site/ if we created it. Best-effort."""
    try:
        if SITE_DIR.exists():
            shutil.rmtree(SITE_DIR)
            print(f'\n🧹 Removed {SITE_DIR.relative_to(REPO_ROOT)}/')
    except OSError:  # noqa: BLE001  # pragma: no cover
        pass


class WebsiteHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that stays quiet on success and suppresses browser noise."""

    _ignored_log_path_prefixes = ('/.well-known/appspecific/',)

    @classmethod
    def _should_ignore_log_request(cls, request_line: str) -> bool:
        """Suppress noisy browser-originated probes that are not actionable."""
        parts = request_line.split()
        if len(parts) < 2:
            return False

        return parts[1].startswith(cls._ignored_log_path_prefixes)

    def log_message(self, format, *args):
        """Print only non-2xx/3xx responses, and never browser probes."""
        request_line = str(args[0]) if args else ''
        if self._should_ignore_log_request(request_line):
            return

        status_code = str(args[1]) if len(args) > 1 else ''
        if status_code.isdigit() and int(status_code) < 400:
            return

        if 'HTTP' in request_line or status_code:
            print(f'  {format % args}', file=sys.stderr)


def serve_website(port: int = 7800) -> None:
    """Stage the site, start an HTTP server, and open the browser."""
    stage_site()

    print()
    build_slide_deck()

    original_dir = os.getcwd()
    httpd = None
    shutdown_printed = False
    previous_handlers: dict[int, object] = {}

    def print_shutdown_once() -> None:
        nonlocal shutdown_printed
        if shutdown_printed:
            return
        print('\n\n✓ Server stopped', flush=True)
        shutdown_printed = True

    def handle_shutdown_signal(signum, frame) -> None:
        del signum, frame
        print_shutdown_once()
        raise KeyboardInterrupt

    os.chdir(SITE_DIR)

    try:
        if current_thread() is main_thread():
            signals_to_handle = [signal.SIGINT]
            if hasattr(signal, 'SIGTERM'):  # pragma: no branch
                signals_to_handle.append(signal.SIGTERM)

            for sig in signals_to_handle:
                previous_handlers[sig] = signal.getsignal(sig)
                signal.signal(sig, handle_shutdown_signal)

        httpd = TCPServer(('127.0.0.1', port), WebsiteHandler)

        url = f'http://localhost:{port}'
        print('\n✨ APIM Samples Website Preview')
        print(f'   Serving from       : {SITE_DIR}')
        print(f'   Landing page       : {url}/')
        print(f'   Slide deck         : {url}/{SLIDE_DECK_STAGED}')
        print()
        print('   🌐 Browser opening in 1 second...')
        print()
        print('   To stop the server : Press Ctrl+C')
        print(flush=True)

        def open_browser() -> None:
            sleep(1)
            print(f'   ✓ Opening browser to {url}/')
            webbrowser.open(f'{url}/')

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
        for sig, prev in previous_handlers.items():
            signal.signal(sig, prev)

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

        cleanup_site()


if __name__ == '__main__':  # pragma: no cover
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7800
    try:
        serve_website(port)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        if 'Address already in use' in str(e):
            print(f'Error: Port {port} is already in use', file=sys.stderr)
            print('Try a different port: python serve_website.py 7801', file=sys.stderr)
        else:
            print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
