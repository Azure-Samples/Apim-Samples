"""Tests for the load-balancing sample-local runtime helpers."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# APIM Samples imports
from apimtypes import HttpStatusCode

LOAD_BALANCING_DIR = Path(__file__).resolve().parents[2] / 'samples' / 'load-balancing'
sys.path.insert(0, str(LOAD_BALANCING_DIR))

from load_balancing_helpers import LoadBalancingScenario, LoadBalancingTrafficRunner, RetryTrackingResult  # noqa: E402


@pytest.mark.unit
def test_load_balancing_policies_use_bounded_retry_count() -> None:
    """Keep every load-balancing route on two retries independent of pool size."""
    notebook = json.loads((LOAD_BALANCING_DIR / 'create.ipynb').read_text(encoding='utf-8'))
    code_source = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code')
    policy_paths = sorted((LOAD_BALANCING_DIR / 'apim-policies').glob('*.xml'))
    params = json.loads((LOAD_BALANCING_DIR / 'params.json').read_text(encoding='utf-8'))
    embedded_policies = {api['name']: api['operations'][0]['policyXml'] for api in params['parameters']['apis']['value']}
    standard_template = (LOAD_BALANCING_DIR / 'apim-policies' / 'aca-backend-pool-load-balancing.xml').read_text(encoding='utf-8')
    error_template = (LOAD_BALANCING_DIR / 'apim-policies' / 'aca-backend-pool-load-balancing-with-429.xml').read_text(encoding='utf-8')
    tracked_template = (LOAD_BALANCING_DIR / 'apim-policies' / 'aca-backend-pool-load-balancing-with-retry-tracked.xml').read_text(encoding='utf-8')
    expected_policies = {
        'lb-prioritized': standard_template.format(backend_id='aca-backend-pool-web-api-429-prioritized', retry_count=2),
        'lb-prioritized-weighted': standard_template.format(backend_id='aca-backend-pool-web-api-429-prioritized-and-weighted', retry_count=2),
        'lb-weighted-equal': standard_template.format(backend_id='aca-backend-pool-web-api-429-weighted-50-50', retry_count=2),
        'lb-weighted-unequal': standard_template.format(backend_id='aca-backend-pool-web-api-429-weighted-80-20', retry_count=2),
        'lb-429-prioritized': error_template.format(backend_id='aca-backend-pool-web-api-429-prioritized', retry_count=2),
        'lb-retry-tracked': tracked_template.format(backend_id='aca-backend-pool-web-api-429-prioritized', retry_count=2, cache_key='retry-tracked'),
    }

    assert 'backend_retry_count = 2' in code_source
    assert code_source.count('retry_count=backend_retry_count') == 6
    assert len(policy_paths) == 3
    assert all('number of backends' not in policy_path.read_text(encoding='utf-8') for policy_path in policy_paths)
    assert embedded_policies == expected_policies


def _create_runner(*, responses=None, sleep=None, clock=None):
    requests = MagicMock()
    requests.headers = {'Ocp-Apim-Subscription-Key': 'initial-key'}
    session = MagicMock()
    session.headers = {}
    if responses is not None:
        session.get.side_effect = responses

    runner = LoadBalancingTrafficRunner(
        requests,
        'https://gateway.example/',
        True,
        session_factory=lambda: session,
        sleep=sleep or MagicMock(),
        clock=clock or MagicMock(side_effect=[1.0, 1.25]),
    )
    return runner, requests, session


def _response(status_code=HttpStatusCode.OK, *, headers=None, text='response', json_data=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {'Content-Type': 'text/plain'}
    response.text = text
    if json_data is not None:
        response.json.return_value = json_data
    return response


@pytest.mark.unit
def test_run_structured_switches_keys_and_pauses_between_scenarios():
    sleep = MagicMock()
    runner, requests, _ = _create_runner(sleep=sleep)
    requests.multiGet.side_effect = [['first'], ['second']]
    observed_keys = []
    requests.multiGet.side_effect = lambda *args, **kwargs: observed_keys.append(requests.subscriptionKey) or [kwargs['runs']]
    scenarios = [
        LoadBalancingScenario('prioritized', 0, '/prioritized', 3),
        LoadBalancingScenario('weighted', 1, '/weighted', 4, 500),
    ]

    results = runner.run_structured(scenarios, ['key-0', 'key-1'])

    assert results == [[3], [4]]
    assert observed_keys == ['key-0', 'key-1']
    sleep.assert_called_once_with(2)
    assert requests.multiGet.call_args_list[1].kwargs['sleepMs'] == 500


@pytest.mark.unit
def test_run_retry_tracking_waits_on_parseable_429_and_normalizes_results():
    responses = [
        _response(headers={'Content-Type': 'application/json'}, text='{"index": 0}', json_data={'index': 0}),
        _response(HttpStatusCode.TOO_MANY_REQUESTS, headers={'Content-Type': 'text/plain', 'Retry-After': '3'}, text='limited'),
        _response(headers={'Content-Type': 'text/plain'}, text='recovered'),
    ]
    sleep = MagicMock()
    clock = MagicMock(side_effect=[1.0, 1.1, 2.0, 2.2, 3.0, 3.3])
    runner, requests, session = _create_runner(responses=responses, sleep=sleep, clock=clock)

    result = runner.run_retry_tracking('/retry-tracked', 3, 'retry-key')

    assert requests.subscriptionKey == 'retry-key'
    assert session.verify is False
    assert session.headers == requests.headers
    assert session.get.call_count == 3
    session.get.assert_called_with('https://gateway.example/retry-tracked', timeout=30)
    assert result.api_results[0]['response'] == '{\n    "index": 0\n}'
    assert result.api_results[1]['response'] == 'limited'
    assert result.retry_after_samples == [3]
    assert result.waits == [(2, 3)]
    assert result.pre_wait_values == [3]
    assert result.recovered_after_first_wait is True
    assert result.chart_separators == [(1.5, 'Waited 3s after 429')]
    sleep.assert_called_once_with(3)


@pytest.mark.unit
def test_retry_tracking_ignores_invalid_retry_after_and_malformed_json():
    response = _response(
        HttpStatusCode.TOO_MANY_REQUESTS,
        headers={'Content-Type': 'application/json', 'Retry-After': 'later'},
        text='not JSON',
    )
    response.json.side_effect = ValueError('invalid JSON')
    runner, _, _ = _create_runner(responses=[response])

    result = runner.run_retry_tracking('retry-tracked', 1, 'retry-key')

    assert result.api_results[0]['response'] == 'not JSON'
    assert not result.retry_after_samples
    assert not result.waits
    assert not result.pre_wait_values
    assert result.recovered_after_first_wait is False
    assert not result.chart_separators


@pytest.mark.unit
def test_retry_tracking_rejects_non_positive_runs():
    runner, _, _ = _create_runner()

    with pytest.raises(ValueError, match='at least 1'):
        runner.run_retry_tracking('retry-tracked', 0, 'retry-key')


@pytest.mark.unit
def test_context_manager_closes_both_clients_after_exception():
    runner, requests, session = _create_runner(responses=[RuntimeError('request failed')])

    with pytest.raises(RuntimeError, match='request failed'), runner:
        runner.run_retry_tracking('retry-tracked', 1, 'retry-key')

    session.close.assert_called_once_with()
    requests.close.assert_called_once_with()


@pytest.mark.unit
def test_close_without_retry_session_still_closes_request_client():
    runner, requests, session = _create_runner()

    runner.close()

    session.close.assert_not_called()
    requests.close.assert_called_once_with()


@pytest.mark.unit
def test_retry_tracking_reuses_existing_session():
    responses = [_response(), _response()]
    session_factory = MagicMock()
    runner, _, session = _create_runner(responses=responses, clock=MagicMock(side_effect=[1.0, 1.1, 2.0, 2.1]))
    runner._session_factory = session_factory
    runner._session = session

    runner.run_retry_tracking('/retry-tracked', 2, 'retry-key')

    session_factory.assert_not_called()
    assert session.get.call_count == 2


@pytest.mark.unit
def test_retry_tracking_result_uses_only_values_through_first_wait():
    result = RetryTrackingResult(
        api_results=[
            {'run': 1, 'status_code': 429, 'headers': {'Retry-After': '5'}},
            {'run': 2, 'status_code': 429, 'headers': {'Retry-After': '4'}},
            {'run': 3, 'status_code': 200, 'headers': {}},
            {'run': 4, 'status_code': 429, 'headers': {'Retry-After': '9'}},
        ],
        retry_after_samples=[4],
        waits=[(2, 4)],
    )

    assert result.pre_wait_values == [5, 4]
    assert result.recovered_after_first_wait is True
