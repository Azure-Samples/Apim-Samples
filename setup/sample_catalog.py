"""Validate the sample catalog and its hand-authored consumers without Azure access."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

INFRASTRUCTURES = ('simple-apim', 'apim-aca', 'afd-apim-pe', 'appgw-apim', 'appgw-apim-pe')
MATRIX_HEADERS = ('SIMPLE APIM', 'APIM ACA', 'AFD APIM PE', 'App Gateway APIM ACA', 'App Gateway APIM PE')
REPOSITORY_PATH = '/Azure-Samples/Apim-Samples/tree/main/samples/'


@dataclass(frozen = True)
class Sample:
    """Stable sample metadata; notebook configuration remains visible to learners."""

    description: str
    display_name: str
    folder: str
    supported_infrastructures: tuple[str, ...]

    def compatibility_label(self, separator: str = ', ') -> str:
        """Format a summary without duplicating infrastructure membership rules."""
        if self.supported_infrastructures == INFRASTRUCTURES:
            return 'All infrastructures'
        return separator.join(self.supported_infrastructures)


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON property: {key}')
        result[key] = value
    return result


def load_catalog(path: Path) -> tuple[Sample, ...]:
    """Load strict, alphabetically ordered metadata or raise an actionable error."""
    entries = json.loads(path.read_text(encoding = 'utf-8'), object_pairs_hook = _unique_json_object)
    if not isinstance(entries, list) or not entries:
        raise ValueError('Catalog must be a non-empty array of samples')
    samples: list[Sample] = []
    fields = {'description', 'display_name', 'folder', 'supported_infrastructures'}
    for index, entry in enumerate(entries, 1):
        context = f'Catalog entry {index}'
        if not isinstance(entry, dict) or set(entry) != fields:
            raise ValueError(f'{context}: expected exactly {sorted(fields)}')
        for key in ('description', 'display_name', 'folder'):
            value = entry[key]
            if not isinstance(value, str) or not value.strip() or value != value.strip() or '\n' in value or '\r' in value:
                raise ValueError(f'{context}: {key} must be a non-empty, trimmed single-line string')
        if re.fullmatch(r'[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*', entry['folder']) is None:
            raise ValueError(f'{context}: folder must be a single sample directory name')
        supported = entry['supported_infrastructures']
        if not isinstance(supported, list) or not supported or any(not isinstance(item, str) or item not in INFRASTRUCTURES for item in supported):
            raise ValueError(f'{context}: supported_infrastructures must contain known infrastructure IDs')
        if supported != [item for item in INFRASTRUCTURES if item in supported]:
            raise ValueError(f'{context}: infrastructure IDs must be unique and in matrix column order')
        samples.append(Sample(entry['description'], entry['display_name'], entry['folder'], tuple(supported)))
    for key in ('display_name', 'folder'):
        values = [getattr(sample, key).casefold() for sample in samples]
        if len(values) != len(set(values)):
            raise ValueError(f'Catalog contains duplicate {key} values')
    if samples != sorted(samples, key = lambda sample: sample.display_name.casefold()):
        raise ValueError('Catalog samples must be alphabetically ordered by display_name')
    return tuple(samples)


def _plain_markdown(value: str) -> str:
    value = re.sub(r'\[([^]]+)\](?:\[[^]]+\]|\([^)]+\))', r'\1', value)
    return value.replace('**', '').strip()


def _table_rows(text: str) -> list[list[str]]:
    return [[part.strip() for part in line.strip().strip('|').split('|')] for line in text.splitlines() if line.lstrip().startswith('|')]


@dataclass
class _HtmlNode:
    tag: str
    attrs: dict[str, str | None] = field(default_factory = dict)
    children: list[_HtmlNode] = field(default_factory = list)
    parts: list[str] = field(default_factory = list)

    @property
    def text(self) -> str:
        return ' '.join(''.join(self.parts).split())

    def select(self, tag: str = '', class_name: str = '') -> list[_HtmlNode]:
        return [
            node for child in self.children for node in [child, *child.select()]
            if (not tag or node.tag == tag) and (not class_name or class_name in (node.attrs.get('class') or '').split())
        ]


class _HtmlDocument(HTMLParser):
    """Read only the structural metadata needed by the catalog checks."""

    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs = True)
        self.root = _HtmlNode('document')
        self.stack = [self.root]
        self.feed(text)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _HtmlNode(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        for node in self.stack:
            node.parts.append(data)


def _sample_url_matches(url: str, folder: str) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlsplit(url)
    return (
        parsed.scheme == 'https' and parsed.netloc == 'github.com'
        and parsed.path == REPOSITORY_PATH + folder
        and not parsed.query and not parsed.fragment
    )


def check_readme(text: str, samples: tuple[Sample, ...]) -> list[str]:
    """Check the root table, summaries, compatibility, and resolved reference links."""
    errors: list[str] = []
    references = dict(re.findall(r'^\[([^]]+)\]:\s*(\S+)\s*$', text, re.MULTILINE))
    rows = [row for row in _table_rows(text) if re.fullmatch(r'\[([^]]+)\]\[([^]]+)\]', row[0]) and len(row) == 3]
    names = [re.fullmatch(r'\[([^]]+)\]\[([^]]+)\]', row[0])[1] for row in rows]
    if names != [sample.display_name for sample in samples]:
        errors.append('sample table names/order differ from catalog')
    for row, sample in zip(rows, samples):
        reference = re.fullmatch(r'\[([^]]+)\]\[([^]]+)\]', row[0])[2]
        if references.get(reference) != f'./samples/{sample.folder}/README.md':
            errors.append(f'{sample.display_name}: sample link must resolve to its README')
        if _plain_markdown(row[1]) != sample.description:
            errors.append(f'{sample.display_name}: description differs from catalog')
        if row[2] != sample.compatibility_label():
            errors.append(f'{sample.display_name}: infrastructure label differs from catalog')
    return errors


def check_website(text: str, samples: tuple[Sample, ...]) -> list[str]:
    """Check visible sample cards and their matching structured-data entries."""
    root = _HtmlDocument(text).root
    errors: list[str] = []
    cards = root.select('a', 'sample-card')
    names = [[node.text for node in card.select('h3')] for card in cards]
    if names != [[sample.display_name] for sample in samples]:
        errors.append('sample card names/order differ from catalog')
    for card, sample in zip(cards, samples):
        if not _sample_url_matches(card.attrs.get('href') or '', sample.folder):
            errors.append(f'{sample.display_name}: incorrect card URL')
        if [node.text for node in card.select(class_name = 'infra-tag')] != [sample.compatibility_label(' \u00b7 ')]:
            errors.append(f'{sample.display_name}: incorrect card compatibility')
    scripts = [node for node in root.select('script') if node.attrs.get('type') == 'application/ld+json']
    if len(scripts) != 1:
        return [*errors, 'expected one JSON-LD block']
    structured_data = json.loads(''.join(scripts[0].parts))
    if not isinstance(structured_data, dict):
        return [*errors, 'JSON-LD must be an object containing @graph']
    graph = structured_data.get('@graph', [])
    if not isinstance(graph, list) or any(not isinstance(node, dict) for node in graph):
        return [*errors, 'JSON-LD @graph must be an array of objects']
    lists = [node for node in graph if node.get('@type') == 'ItemList']
    if len(lists) != 1:
        return [*errors, 'expected one JSON-LD ItemList']
    entries = lists[0].get('itemListElement', [])
    if not isinstance(entries, list) or any(not isinstance(node, dict) for node in entries):
        return [*errors, 'JSON-LD itemListElement must be an array of objects']
    infrastructure_count = len(INFRASTRUCTURES)
    if len(entries) != infrastructure_count + len(samples) or [node.get('position') for node in entries] != list(range(1, len(entries) + 1)):
        errors.append('JSON-LD count/positions differ from infrastructure and sample inventory')
    sample_entries = entries[infrastructure_count:]
    if [node.get('name') for node in sample_entries] != [sample.display_name for sample in samples]:
        errors.append('JSON-LD sample names/order differ from catalog')
    for entry, sample in zip(sample_entries, samples):
        if entry.get('@type') != 'ListItem' or not _sample_url_matches(entry.get('url', ''), sample.folder):
            errors.append(f'{sample.display_name}: incorrect JSON-LD sample URL/type')
    return errors


def check_deck(text: str, samples: tuple[Sample, ...]) -> list[str]:
    """Check the overview slide and sample counts while allowing tailored pitches."""
    root = _HtmlDocument(text).root
    slides = [
        slide for slide in root.select(class_name = 'slide')
        if any(re.fullmatch(r'\d+ Real-World Policy Samples', node.text) for node in slide.select('h2'))
    ]
    errors: list[str] = []
    if len(slides) != 1:
        return ['expected one Real-World Policy Samples overview slide']
    slide = slides[0]
    if [node.text for node in slide.select('h4')] != [sample.display_name for sample in samples]:
        errors.append('overview names/order differ from catalog')
    if [node.text for node in slide.select('h2')] != [f'{len(samples)} Real-World Policy Samples']:
        errors.append('overview sample count differs from catalog')
    summaries = [node.text for node in root.select('p') if re.match(r'\d+ real-world samples\b', node.text)]
    if len(summaries) != 1 or not summaries[0].startswith(f'{len(samples)} real-world samples '):
        errors.append('summary sample count differs from catalog')
    return errors


def check_matrix(text: str, samples: tuple[Sample, ...]) -> list[str]:
    """Check compatibility without changing manual execution results."""
    rows = _table_rows(text)
    errors: list[str] = []
    if not rows or tuple(rows[0][1:]) != MATRIX_HEADERS:
        errors.append('infrastructure column order differs from catalog conventions')
    sample_rows = [row for row in rows if row[0].startswith('**') and row[0] not in {'**INFRASTRUCTURE**', '**INFRASTRUCTURE clean-up**'}]
    if [row[0] for row in sample_rows] != [f'**{sample.display_name}**' for sample in samples]:
        errors.append('sample row names/order differ from catalog')
    for row, sample in zip(sample_rows, samples):
        if len(row) != len(INFRASTRUCTURES) + 1:
            errors.append(f'{sample.display_name}: expected five infrastructure cells')
            continue
        for cell, infrastructure in zip(row[1:], INFRASTRUCTURES):
            supported = infrastructure in sample.supported_infrastructures
            if (supported and (not cell or cell == '**N/A**')) or (not supported and cell != '**N/A**'):
                errors.append(f'{sample.display_name}: incorrect {infrastructure} compatibility')
    return errors


def _svg_texts(element: ET.Element, x: float = 0, y: float = 0) -> list[tuple[float, float, str]]:
    if element.tag.endswith('}g') and element.get('transform'):
        transform = re.fullmatch(r'translate\(([-\d.]+)[ ,]+([-\d.]+)\)', element.attrib['transform'])
        if transform is None:
            raise ValueError('Compatibility SVG groups must use simple translate transforms')
        x += float(transform[1])
        y += float(transform[2])
    result = []
    if element.tag.endswith('}text'):
        result.append((x + float(element.get('x', '0')), y + float(element.get('y', '0')), ''.join(element.itertext()).strip()))
    for child in element:
        result.extend(_svg_texts(child, x, y))
    return result


def check_diagram(text: str, samples: tuple[Sample, ...]) -> list[str]:
    """Check visible SVG labels and check/cross glyphs, including translated rows."""
    texts = _svg_texts(ET.fromstring(text))
    errors: list[str] = []
    labels = sorted((y, name) for x, y, name in texts if x == 120)
    if [name for _, name in labels] != [sample.display_name for sample in samples]:
        errors.append('sample labels/order differ from catalog')
    columns = sorted((x, name[1:-1]) for x, _, name in texts if name in {f'({item})' for item in INFRASTRUCTURES})
    if [name for _, name in columns] != list(INFRASTRUCTURES):
        errors.append('infrastructure columns differ from catalog conventions')
    for (row_y, _), sample in zip(labels, samples):
        for column_x, infrastructure in columns:
            marks = [name for x, y, name in texts if x == column_x and abs(y - row_y) <= 2]
            expected = '\u2713' if infrastructure in sample.supported_infrastructures else '\u2717'
            if marks != [expected]:
                errors.append(f'{sample.display_name}: incorrect {infrastructure} check/cross glyph')
    return errors


def check_notebook(text: str, sample: Sample) -> list[str]:
    """Inspect literal declarations without importing or executing notebook code."""
    notebook = json.loads(text)
    if not isinstance(notebook, dict) or not isinstance(notebook.get('cells'), list):
        raise ValueError('Notebook must contain a cells array')
    declarations: list[ast.expr] = []
    for cell in notebook['cells']:
        if not isinstance(cell, dict) or cell.get('cell_type') not in {'code', 'markdown', 'raw'}:
            raise ValueError('Notebook cells must have a valid cell_type')
        if cell['cell_type'] != 'code':
            continue
        source = cell.get('source')
        if not isinstance(source, str) and (not isinstance(source, list) or any(not isinstance(line, str) for line in source)):
            raise ValueError('Code cell source must be a string or an array of strings')
        tree = ast.parse(''.join(source) if isinstance(source, list) else source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'supported_infras' for target in node.targets):
                declarations.append(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == 'supported_infras' and node.value is not None:
                declarations.append(node.value)
    if len(declarations) != 1 or not isinstance(declarations[0], ast.List):
        return ['expected one literal supported_infras list']
    expected = {item.replace('-', '_').upper() for item in sample.supported_infrastructures}
    values = declarations[0].elts
    actual = [item.attr for item in values if isinstance(item, ast.Attribute) and isinstance(item.value, ast.Name) and item.value.id == 'INFRASTRUCTURE']
    if len(actual) != len(values) or len(actual) != len(set(actual)) or set(actual) != expected:
        return ['supported_infras differs from catalog']
    return []


def check_sample_readme(text: str, sample: Sample) -> list[str]:
    """Check compatibility badges, preserving sample-specific explanations."""
    labels = re.findall(r'\*\*Supported infrastructures\*\*:\s*([^\n]+)', text)
    if len(labels) != 1 or labels[0].split(' (', 1)[0].rstrip('.') != sample.compatibility_label():
        return ['supported infrastructures badge differs from catalog']
    return []


def check_repository(root: Path) -> list[str]:
    """Return path-qualified diagnostics for every catalog consumer."""
    catalog_path = root / 'samples' / 'catalog.json'
    try:
        samples = load_catalog(catalog_path)
    except (OSError, ValueError) as exc:
        return [f'samples/catalog.json: {exc}']
    errors: list[str] = []
    expected_folders = {sample.folder for sample in samples}
    actual_folders = {path.name for path in (root / 'samples').iterdir() if path.is_dir() and not path.name.startswith(('_', '.'))}
    if actual_folders != expected_folders:
        errors.append(f'samples/catalog.json: folder inventory differs (unlisted={sorted(actual_folders - expected_folders)}, missing={sorted(expected_folders - actual_folders)})')
    checks = [
        ('README.md', check_readme),
        ('docs/index.html', check_website),
        ('assets/APIM-Samples-Slide-Deck.html', check_deck),
        ('tests/Test-Matrix.md', check_matrix),
        ('assets/diagrams/Infrastructure-Sample-Compatibility.svg', check_diagram),
    ]
    for relative, checker in checks:
        path = root.joinpath(*relative.split('/'))
        try:
            errors.extend(f'{relative}: {error}' for error in checker(path.read_text(encoding = 'utf-8'), samples))
        except (OSError, ValueError, ET.ParseError) as exc:
            errors.append(f'{relative}: {exc}')
    for sample in samples:
        folder = root / 'samples' / sample.folder
        for filename in ('README.md', 'main.bicep', 'create.ipynb'):
            if not (folder / filename).is_file():
                errors.append(f'samples/{sample.folder}/{filename}: required sample file is missing')
        try:
            errors.extend(f'samples/{sample.folder}/create.ipynb: {error}' for error in check_notebook((folder / 'create.ipynb').read_text(encoding = 'utf-8'), sample))
        except (OSError, ValueError, SyntaxError) as exc:
            errors.append(f'samples/{sample.folder}/create.ipynb: {exc}')
        try:
            errors.extend(f'samples/{sample.folder}/README.md: {error}' for error in check_sample_readme((folder / 'README.md').read_text(encoding = 'utf-8'), sample))
        except OSError as exc:
            errors.append(f'samples/{sample.folder}/README.md: {exc}')
    return errors


def main(argv: list[str] | None = None) -> int:
    """Run a read-only consistency check; the existing pytest job also enforces it."""
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--root', type = Path, default = Path(__file__).resolve().parents[1], help = 'Repository root (default: inferred from this script)')
    args = parser.parse_args(argv)
    errors = check_repository(args.root)
    if errors:
        print('Sample catalog validation failed:', file = sys.stderr)
        for error in errors:
            print(f'- {error}', file = sys.stderr)
        return 1
    print('Sample catalog and all consumers are consistent.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
