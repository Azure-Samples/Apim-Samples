"""Enforce classified autoreload across every repository notebook and runtime module."""

import ast
import json
from pathlib import Path
from types import ModuleType

import pytest

# APIM Samples imports
from notebook_autoreload import get_reload_policy

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS = sorted(path for folder in ('samples', 'infrastructure', 'shared') for path in (PROJECT_ROOT / folder).rglob('*.ipynb'))
RUNTIME_MODULES = sorted([
    *(PROJECT_ROOT / 'shared' / 'python').glob('*.py'),
    *(PROJECT_ROOT / 'samples').glob('*/*.py'),
    *(PROJECT_ROOT / 'infrastructure').glob('*/*.py'),
])


@pytest.mark.parametrize('path', NOTEBOOKS, ids=lambda path: str(path.relative_to(PROJECT_ROOT)))
def test_every_notebook_initializes_classified_autoreload(path: Path) -> None:
    """Configure before any non-import statements without unconditional reloads."""
    notebook = json.loads(path.read_text(encoding='utf-8'))
    code_cells = [cell for cell in notebook['cells'] if cell['cell_type'] == 'code']
    first_code = ast.parse(''.join(code_cells[0]['source']))
    imports = [node for node in first_code.body if isinstance(node, ast.ImportFrom) and node.module == 'notebook_autoreload']
    assert len(imports) == 1
    assert [alias.name for alias in imports[0].names] == ['configure_notebook_autoreload']
    first_statement = next(node for node in first_code.body if not isinstance(node, (ast.Import, ast.ImportFrom)))
    assert isinstance(first_statement, ast.Expr)
    assert ast.unparse(first_statement.value) == 'configure_notebook_autoreload()'
    for cell in code_cells:
        assert cell['outputs'] == [] and cell['execution_count'] is None
        tree = ast.parse(''.join(cell['source']))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert ast.unparse(node.func) not in {'importlib.reload', 'utils.enable_module_autoreload'}
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').endswith('_helpers'), 'Use module-qualified sample-local helper calls.'


@pytest.mark.parametrize('path', RUNTIME_MODULES, ids=lambda path: str(path.relative_to(PROJECT_ROOT)))
def test_runtime_modules_declare_reload_policy_and_reason(path: Path) -> None:
    """Check headers without importing modules or triggering their side effects."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    module = ModuleType(path.stem)
    module.__doc__ = ast.get_docstring(tree)
    assert get_reload_policy(module) in {'reload_safe', 'reload_conditional', 'reload_unsafe'}
    lines = (module.__doc__ or '').splitlines()
    declaration = next(index for index, line in enumerate(lines) if line.startswith('Autoreload: '))
    assert lines[declaration + 1].strip(), 'Explain reload limitations immediately after the classification.'
