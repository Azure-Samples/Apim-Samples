"""Unit tests for setup/normalize_notebook_metadata.py."""

from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, cast

import pytest

# Ensure the setup folder is on sys.path so the script is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / 'setup'
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

if TYPE_CHECKING:
    nnm = cast(ModuleType, None)
else:
    nnm = cast(ModuleType, importlib.import_module('normalize_notebook_metadata'))


# ============================================================
# Helpers
# ============================================================

def _make_notebook(display_name: str = '.venv (3.14.2)', version: str = '3.14.2') -> dict:
    """Return a minimal notebook dict with customizable volatile fields."""
    return {
        'cells': [],
        'metadata': {
            'kernelspec': {
                'display_name': display_name,
                'language': 'python',
                'name': 'python3',
            },
            'language_info': {
                'codemirror_mode': {'name': 'ipython', 'version': 3},
                'file_extension': '.py',
                'mimetype': 'text/x-python',
                'name': 'python',
                'nbconvert_exporter': 'python',
                'pygments_lexer': 'ipython3',
                'version': version,
            },
        },
        'nbformat': 4,
        'nbformat_minor': 5,
    }


# ============================================================
# normalize_notebook_metadata()
# ============================================================

def test_normalizes_display_name():
    """display_name should be replaced with the canonical value."""
    nb = _make_notebook(display_name='APIM Samples Python 3.12')
    nnm.normalize_notebook_metadata(nb)
    assert nb['metadata']['kernelspec']['display_name'] == nnm.CANONICAL_DISPLAY_NAME


def test_normalizes_version():
    """language_info.version should be replaced with the canonical value."""
    nb = _make_notebook(version='3.14.2')
    nnm.normalize_notebook_metadata(nb)
    assert nb['metadata']['language_info']['version'] == nnm.CANONICAL_VERSION


def test_preserves_other_metadata():
    """Fields other than the two volatile ones must remain unchanged."""
    nb = _make_notebook()
    nnm.normalize_notebook_metadata(nb)

    assert nb['metadata']['kernelspec']['language'] == 'python'
    assert nb['metadata']['kernelspec']['name'] == 'python3'
    assert nb['metadata']['language_info']['file_extension'] == '.py'
    assert nb['metadata']['language_info']['codemirror_mode']['version'] == 3


def test_already_canonical_values():
    """No-op when values are already canonical."""
    nb = _make_notebook(display_name=nnm.CANONICAL_DISPLAY_NAME, version=nnm.CANONICAL_VERSION)
    nnm.normalize_notebook_metadata(nb)

    assert nb['metadata']['kernelspec']['display_name'] == nnm.CANONICAL_DISPLAY_NAME
    assert nb['metadata']['language_info']['version'] == nnm.CANONICAL_VERSION


def test_missing_metadata_key():
    """Should not raise when metadata is entirely absent."""
    nb = {'cells': [], 'nbformat': 4, 'nbformat_minor': 5}
    nnm.normalize_notebook_metadata(nb)
    assert 'metadata' not in nb or nb.get('metadata') == {}


def test_missing_kernelspec():
    """Should not raise when kernelspec is absent."""
    nb = {'cells': [], 'metadata': {'language_info': {'version': '3.14.2'}}, 'nbformat': 4, 'nbformat_minor': 5}
    nnm.normalize_notebook_metadata(nb)
    assert nb['metadata']['language_info']['version'] == nnm.CANONICAL_VERSION


def test_missing_language_info():
    """Should not raise when language_info is absent."""
    nb = {'cells': [], 'metadata': {'kernelspec': {'display_name': 'X', 'language': 'python', 'name': 'python3'}}, 'nbformat': 4, 'nbformat_minor': 5}
    nnm.normalize_notebook_metadata(nb)
    assert nb['metadata']['kernelspec']['display_name'] == nnm.CANONICAL_DISPLAY_NAME


# ============================================================
# normalize_stream()
# ============================================================

def test_normalize_stream():
    """Stream mode should read JSON from input and write normalized JSON to output."""
    nb = _make_notebook(display_name='custom name', version='3.99.0')
    input_buf = io.StringIO(json.dumps(nb))
    output_buf = io.StringIO()

    nnm.normalize_stream(input_buf, output_buf)

    result = json.loads(output_buf.getvalue())
    assert result['metadata']['kernelspec']['display_name'] == nnm.CANONICAL_DISPLAY_NAME
    assert result['metadata']['language_info']['version'] == nnm.CANONICAL_VERSION


def test_normalize_stream_trailing_newline():
    """Output should end with exactly one newline."""
    nb = _make_notebook()
    input_buf = io.StringIO(json.dumps(nb))
    output_buf = io.StringIO()

    nnm.normalize_stream(input_buf, output_buf)

    raw = output_buf.getvalue()
    assert raw.endswith('\n')
    assert not raw.endswith('\n\n')


# ============================================================
# normalize_file()
# ============================================================

def test_normalize_file(tmp_path: Path):
    """In-place normalization should update the file on disk."""
    nb = _make_notebook(display_name='My Custom Kernel', version='3.11.5')
    nb_path = tmp_path / 'test.ipynb'
    nb_path.write_text(json.dumps(nb, indent=1), encoding='utf-8')

    assert nnm.normalize_file(nb_path) is True

    result = json.loads(nb_path.read_text(encoding='utf-8'))
    assert result['metadata']['kernelspec']['display_name'] == nnm.CANONICAL_DISPLAY_NAME
    assert result['metadata']['language_info']['version'] == nnm.CANONICAL_VERSION


def test_normalize_file_uses_lf_endings(tmp_path: Path):
    """Normalized file should use LF line endings only."""
    nb = _make_notebook()
    nb_path = tmp_path / 'test.ipynb'
    nb_path.write_text(json.dumps(nb, indent=1), encoding='utf-8')

    nnm.normalize_file(nb_path)

    raw_bytes = nb_path.read_bytes()
    assert b'\r\n' not in raw_bytes
    assert b'\n' in raw_bytes


def test_normalize_file_invalid_json(tmp_path: Path):
    """Should return False and not crash on invalid JSON."""
    nb_path = tmp_path / 'bad.ipynb'
    nb_path.write_text('{ not valid json }', encoding='utf-8')

    assert nnm.normalize_file(nb_path) is False


def test_normalize_file_preserves_cells(tmp_path: Path):
    """Cell content must be preserved through normalization."""
    nb = _make_notebook()
    nb['cells'] = [
        {'cell_type': 'code', 'source': ['print("hello")\n'], 'metadata': {}, 'outputs': [], 'execution_count': None},
    ]
    nb_path = tmp_path / 'cells.ipynb'
    nb_path.write_text(json.dumps(nb, indent=1), encoding='utf-8')

    nnm.normalize_file(nb_path)

    result = json.loads(nb_path.read_text(encoding='utf-8'))
    assert result['cells'][0]['source'] == ['print("hello")\n']


# ============================================================
# setup_notebook_git_filter() in local_setup.py
# ============================================================

# Import local_setup for git filter setup tests
sps = cast(ModuleType, importlib.import_module('local_setup'))


def test_setup_notebook_git_filter_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Git filter setup should succeed with a valid project root."""
    (tmp_path / 'README.md').write_text('x', encoding='utf-8')
    (tmp_path / 'bicepconfig.json').write_text('{}', encoding='utf-8')

    setup_dir = tmp_path / 'setup'
    setup_dir.mkdir()
    (setup_dir / 'normalize_notebook_metadata.py').write_text('', encoding='utf-8')

    monkeypatch.setattr(sps, 'get_project_root', lambda: tmp_path)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return type('Result', (), {'returncode': 0})()

    monkeypatch.setattr('subprocess.run', fake_run)

    assert sps.setup_notebook_git_filter() is True
    assert len(calls) == 2
    assert 'filter.notebook-metadata.clean' in calls[0]
    assert 'filter.notebook-metadata.smudge' in calls[1]


def test_setup_notebook_git_filter_missing_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Should return False when the normalizer script is missing."""
    (tmp_path / 'README.md').write_text('x', encoding='utf-8')
    (tmp_path / 'bicepconfig.json').write_text('{}', encoding='utf-8')

    monkeypatch.setattr(sps, 'get_project_root', lambda: tmp_path)

    assert sps.setup_notebook_git_filter() is False
