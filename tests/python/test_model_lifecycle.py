"""Offline retirement evidence, coverage gaps, thresholds, and reporting tests."""

import json
import runpy
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from urllib.error import URLError

import pytest

# APIM Samples imports
from setup import model_catalog, model_lifecycle
from setup.model_catalog import ModelRecord


NOW = datetime(2026, 11, 4, 23, 59, tzinfo = timezone.utc)
MODELS = {'FIXTURE': ModelRecord(provider = 'openai', model_name = 'fixture-model', version = 'snapshot-a')}


def schedule(cutoff: str, *, lifecycle: str = 'GA', version: str = 'snapshot-a', extra: str = '', heading: str = 'Azure OpenAI') -> str:
    """Build a small published-table-shaped fixture with non-catalog identities."""
    header = ''.join(f'<th>{name}</th>' for name in model_lifecycle.HEADERS)
    row = f'<tr><td><code>fixture-model</code></td><td>{version}</td><td>{lifecycle}</td><td>{cutoff}</td><td>successor</td></tr>'

    return f'<h3>{heading}</h3><table><tr>{header}</tr>{row}{extra}</table>'


@pytest.mark.parametrize('days,status', [(-10, 'attention'), (0, 'attention'), (29, 'attention'), (30, 'attention'), (31, 'clear')])
def test_inclusive_utc_calendar_window(days, status):
    report = model_lifecycle.check_models(MODELS, schedule((NOW.date() + timedelta(days = days)).isoformat()), NOW)
    assert report['status'] == status
    finding = report['findings'][0]
    assert finding['days_remaining'] == days
    assert finding['replacement'] == 'successor'
    assert finding['model_name'] == MODELS['FIXTURE']['model_name']
    assert finding['version'] == MODELS['FIXTURE']['version']
    assert report['source_url'] == model_lifecycle.SOURCE_URL


@pytest.mark.parametrize('document,error', [
    ('<html>Service unavailable</html>', 'Missing or malformed'),
    (schedule('2027-01-01', version = 'other-snapshot'), 'Expected one exact'),
    (schedule('2027-01-01') + schedule('2027-02-01'), 'Expected one exact'),
    (schedule('2027-01-01').replace('<th>Lifecycle</th>', '<th>State</th>'), 'Missing or malformed'),
    (schedule('2027-01-01', extra = '<tr><td>Malformed row</td></tr>'), 'Missing or malformed'),
    (schedule('2027-01-01', extra = '<tr><td>fixture-model</td><td>snapshot-a</td><td>GA</td><td>2027-02-01</td><td>-</td></tr>'), 'found 2'),
    (schedule('-'), 'Missing, qualified'),
    (schedule('No earlier than 2027-01-01'), 'Missing, qualified'),
    (schedule('2027-01-01<sup>1</sup>'), 'Missing, qualified'),
    (schedule('2027-02-30'), 'Invalid retirement'),
    (schedule('2027-01-01', lifecycle = ''), 'unsupported lifecycle'),
    (schedule('2027-01-01', lifecycle = 'Retired'), 'conflicts'),
])
def test_missing_or_ambiguous_evidence_is_blocked(document, error):
    report = model_lifecycle.check_models(MODELS, document, NOW)
    assert report['status'] == 'blocked'
    assert error in report['findings'][0]['error']
    assert 'Check blocked' in model_lifecycle.render_report(report)
    assert 'none is within' not in model_lifecycle.render_report(report)


def test_other_providers_and_fine_tuning_do_not_supply_model_evidence():
    document = schedule('2027-01-01', version = 'wrong')
    document += '<h4>Fine-tuned models</h4>' + schedule('2026-11-05').split('</h3>', 1)[1]
    document += schedule('2026-11-05', heading = 'Anthropic')
    report = model_lifecycle.check_models(MODELS, document, NOW)
    assert report['status'] == 'blocked'


def test_unsupported_providers_are_not_silently_skipped():
    models = {'FIXTURE': ModelRecord(provider = 'other', model_name = 'fixture-model', version = 'snapshot-a')}
    report = model_lifecycle.check_models(models, schedule('2027-01-01'), NOW)
    assert report['status'] == 'blocked'
    assert 'No retirement source mapping' in report['findings'][0]['error']


@pytest.mark.parametrize('provider,heading', [
    ('anthropic', 'Anthropic'), ('meta', 'Meta'), ('cohere', 'Cohere'),
    ('deepseek', 'DeepSeek'), ('microsoft', 'Microsoft'), ('mistral', 'Mistral AI'),
])
def test_provider_specific_evidence_and_unversioned_models(provider, heading):
    models = {'FIXTURE': ModelRecord(provider = provider, model_name = 'fixture-model', version = None)}
    document = schedule('2026-11-05', heading = heading, version = '&#8212;')
    document += schedule('2027-02-01', version = '&#8212;')
    report = model_lifecycle.check_models(models, document, NOW)
    assert report['status'] == 'attention'
    assert report['findings'][0]['provider'] == provider
    assert report['findings'][0]['version'] is None
    assert report['findings'][0]['retirement_date'] == '2026-11-05'


def test_versionless_catalog_entry_does_not_match_a_versioned_row():
    models = {'FIXTURE': ModelRecord(provider = 'anthropic', model_name = 'fixture-model', version = None)}
    report = model_lifecycle.check_models(models, schedule('2027-01-01', heading = 'Anthropic'), NOW)
    assert report['status'] == 'blocked'
    assert 'found 0' in report['findings'][0]['error']


def test_multiple_providers_and_identical_overlapping_rows_are_supported():
    models = {**MODELS, 'PARTNER': ModelRecord(provider = 'anthropic', model_name = 'fixture-model', version = 'snapshot-a')}
    document = schedule('2027-01-01') + schedule('2026-11-05', heading = 'Anthropic') * 2
    report = model_lifecycle.check_models(models, document, NOW)
    assert report['status'] == 'attention'
    assert [finding['status'] for finding in report['findings']] == ['clear', 'attention']


def test_malformed_provider_table_does_not_hide_other_provider_alerts():
    models = {**MODELS, 'PARTNER': ModelRecord(provider = 'anthropic', model_name = 'fixture-model', version = 'snapshot-a')}
    document = schedule('2026-11-05') + schedule('2027-01-01', heading = 'Anthropic', extra = '<tr><td>Malformed row</td></tr>')
    report = model_lifecycle.check_models(models, document, NOW)
    assert report['status'] == 'blocked'
    assert [finding['status'] for finding in report['findings']] == ['attention', 'blocked']


def test_partial_coverage_retains_confirmed_alerts():
    models = {**MODELS, 'MISSING': ModelRecord(provider = 'openai', model_name = 'missing-model', version = 'snapshot-a')}
    report = model_lifecycle.check_models(models, schedule('2026-11-05'), NOW)
    assert report['status'] == 'blocked'
    assert [finding['status'] for finding in report['findings']] == ['attention', 'blocked']
    assert '### FIXTURE: attention' in model_lifecycle.render_report(report)


def test_report_escapes_remote_html_and_preserves_no_replacement():
    document = schedule('2027-01-01').replace('successor', '&lt;img src=x&gt;')
    report = model_lifecycle.check_models(MODELS, document, NOW)
    markdown = model_lifecycle.render_report(report)
    assert '<img' not in markdown
    assert '&lt;img src=x&gt;' in markdown
    report = model_lifecycle.check_models(MODELS, schedule('2027-01-01').replace('successor', '&#8212;'), NOW)
    assert report['findings'][0]['replacement'] is None


def test_report_preserves_word_boundaries_in_multiline_replacement():
    document = schedule('2027-01-01').replace('successor', 'replacement<br>model')
    report = model_lifecycle.check_models(MODELS, document, NOW)
    assert report['status'] == 'clear'
    assert report['findings'][0]['replacement'] == 'replacement model'
    assert '- replacement: replacement model' in model_lifecycle.render_report(report)


def test_fetch_uses_fixed_source_timeout_and_closes_response(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'<html>schedule</html>'
    fetch = MagicMock(return_value = response)
    monkeypatch.setattr(model_lifecycle.urllib.request, 'urlopen', fetch)
    assert model_lifecycle.fetch_schedule() == '<html>schedule</html>'
    request = fetch.call_args.args[0]
    assert request.full_url == model_lifecycle.SOURCE_URL
    assert fetch.call_args.kwargs['timeout'] == 60
    response.__exit__.assert_called_once()


@pytest.mark.parametrize('mode,exit_code,status', [
    ('clear', 0, 'clear'), ('attention', 2, 'attention'), ('network', 1, 'blocked'), ('manifest', 1, 'blocked'),
])
def test_cli_persists_structured_report_on_success_alert_and_failure(tmp_path, monkeypatch, mode, exit_code, status):
    monkeypatch.setattr(sys, 'argv', ['model_lifecycle', '--output-dir', str(tmp_path)])
    load = MagicMock(return_value = MODELS)
    fetch = MagicMock(return_value = schedule('2099-01-01' if mode == 'clear' else '2000-01-01'))
    if mode == 'network':
        fetch.side_effect = URLError('test retrieval failure')
    elif mode == 'manifest':
        load.side_effect = ValueError('test invalid manifest')
    monkeypatch.setattr(model_lifecycle, 'load_models', load)
    monkeypatch.setattr(model_lifecycle, 'fetch_schedule', fetch)
    assert model_lifecycle.main() == exit_code
    report = json.loads((tmp_path / 'report.json').read_text(encoding = 'utf-8'))
    assert report['status'] == status
    assert datetime.fromisoformat(report['checked_at']).tzinfo == timezone.utc
    assert (tmp_path / 'report.md').read_text(encoding = 'utf-8') == model_lifecycle.render_report(report)
    if status == 'blocked':
        assert report['errors']
        assert 'Check blocked' in model_lifecycle.render_report(report)


@pytest.mark.parametrize('cutoff,exit_code,status', [('2099-01-01', 0, 'clear'), ('2000-01-01', 2, 'attention')])
def test_module_entrypoint_propagates_exit_code_and_writes_report(tmp_path, monkeypatch, cutoff, exit_code, status):
    monkeypatch.setattr(sys, 'argv', ['model_lifecycle', '--output-dir', str(tmp_path)])
    monkeypatch.setattr(model_catalog, 'load_models', lambda _root: MODELS)
    response = MagicMock()
    response.__enter__.return_value.read.return_value = schedule(cutoff).encode('utf-8')
    monkeypatch.setattr(model_lifecycle.urllib.request, 'urlopen', MagicMock(return_value = response))

    with pytest.raises(SystemExit) as result:
        runpy.run_path(model_lifecycle.__file__, run_name = '__main__')

    assert result.value.code == exit_code
    report = json.loads((tmp_path / 'report.json').read_text(encoding = 'utf-8'))
    assert report['status'] == status
    assert (tmp_path / 'report.md').read_text(encoding = 'utf-8') == model_lifecycle.render_report(report)
    response.__exit__.assert_called_once()
