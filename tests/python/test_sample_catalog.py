"""Catalog schema and drift checks run offline in the existing Python CI job."""

from __future__ import annotations

import importlib
import json
import runpy
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / 'setup'
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

catalog = importlib.import_module('sample_catalog')
SAMPLES = catalog.load_catalog(PROJECT_ROOT / 'samples' / 'catalog.json')
WEBSITE = 'docs/index.html'
DECK = 'assets/APIM-Samples-Slide-Deck.html'
DIAGRAM = 'assets/diagrams/Infrastructure-Sample-Compatibility.svg'
MATRIX = 'tests/Test-Matrix.md'


def read_surface(relative: str) -> str:
    """Read a real consumer for narrowly targeted mutation tests."""
    return PROJECT_ROOT.joinpath(*relative.split('/')).read_text(encoding = 'utf-8')


def test_repository_catalog_consistency() -> None:
    assert catalog.check_repository(PROJECT_ROOT) == []


@pytest.mark.parametrize(
    ('value', 'message'),
    [
        ({}, 'non-empty array'),
        ([], 'non-empty array'),
        ([None], 'expected exactly'),
        ([{'folder': 'extra'}], 'expected exactly'),
    ],
)
def test_catalog_rejects_invalid_root_and_entry_shapes(tmp_path: Path, value: object, message: str) -> None:
    path = tmp_path / 'catalog.json'
    path.write_text(json.dumps(value), encoding = 'utf-8')
    with pytest.raises(ValueError, match = message):
        catalog.load_catalog(path)


@pytest.mark.parametrize(
    ('field', 'value', 'message'),
    [
        ('description', '', 'description must be'),
        ('description', 'text\nmore', 'single-line'),
        ('display_name', ' Untrimmed ', 'trimmed'),
        ('display_name', 42, 'display_name must be'),
        ('folder', '../escape', 'single sample directory'),
        ('folder', r'other\folder', 'single sample directory'),
        ('folder', '_TEMPLATE', 'single sample directory'),
        ('supported_infrastructures', [], 'known infrastructure'),
        ('supported_infrastructures', 'simple-apim', 'known infrastructure'),
        ('supported_infrastructures', ['unknown'], 'known infrastructure'),
        ('supported_infrastructures', [None], 'known infrastructure'),
        ('supported_infrastructures', ['simple-apim', 'simple-apim'], 'unique'),
        ('supported_infrastructures', ['afd-apim-pe', 'apim-aca'], 'column order'),
    ],
)
def test_catalog_rejects_invalid_fields(tmp_path: Path, field: str, value: object, message: str) -> None:
    entry = json.loads((PROJECT_ROOT / 'samples' / 'catalog.json').read_text(encoding = 'utf-8'))[0]
    entry[field] = value
    path = tmp_path / 'catalog.json'
    path.write_text(json.dumps([entry]), encoding = 'utf-8')
    with pytest.raises(ValueError, match = message):
        catalog.load_catalog(path)


@pytest.mark.parametrize('field', ['display_name', 'folder'])
def test_catalog_rejects_case_insensitive_duplicates(tmp_path: Path, field: str) -> None:
    entries = json.loads((PROJECT_ROOT / 'samples' / 'catalog.json').read_text(encoding = 'utf-8'))
    entries[1][field] = entries[0][field].upper()
    path = tmp_path / 'catalog.json'
    path.write_text(json.dumps(entries), encoding = 'utf-8')
    with pytest.raises(ValueError, match = f'duplicate {field}'):
        catalog.load_catalog(path)


def test_catalog_rejects_unsorted_and_duplicate_json_properties(tmp_path: Path) -> None:
    path = tmp_path / 'catalog.json'
    entries = json.loads((PROJECT_ROOT / 'samples' / 'catalog.json').read_text(encoding = 'utf-8'))
    path.write_text(json.dumps(entries[::-1]), encoding = 'utf-8')
    with pytest.raises(ValueError, match = 'alphabetically'):
        catalog.load_catalog(path)
    path.write_text('[{"folder": "one", "folder": "two"}]', encoding = 'utf-8')
    with pytest.raises(ValueError, match = 'Duplicate JSON property'):
        catalog.load_catalog(path)


@pytest.mark.parametrize(
    ('relative', 'checker', 'before', 'after', 'diagnostic'),
    [
        ('README.md', catalog.check_readme, '[AuthX][sample-authx]', '[Wrong][sample-authx]', 'names/order'),
        ('README.md', catalog.check_readme, './samples/authX/README.md', './samples/general/README.md', 'sample link'),
        ('README.md', catalog.check_readme, 'Authentication and role-based authorization in a mock HR API.', 'Changed.', 'description'),
        ('README.md', catalog.check_readme, 'appgw-apim, appgw-apim-pe', 'All infrastructures', 'infrastructure label'),
        (WEBSITE, catalog.check_website, '<h3>AuthX</h3>', '<h3>Wrong</h3>', 'card names/order'),
        (WEBSITE, catalog.check_website, '<span class="infra-tag">All infrastructures</span>', '<span class="infra-tag">simple-apim</span>', 'card compatibility'),
        (WEBSITE, catalog.check_website, '"name": "AuthX"', '"name": "Wrong"', 'JSON-LD sample names/order'),
        (WEBSITE, catalog.check_website, '"position": 6,', '"position": 99,', 'count/positions'),
        (WEBSITE, catalog.check_website, '"position": 17,', '"position": 16,', 'count/positions'),
        (WEBSITE, catalog.check_website, '"@type": "ItemList"', '"@type": "Wrong"', 'one JSON-LD ItemList'),
        (WEBSITE, catalog.check_website, 'type="application/ld+json"', 'type="text/plain"', 'one JSON-LD block'),
        (DECK, catalog.check_deck, '<h4>AuthX</h4>', '<h4>Wrong</h4>', 'overview names/order'),
        (DECK, catalog.check_deck, '12 Real-World Policy Samples', '11 Real-World Policy Samples', 'overview sample count'),
        (DECK, catalog.check_deck, '12 Real-World Policy Samples', 'Overview', 'one Real-World'),
        (DECK, catalog.check_deck, '12 real-world samples', '11 real-world samples', 'summary sample count'),
        (MATRIX, catalog.check_matrix, '**AuthX**', '**Wrong**', 'row names/order'),
        (MATRIX, catalog.check_matrix, 'SIMPLE APIM', 'Wrong', 'column order'),
        (MATRIX, catalog.check_matrix, '**N/A**', 'Supported', 'incorrect simple-apim'),
        (MATRIX, catalog.check_matrix, '| **AuthX**                     | \u25a2 Local<br>\u25a2 Dev Container', '| **AuthX**                     | **N/A**', 'incorrect simple-apim'),
        (DIAGRAM, catalog.check_diagram, '>AuthX</text>', '>Wrong</text>', 'labels/order'),
        (DIAGRAM, catalog.check_diagram, '&#x2713;', '&#x2717;', 'check/cross glyph'),
        (DIAGRAM, catalog.check_diagram, '&#x2717;', '&#x2713;', 'check/cross glyph'),
        (DIAGRAM, catalog.check_diagram, '(simple-apim)', '(unknown)', 'infrastructure columns'),
    ],
)
def test_detects_consumer_drift(
    relative: str, checker: Callable, before: str, after: str, diagnostic: str,
) -> None:
    text = read_surface(relative)
    assert before in text
    errors = checker(text.replace(before, after, 1), SAMPLES)
    assert any(diagnostic in error for error in errors), errors


@pytest.mark.parametrize(
    'url',
    [
        'http://github.com/Azure-Samples/Apim-Samples/tree/main/samples/authX',
        'https://github.com.evil.example/Azure-Samples/Apim-Samples/tree/main/samples/authX',
        'https://github.com@evil.example/Azure-Samples/Apim-Samples/tree/main/samples/authX',
        'https://github.com:443/Azure-Samples/Apim-Samples/tree/main/samples/authX',
        'https://github.com/Azure-Samples/Apim-Samples/tree/main/samples/authX-extra',
        'https://github.com/Azure-Samples/Apim-Samples/tree/main/samples/authX?redirect=elsewhere',
        'https://github.com/Azure-Samples/Apim-Samples/tree/main/samples/authX#wrong',
        None,
    ],
)
def test_website_checks_exact_url_fields_for_cards_and_json_ld(url: str | None) -> None:
    text = read_surface(WEBSITE)
    document = catalog._HtmlDocument(text).root
    card = document.select('a', 'sample-card')[0]
    correct_url = card.attrs['href']
    errors = catalog.check_website(text.replace(f'href="{correct_url}"', f'href="{url or ""}"', 1), SAMPLES)
    assert 'AuthX: incorrect card URL' in errors
    script = document.select('script')[0]
    data = json.loads(''.join(script.parts))
    item_list = next(node for node in data['@graph'] if node['@type'] == 'ItemList')
    entry = item_list['itemListElement'][len(catalog.INFRASTRUCTURES)]
    assert entry['url'] == correct_url
    entry['url'] = url
    modified = text.replace(''.join(script.parts), json.dumps(data), 1)
    assert 'AuthX: incorrect JSON-LD sample URL/type' in catalog.check_website(modified, SAMPLES)
    assert not catalog._sample_url_matches(url, SAMPLES[0].folder)


def test_manual_matrix_marks_and_tailored_prose_are_not_rewritten() -> None:
    text = read_surface(MATRIX).replace('\u25a2 Local', 'PASS Local')
    assert catalog.check_matrix(text, SAMPLES) == []
    text = read_surface(WEBSITE).replace('using JWT validation.', 'with a tailored explanation.')
    assert catalog.check_website(text, SAMPLES) == []
    text = read_surface(DECK).replace('Perfect starting point.', 'A different short pitch.')
    assert catalog.check_deck(text, SAMPLES) == []


@pytest.mark.parametrize(
    'source',
    [
        '',
        'supported_infras = dynamic_list()',
        'supported_infras = [INFRASTRUCTURE.SIMPLE_APIM]',
        'supported_infras = [OTHER.SIMPLE_APIM]',
        'supported_infras = []\nsupported_infras = []',
        'supported_infras = [INFRASTRUCTURE.APIM_ACA, INFRASTRUCTURE.AFD_APIM_PE, INFRASTRUCTURE.AFD_APIM_PE]',
    ],
)
def test_notebook_declarations_must_match_without_execution(source: str) -> None:
    sample = next(sample for sample in SAMPLES if sample.folder == 'load-balancing')
    notebook = {'cells': [{'cell_type': 'code', 'source': source}]}
    assert catalog.check_notebook(json.dumps(notebook), sample)


def test_notebook_supports_annotations_and_different_literal_order() -> None:
    sample = next(sample for sample in SAMPLES if sample.folder == 'load-balancing')
    notebook = {'cells': [
        {'cell_type': 'markdown', 'source': 'Explanation'},
        {'cell_type': 'code', 'source': [
            'raise RuntimeError("must never execute")\n',
            'supported_infras: list = [INFRASTRUCTURE.AFD_APIM_PE, INFRASTRUCTURE.APIM_ACA]\n',
        ]},
    ]}
    assert catalog.check_notebook(json.dumps(notebook), sample) == []


@pytest.mark.parametrize('value', [[], {}, {'cells': [None]}, {'cells': [{'cell_type': 'code', 'source': [42]}]}])
def test_malformed_notebooks_fail_explicitly(value: object) -> None:
    with pytest.raises(ValueError, match = 'Notebook|Code cell'):
        catalog.check_notebook(json.dumps(value), SAMPLES[0])


@pytest.mark.parametrize(
    ('value', 'diagnostic'),
    [
        ([], 'must be an object'),
        ({'@graph': {}}, '@graph must be an array'),
        ({'@graph': [None]}, '@graph must be an array'),
        ({'@graph': [{'@type': 'ItemList', 'itemListElement': {}}]}, 'itemListElement must be an array'),
        ({'@graph': [{'@type': 'ItemList', 'itemListElement': [None]}]}, 'itemListElement must be an array'),
        ({'@graph': [{'@type': 'ItemList', 'itemListElement': []}]}, 'count/positions'),
    ],
)
def test_malformed_structured_data_fails_explicitly(value: object, diagnostic: str) -> None:
    text = read_surface(WEBSITE)
    script = catalog._HtmlDocument(text).root.select('script')[0]
    modified = text.replace(''.join(script.parts), json.dumps(value), 1)
    assert any(diagnostic in error for error in catalog.check_website(modified, SAMPLES))


def test_html_reader_preserves_inline_text_entities_and_self_closing_elements() -> None:
    root = catalog._HtmlDocument('<p>A <em>brief</em> &amp; clear description<br/><img src="image"/>.</p>').root
    assert root.select('p')[0].text == 'A brief & clear description.'


def test_matrix_rejects_missing_cells() -> None:
    text = read_surface(MATRIX)
    row = next(line for line in text.splitlines() if line.startswith('| **AuthX**'))
    modified = text.replace(row, row.rsplit('|', 2)[0] + '|')
    assert 'AuthX: expected five infrastructure cells' in catalog.check_matrix(modified, SAMPLES)


def test_diagram_checks_translated_rows_and_rejects_unsupported_transforms() -> None:
    text = read_surface(DIAGRAM)
    modified = text.replace('transform="translate(0,46)"', 'transform="translate(0,92)"', 1)
    assert catalog.check_diagram(modified, SAMPLES)
    modified = text.replace('transform="translate(0,46)"', 'transform="scale(2)"', 1)
    with pytest.raises(ValueError, match = 'simple translate'):
        catalog.check_diagram(modified, SAMPLES)


@pytest.fixture
def repository_copy(tmp_path: Path) -> Path:
    """Copy only catalog inputs; never alter real manual results or notebook outputs."""
    relatives = ['samples/catalog.json', 'README.md', WEBSITE, DECK, MATRIX, DIAGRAM]
    relatives.extend(f'samples/{sample.folder}/{filename}' for sample in SAMPLES for filename in ('README.md', 'main.bicep', 'create.ipynb'))
    for relative in relatives:
        source = PROJECT_ROOT.joinpath(*relative.split('/'))
        destination = tmp_path.joinpath(*relative.split('/'))
        destination.parent.mkdir(parents = True, exist_ok = True)
        shutil.copyfile(source, destination)
    return tmp_path


def test_repository_reports_inventory_missing_files_and_parse_errors_together(repository_copy: Path) -> None:
    root = repository_copy
    (root / 'samples' / '_TEMPLATE').mkdir()
    (root / 'samples' / 'unlisted').mkdir()
    (root / 'samples' / 'authX').rename(root / 'samples' / 'renamed')
    (root / 'samples' / 'authX-pro' / 'main.bicep').unlink()
    (root / 'samples' / 'general' / 'create.ipynb').write_text('invalid JSON', encoding = 'utf-8')
    (root / 'samples' / 'costing' / 'README.md').write_text('No badge', encoding = 'utf-8')
    (root / 'docs' / 'index.html').write_text('<script type="application/ld+json">broken</script>', encoding = 'utf-8')
    (root / 'assets' / 'diagrams' / 'Infrastructure-Sample-Compatibility.svg').write_text('<svg', encoding = 'utf-8')
    (root / 'assets' / 'APIM-Samples-Slide-Deck.html').unlink()
    errors = catalog.check_repository(root)
    assert any("unlisted=['renamed', 'unlisted'], missing=['authX']" in error for error in errors)
    assert not any('_TEMPLATE' in error for error in errors)
    for prefix in [
        'samples/authX-pro/main.bicep: required',
        'samples/authX/create.ipynb:',
        'samples/authX/README.md:',
        'samples/general/create.ipynb:',
        'samples/costing/README.md: supported infrastructures badge',
        WEBSITE + ':',
        DECK + ':',
        DIAGRAM + ':',
    ]:
        assert any(error.startswith(prefix) for error in errors), errors


def test_sample_readme_badges_preserve_qualifiers_but_reject_wrong_compatibility() -> None:
    sample = SAMPLES[0]
    badge = '**Supported infrastructures**: All infrastructures'
    assert catalog.check_sample_readme(badge + ' (optional explanation)', sample) == []
    assert catalog.check_sample_readme(badge + '.', sample) == []
    assert catalog.check_sample_readme(badge + '\n' + badge, sample)
    assert catalog.check_sample_readme('**Supported infrastructures**: simple-apim', sample)


def test_catalog_cli_reports_missing_catalog_and_exit_status(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    assert catalog.main(['--root', str(tmp_path)]) == 1
    assert 'samples/catalog.json:' in capsys.readouterr().err
    assert catalog.main(['--root', str(PROJECT_ROOT)]) == 0
    assert 'consistent' in capsys.readouterr().out


def test_script_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'argv', ['sample_catalog.py', '--root', str(PROJECT_ROOT)])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(SETUP_PATH / 'sample_catalog.py'), run_name = '__main__')
    assert exit_info.value.code == 0
