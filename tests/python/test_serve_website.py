"""Unit tests for serve_website module."""

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

# Ensure the setup folder is on sys.path so the module is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / 'setup'
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

serve_web = cast(ModuleType, importlib.import_module('serve_website'))


@pytest.fixture
def mock_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a minimal temp repo tree and point the module's path constants at it.

    All the module-level Path constants are monkeypatched so the real repo
    is never touched by these tests.
    """
    docs = tmp_path / 'docs'
    assets = tmp_path / 'assets'
    diagrams = assets / 'diagrams'
    diagrams.mkdir(parents=True)
    docs.mkdir()

    (docs / 'index.html').write_text('<html>index</html>')
    (docs / 'styles.css').write_text(':root { --brand-blue: #0078D4; }')
    (docs / 'robots.txt').write_text('User-agent: *')
    (docs / 'sitemap.xml').write_text('<urlset/>')

    (assets / 'APIM-Samples.png').write_bytes(b'png')
    for name in serve_web.FAVICON_FILES:
        (assets / name).write_bytes(b'x')

    for src_name in serve_web.DIAGRAM_SLUG_MAP:
        (diagrams / src_name).write_text('<svg/>')

    (assets / 'APIM-Samples-Slide-Deck.html').write_text('<html><body><img src="APIM-Samples.png"></body></html>')

    site = tmp_path / '_site'

    monkeypatch.setattr(serve_web, 'REPO_ROOT', tmp_path)
    monkeypatch.setattr(serve_web, 'DOCS_DIR', docs)
    monkeypatch.setattr(serve_web, 'ASSETS_DIR', assets)
    monkeypatch.setattr(serve_web, 'SITE_DIR', site)
    monkeypatch.setattr(serve_web, 'SLIDE_DECK_SOURCE', assets / 'APIM-Samples-Slide-Deck.html')

    return tmp_path


def _make_handler(path: str = '/') -> Any:
    """Create a handler instance without running the HTTP server base initializer."""
    handler = serve_web.WebsiteHandler.__new__(serve_web.WebsiteHandler)
    handler.path = path

    return handler


# ------------------------------
#    STAGING
# ------------------------------


def test_stage_site_layout(mock_repo: Path) -> None:
    """stage_site should replicate the workflow's artifact layout exactly."""
    serve_web.stage_site()

    site = mock_repo / '_site'
    assert (site / 'index.html').read_text() == '<html>index</html>'
    assert (site / 'styles.css').read_text() == ':root { --brand-blue: #0078D4; }'
    assert (site / 'robots.txt').exists()
    assert (site / 'sitemap.xml').exists()
    assert (site / '.nojekyll').exists()

    assert (site / 'assets' / 'apim-samples-logo.png').exists()
    for name in serve_web.FAVICON_FILES:
        assert (site / 'assets' / name).exists()

    for slug in serve_web.DIAGRAM_SLUG_MAP.values():
        assert (site / 'assets' / 'diagrams' / slug).exists()


def test_stage_site_removes_stale_tree(mock_repo: Path) -> None:
    """stage_site should clear any previous _site/ before staging fresh."""
    site = mock_repo / '_site'
    site.mkdir()
    stale = site / 'stale.txt'
    stale.write_text('old')

    serve_web.stage_site()

    assert not stale.exists()
    assert (site / 'index.html').exists()


def test_stage_site_missing_source_raises(mock_repo: Path) -> None:
    """stage_site should surface a FileNotFoundError when a source file is absent."""
    (mock_repo / 'docs' / 'robots.txt').unlink()

    with pytest.raises(FileNotFoundError):
        serve_web.stage_site()


def test_diagram_slug_map_matches_index_html() -> None:
    """Every slugged diagram filename must appear as an img src in docs/index.html.

    This guards the local preview against drift from the HTML. The
    equivalent workflow-side check lives in the HTML parse validator.
    """
    html = (PROJECT_ROOT / 'docs' / 'index.html').read_text(encoding='utf-8')

    for slug in serve_web.DIAGRAM_SLUG_MAP.values():
        assert f'./assets/diagrams/{slug}' in html, f'slug {slug} not referenced in index.html'


def test_index_html_references_stylesheet() -> None:
    """docs/index.html must reference ./styles.css via <link rel="stylesheet">.

    Guards against the stylesheet link being removed or the CSS being
    re-inlined without updating the staging steps.
    """
    html = (PROJECT_ROOT / 'docs' / 'index.html').read_text(encoding='utf-8')

    assert 'rel="stylesheet" href="./styles.css"' in html
    assert '<style>' not in html


def test_index_html_references_favicon_set() -> None:
    """docs/index.html must reference the full favicon set under ./assets/.

    Guards against the favicon <link> tags being removed or a path
    drifting away from the files staged by stage_site() and the workflow.
    The android-chrome PNGs are referenced inside site.webmanifest, not
    in the HTML, so they are not asserted here.
    """
    html = (PROJECT_ROOT / 'docs' / 'index.html').read_text(encoding='utf-8')

    assert 'href="./assets/apple-touch-icon.png"' in html
    assert 'href="./assets/favicon-32x32.png"' in html
    assert 'href="./assets/favicon-16x16.png"' in html
    assert 'href="./assets/site.webmanifest"' in html


# ------------------------------
#    SLIDE DECK
# ------------------------------


def test_build_slide_deck_inlines_images(mock_repo: Path) -> None:
    """build_slide_deck should stage a self-contained file with data URLs."""
    serve_web.stage_site()
    serve_web.build_slide_deck()

    out = mock_repo / '_site' / serve_web.SLIDE_DECK_STAGED
    assert out.exists()

    staged_html = out.read_text(encoding='utf-8')
    assert 'data:image/png;base64,' in staged_html
    assert 'src="APIM-Samples.png"' not in staged_html


def test_build_slide_deck_skips_when_missing(mock_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """build_slide_deck should warn and skip when the source deck is absent."""
    (mock_repo / 'assets' / 'APIM-Samples-Slide-Deck.html').unlink()
    serve_web.stage_site()

    serve_web.build_slide_deck()

    assert not (mock_repo / '_site' / serve_web.SLIDE_DECK_STAGED).exists()
    assert 'Slide deck not found' in capsys.readouterr().out


# ------------------------------
#    CLEANUP
# ------------------------------


def test_cleanup_site_removes_tree(mock_repo: Path) -> None:
    """cleanup_site should remove the staged directory if it exists."""
    site = mock_repo / '_site'
    site.mkdir()
    (site / 'index.html').write_text('x')

    serve_web.cleanup_site()

    assert not site.exists()


def test_cleanup_site_absent_is_noop(mock_repo: Path) -> None:
    """cleanup_site should be a no-op when _site/ does not exist."""
    serve_web.cleanup_site()  # must not raise


# ------------------------------
#    HANDLER LOG SUPPRESSION
# ------------------------------


def test_handler_suppresses_2xx(capsys: pytest.CaptureFixture[str]) -> None:
    """WebsiteHandler.log_message should stay silent for successful requests."""
    _make_handler().log_message('"%s" %s %s', 'GET / HTTP/1.1', '200', '-')

    assert not capsys.readouterr().err


def test_handler_logs_4xx(capsys: pytest.CaptureFixture[str]) -> None:
    """WebsiteHandler.log_message should print 4xx+ responses to stderr."""
    _make_handler().log_message('"%s" %s %s', 'GET /nope HTTP/1.1', '404', '-')

    assert 'GET /nope HTTP/1.1' in capsys.readouterr().err


def test_handler_suppresses_browser_probe(capsys: pytest.CaptureFixture[str]) -> None:
    """WebsiteHandler.log_message should ignore Chrome DevTools probes."""
    _make_handler().log_message(
        '"%s" %s %s',
        'GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1',
        '404',
        '-',
    )

    assert not capsys.readouterr().err


def test_handler_ignores_short_request_line() -> None:
    """Malformed request lines should not be treated as ignorable probes."""
    assert not serve_web.WebsiteHandler._should_ignore_log_request('MALFORMED')


def test_handler_ignores_non_http_message_without_status(capsys: pytest.CaptureFixture[str]) -> None:
    """Non-HTTP lines with no status code should stay quiet."""
    _make_handler().log_message('%s', 'background task completed')

    assert not capsys.readouterr().err


# ------------------------------
#    SERVE LIFECYCLE
# ------------------------------


def test_serve_website_keyboard_interrupt_cleans_up(mock_repo: Path) -> None:
    """serve_website should shut down gracefully and remove _site/ on Ctrl+C."""
    site = mock_repo / '_site'

    with patch('serve_website.TCPServer') as mock_server:
        mock_instance = MagicMock()
        mock_server.return_value = mock_instance
        mock_instance.serve_forever.side_effect = KeyboardInterrupt()

        with patch('serve_website.Thread'):
            with patch('serve_website.webbrowser'):
                with patch('builtins.print') as mock_print:
                    with patch('os.chdir'):
                        serve_web.serve_website(9999)

    mock_instance.server_close.assert_called_once()
    assert not site.exists()

    printed = [' '.join(str(a) for a in c.args) for c in mock_print.call_args_list]
    assert any('Server stopped' in m for m in printed)


def test_serve_website_survives_close_failure(mock_repo: Path) -> None:
    """serve_website should still clean up _site/ if server_close raises."""
    with patch('serve_website.TCPServer') as mock_server:
        mock_instance = MagicMock()
        mock_server.return_value = mock_instance
        mock_instance.serve_forever.side_effect = KeyboardInterrupt()
        mock_instance.server_close.side_effect = OSError('boom')

        with patch('serve_website.Thread'):
            with patch('serve_website.webbrowser'):
                with patch('builtins.print'):
                    with patch('os.chdir'):
                        serve_web.serve_website(9999)

    assert not (mock_repo / '_site').exists()
