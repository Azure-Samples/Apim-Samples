"""Unit tests for export_presentation module."""

import base64
import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

# Ensure the setup folder is on sys.path so the module is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / "setup"
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

export_pres = cast(ModuleType, importlib.import_module("export_presentation"))


# ============================================================
# TEST CONSTANTS - File Names & Paths
# ============================================================
# Directory structure
TEST_ASSETS_DIR = 'assets'
TEST_DIAGRAMS_DIR = 'diagrams'
TEST_BUILD_DIR = 'build'

# Presentation file
TEST_PRESENTATION_FILE = 'APIM-Samples-Slide-Deck.html'

# Image file names
TEST_PNG_FILENAME = 'logo.png'
TEST_JPG_FILENAME = 'photo.jpg'
TEST_JPEG_FILENAME = 'photo.jpeg'
TEST_SVG_FILENAME = 'diagram.svg'
TEST_GIF_FILENAME = 'animation.gif'
TEST_WEBP_FILENAME = 'modern.webp'
TEST_PNG_UPPERCASE = 'logo.PNG'
TEST_MISSING_PNG = 'missing.png'
TEST_NONEXISTENT_PNG = 'nonexistent.png'
TEST_SHARED_PNG = 'shared.png'

# SVG with directory path
TEST_SVG_PATH = f'{TEST_DIAGRAMS_DIR}/{TEST_SVG_FILENAME}'

# ============================================================
# TEST CONSTANTS - File Signatures & Content
# ============================================================
# Image file signatures (magic bytes)
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
JPEG_SIGNATURE = b'\xff\xd8\xff'
GIF_SIGNATURE = b'GIF89a'
WEBP_SIGNATURE = b'RIFF'

# Dummy content appended to signatures
TEST_CONTENT = b'test content'

# ============================================================
# TEST CONSTANTS - MIME Types
# ============================================================
MIME_PNG = 'image/png'
MIME_JPEG = 'image/jpeg'
MIME_SVG = 'image/svg+xml'
MIME_GIF = 'image/gif'
MIME_WEBP = 'image/webp'

# ============================================================
# TEST CONSTANTS - HTML Patterns & Attributes
# ============================================================
# HTML attributes
ALT_ATTR = 'alt'
CLASS_ATTR = 'class'
ID_ATTR = 'id'
SRC_ATTR = 'src'
HREF_ATTR = 'href'

# HTML attribute values
LOGO_ALT = 'Logo'
PHOTO_ALT = 'Photo'
DIAGRAM_ALT = 'Diagram'
MODERN_ALT = 'Modern'
MY_CLASS = 'my-class'
LOGO_ID = 'logo-img'

# Data URL prefix patterns
DATA_URL_PREFIX = 'data:'
BASE64_SUFFIX = ';base64,'

# Non-image file names (for regex exclusion tests)
APP_JS = 'app.js'
STYLES_CSS = 'styles.css'

# ============================================================
# TEST CONSTANTS - Numeric Values
# ============================================================
EXPECTED_IMAGES_COUNT = 3  # Number of images in multi-image test
EXPECTED_DATA_URLS_ONE = 1
MIN_BASE64_LENGTH = 0  # For validation


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def tmp_repo_structure(tmp_path: Path) -> dict:
    """Create a temporary repo structure with the slide deck under assets/."""
    # Create directory structure
    assets_dir = tmp_path / TEST_ASSETS_DIR
    assets_dir.mkdir()

    presentation_dir = assets_dir

    diagrams_dir = assets_dir / TEST_DIAGRAMS_DIR
    diagrams_dir.mkdir()

    build_dir = tmp_path / TEST_BUILD_DIR
    build_dir.mkdir()

    # Create sample image files
    png_file = presentation_dir / TEST_PNG_FILENAME
    png_file.write_bytes(PNG_SIGNATURE + TEST_CONTENT)

    jpg_file = presentation_dir / TEST_JPG_FILENAME
    jpg_file.write_bytes(JPEG_SIGNATURE + TEST_CONTENT)

    svg_file = diagrams_dir / TEST_SVG_FILENAME
    svg_file.write_text('<svg><circle r="5"/></svg>')

    gif_file = presentation_dir / TEST_GIF_FILENAME
    gif_file.write_bytes(GIF_SIGNATURE + TEST_CONTENT)

    webp_file = presentation_dir / TEST_WEBP_FILENAME
    webp_file.write_bytes(WEBP_SIGNATURE + TEST_CONTENT)

    # Create HTML presentation file
    html_file = presentation_dir / TEST_PRESENTATION_FILE
    html_content = f'''<!DOCTYPE html>
<html>
<head><title>Test Presentation</title></head>
<body>
  <img {SRC_ATTR}="{TEST_PNG_FILENAME}" {ALT_ATTR}="{LOGO_ALT}" />
  <img {SRC_ATTR}="{TEST_JPG_FILENAME}" {ALT_ATTR}="{PHOTO_ALT}" />
  <img {SRC_ATTR}="{TEST_SVG_PATH}" {ALT_ATTR}="{DIAGRAM_ALT}" />
  <a {HREF_ATTR}="{TEST_GIF_FILENAME}">Download GIF</a>
  <img {SRC_ATTR}="{TEST_WEBP_FILENAME}" {ALT_ATTR}="{MODERN_ALT}" />
  <img {SRC_ATTR}="{TEST_MISSING_PNG}" {ALT_ATTR}="Missing" />
</body>
</html>'''
    html_file.write_text(html_content)

    return {
        'tmp_path': tmp_path,
        'presentation_dir': presentation_dir,
        'diagrams_dir': diagrams_dir,
        'build_dir': build_dir,
        'png_file': png_file,
        'jpg_file': jpg_file,
        'svg_file': svg_file,
        'gif_file': gif_file,
        'webp_file': webp_file,
        'html_file': html_file,
    }


# ============================================================
# TESTS: get_repo_root()
# ============================================================

def test_get_repo_root_returns_path_object() -> None:
    """get_repo_root should return a Path object."""
    result = export_pres.get_repo_root()
    assert isinstance(result, Path)


def test_get_repo_root_points_to_project_root() -> None:
    """get_repo_root should return path pointing to project root."""
    result = export_pres.get_repo_root()
    # The setup file should be one level down from repo root
    assert (result / 'setup' / 'export_presentation.py').exists()


# ============================================================
# TESTS: inline_images() - Basic Functionality
# ============================================================

def test_inline_images_with_simple_filename(tmp_repo_structure: dict, capsys: pytest.CaptureFixture) -> None:
    """inline_images should inline simple filenames from base_dir."""
    html = '<img src="logo.png" alt="Logo" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])

    # Check that the result contains a data URL
    assert 'data:image/png;base64,' in result
    assert 'src="data:image/png;base64,' in result
    assert 'logo.png' not in result.split('src="')[1].split('"')[0]


def test_inline_images_with_directory_path(tmp_repo_structure: dict, capsys: pytest.CaptureFixture) -> None:
    """inline_images should inline paths with directory components."""
    html = '<img src="diagrams/diagram.svg" alt="Diagram" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])

    # Check that the result contains a data URL
    assert 'data:image/svg+xml;base64,' in result
    assert 'diagrams/diagram.svg' not in result.split('src="')[1].split('"')[0]


def test_inline_images_with_multiple_images(tmp_repo_structure: dict, capsys: pytest.CaptureFixture) -> None:
    """inline_images should inline multiple images in one HTML."""
    html = '''
    <img src="logo.png" alt="Logo" />
    <img src="diagrams/diagram.svg" alt="Diagram" />
    <img src="photo.jpg" alt="Photo" />
    '''
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])

    # All three images should be inlined
    assert result.count('data:image/') == 3
    assert 'data:image/png;base64,' in result
    assert 'data:image/svg+xml;base64,' in result
    assert 'data:image/jpeg;base64,' in result


def test_inline_images_with_href_attribute(tmp_repo_structure: dict, capsys: pytest.CaptureFixture) -> None:
    """inline_images should inline href attributes as well as src."""
    html = '<a href="animation.gif">Download</a>'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])

    assert 'data:image/gif;base64,' in result
    assert 'href="data:image/gif;base64,' in result


# ============================================================
# TESTS: inline_images() - Image Format Support
# ============================================================

def test_inline_images_png_format(tmp_repo_structure: dict) -> None:
    """inline_images should support PNG format with correct MIME type."""
    html = '<img src="logo.png" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])
    assert 'data:image/png;base64,' in result


def test_inline_images_jpg_format(tmp_repo_structure: dict) -> None:
    """inline_images should support JPG format with correct MIME type."""
    html = '<img src="photo.jpg" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])
    assert 'data:image/jpeg;base64,' in result


def test_inline_images_svg_format(tmp_repo_structure: dict) -> None:
    """inline_images should support SVG format with correct MIME type."""
    html = '<img src="diagrams/diagram.svg" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])
    assert 'data:image/svg+xml;base64,' in result


def test_inline_images_gif_format(tmp_repo_structure: dict) -> None:
    """inline_images should support GIF format with correct MIME type."""
    html = '<img src="animation.gif" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])
    assert 'data:image/gif;base64,' in result


def test_inline_images_webp_format(tmp_repo_structure: dict) -> None:
    """inline_images should support WebP format with correct MIME type."""
    html = '<img src="modern.webp" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])
    assert 'data:image/webp;base64,' in result


def test_inline_images_jpeg_extension(tmp_repo_structure: dict) -> None:
    """inline_images should support .jpeg extension."""
    jpeg_file = tmp_repo_structure['presentation_dir'] / 'photo.jpeg'
    jpeg_file.write_bytes(b'\xff\xd8\xff' + b'test jpeg content')

    html = '<img src="photo.jpeg" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])
    assert 'data:image/jpeg;base64,' in result


# ============================================================
# TESTS: inline_images() - Error Handling
# ============================================================

def test_inline_images_missing_file_returns_unchanged(tmp_repo_structure: dict, capsys: pytest.CaptureFixture) -> None:
    """inline_images should return original HTML unchanged if file not found."""
    html = '<img src="nonexistent.png" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])

    # Original HTML should be unchanged
    assert 'src="nonexistent.png"' in result
    # Should not have been converted to data URL
    assert 'data:image/png;base64,' not in result

    # Check warning was printed
    captured = capsys.readouterr()
    assert 'Warning' in captured.out or 'Warning' in captured.err or 'nonexistent.png' in captured.out


def test_inline_images_with_no_images(tmp_repo_structure: dict) -> None:
    """inline_images should return HTML unchanged if no images present."""
    html = '<p>Just some text</p>'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])

    assert result == html
    assert 'data:image/' not in result


def test_inline_images_mixed_existing_and_missing(tmp_repo_structure: dict, capsys: pytest.CaptureFixture) -> None:
    """inline_images should inline existing files while leaving missing ones."""
    html = '''
    <img src="logo.png" />
    <img src="missing.png" />
    '''
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])

    # Existing image should be inlined
    assert 'data:image/png;base64,' in result
    # Missing image should be unchanged
    assert 'src="missing.png"' in result


# ============================================================
# TESTS: inline_images() - Base64 Encoding Correctness
# ============================================================

def test_inline_images_produces_valid_base64(tmp_repo_structure: dict) -> None:
    """inline_images should produce valid base64-encoded data URLs."""
    html = '<img src="logo.png" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])

    # Extract the base64 portion
    match = result.split('data:image/png;base64,')[1].split('"')[0]

    # Try to decode it - should not raise an exception
    decoded = base64.b64decode(match)
    assert len(decoded) > 0


def test_inline_images_preserves_other_attributes(tmp_repo_structure: dict) -> None:
    """inline_images should preserve other HTML attributes."""
    html = '<img src="logo.png" alt="Logo" class="my-class" id="logo-img" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])

    # Other attributes should be preserved
    assert 'alt="Logo"' in result
    assert 'class="my-class"' in result
    assert 'id="logo-img"' in result


# ============================================================
# TESTS: inline_images() - Case Insensitivity
# ============================================================

def test_inline_images_case_insensitive_extension(tmp_repo_structure: dict) -> None:
    """inline_images should handle uppercase file extensions."""
    # Create a file with uppercase extension
    png_upper = tmp_repo_structure['presentation_dir'] / 'logo.PNG'
    png_upper.write_bytes(b'\x89PNG\r\n\x1a\n' + b'test png content')

    html = '<img src="logo.PNG" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])

    assert 'data:image/png;base64,' in result


# ============================================================
# TESTS: inline_images() - Search Fallback
# ============================================================

def test_inline_images_fallback_search_parent_dir(tmp_repo_structure: dict) -> None:
    """inline_images should search parent directories if file not found in base_dir."""
    # Create a file in the parent directory instead
    png_parent = tmp_repo_structure['presentation_dir'].parent / 'shared.png'
    png_parent.write_bytes(b'\x89PNG\r\n\x1a\n' + b'test png content')

    html = '<img src="shared.png" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'] / 'diagrams')

    # Should find and inline the file from parent
    assert 'data:image/png;base64,' in result


# ============================================================
# TESTS: strip_live_reload()
# ============================================================

def test_strip_live_reload_removes_polling_block() -> None:
        """strip_live_reload should remove the live-reload polling script."""
        html = '''<script>
        (function () {
            console.log("presentation engine");
        })();

        // ── Live reload (polls server for changes) ──
        (function () {
            setInterval(function () {
                fetch(window.location.href, { method: 'HEAD', cache: 'no-store' });
            }, 2000);
        })();
    </script>'''

        result = export_pres.strip_live_reload(html)

        assert 'presentation engine' in result
        assert 'Live reload (polls server for changes)' not in result
        assert "method: 'HEAD'" not in result


def test_strip_live_reload_leaves_html_without_polling_unchanged() -> None:
        """strip_live_reload should leave HTML unchanged when no polling block exists."""
        html = '<script>(function () { console.log("presentation engine"); })();</script>'

        assert export_pres.strip_live_reload(html) == html


# ============================================================
# TESTS: export_presentation() - Integration
# ============================================================

def test_export_presentation_creates_build_directory(tmp_repo_structure: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """export_presentation should create build directory if it doesn't exist."""
    # Mock get_repo_root to return our temp structure
    monkeypatch.setattr(export_pres, 'get_repo_root', lambda: tmp_repo_structure['tmp_path'])

    # Remove build dir for this test
    build_dir = tmp_repo_structure['build_dir']
    if build_dir.exists():
        import shutil
        shutil.rmtree(build_dir)

    # Run export
    export_pres.export_presentation()

    # Build directory should now exist
    assert build_dir.exists()


def test_export_presentation_creates_output_file(tmp_repo_structure: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """export_presentation should create the output HTML file in build directory."""
    monkeypatch.setattr(export_pres, 'get_repo_root', lambda: tmp_repo_structure['tmp_path'])

    # Run export
    export_pres.export_presentation()

    # Output file should exist
    output_file = tmp_repo_structure['build_dir'] / 'APIM-Samples-Slide-Deck.html'
    assert output_file.exists()


def test_export_presentation_inlines_images(tmp_repo_structure: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """export_presentation should inline images in the output file."""
    monkeypatch.setattr(export_pres, 'get_repo_root', lambda: tmp_repo_structure['tmp_path'])

    # Run export
    export_pres.export_presentation()

    # Read output file
    output_file = tmp_repo_structure['build_dir'] / 'APIM-Samples-Slide-Deck.html'
    output_content = output_file.read_text()

    # Should contain inlined images
    assert 'data:image/png;base64,' in output_content
    assert 'data:image/jpeg;base64,' in output_content
    assert 'data:image/svg+xml;base64,' in output_content


def test_export_presentation_strips_live_reload_polling(tmp_repo_structure: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        """export_presentation should omit authoring-only polling from the build output."""
        monkeypatch.setattr(export_pres, 'get_repo_root', lambda: tmp_repo_structure['tmp_path'])

        html_file = tmp_repo_structure['presentation_dir'] / TEST_PRESENTATION_FILE
        html_file.write_text(
                '''<!DOCTYPE html>
<html>
<body>
    <img src="logo.png" alt="Logo" />
    <script>
        (function () {
            console.log("presentation engine");
        })();

        // ── Live reload (polls server for changes) ──
        (function () {
            setInterval(function () {
                fetch(window.location.href, { method: 'HEAD', cache: 'no-store' });
            }, 2000);
        })();
    </script>
</body>
</html>''',
                encoding = 'utf-8',
        )

        export_pres.export_presentation()

        output_content = (tmp_repo_structure['build_dir'] / TEST_PRESENTATION_FILE).read_text(encoding = 'utf-8')
        assert 'data:image/png;base64,' in output_content
        assert 'presentation engine' in output_content
        assert 'Live reload (polls server for changes)' not in output_content
        assert "method: 'HEAD'" not in output_content


def test_export_presentation_missing_source_file_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """export_presentation should exit if source presentation file not found."""
    # Create minimal structure without presentation file
    assets_dir = tmp_path / 'assets'
    assets_dir.mkdir(parents=True)

    monkeypatch.setattr(export_pres, 'get_repo_root', lambda: tmp_path)

    # Should raise SystemExit
    with pytest.raises(SystemExit):
        export_pres.export_presentation()


# ============================================================
# TESTS: Regex Pattern Matching
# ============================================================

def test_inline_images_regex_ignores_non_image_files(tmp_repo_structure: dict) -> None:
    """inline_images should not match non-image file references."""
    html = '''
    <img src="logo.png" />
    <script src="app.js"></script>
    <link href="styles.css" rel="stylesheet" />
    '''
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])

    # Only PNG should be inlined
    assert result.count('data:image/') == 1
    # Script and CSS should be unchanged
    assert 'src="app.js"' in result
    assert 'href="styles.css"' in result


def test_inline_images_handles_quotes_in_attributes(tmp_repo_structure: dict) -> None:
    """inline_images should preserve quotes in other attributes."""
    html = '<img src="logo.png" alt="My "Logo"" />'
    result = export_pres.inline_images(html, tmp_repo_structure['presentation_dir'])

    # Image should be inlined
    assert 'data:image/png;base64,' in result
