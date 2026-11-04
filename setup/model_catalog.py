"""Developer maintenance tooling, not environment setup or a runtime dependency.

Generate the explicit Python enum from shared/ai-models.json; Bicep reads that
source JSON directly. Asset bindings also synchronize non-Python model references.
Generation never imports or executes the previous generated module or notebooks.
Check mode verifies drift and ownership without writing or calling Azure.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import subprocess
import sys
import tokenize
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, TypedDict


MANIFEST_PATH = 'shared/ai-models.json'
PYTHON_PATH = 'shared/python/ai_models.py'
BINDINGS_PATH = 'setup/model_catalog_bindings.json'
EXCEPTIONS_PATH = 'setup/model_catalog_exceptions.json'
TOKEN = re.compile(r'\{\{model:([a-zA-Z0-9_.-]+):(model_name|version|slug)\}\}')
MODEL_LITERAL = re.compile(r'(?<![a-zA-Z0-9_])(?:gpt-[a-zA-Z0-9][a-zA-Z0-9._-]*|claude-[a-zA-Z0-9._-]+|gemini-[a-zA-Z0-9._-]+|llama-[a-zA-Z0-9._-]+)', re.IGNORECASE)
SUFFIXES = {'.py', '.ipynb', '.json', '.bicep', '.xml', '.kql', '.md', '.html', '.svg', '.drawio', '.yml', '.yaml'}
SELECTION_FIELDS = {'primary_model', 'secondary_model', 'ai_model_name', 'model_name', 'model_version', 'primary_model_version', 'secondary_model_version'}
ASSET_SELECTION_FIELDS = {'model_name', 'modelVersion', 'primaryModelName', 'primaryModelVersion', 'secondaryModelName', 'secondaryModelVersion'}
BICEP_SELECTION = re.compile(r"(?:\b(?:modelName|modelVersion)\s*:\s*'[^']+'|\bparam\s+(?:primary|secondary)Model(?:Name|Version)\s+string\s*=\s*'[^']+')")


class ModelRecord(TypedDict):
    """Validated manifest fields; a missing JSON version is normalized to None."""

    provider: str
    model_name: str
    version: str | None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding = 'utf-8'), object_pairs_hook = _unique_object)


def _resolve_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str):
        raise ValueError('Expected a repository-relative string path')
    parsed = PurePosixPath(relative)
    if not relative or parsed.is_absolute() or '..' in parsed.parts or '\\' in relative or ':' in relative:
        raise ValueError(f'Expected a repository-relative path: {relative!r}')
    path = root.joinpath(*parsed.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes repository: {relative}')
    return path


def load_models(root: Path) -> dict[str, ModelRecord]:
    """Validate the JSON authority before generating code or changing any assets."""
    manifest = _load(root / MANIFEST_PATH)
    if not isinstance(manifest, dict) or set(manifest) != {'approved'} or not isinstance(manifest['approved'], dict) or not manifest['approved']:
        raise ValueError(f'{MANIFEST_PATH}: expected a non-empty approved model object')
    models: dict[str, ModelRecord] = {}
    identities: set[tuple[str, str, str | None]] = set()
    for member, spec in sorted(manifest['approved'].items()):
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', member) or not isinstance(spec, dict) or not {'provider', 'model_name'} <= set(spec) <= {'provider', 'model_name', 'version'}:
            raise ValueError(f'{MANIFEST_PATH}:{member}: expected an uppercase enum ID and provider/name/optional-version fields')
        provider, name, version = spec['provider'], spec['model_name'], spec.get('version')
        if any(not isinstance(value, str) or not value.strip() or value != value.strip() for value in (provider, name)):
            raise ValueError(f'{MANIFEST_PATH}:{member}: provider and model_name must be non-empty, trimmed strings')
        if version is not None and (not isinstance(version, str) or not version.strip() or version != version.strip()):
            raise ValueError(f'{MANIFEST_PATH}:{member}: version must be a non-empty, trimmed string or null')
        identity = provider, name, version
        if identity in identities:
            raise ValueError(f'{MANIFEST_PATH}:{member}: duplicate model identity')
        identities.add(identity)
        models[member] = {'provider': provider, 'model_name': name, 'version': version}
    return models


def python_source(models: dict[str, ModelRecord]) -> str:
    """Generate statically discoverable members; repr keeps metadata literal and safe."""
    header = '''"""Generated from shared/ai-models.json. Do not edit directly.

Regenerate with: python setup/model_catalog.py --write
Runtime imports perform no JSON reads or code generation.

Autoreload: reload_unsafe
Restart the kernel after catalog edits.
"""

from dataclasses import dataclass
from enum import Enum, unique


@dataclass(frozen = True)
class ModelSpec:
    """A provider-neutral model identity with an optional opaque version."""

    provider: str
    model_name: str
    version: str | None = None


@unique
class ApprovedModel(Enum):
    """Only these exact model snapshots are approved for sample deployments."""

'''
    members = '\n'.join(
        f"    {member} = ModelSpec({spec['provider']!r}, {spec['model_name']!r}, {spec['version']!r})" for member, spec in sorted(models.items())
    )
    return header + members + """

    @property
    def model_name(self) -> str:
        return self.value.model_name

    @property
    def version(self) -> str | None:
        return self.value.version

    def __str__(self) -> str:
        return self.model_name
"""


def _previous_models(path: Path) -> list[ModelRecord]:
    """Read old literals only to migrate assets, never to approve models or execute code."""
    records: list[ModelRecord] = []
    if path.exists():
        tree = ast.parse(path.read_text(encoding = 'utf-8'))
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef) or cls.name != 'ApprovedModel':
                continue
            for node in cls.body:
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == 'ModelSpec':
                    provider, name, version = (ast.literal_eval(arg) for arg in node.value.args)
                    if not isinstance(provider, str) or not isinstance(name, str) or version is not None and not isinstance(version, str):
                        raise ValueError(f'{path}: invalid previous model literals')
                    records.append({'provider': provider, 'model_name': name, 'version': version})
    return records


def sample_models(root: Path, approved: dict[str, ModelRecord] | None = None) -> dict[str, tuple[str, ...]]:
    """Read sample-owned enum declarations without importing or executing notebooks."""
    if approved is None:
        approved = load_models(root)
    selections = {}
    for path in sorted(root.glob('samples/*/create.ipynb')):
        notebook = _load(path)
        first_code = next((cell for cell in notebook['cells'] if cell['cell_type'] == 'code'), None)
        if first_code is None:
            continue
        assignments = [
            node.value for node in ast.parse(''.join(first_code['source'])).body
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'sample_models' for target in node.targets)
        ]
        if not assignments:
            continue
        if len(assignments) != 1 or not isinstance(assignments[0], ast.Tuple) or not assignments[0].elts:
            raise ValueError(f'{path}: declare sample_models once as a non-empty tuple of ApprovedModel members')
        models = []
        for node in assignments[0].elts:
            if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name) or node.value.id != 'ApprovedModel':
                raise ValueError(f'{path}: sample_models must reference ApprovedModel members directly')
            if node.attr not in approved:
                raise ValueError(f'{path}: unknown approved model {node.attr}')
            models.append(node.attr)
        if len(set(models)) != len(models):
            raise ValueError(f'{path}: sample_models must contain distinct approved models')
        selections[path.parent.name] = tuple(models)
    return selections


def render(reference: str, selections: dict[str, tuple[str, ...]], approved: dict[str, ModelRecord]) -> str:
    """Resolve a model name, version, or resource slug from an explicit reference."""
    if not TOKEN.search(reference) or _has_literal(reference, approved):
        raise ValueError(f'Expected a symbolic model reference: {reference}')

    def resolve(token: re.Match[str]) -> str:
        identity, field = token.groups()
        owner, member = identity.rsplit('.', 1)
        if owner == 'approved':
            model = approved[member]
        else:
            if member not in {'primary', 'secondary'} and not member.isdecimal():
                raise ValueError(f'Unknown sample model member: {reference}')
            model = approved[selections[owner][0 if member == 'primary' else 1 if member == 'secondary' else int(member)]]
        value = _model_field(model, field)
        if value is None:
            raise ValueError(f'{reference} has no version')
        if field == 'slug' and not re.fullmatch(r'[a-z0-9-]+', value):
            raise ValueError(f'{reference} must produce a safe lowercase deployment identifier')
        return value

    return TOKEN.sub(resolve, reference)


def _model_field(model: ModelRecord, field: str) -> str | None:
    if field == 'version':
        return model['version']
    return model['model_name'].replace('.', '-') if field == 'slug' else model['model_name']


def _render_field(actual: str, references: list[str], selections: dict[str, tuple[str, ...]], known: list[ModelRecord],
                  approved: dict[str, ModelRecord], location: str = 'model field') -> str:
    """Replace only identities; fail on unknown models or changed occurrence counts."""
    values = iter(render(reference, selections, approved) for reference in references)
    candidates = {
        TOKEN.sub(lambda token: str(_model_field(spec, token[2])), reference)
        for reference in references for spec in known
        if all(_model_field(spec, token[2]) is not None for token in TOKEN.finditer(reference))
    }
    pattern = re.compile(r'(?<![\w.-])(?:' + '|'.join(re.escape(value) for value in sorted(candidates, key = lambda value: (-len(value), value))) + r')(?![\w.-])')
    if len(pattern.findall(actual)) != len(references) or _has_literal(pattern.sub('', actual), approved):
        raise ValueError(f'{location}: Model references changed; update the asset binding before rendering')
    return pattern.sub(lambda _match: next(values), actual)


def _format_model_tables(lines: list[str], owned: set[int]) -> None:
    """Keep model-bearing Markdown tables aligned when names or versions change width."""
    start = 0
    while start < len(lines):
        if not lines[start].startswith('|'):
            start += 1
            continue
        end = start
        while end < len(lines) and lines[end].startswith('|'):
            end += 1
        rows = [[cell.strip() for cell in line.strip().strip('|').split('|')] for line in lines[start:end]]
        if len(rows) >= 2 and owned.intersection(range(start + 1, end + 1)) and all(re.fullmatch(r':?-+:?', cell) for cell in rows[1]):
            if len({len(row) for row in rows}) != 1:
                raise ValueError('Model-bearing Markdown table has inconsistent column counts')
            widths = [max(3, *(len(row[column]) for index, row in enumerate(rows) if index != 1)) for column in range(len(rows[0]))]
            for index, row in enumerate(rows):
                formatted = row
                if index == 1:
                    formatted = [
                        (':' if cell.startswith(':') else '')
                        + '-' * (width - cell.startswith(':') - cell.endswith(':'))
                        + (':' if cell.endswith(':') else '')
                        for cell, width in zip(row, widths)
                    ]
                newline = '\n' if lines[start + index].endswith('\n') else ''
                lines[start + index] = '| ' + ' | '.join(cell.ljust(width) for cell, width in zip(formatted, widths)) + ' |' + newline
        start = end


def _json_strings(value: Any, pointer: tuple[str | int, ...] = ()):
    if isinstance(value, str):
        yield pointer, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _json_strings(child, (*pointer, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _json_strings(child, (*pointer, index))


def _has_literal(text: str, approved: dict[str, ModelRecord]) -> bool:
    versions = {model['version'] for model in approved.values() if model['version'] is not None}
    names = {model['model_name'] for model in approved.values()}
    return bool(MODEL_LITERAL.search(text)) or any(value in text for value in versions | names)


def _python_literals(source: str, approved: dict[str, ModelRecord]) -> set[str]:
    """Find model-bearing Python scopes without executing code."""
    tree = ast.parse(source)
    groups: set[str] = set()

    class Visitor(ast.NodeVisitor):
        scope = '<module>'

        def visit_FunctionDef(self, node):
            previous = self.scope
            self.scope = f'{previous}.{node.name}' if previous != '<module>' else node.name
            self.generic_visit(node)
            self.scope = previous

        visit_AsyncFunctionDef = visit_FunctionDef
        visit_ClassDef = visit_FunctionDef

        def visit_Assign(self, node):
            previous = self.scope
            if previous == '<module>' and isinstance(node.targets[0], ast.Name):
                self.scope = node.targets[0].id
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in SELECTION_FIELDS and isinstance(node.value, (ast.Constant, ast.BinOp, ast.JoinedStr)):
                    groups.add(self.scope)
            self.generic_visit(node)
            self.scope = previous

        def visit_AnnAssign(self, node):
            if isinstance(node.target, ast.Name) and node.target.id in SELECTION_FIELDS and isinstance(node.value, (ast.Constant, ast.BinOp, ast.JoinedStr)):
                groups.add(self.scope)
            self.generic_visit(node)

        def visit_Dict(self, node):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value in ASSET_SELECTION_FIELDS and isinstance(value, (ast.Constant, ast.BinOp, ast.JoinedStr)):
                    groups.add(self.scope)
            self.generic_visit(node)

        def visit_Constant(self, node):
            if isinstance(node.value, str) and _has_literal(node.value, approved):
                groups.add(self.scope)

        def visit_Call(self, node):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else None
            if name == 'ModelSpec':
                groups.add(self.scope)
            self.generic_visit(node)

    Visitor().visit(tree)
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and _has_literal(token.string, approved):
            groups.add('<comments>')
    return groups


def source_paths(root: Path) -> list[str]:
    """Inspect tracked and not-ignored new source, never local generated deployment output."""
    result = subprocess.run(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        cwd = root, check = True, capture_output = True, text = True,
    )
    return sorted(set(path for path in result.stdout.split('\0') if path and (root / path).is_file()))


def check_catalog(root: Path, *, write: bool = False, paths: list[str] | None = None) -> list[str]:
    """Check all declared renderings and detect unowned model text or unsafe selections."""
    approved = load_models(root)
    selections = sample_models(root, approved)
    bindings = _load(root / BINDINGS_PATH)
    exceptions = _load(root / EXCEPTIONS_PATH)
    if not isinstance(bindings, dict) or not isinstance(exceptions, dict):
        raise ValueError('Bindings and fixture exceptions must be objects')
    exception_keys: set[tuple[str, str]] = set()
    for relative, scopes in exceptions.items():
        _resolve_path(root, relative)
        if not relative.startswith('tests/python/') or not relative.endswith('.py') or not isinstance(scopes, list):
            raise ValueError('Only exact test fixture scopes are permitted')
        for scope in scopes:
            if not isinstance(scope, str) or not re.fullmatch(r'[A-Za-z_<>][A-Za-z0-9_.<>]*', scope) or (relative, scope) in exception_keys:
                raise ValueError('Only distinct, exact test fixture scopes are permitted')
            exception_keys.add((relative, scope))
    errors: list[str] = []
    seen_exceptions: set[tuple[str, str]] = set()
    bound: dict[str, set[Any]] = defaultdict(set)
    rendered: dict[str, str] = {}
    module_path = _resolve_path(root, PYTHON_PATH)
    generated = python_source(approved)
    known = [*_previous_models(module_path), *approved.values()]
    if not write and (not module_path.exists() or module_path.read_text(encoding = 'utf-8') != generated):
        errors.append(f'{PYTHON_PATH}: generated Python is stale; run setup/model_catalog.py --write')
    for relative, entries in bindings.items():
        path = _resolve_path(root, relative)
        if path.suffix not in SUFFIXES - {'.py', '.bicep'} or not relative.startswith('samples/'):
            raise ValueError(f'Bindings may only own sample asset fields: {relative}')
        if not isinstance(entries, list) or not entries:
            raise ValueError(f'{relative}: bindings must be a non-empty array')
        original = path.read_text(encoding = 'utf-8')
        document = None
        lines = original.splitlines(keepends = True)
        if path.suffix in {'.json', '.ipynb'}:
            document = json.loads(original, object_pairs_hook = _unique_object)
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) not in ({'line', 'models'}, {'pointer', 'models'}):
                raise ValueError(f'{relative}: invalid binding shape')
            if not isinstance(entry['models'], list) or not entry['models'] or any(not isinstance(symbol, str) for symbol in entry['models']):
                raise ValueError(f'{relative}: bindings require model references')
            if 'pointer' in entry:
                if not isinstance(entry['pointer'], list) or any(type(part) not in {str, int} or isinstance(part, int) and part < 0 for part in entry['pointer']):
                    raise ValueError(f'{relative}: invalid JSON pointer')
                pointer = tuple(entry['pointer'])
                if document is None or not pointer or pointer in bound[relative]:
                    raise ValueError(f'{relative}: invalid or duplicate JSON pointer')
                parent = document
                for part in pointer[:-1]:
                    parent = parent[part]
                actual = parent[pointer[-1]]
                if not isinstance(actual, str):
                    raise ValueError(f'{relative}: bindings must target JSON strings')
                if path.suffix == '.ipynb' and pointer[0] == 'cells' and document['cells'][pointer[1]]['cell_type'] == 'code':
                    raise ValueError(f'{relative}: Python cells must reference the catalog directly')
                parent[pointer[-1]] = _render_field(actual, entry['models'], selections, known, approved, f'{relative}:{pointer}')
                bound[relative].add(pointer)
            else:
                line = entry['line']
                if document is not None or type(line) is not int or line < 1 or line > len(lines) or line in bound[relative]:
                    raise ValueError(f'{relative}: invalid or duplicate line binding')
                actual = lines[line - 1].removesuffix('\n')
                lines[line - 1] = _render_field(actual, entry['models'], selections, known, approved, f'{relative}:{line}') + ('\n' if lines[line - 1].endswith('\n') else '')
                bound[relative].add(line)
        if path.suffix == '.md':
            _format_model_tables(lines, bound[relative])
        elif path.suffix == '.ipynb':
            for index, cell in enumerate(document['cells']):
                if cell['cell_type'] == 'markdown':
                    owned = {pointer[3] + 1 for pointer in bound[relative] if len(pointer) == 4 and pointer[:3] == ('cells', index, 'source')}
                    _format_model_tables(cell['source'], owned)
        updated = json.dumps(document, indent = 1 if path.suffix == '.ipynb' else 2, ensure_ascii = False) + '\n' if document is not None else ''.join(lines)
        changed = document != json.loads(original, object_pairs_hook = _unique_object) if document is not None else updated != original
        if changed and not write:
            errors.append(f'{relative}: generated model fields are stale; run setup/model_catalog.py --write')
        rendered[relative] = updated if write else original
    for relative in paths if paths is not None else source_paths(root):
        path = _resolve_path(root, relative)
        if path.suffix not in SUFFIXES or relative in {PYTHON_PATH, MANIFEST_PATH, BINDINGS_PATH, EXCEPTIONS_PATH}:
            continue
        text = rendered.get(relative)
        if text is None:
            text = path.read_text(encoding = 'utf-8')
        if path.suffix == '.py':
            for scope in _python_literals(text, approved):
                key = relative, scope
                if key in exception_keys:
                    seen_exceptions.add(key)
                else:
                    errors.append(f'{relative}:{scope}: independent model literal/selection; reference ai_models (or review an exact test fixture exception)')
        elif path.suffix in {'.json', '.ipynb'}:
            document = json.loads(text, object_pairs_hook = _unique_object)
            if path.suffix == '.ipynb':
                for index, cell in enumerate(document['cells']):
                    if cell['cell_type'] == 'code':
                        for scope in _python_literals(''.join(cell['source']), approved):
                            errors.append(f'{relative}:Cell {index + 1}:{scope}: independent model literal/selection')
            for pointer, value in _json_strings(document):
                if path.suffix == '.ipynb' and len(pointer) > 2 and pointer[0] == 'cells' and document['cells'][pointer[1]]['cell_type'] == 'code':
                    continue
                if (_has_literal(value, approved) or pointer and pointer[-1] in ASSET_SELECTION_FIELDS) and pointer not in bound[relative]:
                    errors.append(f'{relative}:{pointer}: unbound model text; add a symbolic asset binding')
        else:
            for index, line in enumerate(text.splitlines(), 1):
                if (_has_literal(line, approved) or path.suffix == '.bicep' and BICEP_SELECTION.search(line)) and index not in bound[relative]:
                    errors.append(f'{relative}:{index}: unbound model text; use catalog-derived values')
    for key in exception_keys - seen_exceptions:
        errors.append(f'{key[0]}:{key[1]}: fixture exception is stale; review or remove it')
    if write and not errors:
        rendered[PYTHON_PATH] = generated
        for relative, updated in rendered.items():
            path = _resolve_path(root, relative)
            if not path.exists() or path.read_text(encoding = 'utf-8') != updated:
                path.parent.mkdir(parents = True, exist_ok = True)
                path.write_text(updated, encoding = 'utf-8', newline = '\n')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description = __doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--write', action = 'store_true', help = 'Generate Python and synchronize model-owned asset fields')
    mode.add_argument('--check', action = 'store_true', help = 'Verify without writing (default)')
    parser.add_argument('--root', type = Path, default = Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        errors = check_catalog(args.root, write = args.write)
    except (OSError, ValueError, KeyError, IndexError, SyntaxError, subprocess.CalledProcessError) as error:
        print(f'Model catalog check failed: {error}', file = sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(error, file = sys.stderr)
        return 1
    print('Model catalog, generated fields, and literal ownership verified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
