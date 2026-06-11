"""Tests for the Dynamic CORS sample-local runtime helpers."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

DYNAMIC_CORS_DIR = Path(__file__).resolve().parents[2] / 'samples' / 'dynamic-cors'
sys.path.insert(0, str(DYNAMIC_CORS_DIR))

import dynamic_cors_helpers  # noqa: E402
from dynamic_cors_helpers import DynamicCorsTestRunner, load_test_results, wait_for_gateway_dns  # noqa: E402


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


def test_load_test_results_rejects_non_dictionary_members(tmp_path):
    results_path = tmp_path / 'results.local.json'
    results_path.write_text('[{"valid": true}, "invalid"]', encoding='utf-8')

    with pytest.raises(ValueError, match='Invalid Dynamic CORS result data'):
        load_test_results(results_path)


def test_runner_without_endpoint_headers_keeps_session_headers_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(dynamic_cors_helpers.utils, 'get_endpoint', lambda *_: ('https://gateway.example', None, True))
    session = MagicMock()
    monkeypatch.setattr(dynamic_cors_helpers.http_requests, 'Session', lambda: session)

    runner = DynamicCorsTestRunner('deployment', 'rg', 'gateway', tmp_path / 'results.json', ['Option 1'])

    assert runner.session.verify is False
    session.headers.update.assert_not_called()


def test_request_helpers_return_normalized_results(monkeypatch, tmp_path):
    runner = _create_runner(monkeypatch, tmp_path / 'results.json')
    elapsed = MagicMock()
    elapsed.total_seconds.return_value = 0.01234
    options_response = MagicMock(status_code=204, headers={'Allow': 'GET'}, elapsed=elapsed)
    get_response = MagicMock(status_code=200, ok=True, elapsed=elapsed)
    get_response.json.return_value = {'corsAllowed': True}
    post_response = MagicMock(status_code=202, elapsed=elapsed)
    runner.session.options.return_value = options_response
    runner.session.get.return_value = get_response
    runner.session.post.return_value = post_response

    assert runner.options_request('products', 'https://shop.contoso.com') == (204, {'Allow': 'GET'}, 12.3)
    assert runner.get('products', 'https://shop.contoso.com', 'Products') == ({'corsAllowed': True}, 12.3)
    assert runner.post('admin/load', headers={'x': 'y'}, data='body') == (post_response, 12.3)
    runner.session.options.assert_called_once_with(
        'https://gateway.example/products',
        headers={'Origin': 'https://shop.contoso.com', 'Access-Control-Request-Method': 'GET'},
        timeout=30,
    )


def test_get_does_not_parse_error_response(monkeypatch, tmp_path):
    runner = _create_runner(monkeypatch, tmp_path / 'results.json')
    response = MagicMock(status_code=500, ok=False)
    response.elapsed.total_seconds.return_value = 0
    runner.session.get.return_value = response

    assert runner.get('products', 'https://origin', 'Products') == ({}, 0.0)
    response.json.assert_not_called()


def test_track_returns_suite_result_and_records_values(monkeypatch, tmp_path):
    runner = _create_runner(monkeypatch, tmp_path / 'results.json')
    suite = MagicMock()
    suite.verify.return_value = False

    assert runner.track(suite, 'Option 1', 'label', None, True) is False
    assert runner.results == [
        {
            'Option': 'Option 1',
            'Test': 'label',
            'Expected': 'True',
            'Actual': 'None',
            'Duration (ms)': None,
            'Result': False,
        }
    ]


def test_run_option_tests_executes_complete_matrix(monkeypatch, tmp_path):
    runner = _create_runner(monkeypatch, tmp_path / 'results.json')
    suite = MagicMock()
    suite.verify.return_value = True
    runner.options_request = MagicMock(
        side_effect=[
            (200, {'Access-Control-Allow-Origin': 'https://shop.contoso.com'}, 1.0),
            (200, {'Access-Control-Allow-Origin': 'https://admin.contoso.com'}, 2.0),
            (403, {}, 3.0),
            (200, {'Access-Control-Allow-Origin': 'https://dashboard.contoso.com'}, 4.0),
            (403, {}, 5.0),
        ]
    )
    runner.get = MagicMock(
        side_effect=[
            ({'corsAllowed': True, 'allowedOrigin': 'https://shop.contoso.com'}, 6.0),
            ({'corsAllowed': False}, 7.0),
            ({'corsAllowed': True}, 8.0),
            ({'corsAllowed': False}, 9.0),
        ]
    )

    runner.run_option_tests(suite, 'Option 1', 'products', 'analytics')

    assert runner.options_request.call_count == 5
    assert runner.get.call_count == 4
    assert suite.verify.call_count == 13
    assert runner.results[0]['Test'].startswith('OPTION1')


def test_wait_for_gateway_dns_rejects_url_without_hostname():
    with pytest.raises(ValueError, match='no hostname'):
        wait_for_gateway_dns('not-a-url')


def test_wait_for_gateway_dns_returns_immediately_when_resolved(monkeypatch):
    getaddrinfo = MagicMock(return_value=[('resolved',)])
    sleep = MagicMock()
    monkeypatch.setattr(dynamic_cors_helpers.socket, 'getaddrinfo', getaddrinfo)
    monkeypatch.setattr(dynamic_cors_helpers.time, 'sleep', sleep)

    wait_for_gateway_dns('https://apim.example')

    getaddrinfo.assert_called_once_with('apim.example', 443)
    sleep.assert_not_called()


def test_wait_for_gateway_dns_polls_then_resolves_without_real_sleep(monkeypatch):
    getaddrinfo = MagicMock(side_effect=[dynamic_cors_helpers.socket.gaierror(), None])
    sleep = MagicMock()
    monkeypatch.setattr(dynamic_cors_helpers.socket, 'getaddrinfo', getaddrinfo)
    monkeypatch.setattr(dynamic_cors_helpers.time, 'sleep', sleep)

    wait_for_gateway_dns('https://apim.example', max_wait=10, poll_interval=10)

    sleep.assert_called_once_with(10)


def test_wait_for_gateway_dns_exits_after_last_failed_poll(monkeypatch):
    monkeypatch.setattr(
        dynamic_cors_helpers.socket,
        'getaddrinfo',
        MagicMock(side_effect=dynamic_cors_helpers.socket.gaierror()),
    )
    sleep = MagicMock()
    monkeypatch.setattr(dynamic_cors_helpers.time, 'sleep', sleep)
    print_error = MagicMock()
    monkeypatch.setattr(dynamic_cors_helpers, 'print_error', print_error)

    with pytest.raises(SystemExit) as exc_info:
        wait_for_gateway_dns('https://apim.example', max_wait=20, poll_interval=10)

    assert exc_info.value.code == 1
    assert sleep.call_count == 2
    assert print_error.call_count == 2
