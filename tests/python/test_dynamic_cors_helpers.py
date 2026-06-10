"""Tests for the Dynamic CORS sample-local runtime helpers."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

DYNAMIC_CORS_DIR = Path(__file__).resolve().parents[2] / 'samples' / 'dynamic-cors'
sys.path.insert(0, str(DYNAMIC_CORS_DIR))

from dynamic_cors_helpers import DynamicCorsTestRunner, load_test_results  # noqa: E402


def _create_runner(monkeypatch, results_path: Path, result_groups: list[str] | None = None) -> DynamicCorsTestRunner:
    monkeypatch.setattr(
        'dynamic_cors_helpers.utils.get_endpoint',
        lambda deployment, rg_name, gateway_url: ('https://gateway.example', {'Host': 'apim.example'}, False),
    )
    session = MagicMock()
    monkeypatch.setattr('dynamic_cors_helpers.http_requests.Session', lambda: session)

    return DynamicCorsTestRunner('deployment', 'resource-group', 'https://apim.example', results_path, result_groups or ['Option 1'])


def test_runner_owns_and_closes_cell_session(monkeypatch, tmp_path):
    runner = _create_runner(monkeypatch, tmp_path / 'results.local.json')

    with runner:
        assert runner.session.headers.update.call_args.args[0] == {'Host': 'apim.example'}

    runner.session.close.assert_called_once()


def test_runner_replaces_only_current_result_group(monkeypatch, tmp_path):
    results_path = tmp_path / 'results.local.json'
    results_path.write_text(
        json.dumps(
            [
                {'Option': 'Option 1', 'Test': 'stale'},
                {'Option': 'Option 2', 'Test': 'preserved'},
            ]
        ),
        encoding='utf-8',
    )
    runner = _create_runner(monkeypatch, results_path)
    suite = MagicMock()
    suite.verify.return_value = True

    with runner:
        runner.track(suite, 'Option 1', 'fresh', 200, 200, 10.0)

    assert load_test_results(results_path) == [
        {'Option': 'Option 2', 'Test': 'preserved'},
        {
            'Option': 'Option 1',
            'Test': 'fresh',
            'Expected': '200',
            'Actual': '200',
            'Duration (ms)': 10.0,
            'Result': True,
        },
    ]


def test_runner_persists_results_when_cell_raises(monkeypatch, tmp_path):
    results_path = tmp_path / 'results.local.json'
    runner = _create_runner(monkeypatch, results_path)
    suite = MagicMock()
    suite.verify.return_value = False

    with pytest.raises(RuntimeError, match='cell failed'):
        with runner:
            runner.track(suite, 'Option 1', 'recorded before failure', 500, 200)
            raise RuntimeError('cell failed')

    assert load_test_results(results_path)[0]['Test'] == 'recorded before failure'
    runner.session.close.assert_called_once()


def test_load_test_results_rejects_invalid_shape(tmp_path):
    results_path = tmp_path / 'results.local.json'
    results_path.write_text('{"not": "a list"}', encoding='utf-8')

    with pytest.raises(ValueError, match='Invalid Dynamic CORS result data'):
        load_test_results(results_path)
