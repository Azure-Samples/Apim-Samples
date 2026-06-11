"""Validate selective autoreload coverage for sample-local notebook helpers."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = PROJECT_ROOT / 'samples'


def _get_notebook_code(notebook_path: Path) -> str:
    """Return all Python cell source from a notebook."""
    notebook = json.loads(notebook_path.read_text(encoding='utf-8'))

    return '\n'.join(''.join(cell.get('source', [])) for cell in notebook.get('cells', []) if cell.get('cell_type') == 'code')


def _get_sample_helpers() -> list[Path]:
    """Return sample-local helper modules that notebooks actively consume."""
    helper_paths = set(SAMPLES_DIR.glob('*/*_helpers.py'))
    helper_paths.update(SAMPLES_DIR.glob('*/_helpers.py'))

    return sorted(helper_paths)


def test_sample_local_helpers_enable_selective_autoreload() -> None:
    """Require every helper-owning sample notebook to register selective autoreload."""
    helper_paths = _get_sample_helpers()
    failures = []
    assert helper_paths, 'No sample-local helper modules were discovered.'

    for helper_path in helper_paths:
        notebook_path = helper_path.parent / 'create.ipynb'
        module_name = helper_path.stem

        if not notebook_path.is_file():
            failures.append(f'{helper_path.parent.name}: missing create.ipynb')
            continue

        notebook_code = _get_notebook_code(notebook_path)
        registration = f"utils.enable_module_autoreload('{module_name}')"
        if registration not in notebook_code:
            failures.append(f'{helper_path.parent.name}: missing {registration}')

    assert not failures, '\n'.join(failures)
