"""Offline catalog ownership, asset generation, and regression checks."""

import json
import os
import re
import runpy
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest

from ai_models import ApprovedModel
from setup import model_catalog

ROOT = Path(__file__).resolve().parents[2]
PRIMARY = '{{model:costing.primary:model_name}}'


def _write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents = True, exist_ok = True)
    path.write_text(text, encoding = 'utf-8', newline = '\n')
    return path


def _json(root, relative, value):
    return _write(root, relative, json.dumps(value, indent = 2) + '\n')


@pytest.fixture
def catalog_root(tmp_path):
    _json(tmp_path, model_catalog.MANIFEST_PATH, json.loads((ROOT / model_catalog.MANIFEST_PATH).read_text(encoding = 'utf-8')))
    _json(tmp_path, model_catalog.BINDINGS_PATH, {})
    _json(tmp_path, model_catalog.EXCEPTIONS_PATH, {})
    _json(tmp_path, 'samples/costing/create.ipynb', {'cells': [{
        'cell_type': 'code', 'source': ['sample_models = (ApprovedModel.GPT_5_MINI, ApprovedModel.GPT_5_NANO)\n'],
    }]})
    assert model_catalog.check_catalog(tmp_path, write = True, paths = []) == []
    return tmp_path


def test_repository_catalog_is_current():
    assert model_catalog.check_catalog(ROOT) == []
    manifest = json.loads((ROOT / model_catalog.MANIFEST_PATH).read_text(encoding = 'utf-8'))
    assert set(manifest) == {'approved'}
    assert manifest['approved'] == {model.name: vars(model.value) for model in ApprovedModel}
    bicep = (ROOT / 'samples' / 'costing' / 'main.bicep').read_text(encoding = 'utf-8')
    assert "loadJsonContent('../../shared/ai-models.json')" in bicep
    assert re.findall(r'modelCatalog\.approved\.(\w+)', bicep) == list(model_catalog.sample_models(ROOT)['costing'])


def test_cli_runs_without_notebook_pythonpath():
    result = subprocess.run(
        [sys.executable, str(ROOT / 'setup' / 'model_catalog.py'), '--check'],
        cwd = ROOT, env = {**os.environ, 'PYTHONPATH': ''}, capture_output = True, text = True, check = False,
    )
    assert result.returncode == 0, result.stderr
    assert 'verified' in result.stdout


def test_costing_mock_identifies_the_selected_approved_model():
    body = ElementTree.parse(ROOT / 'samples' / 'costing' / 'apim-policies' / 'mock-ai-response.xml').find('.//set-body')
    assert body is not None and body.text is not None
    primary = model_catalog.sample_models(ROOT)['costing'][0]
    assert re.findall(r'JProperty\("model", "([^"]+)"\)', body.text) == [model_catalog.load_models(ROOT)[primary]['model_name']]


def test_check_never_writes_and_generation_is_idempotent(catalog_root):
    generated = catalog_root / model_catalog.PYTHON_PATH
    generated.write_text('raise AssertionError("Never import old generated Python")\n', encoding = 'utf-8')
    stale = generated.read_bytes(), generated.stat().st_mtime_ns
    assert model_catalog.check_catalog(catalog_root, paths = [])
    assert (generated.read_bytes(), generated.stat().st_mtime_ns) == stale
    assert model_catalog.check_catalog(catalog_root, write = True, paths = []) == []
    before = generated.read_bytes(), generated.stat().st_mtime_ns
    assert model_catalog.check_catalog(catalog_root, write = True, paths = []) == []
    assert (generated.read_bytes(), generated.stat().st_mtime_ns) == before


@pytest.mark.parametrize('manifest', [None, [], {}, {'approved': {}}, {'approved': []}, {'approved': {}, 'samples': {}}])
def test_manifest_requires_only_a_nonempty_approved_object(catalog_root, manifest):
    _json(catalog_root, model_catalog.MANIFEST_PATH, manifest)
    with pytest.raises(ValueError, match = 'non-empty approved'):
        model_catalog.check_catalog(catalog_root, write = True, paths = [])


@pytest.mark.parametrize('member,record', [
    ('lowercase', {'provider': 'other', 'model_name': 'neutral'}),
    ('INVALID-ID', {'provider': 'other', 'model_name': 'neutral'}),
    ('_RESERVED_', {'provider': 'other', 'model_name': 'neutral'}),
    ('VALID', []), ('VALID', {'provider': 'other'}), ('VALID', {'model_name': 'neutral'}),
    ('VALID', {'provider': 'other', 'model_name': 'neutral', 'extra': True}),
    ('VALID', {'provider': '', 'model_name': 'neutral'}),
    ('VALID', {'provider': ' other', 'model_name': 'neutral'}),
    ('VALID', {'provider': 123, 'model_name': 'neutral'}),
    ('VALID', {'provider': 'other', 'model_name': ''}),
    ('VALID', {'provider': 'other', 'model_name': 'neutral '}),
    ('VALID', {'provider': 'other', 'model_name': 'neutral', 'version': ''}),
    ('VALID', {'provider': 'other', 'model_name': 'neutral', 'version': ' opaque'}),
    ('VALID', {'provider': 'other', 'model_name': 'neutral', 'version': 123}),
])
def test_manifest_rejects_invalid_members_and_records(catalog_root, member, record):
    generated = catalog_root / model_catalog.PYTHON_PATH
    before = generated.read_bytes(), generated.stat().st_mtime_ns
    _json(catalog_root, model_catalog.MANIFEST_PATH, {'approved': {member: record}})
    with pytest.raises(ValueError):
        model_catalog.check_catalog(catalog_root, write = True, paths = [])
    assert (generated.read_bytes(), generated.stat().st_mtime_ns) == before


def test_manifest_rejects_duplicate_keys_and_identities(catalog_root):
    models = model_catalog.load_models(catalog_root)
    models['COPY'] = dict(models['GPT_5_MINI'])
    _json(catalog_root, model_catalog.MANIFEST_PATH, {'approved': models})
    with pytest.raises(ValueError, match = 'duplicate model identity'):
        model_catalog.load_models(catalog_root)
    _write(catalog_root, model_catalog.MANIFEST_PATH, '{"approved": {}, "approved": {}}')
    with pytest.raises(ValueError, match = 'Duplicate JSON key'):
        model_catalog.load_models(catalog_root)


@pytest.mark.parametrize('version', [None, 'opaque+build.2'])
@pytest.mark.parametrize('missing_module', [False, True])
def test_json_changes_generate_explicit_members_without_importing_old_python(catalog_root, version, missing_module):
    models = model_catalog.load_models(catalog_root)
    del models['GPT_5_1']
    models['GPT_5_MINI']['version'] = 'replacement-snapshot'
    models['NEW_ENTRY'] = {'provider': 'other', 'model_name': 'neutral', 'version': version}
    _json(catalog_root, model_catalog.MANIFEST_PATH, {'approved': models})
    generated = catalog_root / model_catalog.PYTHON_PATH
    if missing_module:
        generated.unlink()
    else:
        generated.write_text(generated.read_text(encoding = 'utf-8') + '\nraise AssertionError("Never import old Python")\n', encoding = 'utf-8')
    assert model_catalog.check_catalog(catalog_root, paths = [])
    assert model_catalog.check_catalog(catalog_root, write = True, paths = []) == []
    enum = runpy.run_path(str(generated))['ApprovedModel']
    assert set(enum.__members__) == set(models)
    assert enum.GPT_5_MINI.version == 'replacement-snapshot'
    assert vars(enum.NEW_ENTRY.value) == models['NEW_ENTRY']
    assert '    NEW_ENTRY = ModelSpec(' in generated.read_text(encoding = 'utf-8')
    assert model_catalog.check_catalog(catalog_root, paths = []) == []
    before = generated.read_bytes(), generated.stat().st_mtime_ns
    _json(catalog_root, model_catalog.MANIFEST_PATH, {'approved': dict(reversed(list(models.items())))})
    assert model_catalog.check_catalog(catalog_root, write = True, paths = []) == []
    assert (generated.read_bytes(), generated.stat().st_mtime_ns) == before


def test_optional_versions_and_quoted_metadata_stay_literal(catalog_root):
    models = json.loads((catalog_root / model_catalog.MANIFEST_PATH).read_text(encoding = 'utf-8'))['approved']
    name = "neutral'); raise AssertionError('metadata executed') #"
    models['QUOTED'] = {'provider': 'other', 'model_name': name}
    _json(catalog_root, model_catalog.MANIFEST_PATH, {'approved': models})
    assert model_catalog.check_catalog(catalog_root, write = True, paths = []) == []
    generated = catalog_root / model_catalog.PYTHON_PATH
    enum = runpy.run_path(str(generated))['ApprovedModel']
    assert enum.QUOTED.model_name == name
    assert enum.QUOTED.version is None
    approved = model_catalog.load_models(catalog_root)
    with pytest.raises(ValueError, match = 'has no version'):
        model_catalog.render('{{model:approved.QUOTED:version}}', {}, approved)
    with pytest.raises(ValueError, match = 'safe lowercase'):
        model_catalog.render('{{model:approved.QUOTED:slug}}', {}, approved)


def test_json_identity_changes_update_bound_names_versions_and_slugs(catalog_root):
    models = model_catalog.load_models(catalog_root)
    original = models['GPT_5_MINI']
    relative = 'samples/fixture/README.md'
    asset = _write(catalog_root, relative, f"{original['model_name']}-{original['version']} c-{original['model_name'].replace('.', '-')}-pool\n")
    _json(catalog_root, model_catalog.BINDINGS_PATH, {relative: [{'line': 1, 'models': [
        '{{model:costing.primary:model_name}}-{{model:costing.primary:version}}',
        'c-{{model:costing.primary:slug}}-pool',
    ]}]})
    original.update(model_name = 'neutral-replacement', version = 'opaque+build')
    _json(catalog_root, model_catalog.MANIFEST_PATH, {'approved': models})
    assert model_catalog.check_catalog(catalog_root, paths = [relative])
    assert model_catalog.check_catalog(catalog_root, write = True, paths = [relative]) == []
    assert asset.read_text(encoding = 'utf-8') == 'neutral-replacement-opaque+build c-neutral-replacement-pool\n'
    assert model_catalog.check_catalog(catalog_root, paths = [relative]) == []


@pytest.mark.parametrize('source', [
    'class ApprovedModel:\n    BROKEN = ModelSpec(1, "neutral", None)\n',
    'class ApprovedModel:\n    BROKEN = ModelSpec("other", "neutral", print("Do not execute"))\n',
    'class ApprovedModel:\n',
])
def test_invalid_previous_python_fails_without_execution_or_writes(catalog_root, source):
    generated = _write(catalog_root, model_catalog.PYTHON_PATH, source)
    before = generated.read_bytes(), generated.stat().st_mtime_ns
    with pytest.raises((ValueError, SyntaxError)):
        model_catalog.check_catalog(catalog_root, write = True, paths = [])
    assert (generated.read_bytes(), generated.stat().st_mtime_ns) == before


def test_ownership_failure_prevents_python_and_asset_writes(catalog_root):
    generated = catalog_root / model_catalog.PYTHON_PATH
    generated.write_text('pass\n', encoding = 'utf-8')
    before = generated.read_bytes(), generated.stat().st_mtime_ns
    relative = 'samples/fixture/README.md'
    asset = _write(catalog_root, relative, ApprovedModel.GPT_5_NANO.model_name + '\n')
    _json(catalog_root, model_catalog.BINDINGS_PATH, {relative: [{'line': 1, 'models': [PRIMARY]}]})
    unowned = 'samples/fixture/helper.py'
    _write(catalog_root, unowned, "model_name = 'unregistered'\n")
    assert model_catalog.check_catalog(catalog_root, write = True, paths = [relative, unowned])
    assert (generated.read_bytes(), generated.stat().st_mtime_ns) == before
    assert asset.read_text(encoding = 'utf-8') == ApprovedModel.GPT_5_NANO.model_name + '\n'


def test_line_and_json_bindings_render_and_detect_drift(catalog_root):
    original = f'Model {ApprovedModel.GPT_5_NANO.model_name}'
    text = _write(catalog_root, 'samples/fixture/README.md', original + '\n')
    asset = _json(catalog_root, 'samples/fixture/fixture.workbook.json', {'content': original})
    paths = ['samples/fixture/README.md', 'samples/fixture/fixture.workbook.json']
    _json(catalog_root, model_catalog.BINDINGS_PATH, {
        paths[0]: [{'line': 1, 'models': [PRIMARY]}],
        paths[1]: [{'pointer': ['content'], 'models': [PRIMARY]}],
    })
    assert len(model_catalog.check_catalog(catalog_root, paths = paths)) == 2
    assert text.read_text(encoding = 'utf-8') == original + '\n'
    assert model_catalog.check_catalog(catalog_root, write = True, paths = paths) == []
    expected = f'Model {ApprovedModel.GPT_5_MINI.model_name}'
    assert text.read_text(encoding = 'utf-8') == expected + '\n'
    assert json.loads(asset.read_text(encoding = 'utf-8')) == {'content': expected}
    assert model_catalog.check_catalog(catalog_root, paths = paths) == []


def test_moved_fields_cannot_overwrite_unrelated_edits(catalog_root):
    original = ApprovedModel.GPT_5_NANO.model_name
    first = _write(catalog_root, 'samples/fixture/first.md', original + '\n')
    second = _write(catalog_root, 'samples/fixture/second.md', '# New heading\n' + original + '\n')
    _json(catalog_root, model_catalog.BINDINGS_PATH, {
        'samples/fixture/first.md': [{'line': 1, 'models': [PRIMARY]}],
        'samples/fixture/second.md': [{'line': 1, 'models': [PRIMARY]}],
    })
    with pytest.raises(ValueError, match = 'Model references changed'):
        model_catalog.check_catalog(catalog_root, write = True, paths = [])
    assert first.read_text(encoding = 'utf-8') == original + '\n'
    assert second.read_text(encoding = 'utf-8').startswith('# New heading')


def test_previous_python_only_migrates_assets_and_never_approves_removed_models(catalog_root):
    generated = catalog_root / model_catalog.PYTHON_PATH
    models = model_catalog.load_models(catalog_root)
    models['REMOVED'] = {'provider': 'other', 'model_name': 'removed-model', 'version': 'old-snapshot'}
    generated.write_text(model_catalog.python_source(models) + '\nraise AssertionError("Never execute old Python")\n', encoding = 'utf-8')
    relative = 'samples/fixture/README.md'
    asset = _write(catalog_root, relative, 'Model removed-model\n')
    _json(catalog_root, model_catalog.BINDINGS_PATH, {relative: [{'line': 1, 'models': [PRIMARY]}]})
    notebook = _json(catalog_root, 'samples/fixture/create.ipynb', {'cells': [{'cell_type': 'code', 'source': ['sample_models = (ApprovedModel.REMOVED,)\n']}]})
    before = generated.read_bytes()
    with pytest.raises(ValueError, match = 'unknown approved model REMOVED'):
        model_catalog.check_catalog(catalog_root, write = True, paths = [relative])
    assert generated.read_bytes() == before
    notebook.unlink()
    assert model_catalog.check_catalog(catalog_root, write = True, paths = [relative]) == []
    assert asset.read_text(encoding = 'utf-8') == f'Model {ApprovedModel.GPT_5_MINI.model_name}\n'
    assert 'REMOVED' not in runpy.run_path(str(generated))['ApprovedModel'].__members__


@pytest.mark.parametrize('source', [
    "model_name = 'unregistered-provider-model'\n", "model_name = f'unregistered-{suffix}'\n",
    "model_version: str = 'opaque-build'\n", "selection = {'model_name': 'outside-known-families'}\n",
    "selected = ModelSpec('other', name, version)\n", "name = 'claude-unregistered'\n", '# gpt-unregistered\n',
])
def test_independent_python_identity_is_rejected(catalog_root, source):
    relative = 'samples/fixture/helpers.py'
    _write(catalog_root, relative, source)
    assert model_catalog.check_catalog(catalog_root, paths = [relative])


@pytest.mark.parametrize('relative,source', [
    ('samples/fixture/config.json', '{"model_name": "outside-known-families"}'),
    ('samples/fixture/main.bicep', "param primaryModelName string = 'outside-known-families'\n"),
    ('samples/fixture/main.bicep', "  modelVersion: 'opaque-build'\n"),
    ('samples/fixture/queries/test.kql', '// gpt-unregistered\nprint 1\n'),
])
def test_independent_asset_identity_is_rejected(catalog_root, relative, source):
    _write(catalog_root, relative, source)
    assert model_catalog.check_catalog(catalog_root, paths = [relative])


def test_notebook_code_cannot_be_hidden_by_a_binding(catalog_root):
    relative = 'samples/fixture/create.ipynb'
    _json(catalog_root, relative, {'cells': [{'cell_type': 'code', 'source': ['selected = ApprovedModel.GPT_5_NANO\n']}]})
    _json(catalog_root, model_catalog.BINDINGS_PATH, {relative: [{'pointer': ['cells', 0, 'source', 0], 'models': [PRIMARY]}]})
    with pytest.raises(ValueError, match = 'Python cells must reference'):
        model_catalog.check_catalog(catalog_root, paths = [relative])


def test_notebook_code_is_scanned_without_execution(catalog_root):
    relative = 'samples/fixture/create.ipynb'
    _json(catalog_root, relative, {'cells': [{'cell_type': 'code', 'source': ["selected = 'gpt-unapproved'\nraise AssertionError\n"]}]})
    assert any('Cell 1' in error for error in model_catalog.check_catalog(catalog_root, paths = [relative]))


def test_fixture_exceptions_are_exact_and_stale_entries_fail(catalog_root):
    relative = 'tests/python/test_fixture.py'
    source = "def test_golden():\n    return 'gpt-regression'\n"
    path = _write(catalog_root, relative, source)
    _json(catalog_root, model_catalog.EXCEPTIONS_PATH, {relative: ['test_golden']})
    assert model_catalog.check_catalog(catalog_root, paths = [relative]) == []
    path.write_text(source + "\ndef test_new():\n    return 'gpt-other'\n", encoding = 'utf-8')
    assert any('test_new' in error for error in model_catalog.check_catalog(catalog_root, paths = [relative]))
    path.write_text('pass\n', encoding = 'utf-8')
    assert any('stale' in error for error in model_catalog.check_catalog(catalog_root, paths = [relative]))
    _json(catalog_root, model_catalog.EXCEPTIONS_PATH, {relative: ['*']})
    with pytest.raises(ValueError):
        model_catalog.check_catalog(catalog_root, paths = [])


@pytest.mark.parametrize('relative', ['../outside.md', '/outside.md', 'samples/../outside.md', 'samples\\fixture\\README.md', 'C:/outside.md', 'shared/python/ai_models.py'])
def test_binding_paths_are_narrow_and_cannot_escape(catalog_root, relative):
    _json(catalog_root, model_catalog.BINDINGS_PATH, {relative: [{'line': 1, 'models': [PRIMARY]}]})
    with pytest.raises(ValueError):
        model_catalog.check_catalog(catalog_root, paths = [])


@pytest.mark.parametrize('reference', ['{{model:approved.UNKNOWN:model_name}}', '{{model:missing.primary:model_name}}', '{{model:costing.-1:model_name}}',
                                       '{{model:costing.99:model_name}}', '{{model:costing.primary:invalid}}', 'not symbolic'])
def test_unknown_or_literal_templates_fail(reference):
    with pytest.raises((ValueError, KeyError, IndexError)):
        model_catalog.render(reference, {'costing': ('GPT_5_MINI',)}, model_catalog.load_models(ROOT))


def test_resource_bindings_keep_slug_semantics_when_sample_roles_change():
    selections = {'fixture': ('GPT_5_MINI', 'GPT_5_1')}
    approved = model_catalog.load_models(ROOT)
    assert model_catalog.render('c-{{model:fixture.secondary:slug}}-pool', selections, approved) == 'c-gpt-5-1-pool'
    assert model_catalog.render('{{model:fixture.secondary:model_name}}', selections, approved) == 'gpt-5.1'
    assert model_catalog.render('{{model:fixture.secondary:version}}', selections, approved) == '2025-11-13'
    with pytest.raises(ValueError, match = 'Model references changed'):
        model_catalog._render_field('gpt-5.10', ['{{model:fixture.secondary:model_name}}'], selections, list(approved.values()), approved)


def test_model_markdown_tables_resize_deterministically(catalog_root):
    relative = 'samples/fixture/README.md'
    _write(catalog_root, relative, f'| Model | Version |\n| ----- | ------- |\n| {ApprovedModel.GPT_5_1.model_name} | {ApprovedModel.GPT_5_1.version} |\n')
    _json(catalog_root, model_catalog.BINDINGS_PATH, {relative: [{'line': 3, 'models': [PRIMARY, '{{model:costing.primary:version}}']}]})
    assert model_catalog.check_catalog(catalog_root, write = True, paths = [relative]) == []
    path = catalog_root / relative
    before = path.read_bytes(), path.stat().st_mtime_ns
    assert model_catalog.check_catalog(catalog_root, write = True, paths = [relative]) == []
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    assert len({line.index('|', 1) for line in path.read_text(encoding = 'utf-8').splitlines()}) == 1


@pytest.mark.parametrize('expression', ['()', '[ApprovedModel.GPT_5_MINI]', "('unapproved',)", '(ApprovedModel.GPT_5_MINI, ApprovedModel.GPT_5_MINI)', '(ApprovedModel.REMOVED,)'])
def test_sample_model_declarations_must_reference_current_approved_members(catalog_root, expression):
    _json(catalog_root, 'samples/costing/create.ipynb', {'cells': [{'cell_type': 'code', 'source': [f'sample_models = {expression}\n']}]})
    with pytest.raises((ValueError, KeyError)):
        model_catalog.sample_models(catalog_root)


def test_sample_model_discovery_never_executes_notebook_code(catalog_root):
    _json(catalog_root, 'samples/costing/create.ipynb', {'cells': [{
        'cell_type': 'code', 'source': ['sample_models = (ApprovedModel.GPT_5_MINI,)\nraise AssertionError("Do not execute")\n'],
    }]})
    assert model_catalog.sample_models(catalog_root) == {'costing': ('GPT_5_MINI',)}


@pytest.mark.parametrize('binding', [
    {'line': True, 'models': [PRIMARY]}, {'line': 0, 'models': [PRIMARY]},
    {'line': 1, 'models': []}, {'line': 1, 'models': None}, {'line': 1, 'models': [PRIMARY], 'ignore': True},
    {'pointer': [True], 'models': [PRIMARY]}, {'pointer': [], 'models': [PRIMARY]},
    {'pointer': ['capacity'], 'models': [PRIMARY]},
])
def test_malformed_binding_fails(catalog_root, binding):
    relative = 'samples/fixture/config.json' if 'pointer' in binding else 'samples/fixture/README.md'
    _write(catalog_root, relative, '{"capacity": 10}' if 'pointer' in binding else ApprovedModel.GPT_5_NANO.model_name + '\n')
    _json(catalog_root, model_catalog.BINDINGS_PATH, {relative: [binding]})
    with pytest.raises(ValueError):
        model_catalog.check_catalog(catalog_root, paths = [])


def test_duplicate_binding_and_json_keys_fail(catalog_root):
    relative = 'samples/fixture/README.md'
    _write(catalog_root, relative, ApprovedModel.GPT_5_NANO.model_name + '\n')
    _json(catalog_root, model_catalog.BINDINGS_PATH, {relative: [{'line': 1, 'models': [PRIMARY]}] * 2})
    with pytest.raises(ValueError, match = 'duplicate'):
        model_catalog.check_catalog(catalog_root, paths = [])
    _write(catalog_root, model_catalog.BINDINGS_PATH, '{"duplicate": [], "duplicate": []}')
    with pytest.raises(ValueError, match = 'Duplicate JSON key'):
        model_catalog.check_catalog(catalog_root, paths = [])


@pytest.mark.parametrize('mode', ['success', 'drift', 'missing'])
def test_cli_reports_failures_explicitly(catalog_root, monkeypatch, capsys, mode):
    monkeypatch.setattr(sys, 'argv', ['model_catalog.py', '--root', str(catalog_root), '--check'])
    monkeypatch.setattr(model_catalog, 'source_paths', lambda _root: [])
    if mode == 'drift':
        (catalog_root / model_catalog.PYTHON_PATH).write_text('pass\n', encoding = 'utf-8')
    elif mode == 'missing':
        (catalog_root / model_catalog.BINDINGS_PATH).unlink()
    assert model_catalog.main() == (0 if mode == 'success' else 1)
    output = capsys.readouterr()
    assert bool(output.err) == (mode != 'success')
