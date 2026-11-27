"""Offline configuration, request lifecycle, notebook and APIM policy contracts."""

import ast
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape
from math import ceil
from pathlib import Path
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests
from matplotlib import pyplot as plt
from matplotlib.colors import to_rgb

# APIM Samples imports
import azure_resources as az
import utils
from ai_models import ApprovedModel
from apimrequests import ApimRequests
from test_helpers import create_mock_http_response, create_mock_session_with_response

SAMPLE = Path(__file__).resolve().parents[2] / 'samples' / 'aoai-v1-routing'
SPEC = importlib.util.spec_from_file_location('routing_helpers', SAMPLE / 'routing_helpers.py')
helpers = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = helpers
SPEC.loader.exec_module(helpers)
REQUEST_ID = '12345678-1234-1234-1234-123456789abc'


def response(status = 200, body = None, headers = None):
    """Build the shared client's actual result shape."""
    if body is None:
        body = {'choices': [{'message': {'content': 'Hello'}}]}
    if headers is None:
        headers = {'X-Routing-Request-Id': REQUEST_ID, 'X-Routing-Pool': f'aoai-v1-routing-1-{ApprovedModel.GPT_5_MINI.model_name}-standard-pool'}

    return [{'status_code': status, 'response': json.dumps(body), 'headers': headers, 'response_time': 0.25}]


def client_for(rows):
    """Provide an injected context-managed remote boundary."""
    client = MagicMock(spec = ApimRequests)
    client.__enter__.return_value = client
    client.multiPost.return_value = rows

    return client


def responses_body():
    """Represent raw Responses output, including reasoning before assistant text."""
    return {
        'object': 'response',
        'status': 'completed',
        'error': None,
        'output': [
            {'type': 'reasoning', 'summary': []},
            {
                'type': 'message', 'role': 'assistant', 'status': 'completed',
                'content': [{'type': 'output_text', 'text': 'Hello from Responses'}],
            },
        ],
    }


@pytest.mark.parametrize('input_value', ['Reply hello.', [{'role': 'user', 'content': 'Reply hello.'}]])
def test_responses_probe_reads_raw_output_without_retaining_text(input_value):
    """Responses text is nested in output items, not Chat Completions choices."""
    payload = {'model': ApprovedModel.GPT_5_MINI.model_name, 'input': input_value, 'store': False}
    client = client_for(response(body = responses_body()))
    path = '/sample/openai/v1/responses?probe=true'
    result = helpers.probe(lambda: client, path, payload)
    assert result.status == 200 and result.completion
    assert result.request_id == REQUEST_ID
    assert 'Hello from Responses' not in repr(result)
    assert payload['input'] == input_value and payload['store'] is False
    client.multiPost.assert_called_once_with(path, 1, data = payload, headers = None, printResponse = False)
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('changes', [
    {'status': 'incomplete'},
    {'status': 'in_progress'},
    {'object': 'chat.completion'},
    {'error': {'code': 'server_error'}},
    {'output': []},
    {'output': [{'type': 'reasoning'}]},
    {'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed', 'content': [{'type': 'output_text', 'text': ' '}]}]},
    {'output': [{'type': 'message', 'role': 'user', 'status': 'completed', 'content': [{'type': 'output_text', 'text': 'not assistant output'}]}]},
    {'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed', 'content': 'not a content array'}]},
])
def test_responses_probe_rejects_noncompleted_or_missing_assistant_text(changes):
    """HTTP 200 alone must not pass a Responses inference gate."""
    client = client_for(response(body = {**responses_body(), **changes}))
    with pytest.raises(ValueError, match = 'Responses'):
        helpers.probe(lambda: client, '/sample/openai/v1/responses', {})
    client.__exit__.assert_called_once()
    client.multiPost.assert_called_once()


@pytest.mark.parametrize('path,body', [
    ('/sample/openai/v1/responses', {'choices': [{'message': {'content': 'Wrong API'}}]}),
    ('/sample/openai/v1/chat/completions', responses_body()),
])
def test_probe_requires_the_requested_operation_response_shape(path, body):
    """A misrouted operation cannot pass using the other endpoint's success shape."""
    client = client_for(response(body = body))
    with pytest.raises(ValueError):
        helpers.probe(lambda: client, path, {})
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('sku', ['Standard', 'GlobalStandard'])
@pytest.mark.parametrize('models', [
    [ApprovedModel.GPT_5_MINI],
    [ApprovedModel.GPT_5_MINI, ApprovedModel.GPT_5_NANO],
    [ApprovedModel.GPT_5_MINI, ApprovedModel.GPT_5_NANO, ApprovedModel.GPT_5_1],
])
def test_model_list_can_grow_and_shrink_without_routing_changes(sku, models):
    """Every selected model keeps its exact deployment identity, including dots."""
    result = helpers.build_models('aoai-v1-routing-1', models, sku, 10)
    assert len(result) == len(models)
    for row, model in zip(result, models, strict = True):
        assert row['deploymentName'] == row['name'] == model.model_name
        assert row['version'] == model.version
        assert row['capacity'] == 10
        assert not {'poolName', 'backendName'} & row.keys()


@pytest.mark.parametrize('name,models,sku,capacity', [
    (None, [ApprovedModel.GPT_5_MINI], 'Standard', 10),
    ('other-sample', [ApprovedModel.GPT_5_MINI], 'Standard', 10),
    ('aoai-v1-routing-UPPER', [ApprovedModel.GPT_5_MINI], 'Standard', 10),
    ('aoai-v1-routing-' + 'a' * 17, [ApprovedModel.GPT_5_MINI], 'Standard', 10),
    ('aoai-v1-routing-1', [], 'Standard', 10),
    ('aoai-v1-routing-1', ['not-an-enum'], 'Standard', 10),
    ('aoai-v1-routing-1', [ApprovedModel.GPT_5_MINI] * 2, 'Standard', 10),
    ('aoai-v1-routing-1', [ApprovedModel.GPT_5_MINI], 'ProvisionedManaged', 10),
    ('aoai-v1-routing-1', [ApprovedModel.GPT_5_MINI], 'GlobalProvisionedManaged', 10),
    ('aoai-v1-routing-1', [ApprovedModel.GPT_5_MINI], 'Standard', 0),
    ('aoai-v1-routing-1', [ApprovedModel.GPT_5_MINI], 'Standard', True),
    ('aoai-v1-routing-1', [ApprovedModel.GPT_5_MINI], 'Standard', '10'),
])
def test_invalid_configuration_fails_before_deployment(name, models, sku, capacity):
    """Reject PTU purchasing, unsafe names and malformed deployment data."""
    with pytest.raises(ValueError):
        helpers.build_models(name, models, sku, capacity)


@pytest.mark.parametrize('model_name', ['unsafe/name', 'UPPER', 'a' * 49, 'a' * 40])
def test_future_catalog_name_safety(monkeypatch, model_name):
    """New catalog entries cannot overflow APIM backend identifiers."""
    monkeypatch.setattr(ApprovedModel, 'model_name', property(lambda _: model_name))
    with pytest.raises(ValueError):
        helpers.build_models('aoai-v1-routing-' + 'a' * 16, [ApprovedModel.GPT_5_MINI], 'Standard', 10)


def test_select_secret_without_copying_other_outputs():
    """A distinct API output is selected, never an arbitrary first subscription."""
    outputs = [{'name': 'other', 'subscriptionPrimaryKey': 'wrong'}, {'name': 'wanted', 'subscriptionPrimaryKey': 'secret'}]
    assert helpers.subscription_key(outputs, 'wanted') == 'secret'


@pytest.mark.parametrize('outputs', [
    [], [{'name': 'other', 'subscriptionPrimaryKey': 'secret'}],
    [{'name': 'wanted'}], [{'name': 'wanted', 'subscriptionPrimaryKey': ' '}],
    [{'name': 'wanted', 'subscriptionPrimaryKey': 7}],
    [{'name': 'wanted', 'subscriptionPrimaryKey': 'one'}, {'name': 'wanted', 'subscriptionPrimaryKey': 'two'}],
])
def test_secret_selection_rejects_missing_or_ambiguous_outputs(outputs):
    """Never silently use a wrong or malformed subscription key."""
    with pytest.raises(ValueError, match = 'exactly one'):
        helpers.subscription_key(outputs, 'wanted')


def test_completion_probe_uses_shared_client_and_closes_it():
    """The helper performs exactly one request and retains no completion content."""
    client = client_for(response())
    selector = ApprovedModel.GPT_5_MINI.model_name
    payload = {'model': selector, 'stream': False}
    headers = {'x-ai-model': selector}
    result = helpers.probe(lambda: client, '/sample/chat/completions', payload, headers = headers)
    assert result.status == 200 and result.completion
    assert result.request_id == REQUEST_ID
    assert result.pool.endswith(f'-{selector}-standard-pool')
    assert result.error_code is None and result.error_message is None
    assert 'Hello' not in repr(result)
    client.multiPost.assert_called_once_with('/sample/chat/completions', 1, data = payload, headers = headers, printResponse = False)
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('path,body', [
    ('/sample/chat/completions', {'choices': [{'message': {'content': 'private completion'}}]}),
    ('/sample/responses', responses_body()),
])
def test_real_shared_client_session_cleanup(monkeypatch, path, body):
    """Exercise actual shared-client parsing and cleanup for both response contracts."""
    mock_response = create_mock_http_response(status_code = 200, json_data = body)
    selector = ApprovedModel.GPT_5_MINI.model_name
    mock_response.headers = {'Content-Type': 'application/json', 'x-routing-request-id': REQUEST_ID, 'x-routing-pool': f'aoai-v1-routing-1-{selector}-standard-pool'}
    session = create_mock_session_with_response(mock_response)
    monkeypatch.setattr('apimrequests.requests.Session', lambda: session)
    result = helpers.probe(lambda: ApimRequests('https://gateway.invalid', 'secret'), path, {'model': selector})
    assert result.completion
    session.close.assert_called_once()


@pytest.mark.parametrize('path', ['/sample/chat/completions', '/sample/responses'])
@pytest.mark.parametrize('status,code,message', [
    (404, 'ModelNotAvailable', 'The specified model is not available for use'),
    (400, 'InvalidRequest', 'The request payload is invalid.'),
    (403, 'SubscriptionNotAllowed', 'The subscription is not permitted for this scenario.'),
    (404, 'DeploymentNotFound', 'The upstream service rejected the request.'),
    (404, 'model_not_found', 'The upstream service rejected the request.'),
    (429, 'RateLimitReached', 'The upstream service rejected the request.'),
    (404, 'model_not_available', 'The specified model is not available for use'),
    (503, 'UpstreamUnavailable', 'The upstream service is unavailable.'),
    (504, 'UpstreamTimeout', 'The upstream request timed out.'),
    (500, 'GatewayError', 'The gateway could not complete the request.'),
])
def test_probe_keeps_distinct_safe_error_evidence(path, status, code, message):
    """Actual error identities, not HTTP statuses alone, survive normalization."""
    client = client_for(response(status, {'error': {'code': code, 'message': message}}))
    result = helpers.probe(lambda: client, path, {})
    assert (result.status, result.error_code, result.error_message, result.completion) == (status, code, message, False)
    client.multiPost.assert_called_once()
    client.__exit__.assert_called_once()


def test_local_early_return_needs_no_pool_header():
    """A local model rejection has correlation but no fabricated selected pool."""
    client = client_for(response(
        404, {'error': {'code': 'ModelNotAvailable', 'message': 'The specified model is not available for use'}},
        {'x-routing-request-id': REQUEST_ID},
    ))
    result = helpers.probe(lambda: client, '/sample/chat/completions', {})
    assert not result.pool


@pytest.mark.parametrize('path,payload', [('relative', {}), (None, {}), ('/valid', []), ('/valid', None)])
def test_probe_input_errors_do_not_open_a_client(path, payload):
    """Bad local inputs create no remote resources."""
    factory = MagicMock()
    with pytest.raises(ValueError):
        helpers.probe(factory, path, payload)
    factory.assert_not_called()


@pytest.mark.parametrize('rows', [
    [], [None], [{}, {}], [{'status_code': True}], [{'status_code': 600}], [{'status_code': '404'}],
    [{'status_code': 200, 'response': None}],
    [{'status_code': 200, 'response': '{'}],
    [{'status_code': 200, 'response': '[]', 'headers': {}}],
    [{'status_code': 200, 'response': '{}', 'headers': []}],
    response(headers = {}),
    response(headers = {'x-routing-request-id': 7}),
    response(headers = {'x-routing-request-id': REQUEST_ID, 'x-routing-pool': '../unsafe'}),
    response(headers = {'x-routing-request-id': REQUEST_ID, 'x-routing-pool': 7}),
    response(body = {}),
    response(body = {'choices': []}),
    response(body = {'choices': ['bad']}),
    response(body = {'choices': [{'message': {'content': None}}]}),
    response(body = {'choices': [{'message': {'content': ' '}}]}),
    response(status = 201),
    response(status = 404, body = {'message': 'status alone is not evidence'}),
    response(status = 404, body = {'error': {'code': 'Untrusted', 'message': 'The upstream service rejected the request.'}}),
    response(status = 404, body = {'error': {'code': 'DeploymentNotFound', 'message': 'sensitive backend details'}}),
    response(status = 404, body = {'error': {'code': {}, 'message': []}}),
])
def test_malformed_remote_results_always_close_client(rows):
    """Success-looking responses, unsafe errors and parser failures cannot pass."""
    client = client_for(rows)
    with pytest.raises(ValueError):
        helpers.probe(lambda: client, '/sample/chat/completions', {})
    client.__exit__.assert_called_once()
    client.multiPost.assert_called_once()


def test_transport_failure_closes_without_retry_or_sleep():
    """No hidden readiness retries can obscure actual backend failure evidence."""
    client = client_for([])
    client.multiPost.side_effect = RuntimeError('transport failed')
    with pytest.raises(RuntimeError, match = 'transport failed'):
        helpers.probe(lambda: client, '/sample/chat/completions', 'not-an-object')
    client.__exit__.assert_called_once()
    client.multiPost.assert_called_once()


CAPACITY_LABELS = {f'{tier}.example.invalid': tier for tier in ('global-standard', 'ptu', 'consumption')}
CAPACITY_POOL = f'aoai-v1-routing-1-{ApprovedModel.GPT_5_MINI.model_name}-standard-pool'


def capacity_response(tier, status = 200, *, path = '/sample/chat/completions', retry_after = None):
    """Build real-operation response shapes with exact, independent backend evidence."""
    headers = {'x-routing-request-id': REQUEST_ID, 'x-routing-pool': CAPACITY_POOL}
    if tier:
        headers['x-routing-backend-host'] = f'{tier}.example.invalid'
    if retry_after is not None:
        headers['Retry-After'] = retry_after
    body = responses_body() if path.endswith('/responses') else {'choices': [{'message': {'content': 'Hello'}}]}
    if status >= 400:
        body = {'error': {'code': 'UpstreamError', 'message': 'The upstream service rejected the request.'}}

    return response(status, body, headers)


def capacity_test(client, *, path = '/sample/chat/completions', sleep = None, **overrides):
    """Inject an owned shared client and a no-delay clock into the public scenario."""
    payload = {'model': ApprovedModel.GPT_5_MINI.model_name, 'stream': False, 'store': False}
    arguments = {
        'pool': CAPACITY_POOL, 'backend_labels': CAPACITY_LABELS,
        'preferred_labels': ('global-standard', 'consumption'), 'fallback_label': 'ptu',
        'max_requests': 8, 'clock': lambda: 0.0, **overrides,
    }

    return helpers.exercise_capacity(
        lambda: client, path, payload, {**payload, 'input': 'pressure'},
        sleep = sleep if sleep is not None else MagicMock(), **arguments,
    )


@pytest.mark.parametrize('path', ['/sample/chat/completions', '/sample/responses'])
@pytest.mark.parametrize('gateway_exhaustion', [False, True])
@pytest.mark.parametrize('wait_for_initial_cooldown', [True, False])
def test_capacity_proves_ordered_failover_exhaustion_and_single_recovery(path, gateway_exhaustion, wait_for_initial_cooldown):
    """Require real per-tier 429s, a later fallback completion and overlapping exhaustion."""
    steps = [
        ('global-standard', 200, None), ('global-standard', 429, '70'),
        ('consumption', 200, None), ('consumption', 429, '60'),
        ('ptu', 200, None), ('ptu', 429, '60'), (None, 503, '60'),
        ('global-standard', 200, None),
    ]
    client = client_for([])
    rows = [capacity_response(tier, status, path = path, retry_after = retry) for tier, status, retry in steps]
    if gateway_exhaustion:
        rows[-2] = response(
            503, {'error': {'code': 'UpstreamUnavailable', 'message': 'The upstream service is unavailable.'}},
            {'x-routing-request-id': REQUEST_ID},
        )
    client.multiPost.side_effect = rows
    sleep = MagicMock()
    result = capacity_test(client, path = path, sleep = sleep, wait_for_initial_cooldown = wait_for_initial_cooldown)
    assert result.fallback_served and result.exhausted and result.recovery.completion
    assert result.baseline.backend_host == 'global-standard.example.invalid'
    assert [row.status for row in result.pressure] == [429, 200, 429, 200, 429, 503]
    if gateway_exhaustion:
        assert result.pressure[-1].error_code == 'UpstreamUnavailable'
        assert not result.pressure[-1].pool and not result.pressure[-1].backend_host
    assert [call.args for call in sleep.call_args_list] == ([(65,), (65,)] if wait_for_initial_cooldown else [(65,)])
    assert client.multiPost.call_count == len(steps)
    client.__exit__.assert_called_once()
    assert all(call.args == (path, 1) for call in client.multiPost.call_args_list)
    assert all(call.kwargs['printResponse'] is False for call in client.multiPost.call_args_list)
    assert 'Hello' not in repr(result) and "'input'" not in repr(result)


@pytest.mark.parametrize('steps', [
    [('global-standard', 200)] * 4,
    [(None, 503)] * 4,
    [('global-standard', 429), ('ptu', 200), (None, 503), (None, 503)],
    [('ptu', 200), ('global-standard', 429), ('consumption', 429), (None, 503)],
])
def test_capacity_never_passes_without_ordered_complete_evidence(steps):
    """Healthy-only traffic, one 429, isolated 503s or premature fallback cannot pass."""
    client = client_for([])
    client.multiPost.side_effect = [
        capacity_response('global-standard'),
        *[capacity_response(tier, status) for tier, status in steps],
        capacity_response('consumption'),
    ]
    result = capacity_test(client, max_requests = 4)
    assert not result.fallback_served and not result.exhausted
    assert len(result.pressure) == 4 and result.recovery.completion
    client.__exit__.assert_called_once()


def test_capacity_expired_429_windows_do_not_prove_exhaustion():
    """Throttles spread beyond the trip window cannot be combined into false proof."""
    elapsed = [0.0]
    rows = iter([
        capacity_response('global-standard'),
        capacity_response('global-standard', 429),
        capacity_response('consumption', 429),
        capacity_response('ptu', 200),
        capacity_response('ptu', 429),
        capacity_response(None, 503),
        capacity_response('global-standard'),
    ])

    def remote(*_args, **_kwargs):
        elapsed[0] += 40
        return next(rows)

    client = client_for([])
    client.multiPost.side_effect = remote
    result = capacity_test(client, max_requests = 5, max_seconds = 300, clock = lambda: elapsed[0])
    assert not result.fallback_served and not result.exhausted


def test_capacity_success_invalidates_an_earlier_throttle_observation():
    """A recovered member cannot still count as unavailable because of an old 429."""
    client = client_for([])
    steps = [
        ('global-standard', 200), ('global-standard', 429), ('consumption', 429),
        ('global-standard', 200), ('ptu', 200), ('ptu', 429), (None, 503),
        ('global-standard', 200),
    ]
    client.multiPost.side_effect = [capacity_response(tier, status) for tier, status in steps]
    result = capacity_test(client, max_requests = 6)
    assert not result.fallback_served and not result.exhausted


def test_capacity_burst_exhausts_before_the_first_member_recovers():
    """Reproduce sequential quota replenishment using model latency and real request limits."""
    clients = []
    elapsed = [0.0]
    pressure_calls = [0]
    used = dict.fromkeys(('global-standard', 'consumption', 'ptu'), 0)
    blocked_until = dict.fromkeys(used, 0.0)
    remote_lock = Lock()

    def clock():
        return elapsed[0] + 3 * ceil(pressure_calls[0] / max(1, len(clients)))

    def remote(_path, _runs, *, data, **_kwargs):
        if data.get('input') != 'pressure':
            return capacity_response('global-standard')
        with remote_lock:
            pressure_calls[0] += 1
            now = clock()
            for tier in used:
                if blocked_until[tier] > now:
                    continue
                if blocked_until[tier]:
                    used[tier] = 0
                    blocked_until[tier] = 0
                used[tier] += 1
                if used[tier] > 15:
                    blocked_until[tier] = now + 60
                    return capacity_response(tier, 429, retry_after = '60')
                return capacity_response(tier)

        return capacity_response(None, 503)

    def factory():
        client = client_for([])
        client.multiPost.side_effect = remote
        clients.append(client)
        return client

    payload = {'model': ApprovedModel.GPT_5_MINI.model_name, 'stream': False}
    result = helpers.exercise_capacity(
        factory, '/sample/chat/completions', payload, {**payload, 'input': 'pressure'},
        pool = CAPACITY_POOL, backend_labels = CAPACITY_LABELS,
        preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
        max_requests = 80, max_seconds = 300, concurrency = 4,
        sleep = lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds), clock = clock,
    )
    assert result.fallback_served and result.exhausted and result.recovery.completion
    assert len(result.pressure) <= 80
    assert result.stop_reason == 'exhausted'
    for client in clients:
        client.__exit__.assert_called_once()


@pytest.mark.parametrize('path', ['/sample/chat/completions', '/sample/responses'])
@pytest.mark.parametrize('preferred,fallback', [
    (('global-standard', 'consumption'), 'ptu'),
    (('ptu', 'consumption'), 'global-standard'),
])
def test_larger_sequential_load_exhausts_before_preferred_windows_expire(monkeypatch, path, preferred, fallback):
    """Model input-quota consumption and latency, not Azure's actual quota conversion."""
    def run(repetitions, max_requests):
        elapsed = [0.0]
        used = dict.fromkeys((*preferred, fallback), 0)
        blocked_until = dict.fromkeys(used, 0.0)
        client = client_for([])

        def remote(_path, _runs, *, data, **_kwargs):
            elapsed[0] += 1.5
            text = data['input'] if path.endswith('/responses') else data['messages'][0]['content']
            units = text.count('Capacity routing context. ')
            if not units:
                return capacity_response(preferred[0], path = path)
            for tier in used:
                if blocked_until[tier] > elapsed[0]:
                    continue
                if blocked_until[tier]:
                    used[tier] = 0
                    blocked_until[tier] = 0
                used[tier] += units
                if used[tier] > 3000:
                    blocked_until[tier] = elapsed[0] + 30
                    return capacity_response(tier, 429, path = path, retry_after = '30')
                return capacity_response(tier, path = path)

            return capacity_response(None, 503, path = path)

        client.multiPost.side_effect = remote
        baseline = {'model': ApprovedModel.GPT_5_MINI.model_name, 'stream': False}
        text = 'Capacity routing context. ' * repetitions + 'Reply with a short greeting.'
        field = 'input' if path.endswith('/responses') else 'messages'
        baseline[field] = 'Reply with a short greeting.' if field == 'input' else [{'role': 'user', 'content': 'Reply with a short greeting.'}]
        load = {**baseline, field: text if field == 'input' else [{'role': 'user', 'content': text}]}
        evidence = helpers.exercise_capacity(
            lambda: client, path, baseline, load,
            pool = CAPACITY_POOL, backend_labels = CAPACITY_LABELS,
            preferred_labels = preferred, fallback_label = fallback, max_requests = max_requests,
            clock = lambda: elapsed[0], sleep = lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds),
        )
        assert client.multiPost.call_count == len(evidence.pressure) + 2
        client.__exit__.assert_called_once()

        return evidence

    previous = run(200, 80)
    assert not previous.exhausted and previous.stop_reason == 'time-limit'
    namespace, _ = initialized_notebook(monkeypatch)
    current = run(namespace['load_context_repetitions'], namespace['pressure_max_requests'])
    assert current.fallback_served and current.exhausted and current.recovery.completion
    assert len(current.pressure) <= namespace['pressure_max_requests']
    assert current.stop_reason == 'exhausted'


@pytest.mark.parametrize('worker_fails', [False, True])
def test_capacity_uses_independent_concurrent_clients_and_drains_before_cleanup(worker_fails):
    """Four POSTs overlap without sharing sessions; worker failures still close every owner."""
    clients = []
    barrier = Barrier(4, timeout = 5)
    lock = Lock()
    active = set()
    overlap = []

    def factory():
        client = client_for([])
        index = len(clients)

        def remote(_path, _runs, *, data, **_kwargs):
            if data.get('input') != 'pressure':
                return capacity_response('global-standard')
            with lock:
                assert index not in active
                active.add(index)
                overlap.append(len(active))
            try:
                barrier.wait()
                if worker_fails and index == 2:
                    raise requests.Timeout('worker timed out')
                return capacity_response('global-standard')
            finally:
                with lock:
                    active.remove(index)

        client.multiPost.side_effect = remote
        clients.append(client)
        return client

    payload = {'model': ApprovedModel.GPT_5_MINI.model_name, 'stream': False}

    def run():
        return helpers.exercise_capacity(
            factory, '/sample/chat/completions', payload, {**payload, 'input': 'pressure'},
            pool = CAPACITY_POOL, backend_labels = CAPACITY_LABELS,
            preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
            max_requests = 4, concurrency = 4, sleep = MagicMock(), clock = lambda: 0.0,
        )

    if worker_fails:
        with pytest.raises(requests.Timeout, match = 'worker timed out'):
            run()
    else:
        result = run()
        assert len(result.pressure) == 4 and result.stop_reason == 'request-limit'
    assert len(clients) == 4 and max(overlap) == 4 and not active
    for client in clients:
        client.__exit__.assert_called_once()


@pytest.mark.parametrize('steps', [
    [('global-standard', 429), ('consumption', 429), ('ptu', 200), ('ptu', 429)],
    [('global-standard', 429), ('consumption', 429), ('ptu', 429), (None, 503)],
])
def test_capacity_already_inflight_requests_cannot_prove_later_routing_decisions(steps):
    """A same-batch success/503 is not causally after that batch's new 429 observations."""
    rows = iter([capacity_response(tier, status) for tier, status in steps])
    lock = Lock()

    def remote(_path, _runs, *, data, **_kwargs):
        if data.get('input') != 'pressure':
            return capacity_response('global-standard')
        with lock:
            return next(rows)

    def factory():
        client = client_for([])
        client.multiPost.side_effect = remote
        return client

    payload = {'model': ApprovedModel.GPT_5_MINI.model_name, 'stream': False}
    result = helpers.exercise_capacity(
        factory, '/sample/chat/completions', payload, {**payload, 'input': 'pressure'},
        pool = CAPACITY_POOL, backend_labels = CAPACITY_LABELS,
        preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
        max_requests = 4, concurrency = 4, sleep = MagicMock(), clock = lambda: 0.0,
    )
    assert not result.fallback_served and not result.exhausted


def test_capacity_rejects_a_factory_that_shares_a_client_between_workers():
    """A factory must not introduce concurrent access to one requests session."""
    client = client_for(capacity_response('global-standard'))
    with pytest.raises(ValueError, match = 'distinct clients'):
        capacity_test(client, concurrency = 2)
    client.multiPost.assert_called_once()
    client.__exit__.assert_called_once()


def test_capacity_time_budget_stops_starting_requests_and_preserves_input():
    """A slow in-flight call can finish, but no further pressure call starts after budget."""
    elapsed = [0.0]
    rows = iter([capacity_response('global-standard')] * 3)

    def remote(*_args, **_kwargs):
        elapsed[0] += 100
        return next(rows)

    client = client_for([])
    client.multiPost.side_effect = remote
    result = capacity_test(client, clock = lambda: elapsed[0])
    assert len(result.pressure) == 1 and not result.exhausted
    assert result.stop_reason == 'time-limit'
    assert client.multiPost.call_count == 3  # Baseline, one pressure call, one recovery call.


@pytest.mark.parametrize('bad_response', [
    capacity_response(None), capacity_response('unknown'),
    capacity_response('global-standard', 400), capacity_response('global-standard', 504),
    response(
        500, {'error': {'code': 'GatewayError', 'message': 'The gateway could not complete the request.'}},
        {'x-routing-request-id': REQUEST_ID},
    ),
])
def test_capacity_stops_on_faulty_baseline_or_unexpected_pressure_and_closes(bad_response):
    """Configuration, validation and connectivity errors are not called capacity exhaustion."""
    client = client_for([])
    client.multiPost.side_effect = [capacity_response('global-standard'), bad_response]
    with pytest.raises(RuntimeError, match = 'capacity-test response'):
        capacity_test(client)
    assert client.multiPost.call_count == 2
    client.__exit__.assert_called_once()


def test_capacity_unhealthy_baseline_never_starts_pressure():
    """Do not generate more billable traffic when the preferred warm path is already broken."""
    client = client_for(capacity_response('ptu'))
    with pytest.raises(RuntimeError, match = 'baseline'):
        capacity_test(client)
    client.multiPost.assert_called_once()
    client.__exit__.assert_called_once()


def test_capacity_long_retry_after_and_transport_failure_always_close():
    """Never sleep unboundedly or silently replay a failed model POST."""
    client = client_for([])
    client.multiPost.side_effect = [capacity_response('global-standard'), capacity_response('global-standard', 429, retry_after = '86400')]
    sleep = MagicMock()
    with pytest.raises(RuntimeError, match = 'bounded recovery'):
        capacity_test(client, sleep = sleep, max_requests = 1)
    sleep.assert_called_once_with(65)
    client.__exit__.assert_called_once()

    client = client_for([])
    client.multiPost.side_effect = [capacity_response('global-standard'), requests.Timeout('transport timeout')]
    with pytest.raises(requests.Timeout):
        capacity_test(client)
    assert client.multiPost.call_count == 2
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('overrides', [
    {'max_requests': 0}, {'max_requests': True}, {'max_requests': 201},
    {'max_seconds': 0}, {'max_seconds': 301}, {'recovery_limit_seconds': 64},
    {'recovery_limit_seconds': 601}, {'preferred_labels': ('ptu', 'ptu')},
    {'fallback_label': 'consumption'}, {'backend_labels': {}},
    {'concurrency': 0}, {'concurrency': 9}, {'concurrency': True}, {'wait_for_initial_cooldown': None},
])
def test_capacity_invalid_configuration_creates_no_client_or_delay(overrides):
    """Reject unbounded or inconsistent experiments before any remote work."""
    client = client_for([])
    sleep = MagicMock()
    with pytest.raises(ValueError):
        capacity_test(client, sleep = sleep, **overrides)
    client.__enter__.assert_not_called()
    sleep.assert_not_called()


def test_backend_labels_parse_exact_distinct_deployed_https_origins():
    """Use published origins, not account-name assumptions or URL substring matching."""
    accounts = [{'label': label, 'endpoint': f'https://{host}/'} for host, label in CAPACITY_LABELS.items()]
    assert helpers.capacity_backend_labels(accounts) == CAPACITY_LABELS
    for endpoint in ('http://ptu.example.invalid', 'https://user@ptu.example.invalid', 'https://ptu.example.invalid:444', 'https://ptu.example.invalid/path'):
        with pytest.raises(ValueError, match = 'HTTPS inference origins'):
            helpers.capacity_backend_labels([*accounts[:2], {**accounts[2], 'endpoint': endpoint}])
    with pytest.raises(ValueError, match = 'Redeploy'):
        helpers.capacity_backend_labels([{'label': 'ptu'}])
    with pytest.raises(ValueError, match = 'three distinct'):
        helpers.capacity_backend_labels(accounts[:2])
    with pytest.raises(ValueError, match = 'distinct HTTPS'):
        helpers.capacity_backend_labels([*accounts[:2], accounts[0]])


def test_probe_retains_backend_host_and_normalizes_retry_after(monkeypatch):
    """Retain bounded routing evidence and normalize both standard Retry-After formats."""
    now = datetime(2026, 11, 23, 12, 0, tzinfo = timezone.utc)
    fake_datetime = MagicMock()
    fake_datetime.now.return_value = now
    monkeypatch.setattr(helpers, 'datetime', fake_datetime)
    for value, expected in [('12', 12), (format_datetime(now.replace(minute = 1)), 60), (format_datetime(now.replace(hour = 11)), 0)]:
        client = client_for(capacity_response('ptu', 429, retry_after = value))
        result = helpers.probe(lambda: client, '/sample/chat/completions', {})
        assert result.backend_host == 'ptu.example.invalid'
        assert result.retry_after_seconds == expected


@pytest.mark.parametrize('status', [200, 429])
def test_probe_retains_measured_response_time(status):
    """Keep the shared client's measured latency for both successes and errors."""
    rows = capacity_response('ptu', status)
    rows[0]['response_time'] = 1.234
    result = helpers.probe(lambda: client_for(rows), '/sample/chat/completions', {})
    assert result.response_time_seconds == 1.234


@pytest.mark.parametrize('duration', [None, True, -0.1, float('inf'), float('nan'), '1.0'])
def test_probe_rejects_invalid_response_time(duration):
    """Missing or invalid timing is not silently rendered as a real measurement."""
    rows = capacity_response('ptu')
    rows[0]['response_time'] = duration
    client = client_for(rows)
    with pytest.raises(ValueError, match = 'response time'):
        helpers.probe(lambda: client, '/sample/chat/completions', {})
    client.__exit__.assert_called_once()


def chart_probe(status, tier, duration = None, pool = CAPACITY_POOL, retry_after = 0):
    """Create sanitized observations without response bodies."""
    args = (status, None, None, status == 200, pool, REQUEST_ID, f'{tier}.example.invalid' if tier else '', retry_after)
    if duration is None:
        return helpers.ProbeResult(*args)

    return helpers.TimedProbeResult(*args, response_time_seconds = duration)


@pytest.mark.parametrize('duration', [0.1, None])
@pytest.mark.parametrize('timed', [False, True])
@pytest.mark.parametrize('recovery_status', [200, 500])
def test_capacity_chart_places_legend_below_axis_without_overlapping_footer(duration, timed, recovery_status):
    """Keep the legend, axis label and footer separate for current and older evidence."""
    baseline = chart_probe(200, 'global-standard', duration)
    pressure = (chart_probe(429, 'global-standard', duration, retry_after = 5), chart_probe(503, None, duration))
    recovery = chart_probe(recovery_status, 'global-standard' if recovery_status == 200 else None, duration)
    evidence = (
        helpers.TimedCapacityEvidence(baseline, pressure, recovery, True, True, 27, observation_times_seconds = (0, 1, 2, 30))
        if timed else helpers.CapacityEvidence(baseline, pressure, recovery, True, True, 27)
    )
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        latency, routing = figure.axes
        legend = routing.get_legend()
        expected = ['HTTP 200 - completed', 'HTTP 429 - throttled']
        if recovery_status == 500:
            expected.append('HTTP 500 - other')
        expected.append('HTTP 503 - unavailable')
        if timed:
            expected.append('Reported Retry-After (not breaker state)')
        assert [text.get_text() for text in legend.get_texts()] == expected

        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        legend_bounds = legend.get_window_extent(renderer)
        label_bounds = routing.xaxis.label.get_window_extent(renderer)
        summary_bounds = figure.texts[1].get_window_extent(renderer)
        assert figure.bbox.contains(legend_bounds.x0, legend_bounds.y0)
        assert figure.bbox.contains(legend_bounds.x1, legend_bounds.y1)
        assert summary_bounds.y1 < legend_bounds.y0 < legend_bounds.y1 < label_bounds.y0
        assert 0 < latency.bbox.y0 - routing.bbox.y1 < 0.08 * figure.bbox.height
    finally:
        plt.close(figure)


@pytest.mark.parametrize('pressure_count', [1, 2, 6, 14, 20, 30, 44, 68, 80, 200])
def test_capacity_chart_places_responses_in_equally_spaced_observation_order(pressure_count):
    """Keep concurrent responses readable without presenting their spacing as elapsed time."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    pressure = tuple(chart_probe(200, 'global-standard', 0.2) for _ in range(pressure_count))
    times = (0.0, *(0.5 + (index // 4) * 1.1 + (index % 4) * 0.0001 for index in range(pressure_count)), 80.0)
    evidence = helpers.TimedCapacityEvidence(baseline, pressure, baseline, False, False, 65, observation_times_seconds = times)
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        latency, routing = figure.axes
        centers = [bar.get_x() + bar.get_width() / 2 for container in latency.containers for bar in container]
        assert centers == pytest.approx(range(len(times)))
        completed = next(collection for collection in routing.collections if collection.get_label() == 'HTTP 200 - completed')
        assert [point[0] for point in completed.get_offsets()] == pytest.approx(centers)
        request_axis = latency.child_axes[0]
        assert 'load request number' in request_axis.get_xlabel()
        assert 'equally spaced, not to scale' in request_axis.get_xlabel()
        assert routing.get_xlabel() == 'Request\nTime'
        ticks = routing.get_xticks().astype(int).tolist()
        assert ticks[0] == 0 and ticks[-1] == len(times) - 1
        assert ticks[1] == 1 and ticks[-2] == pressure_count
        assert all(tick in (1, pressure_count) or tick % 5 == 0 for tick in ticks[1:-1])
        if pressure_count == 14:
            assert ticks == [0, 1, 5, 10, 14, 15]
        if pressure_count == 20:
            assert ticks == [0, 1, 5, 10, 15, 20, 21]
        assert request_axis.get_xticks().tolist() == ticks
        requests = [
            'Warm-up' if index == 0 else 'Recovery' if index == len(times) - 1 else str(index)
            for index in ticks
        ]
        assert [tick.get_text() for tick in request_axis.get_xticklabels()] == requests
        assert [tick.get_text() for tick in routing.get_xticklabels()] == [
            f'{request}\n' + (f'{times[index] - times[1]:.1f}s' if index else '')
            for request, index in zip(requests, ticks, strict = True)
        ]
        assert evidence.observation_times_seconds == times
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        for axis in (request_axis, routing):
            tick_boxes = [tick.get_window_extent(renderer) for tick in axis.get_xticklabels()]
            assert all(not first.overlaps(second) for first, second in zip(tick_boxes, tick_boxes[1:]))
            assert all(figure.bbox.contains(box.x0, box.y0) and figure.bbox.contains(box.x1, box.y1) for box in tick_boxes)
            label_bounds = axis.xaxis.label.get_window_extent(renderer)
            assert figure.bbox.contains(label_bounds.x0, label_bounds.y0) and figure.bbox.contains(label_bounds.x1, label_bounds.y1)
        assert label_bounds.x1 < routing.bbox.x0 and label_bounds.x1 < tick_boxes[0].x0
        assert label_bounds.y0 == pytest.approx(tick_boxes[0].y0, abs = 1)
        assert label_bounds.y1 == pytest.approx(tick_boxes[0].y1, abs = 1)
        assert request_axis.get_tightbbox(renderer).y1 < figure.texts[0].get_window_extent(renderer).y0
        for axis in (latency, routing):
            band = next(patch for patch in axis.patches if patch.get_label() == '_warmup_phase')
            vertices = axis.transData.inverted().transform(band.get_transform().transform(band.get_path().vertices))
            assert (min(vertices[:, 0]), max(vertices[:, 0])) == pytest.approx((-0.65, 0.5))
            bounds = band.get_window_extent(renderer)
            assert (bounds.y0, bounds.y1) == pytest.approx((axis.bbox.y0, axis.bbox.y1))
            assert all(channel >= 0.9 for channel in band.get_facecolor()[:3])
            assert band.get_zorder() < completed.get_zorder()
            marker = next(line for line in axis.lines if line.get_label() == '_recovery_gap_break')
            assert marker.get_window_extent(figure.canvas.get_renderer()).width >= 15
    finally:
        plt.close(figure)


def test_capacity_chart_shades_reported_windows_on_the_verified_backend():
    """Merge overlapping windows, label their actual expiry, and do not attribute a 503."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    pressure = (
        chart_probe(429, 'global-standard', 0.2, retry_after = 5),
        chart_probe(200, 'global-standard', 0.3),
        chart_probe(429, 'global-standard', 0.2, retry_after = 5),
        chart_probe(429, 'consumption', 0.2, retry_after = 2),
        chart_probe(429, 'ptu', 0.2),
        chart_probe(503, 'ptu', 0.1, retry_after = 60),
    )
    evidence = helpers.TimedCapacityEvidence(
        baseline, pressure, baseline, True, True, 65,
        observation_times_seconds = (0, 1, 2, 3, 4, 5, 6, 72),
    )
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        latency, routing = figure.axes
        assert [bar.get_x() + bar.get_width() / 2 for container in latency.containers for bar in container] == pytest.approx(range(8))
        bands = [collection for collection in routing.collections if collection.get_hatch() == '///']
        assert len(bands) == 2
        for band, expected in zip(bands, [(1, 6 + 2 / 66, -0.35, 0.35), (4, 6, 0.65, 1.35)], strict = True):
            vertices = band.get_paths()[0].vertices
            assert (min(vertices[:, 0]), max(vertices[:, 0]), min(vertices[:, 1]), max(vertices[:, 1])) == pytest.approx(expected)
            assert band.get_alpha() == 0.12
        assert [text.get_text() for text in routing.texts] == ['5s durations (0.0s - 7.0s, merged)', '2s duration (3.0s - 5.0s)']
        red = to_rgb(routing.texts[0].get_color())
        background = [1 - 0.12 * (1 - channel) for channel in red]

        def luminance(rgb):
            channels = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in rgb]
            return sum(channel * weight for channel, weight in zip(channels, (0.2126, 0.7152, 0.0722), strict = True))

        assert (luminance(background) + 0.05) / (luminance(red) + 0.05) >= 4.5
        assert 'Reported Retry-After (not breaker state)' in [text.get_text() for text in routing.get_legend().get_texts()]
        completed = next(collection for collection in routing.collections if collection.get_label() == 'HTTP 200 - completed')
        assert completed.get_offsets().tolist() == [[0, 0], [2, 0], [7, 0]]
        figure.canvas.draw()
    finally:
        plt.close(figure)


def test_capacity_chart_staggered_retry_windows_end_at_actual_elapsed_times():
    """Two 30-second windows report their actual end times on a compressed axis."""
    baseline = chart_probe(200, 'consumption', 0.1)
    evidence = helpers.TimedCapacityEvidence(
        baseline,
        (chart_probe(429, 'global-standard', 0.1, retry_after = 30), chart_probe(429, 'consumption', 0.1, retry_after = 30)),
        chart_probe(200, 'global-standard', 0.1), False, False, 5,
        observation_times_seconds = (0, 6.1, 8.1, 41.5),
    )
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        latency, routing = figure.axes
        assert [bar.get_x() + bar.get_width() / 2 for container in latency.containers for bar in container] == pytest.approx(range(4))
        bands = [collection for collection in routing.collections if collection.get_hatch() == '///']
        for band, expected in zip(bands, [(1, 2 + 28 / 33.4), (2, 2 + 30 / 33.4)], strict = True):
            xs = band.get_paths()[0].vertices[:, 0]
            assert (min(xs), max(xs)) == pytest.approx(expected)
        assert [text.get_text() for text in routing.texts] == ['30s duration (0.0s - 30.0s)', '30s duration (2.0s - 32.0s)']
        completed = next(collection for collection in routing.collections if collection.get_label() == 'HTTP 200 - completed')
        assert completed.get_offsets().tolist() == [[0, 1], [3, 0]]
        assert '// 33.4s between final load and recovery responses (compressed)' in ' '.join(text.get_text() for text in figure.texts)
        for axis in (latency, routing):
            breaks = [line for line in axis.lines if line.get_label() == '_recovery_gap_break']
            assert len(breaks) == 1
            assert breaks[0].get_xdata()[0] == pytest.approx(2.5)
    finally:
        plt.close(figure)


@pytest.mark.parametrize('count', [3, 4])
def test_capacity_chart_labels_repeated_30_second_throttles_without_multiplication(count):
    """Each reported delay is 30 seconds; later overlapping reports extend the shaded union."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    pressure = tuple(chart_probe(429, 'global-standard', 0.1, retry_after = 30) for _ in range(count))
    evidence = helpers.TimedCapacityEvidence(
        baseline, pressure, baseline, False, False, 65,
        observation_times_seconds = (0, *range(1, count + 1), 80),
    )
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        routing = figure.axes[1]
        bands = [collection for collection in routing.collections if collection.get_hatch() == '///']
        assert len(bands) == 1
        vertices = bands[0].get_paths()[0].vertices
        assert (min(vertices[:, 0]), max(vertices[:, 0])) == pytest.approx((1, count + 30 / (80 - count)))
        assert [text.get_text() for text in routing.texts] == [f'30s durations (0.0s - {count + 29:.1f}s, merged)']
    finally:
        plt.close(figure)


def test_capacity_chart_keeps_separate_retry_windows_and_reports_duration_range():
    """Disjoint intervals stay separate; labels do not invent a merged Retry-After value."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    pressure = (
        chart_probe(429, 'global-standard', 0.1, retry_after = 5),
        chart_probe(429, 'global-standard', 0.1, retry_after = 2),
        chart_probe(200, 'consumption', 0.1),
        chart_probe(429, 'global-standard', 0.1, retry_after = 2),
        chart_probe(200, 'consumption', 0.1),
    )
    evidence = helpers.TimedCapacityEvidence(
        baseline, pressure, baseline, False, False, 65,
        observation_times_seconds = (0, 1, 2, 4, 8, 11, 80),
    )
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        routing = figure.axes[1]
        bands = [collection for collection in routing.collections if collection.get_hatch() == '///']
        assert len(bands) == 2
        first, second = [band.get_paths()[0].vertices for band in bands]
        assert (min(first[:, 0]), max(first[:, 0])) == pytest.approx((1, 3.5))
        assert (min(second[:, 0]), max(second[:, 0])) == pytest.approx((4, 4 + 2 / 3))
        assert [text.get_text() for text in routing.texts] == ['2-5s durations (0.0s - 5.0s, merged)', '2s duration (7.0s - 9.0s)']
    finally:
        plt.close(figure)


def test_capacity_chart_plots_simultaneous_observations_and_unfinished_windows():
    """Same-time responses remain distinct; a window past recovery keeps its actual expiry."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    pressure = (
        chart_probe(429, 'global-standard', 0.1, retry_after = 5),
        chart_probe(200, 'global-standard', 0.1),
        chart_probe(429, 'ptu', 0.1, retry_after = 100),
    )
    evidence = helpers.TimedCapacityEvidence(
        baseline, pressure, baseline, False, False, 65,
        observation_times_seconds = (0, 1, 1, 2, 10),
    )
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        routing = figure.axes[1]
        bands = [collection for collection in routing.collections if collection.get_hatch() == '///']
        assert len(bands) == 2
        global_vertices, ptu_vertices = [band.get_paths()[0].vertices for band in bands]
        assert (min(global_vertices[:, 0]), max(global_vertices[:, 0])) == pytest.approx((1, 3.5))
        assert (min(ptu_vertices[:, 0]), max(ptu_vertices[:, 0])) == pytest.approx((3, 4.55))
        assert [text.get_text() for text in routing.texts] == ['5s duration (0.0s - 5.0s)', '100s duration (1.0s - 101.0s) (continues)']
        completed = next(collection for collection in routing.collections if collection.get_label() == 'HTTP 200 - completed')
        assert completed.get_offsets().tolist() == [[0, 0], [2, 0], [4, 0]]
    finally:
        plt.close(figure)


def test_capacity_chart_handles_window_expiry_at_duplicate_timestamps():
    """A window ending at multiple simultaneous observations cannot divide by zero."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    evidence = helpers.TimedCapacityEvidence(
        baseline,
        (chart_probe(429, 'global-standard', 0.1, retry_after = 5), baseline, baseline),
        baseline, False, False, 5, observation_times_seconds = (0, 1, 6, 6, 10),
    )
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        routing = figure.axes[1]
        band = next(collection for collection in routing.collections if collection.get_hatch() == '///')
        xs = band.get_paths()[0].vertices[:, 0]
        assert (min(xs), max(xs)) == pytest.approx((1, 3))
        assert [text.get_text() for text in routing.texts] == ['5s duration (0.0s - 5.0s)']
    finally:
        plt.close(figure)


@pytest.mark.parametrize('gap,marked', [(19.9, False), (20.0, True), (20.1, True)])
def test_capacity_chart_marks_only_long_recorded_recovery_gaps(gap, marked):
    """A break describes the observed response gap, not an inferred waiting period."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    evidence = helpers.TimedCapacityEvidence(
        baseline, (baseline,), baseline, False, False, 5, observation_times_seconds = (0, 1, 1 + gap),
    )
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        for axis in figure.axes:
            assert len([line for line in axis.lines if line.get_label() == '_recovery_gap_break']) == (1 if marked else 0)
        summary = ' '.join(text.get_text() for text in figure.texts)
        assert ('between final load and recovery responses (compressed)' in summary) is marked
        if marked:
            assert f'// {gap:.1f}s' in summary
    finally:
        plt.close(figure)


def test_capacity_chart_does_not_invent_a_load_gap_without_load_responses():
    """A long baseline-to-recovery interval is not a last-load-to-recovery gap."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    evidence = helpers.TimedCapacityEvidence(
        baseline, (), baseline, False, False, 65, observation_times_seconds = (0, 65),
    )
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        assert all(not any(line.get_label() == '_recovery_gap_break' for line in axis.lines) for axis in figure.axes)
        assert 'between final load and recovery responses' not in ' '.join(text.get_text() for text in figure.texts)
        routing = figure.axes[1]
        assert routing.get_xlabel() == 'Request\nTime (no load)'
        assert [tick.get_text() for tick in routing.get_xticklabels()] == ['Warm-up\n', 'Recovery\n']
    finally:
        plt.close(figure)


def test_capacity_chart_without_load_keeps_retry_duration_without_inventing_an_origin():
    """A recovery throttle can be shown even when there was no first load response."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    recovery = chart_probe(429, 'global-standard', 0.1, retry_after = 5)
    evidence = helpers.TimedCapacityEvidence(
        baseline, (), recovery, False, False, 65, observation_times_seconds = (0, 65),
    )
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        routing = figure.axes[1]
        assert any(collection.get_hatch() == '///' for collection in routing.collections)
        assert [text.get_text() for text in routing.texts] == ['5s duration (continues)']
        assert routing.get_xlabel() == 'Request\nTime (no load)'
    finally:
        plt.close(figure)


def test_capacity_chart_keeps_long_window_labels_and_gap_summary_readable():
    """Long annotations remain inside their panels and the gap summary fits the footer."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    pressure = (
        *(baseline for _ in range(17)),
        chart_probe(429, 'global-standard', 0.1, retry_after = 30),
        chart_probe(429, 'consumption', 0.1, retry_after = 30),
        chart_probe(429, 'ptu', 0.1, retry_after = 30),
    )
    evidence = helpers.TimedCapacityEvidence(
        baseline, pressure, baseline, False, False, 20, observation_times_seconds = (*range(21), 41),
    )
    figure = helpers.capacity_figure(
        'responses/standard/gpt-5-mini', evidence, CAPACITY_LABELS,
        preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        routing = figure.axes[1]
        labels = [text.get_window_extent(renderer) for text in routing.texts]
        assert len(labels) == 3
        assert all(routing.bbox.contains(box.x0, box.y0) and routing.bbox.contains(box.x1, box.y1) for box in labels)
        assert all(not first.overlaps(second) for index, first in enumerate(labels) for second in labels[index + 1:])
        title, timing, summary, caption = figure.texts
        footer = [text.get_window_extent(renderer) for text in (caption, summary, timing)]
        assert all(figure.bbox.contains(box.x0, box.y0) and figure.bbox.contains(box.x1, box.y1) for box in footer)
        assert all(lower.y1 < upper.y0 for lower, upper in zip(footer, footer[1:]))
        assert footer[1].y0 - footer[0].y1 < 0.02 * figure.bbox.height
        assert footer[-1].y1 < routing.get_tightbbox(renderer).y0
    finally:
        plt.close(figure)


def test_capacity_chart_keeps_labels_inside_dense_axis_edges():
    """Earlier high-volume evidence still displays first and last window labels in full."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    pressure = (
        chart_probe(429, 'global-standard', 0.1, retry_after = 1),
        *(baseline for _ in range(78)),
        chart_probe(429, 'ptu', 0.1, retry_after = 100),
    )
    evidence = helpers.TimedCapacityEvidence(
        baseline, pressure, baseline, False, False, 40, observation_times_seconds = (*range(81), 120),
    )
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        figure.canvas.draw()
        routing = figure.axes[1]
        assert [text.get_ha() for text in routing.texts] == ['left', 'right']
        for text in routing.texts:
            bounds = text.get_window_extent(figure.canvas.get_renderer())
            assert routing.bbox.contains(bounds.x0, bounds.y0) and routing.bbox.contains(bounds.x1, bounds.y1)
    finally:
        plt.close(figure)


@pytest.mark.parametrize('positions', [(1, 2), (14, 15, 16), (18, 19, 20), (1, 2, 3, 4, 5), (16, 17, 18, 19, 20), tuple(range(1, 21))])
def test_capacity_chart_separates_adjacent_disjoint_window_labels(positions):
    """Consecutive, short windows on one backend must not stack their labels."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    pressure = tuple(
        chart_probe(429, 'global-standard', 0.1, retry_after = 1) if index in positions else baseline
        for index in range(1, 21)
    )
    evidence = helpers.TimedCapacityEvidence(
        baseline, pressure, baseline, False, False, 20, observation_times_seconds = (0, *range(2, 42, 2), 70),
    )
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        figure.canvas.draw()
        routing = figure.axes[1]
        labels = [text.get_window_extent(figure.canvas.get_renderer()) for text in routing.texts]
        assert len(labels) == len(positions)
        assert [text.xy[0] for text in routing.texts] == list(positions)
        assert all(routing.bbox.contains(box.x0, box.y0) and routing.bbox.contains(box.x1, box.y1) for box in labels)
        assert all(not first.overlaps(second) for index, first in enumerate(labels) for second in labels[index + 1:])
    finally:
        plt.close(figure)


def test_capacity_chart_separates_dense_labels_across_backend_rows():
    """Keep distinct windows readable when adjacent rows each need several label lanes."""
    tiers = ('global-standard', 'consumption', 'ptu')
    per_row = 26
    baseline = chart_probe(200, tiers[0], 0.1)
    pressure = tuple(chart_probe(429, tiers[index % len(tiers)], 0.1, retry_after = 1) for index in range(per_row * len(tiers)))
    evidence = helpers.TimedCapacityEvidence(
        baseline, pressure, baseline, False, False, 20, observation_times_seconds = (0, *range(2, 6 * per_row + 1, 2), 300),
    )
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = tiers[:2], fallback_label = tiers[2],
    )
    try:
        figure.canvas.draw()
        routing = figure.axes[1]
        labels = [text.get_window_extent(figure.canvas.get_renderer()) for text in routing.texts]
        assert len(labels) == len(pressure)
        assert all(routing.bbox.contains(box.x0, box.y0) and routing.bbox.contains(box.x1, box.y1) for box in labels)
        assert all(not first.overlaps(second) for index, first in enumerate(labels) for second in labels[index + 1:])
    finally:
        plt.close(figure)


def test_capacity_chart_warns_when_retry_window_labels_cannot_fit():
    """Keep every recorded interval and explicitly report an overcrowded row."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    pressure = tuple(chart_probe(429, 'global-standard', 0.1, retry_after = 1) for _ in range(40))
    evidence = helpers.TimedCapacityEvidence(
        baseline, pressure, baseline, False, False, 20, observation_times_seconds = (0, *range(2, 82, 2), 100),
    )
    with pytest.warns(UserWarning, match = 'Retry-After window labels.*overlap'):
        figure = helpers.capacity_figure(
            'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
        )
    try:
        assert len(figure.axes[1].texts) == 40
    finally:
        plt.close(figure)


def test_capacity_chart_legacy_retry_after_does_not_invent_elapsed_time():
    """Latency and response order cannot establish when a retry window expires."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    evidence = helpers.CapacityEvidence(baseline, (chart_probe(429, 'consumption', 0.1, retry_after = 5),), baseline, False, False, 65)
    figure = helpers.capacity_figure(
        'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        routing = figure.axes[1]
        assert not any(collection.get_hatch() == '///' for collection in routing.collections)
        assert routing.get_xlabel() == 'Request\nTime (not recorded)'
        request_axis = figure.axes[0].child_axes[0]
        assert 'equally spaced, not to scale' in request_axis.get_xlabel()
        assert [tick.get_text() for tick in request_axis.get_xticklabels()] == ['Warm-up', '1', 'Recovery']
        assert [tick.get_text() for tick in routing.get_xticklabels()] == ['Warm-up\n', '1\n', 'Recovery\n']
        assert not routing.texts
        assert all(not any(line.get_label() == '_recovery_gap_break' for line in axis.lines) for axis in figure.axes)
    finally:
        plt.close(figure)


@pytest.mark.parametrize('times', [(0,), (0, -1), (0, float('nan')), (0, True), (2, 1)])
def test_capacity_chart_rejects_invalid_observation_times(times):
    """Malformed or reordered timestamps must not produce misleading bands."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    evidence = helpers.TimedCapacityEvidence(baseline, (), baseline, False, False, 65, observation_times_seconds = times)
    with pytest.raises(ValueError, match = 'invalid observation times'):
        helpers.capacity_figure(
            'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
        )


@pytest.mark.parametrize('path', ['/sample/chat/completions', '/sample/responses'])
def test_capacity_single_recovery_allows_short_retry_after_boundary_slack(path):
    """Model a quota reset two seconds after its reported deadline, without retrying recovery."""
    elapsed = [0.0]
    client = client_for([])
    steps = iter([
        (0, 'global-standard', 200, None),
        (4, 'global-standard', 429, '16'),
        (5, 'consumption', 200, None),
        (6, 'consumption', 429, '30'),
        (7, 'ptu', 200, None),
        (8, 'ptu', 429, '30'),
        (8.2, None, 503, None),
    ])

    def remote(*_args, **_kwargs):
        if client.multiPost.call_count <= 7:
            observed_at, tier, status, retry = next(steps)
            elapsed[0] = observed_at
            return capacity_response(tier, status, path = path, retry_after = retry)
        if elapsed[0] < 22:
            return capacity_response('global-standard', 429, path = path, retry_after = '1')
        return capacity_response('global-standard', path = path)

    client.multiPost.side_effect = remote
    result = capacity_test(
        client, path = path, max_requests = 6, clock = lambda: elapsed[0],
        wait_for_initial_cooldown = False,
        sleep = lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds),
    )
    assert result.fallback_served and result.exhausted
    assert result.recovery.status == 200 and result.recovery.completion
    assert result.recovery_wait_seconds == pytest.approx(16.8)
    assert result.observation_times_seconds[-1] == 25
    assert client.multiPost.call_count == 8
    client.__exit__.assert_called_once()


def test_capacity_records_observation_times_including_recovery_wait():
    """Keep actual clock offsets rather than summing concurrent response latencies."""
    elapsed = [0.0]
    client = client_for([])
    rows = iter([capacity_response('global-standard'), capacity_response('global-standard', 429, retry_after = '5'), capacity_response('consumption')])

    def remote(*_args, **_kwargs):
        elapsed[0] += 2
        return next(rows)

    client.multiPost.side_effect = remote
    result = capacity_test(
        client, max_requests = 1, clock = lambda: elapsed[0],
        sleep = lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds),
    )
    assert isinstance(result, helpers.TimedCapacityEvidence)
    assert result.observation_times_seconds == (0, 2, 14)
    assert result.pressure[0].retry_after_seconds == 5


@pytest.mark.parametrize('first_delay,later_delay,later_elapsed,expected_wait', [
    ('30', '5', 3, 10),
    ('5', None, 13, 0),
    (None, None, 3, 62),
    ('0', '0', 3, 62),
])
def test_capacity_recovers_once_after_earliest_preferred_window(first_delay, later_delay, later_elapsed, expected_wait):
    """Wait for the earliest observed preferred deadline, with a default for missing headers."""
    elapsed = [0.0]
    client = client_for([])
    rows = iter([
        (0, capacity_response('global-standard')),
        (1, capacity_response('global-standard', 429, retry_after = first_delay)),
        (later_elapsed, capacity_response('consumption', 429, retry_after = later_delay)),
        (0, capacity_response('global-standard')),
    ])

    def remote(*_args, **_kwargs):
        delay, row = next(rows)
        elapsed[0] += delay
        return row

    client.multiPost.side_effect = remote
    result = capacity_test(
        client, max_requests = 2, clock = lambda: elapsed[0],
        sleep = lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds),
    )
    assert result.recovery_wait_seconds == expected_wait
    assert client.multiPost.call_count == 4
    assert result.recovery.completion


@pytest.mark.parametrize('steps,expected_wait', [
    ([(1, 'global-standard', '5'), (8, 'global-standard', '30'),
      (1, 'consumption', '35'), (2, 'ptu', '1')], 32),
    ([(1, 'global-standard', '30'), (2, 'global-standard', '5'),
      (1, 'consumption', '50')], 32),
    ([(1, 'global-standard', None), (2, 'global-standard', '0'),
      (1, 'consumption', '90')], 64),
    ([(1, 'ptu', '5')], 65),
    ([(0, 'global-standard', '400'), (0, 'consumption', '175')], 180),
])
def test_capacity_uses_latest_deadline_per_preferred_backend(steps, expected_wait):
    """Later 429s extend a tier without shortening earlier windows or selecting fallback."""
    elapsed = [0.0]
    client = client_for([])
    rows = iter([
        (0, capacity_response('global-standard')),
        *((delay, capacity_response(tier, 429, retry_after = retry)) for delay, tier, retry in steps),
        (0, capacity_response('global-standard')),
    ])

    def remote(*_args, **_kwargs):
        delay, row = next(rows)
        elapsed[0] += delay
        return row

    client.multiPost.side_effect = remote
    result = capacity_test(
        client, max_requests = len(steps), clock = lambda: elapsed[0],
        sleep = lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds),
    )
    assert result.recovery_wait_seconds == expected_wait
    assert client.multiPost.call_count == len(steps) + 2
    assert result.recovery.completion


def test_capacity_next_case_waits_for_other_backends_after_early_recovery():
    """The early recovery request does not imply all shared backends have cooled down."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    evidence = helpers.TimedCapacityEvidence(
        baseline,
        (chart_probe(429, 'global-standard', 0.1, retry_after = 30), chart_probe(429, 'consumption', 0.1, retry_after = 90)),
        baseline, True, True, 28, observation_times_seconds = (0, 1, 4, 32),
    )
    sleep = MagicMock()
    assert helpers.wait_for_capacity_isolation(evidence, sleep = sleep) == 67
    sleep.assert_called_once_with(67)


@pytest.mark.parametrize('status,tier', [(429, 'global-standard'), (503, None)])
def test_capacity_does_not_retry_a_failed_early_recovery(status, tier):
    """A still-throttled recovery is returned as evidence without another request."""
    client = client_for([])
    client.multiPost.side_effect = [
        capacity_response('global-standard'),
        capacity_response('global-standard', 429, retry_after = '30'),
        capacity_response(tier, status, retry_after = '30'),
    ]
    result = capacity_test(client, max_requests = 1)
    assert result.recovery.status == status
    assert client.multiPost.call_count == 3


@pytest.mark.parametrize('error_tier', [None, 'global-standard'])
def test_capacity_chart_shows_latency_routing_and_unattributed_exhaustion(error_tier):
    """The graph must preserve actual tiers, HTTP statuses, phase and measured latency."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    pressure = (
        chart_probe(429, 'global-standard', 0.2),
        chart_probe(429, 'consumption', 0.3),
        chart_probe(200, 'ptu', 0.4),
        chart_probe(429, 'ptu', 0.5),
        chart_probe(503, error_tier, 0.6),
    )
    recovery = chart_probe(200, 'consumption', 0.7)
    evidence = helpers.CapacityEvidence(baseline, pressure, recovery, True, True, 65, 'exhausted', 15)
    figure = helpers.capacity_figure(
        'chat/completions/standard/gpt-5-mini', evidence, CAPACITY_LABELS,
        preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        latency, routing = figure.axes
        assert [bar.get_height() for container in latency.containers for bar in container] == pytest.approx([100, 200, 300, 400, 500, 600, 700])
        assert [tick.get_text() for tick in routing.get_yticklabels()] == [
            'global-standard (preferred, priority 1, weight 3)',
            'consumption (preferred, priority 1, weight 1)',
            'ptu (fallback, priority 2, weight 1)',
            'No backend identified',
        ]
        figure.canvas.draw()
        assert all(tick.get_window_extent().x0 >= 0 for tick in routing.get_yticklabels())
        markers = {collection.get_label(): collection.get_offsets().tolist() for collection in routing.collections}
        assert markers['HTTP 200 - completed'] == [[0.0, 0.0], [3.0, 2.0], [6.0, 1.0]]
        assert markers['HTTP 429 - throttled'] == [[1.0, 0.0], [2.0, 1.0], [4.0, 2.0]]
        assert markers['HTTP 503 - unavailable'] == [[5.0, 3.0]]
        summary = ' '.join(text.get_text() for text in figure.texts)
        assert 'Fallback: demonstrated' in summary
        assert 'Exhaustion: demonstrated' in summary
        assert 'Preferred recovery: demonstrated' in summary
        assert '65' in summary
        assert 'Stop:' not in summary
        assert 'Priorities and weights are template values' not in summary
        assert 'Tier labels are simulated' not in summary
    finally:
        plt.close(figure)


def test_capacity_chart_handles_previous_runs_and_missing_transitions():
    """Older probe objects still show routing evidence without invented response times."""
    baseline = SimpleNamespace(status = 200, backend_host = 'global-standard.example.invalid', completion = True, pool = CAPACITY_POOL)
    throttle = SimpleNamespace(status = 429, backend_host = 'consumption.example.invalid')
    recovery = SimpleNamespace(status = 503, backend_host = '', completion = False, pool = '')
    evidence = SimpleNamespace(
        baseline = baseline, pressure = (throttle,), recovery = recovery, fallback_served = False,
        exhausted = False, recovery_wait_seconds = 65, stop_reason = 'request-limit', elapsed_seconds = 2,
    )
    figure = helpers.capacity_figure(
        'responses/standard/gpt-5-mini', evidence, CAPACITY_LABELS,
        preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        latency, routing = figure.axes
        assert not latency.containers
        assert not len(latency.get_yticks())
        assert latency.get_position().height < routing.get_position().height
        assert 'not recorded' in ' '.join(text.get_text() for text in latency.texts).lower()
        assert {collection.get_label() for collection in routing.collections} == {
            'HTTP 200 - completed', 'HTTP 429 - throttled', 'HTTP 503 - unavailable',
        }
        summary = ' '.join(text.get_text() for text in figure.texts)
        assert 'Fallback: not demonstrated' in summary
        assert 'Exhaustion: not demonstrated' in summary
        assert 'Preferred recovery: not demonstrated' in summary
    finally:
        plt.close(figure)


def test_capacity_chart_never_invents_missing_response_times():
    """A partially timed run shows measured bars only and calls out missing values."""
    baseline = chart_probe(200, 'global-standard', 0.2)
    evidence = helpers.CapacityEvidence(baseline, (chart_probe(429, 'consumption'),), baseline, False, False, 65)
    figure = helpers.capacity_figure(
        'responses/standard/gpt-5-mini', evidence, CAPACITY_LABELS,
        preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    try:
        latency = figure.axes[0]
        assert [bar.get_height() for container in latency.containers for bar in container] == pytest.approx([200, 200])
        assert '1' in ' '.join(text.get_text() for text in latency.texts)
        assert 'not recorded' in ' '.join(text.get_text() for text in latency.texts).lower()
    finally:
        plt.close(figure)


def test_capacity_chart_uses_priority_family_and_does_not_overclaim_recovery():
    """Pool-family labels and recovery evidence must match the actual selected account."""
    pool = CAPACITY_POOL.replace('-standard-pool', '-priority-pool')
    baseline = chart_probe(200, 'ptu', 0.1, pool)
    recovery = chart_probe(200, 'global-standard', 0.2, pool)
    evidence = helpers.CapacityEvidence(baseline, (), recovery, True, True, 65, 'exhausted', 1)
    figure = helpers.capacity_figure(
        'responses/priority/gpt-5-mini', evidence, CAPACITY_LABELS,
        preferred_labels = ('ptu', 'consumption'), fallback_label = 'global-standard',
    )
    try:
        assert [tick.get_text() for tick in figure.axes[1].get_yticklabels()] == [
            'ptu (preferred, priority 1, weight 3)',
            'consumption (preferred, priority 1, weight 1)',
            'global-standard (fallback, priority 2, weight 1)',
            'No backend identified',
        ]
        assert 'Preferred recovery: not demonstrated' in ' '.join(text.get_text() for text in figure.texts)
    finally:
        plt.close(figure)


@pytest.mark.parametrize(
    'family,preferred,fallback',
    [
        ('standard', ('global-standard', 'consumption'), 'ptu'),
        ('standard', ('consumption', 'global-standard'), 'ptu'),
        ('priority', ('ptu', 'consumption'), 'global-standard'),
        ('priority', ('consumption', 'ptu'), 'global-standard'),
    ],
)
def test_capacity_chart_member_labels_match_bicep_pool_configuration(family, preferred, fallback):
    """Keep displayed member settings aligned with the template actually used for pool deployment."""
    bicep = (SAMPLE / 'main.bicep').read_text(encoding = 'utf-8')
    accounts_match = re.search(r'var accounts = \[(.*?)\n\]', bicep, re.DOTALL)
    assert accounts_match is not None
    accounts = re.findall(r"label:\s*'([^']+)'", accounts_match.group(1))
    family_match = re.search(
        rf"\{{\s*name:\s*'{family}',\s*priorities:\s*\[([^\]]+)\],\s*weights:\s*\[([^\]]+)\]\s*\}}",
        bicep,
    )
    assert family_match is not None
    priorities, weights = ([int(value.strip()) for value in group.split(',')] for group in family_match.groups())
    members = {tier: (priority, weight) for tier, priority, weight in zip(accounts, priorities, weights, strict = True)}
    assert 'priority: family.priorities[i]' in bicep
    assert 'weight: family.weights[i]' in bicep

    pool = CAPACITY_POOL.replace('-standard-pool', f'-{family}-pool')
    baseline = chart_probe(200, preferred[0], 0.1, pool)
    evidence = helpers.CapacityEvidence(baseline, (), baseline, False, False, 0)
    figure = helpers.capacity_figure(
        f'chat/completions/{family}/gpt-5-mini', evidence, CAPACITY_LABELS,
        preferred_labels = preferred, fallback_label = fallback,
    )
    try:
        roles = [(tier, 'preferred') for tier in preferred] + [(fallback, 'fallback')]
        expected = [
            f'{tier} ({role}, priority {members[tier][0]}, weight {members[tier][1]})'
            for tier, role in roles
        ]
        assert [tick.get_text() for tick in figure.axes[1].get_yticklabels()] == [*expected, 'No backend identified']
    finally:
        plt.close(figure)


@pytest.mark.parametrize(
    'pool,preferred,fallback',
    [
        ('unrecognized-pool', ('global-standard', 'consumption'), 'ptu'),
        (CAPACITY_POOL, ('ptu', 'consumption'), 'global-standard'),
    ],
)
def test_capacity_chart_rejects_unknown_or_mismatched_pool_configuration(pool, preferred, fallback):
    """Do not label unknown or mismatched pools with invented priority and weight values."""
    baseline = chart_probe(200, preferred[0], 0.1, pool)
    evidence = helpers.CapacityEvidence(baseline, (), baseline, False, False, 0)
    with pytest.raises(ValueError, match = 'pool configuration'):
        helpers.capacity_figure('case', evidence, CAPACITY_LABELS, preferred_labels = preferred, fallback_label = fallback)


@pytest.mark.parametrize('operation', ['chat/completions', 'responses'])
@pytest.mark.parametrize('family', ['standard', 'priority'])
@pytest.mark.parametrize('duration', [0.1, None])
@pytest.mark.parametrize('timed', [False, True])
def test_capacity_chart_explains_each_experiment_with_accessible_labels(operation, family, duration, timed):
    """Each of the four charts explains intent, identifies roles and fits its footer."""
    preferred = ('global-standard', 'consumption') if family == 'standard' else ('ptu', 'consumption')
    fallback = 'ptu' if family == 'standard' else 'global-standard'
    pool = CAPACITY_POOL.replace('-standard-pool', f'-{family}-pool')
    baseline = chart_probe(200, preferred[0], duration, pool)
    evidence = (
        helpers.TimedCapacityEvidence(baseline, (), baseline, False, False, 65, observation_times_seconds = (0.0, 65.0))
        if timed else helpers.CapacityEvidence(baseline, (), baseline, False, False, 65)
    )
    label = f'{operation}/{family}/gpt-5-mini'
    figure = helpers.capacity_figure(label, evidence, CAPACITY_LABELS, preferred_labels = preferred, fallback_label = fallback)
    try:
        title, timing, summary, caption = figure.texts
        assert caption.get_text() == (
            f'Experiment: {label} via the recommended API: healthy warm-up -> bounded load testing -> cooldown -> recovery.\n'
            f'Routing: preferred members {preferred[0]} + {preferred[1]}; fallback member {fallback}.\n'
            'Goal: demonstrate successful fallback, full-pool exhaustion and recovery on a preferred member.'
        )
        assert 'Fallback: not demonstrated' in summary.get_text()
        assert 'load-test responses' in timing.get_text()
        assert timing.get_position()[1] > summary.get_position()[1]
        assert 'Stop:' not in timing.get_text()
        latency, routing = figure.axes
        request_axis = latency.child_axes[0]
        assert [tick.get_text() for tick in request_axis.get_xticklabels()] == ['Warm-up', 'Recovery']
        assert routing.get_xlabel() == ('Request\nTime (no load)' if timed else 'Request\nTime (not recorded)')
        assert [tick.get_text() for tick in routing.get_xticklabels()] == ['Warm-up\n', 'Recovery\n']
        for axis in (latency, routing):
            assert sum(patch.get_label() == '_warmup_phase' for patch in axis.patches) == 1
        ticks = figure.axes[1].get_yticklabels()
        assert ticks[0].get_color() == ticks[1].get_color()
        assert ticks[0].get_color() != ticks[2].get_color()
        assert title.get_color() == ('#005a9e' if family == 'standard' else '#6b3f8d')
        for text in (title, *ticks):
            channels = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in to_rgb(text.get_color())]
            luminance = sum(channel * weight for channel, weight in zip(channels, (0.2126, 0.7152, 0.0722), strict = True))
            assert 1.05 / (luminance + 0.05) >= 4.5

        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        top_bounds = request_axis.get_tightbbox(renderer)
        assert figure.bbox.contains(top_bounds.x0, top_bounds.y0) and figure.bbox.contains(top_bounds.x1, top_bounds.y1)
        assert top_bounds.y1 < title.get_window_extent(renderer).y0
        for tick in ticks:
            bounds = tick.get_window_extent(renderer)
            assert figure.bbox.contains(bounds.x0, bounds.y0) and figure.bbox.contains(bounds.x1, bounds.y1)
        footer = [text.get_window_extent(renderer) for text in (caption, summary, timing)]
        assert all(figure.bbox.contains(box.x0, box.y0) and figure.bbox.contains(box.x1, box.y1) for box in footer)
        assert all(lower.y1 < upper.y0 for lower, upper in zip(footer, footer[1:]))
        assert footer[1].y0 - footer[0].y1 < 0.02 * figure.bbox.height
        assert footer[-1].y1 < figure.axes[1].get_tightbbox(renderer).y0
    finally:
        plt.close(figure)


@pytest.mark.parametrize('bad_duration', [-1, float('nan'), 'unknown'])
def test_capacity_chart_rejects_invalid_timing(bad_duration):
    """Invalid retained values cannot silently become chart bars."""
    baseline = chart_probe(200, 'global-standard', bad_duration)
    evidence = helpers.CapacityEvidence(baseline, (), baseline, False, False, 65)
    with pytest.raises(ValueError, match = 'invalid response time'):
        helpers.capacity_figure(
            'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
        )


def test_capacity_chart_closes_figure_when_plotting_fails(monkeypatch):
    """A failed render must not leak its Matplotlib figure."""
    baseline = chart_probe(200, 'global-standard', 0.1)
    evidence = helpers.CapacityEvidence(baseline, (), baseline, False, False, 65)
    subplots = plt.subplots
    created = []

    def failing_subplots(*args, **kwargs):
        figure, axes = subplots(*args, **kwargs)
        created.append(figure)
        monkeypatch.setattr(axes[0], 'bar', MagicMock(side_effect = RuntimeError('plot failed')))

        return figure, axes

    monkeypatch.setattr(helpers.plt, 'subplots', failing_subplots)
    with pytest.raises(RuntimeError, match = 'plot failed'):
        helpers.capacity_figure(
            'case', evidence, CAPACITY_LABELS, preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
        )
    assert len(created) == 1 and created[0].number not in plt.get_fignums()


@pytest.mark.parametrize('header,value', [
    ('Retry-After', 'tomorrow'), ('Retry-After', ''), ('Retry-After', 3),
    ('Retry-After', 'Mon, 23 Nov 2026 12:00:00'),
    ('x-routing-backend-host', 'https://ptu.example.invalid/private'),
    ('x-routing-backend-host', None),
])
def test_probe_malformed_capacity_headers_fail_and_close(header, value):
    """Arbitrary header strings cannot become trusted backend or timing evidence."""
    rows = capacity_response('ptu')
    rows[0]['headers'][header] = value
    client = client_for(rows)
    with pytest.raises(ValueError):
        helpers.probe(lambda: client, '/sample/chat/completions', {})
    client.__exit__.assert_called_once()


def initialized_notebook(monkeypatch):
    """Run the actual initialization and mock infrastructure orchestration."""
    notebook = json.loads((SAMPLE / 'create.ipynb').read_text(encoding = 'utf-8'))
    code = {
        cell['id']: ''.join(cell['source']) if isinstance(cell['source'], list) else cell['source']
        for cell in notebook['cells'] if cell['cell_type'] == 'code'
    }
    monkeypatch.setattr('utils.NotebookHelper', MagicMock())
    namespace = {}
    exec(compile(code['routing-initialize'], '<routing-initialization>', 'exec'), namespace)
    namespace['context'] = MagicMock(apim_gateway_url = 'https://gateway.invalid')
    namespace['keys'] = {'body': 'body-key', 'header': 'header-key', 'subscription': 'standard-key', 'recommended': 'recommended-standard-key'}
    namespace['priority_key'] = 'priority-key'
    namespace['recommended_priority_key'] = 'recommended-priority-key'

    return namespace, code


@pytest.mark.parametrize('enabled', [True, False])
def test_notebook_capacity_covers_both_operations_and_families_or_explicitly_skips(monkeypatch, enabled):
    """Run the notebook's declarations and gates without Azure traffic or real waits."""
    namespace, code = initialized_notebook(monkeypatch)
    namespace['run_capacity_tests'] = enabled
    accounts = [{'label': label, 'endpoint': f'https://{host}/'} for host, label in CAPACITY_LABELS.items()]
    namespace['output'] = MagicMock()
    namespace['output'].getJson.return_value = accounts
    calls = []

    def exercise(factory, path, baseline_payload, pressure_payload, **options):
        client = factory()
        calls.append((path, baseline_payload, pressure_payload, client.key, options))
        preferred = options['preferred_labels'][0]
        result = helpers.ProbeResult(200, None, None, True, options['pool'], REQUEST_ID, f'{preferred}.example.invalid')

        return helpers.CapacityEvidence(result, (result,), result, True, True, 65)

    namespace['nb_helper'].create_apim_requests.side_effect = lambda _url, key: MagicMock(key = key)
    monkeypatch.setattr(helpers, 'exercise_capacity', exercise)
    isolation = MagicMock(return_value = 0)
    monkeypatch.setattr(helpers, 'wait_for_capacity_isolation', isolation)
    exec(compile(code['routing-capacity'], '<routing-capacity>', 'exec'), namespace)
    assert len(calls) == (4 if enabled else 0)
    assert len(namespace['capacity_results']) == len(calls)
    assert isolation.call_count == (3 if enabled else 0)
    assert [options['wait_for_initial_cooldown'] for *_, options in calls] == ([True, False, False, False] if enabled else [])
    for path, baseline, pressure, key, options in calls:
        pathway = path.split('/openai/v1/')[1]
        assert baseline == {'model': namespace['model_configuration'][0]['deploymentName'], **namespace['request_payloads'][pathway]}
        assert pressure['model'] == baseline['model'] and pressure['stream'] is False
        if pathway == 'responses':
            assert pressure['store'] is False and 'messages' not in pressure
            assert len(pressure['input']) > len(baseline['input'])
        else:
            assert 'input' not in pressure
            assert len(pressure['messages'][0]['content']) > len(baseline['messages'][0]['content'])
        text = pressure['input'] if pathway == 'responses' else pressure['messages'][0]['content']
        assert text.count('Capacity routing context. ') == namespace['load_context_repetitions']
        family = 'priority' if key == 'recommended-priority-key' else 'standard'
        assert options['pool'].endswith(f'-{family}-pool')
        assert set(options['preferred_labels']) == ({'ptu', 'consumption'} if family == 'priority' else {'global-standard', 'consumption'})
        assert options['max_requests'] == namespace['pressure_max_requests']
        assert options['max_seconds'] == namespace['pressure_max_seconds']
        assert options['concurrency'] == 1
        assert options['backend_labels'] == CAPACITY_LABELS


@pytest.mark.parametrize('fallback,exhausted,recovered', [(False, False, True), (True, False, True), (True, True, False)])
def test_notebook_capacity_missing_evidence_fails_instead_of_reporting_success(monkeypatch, fallback, exhausted, recovered):
    """The visible notebook assertions reject missing pressure or recovery evidence."""
    namespace, code = initialized_notebook(monkeypatch)
    namespace['output'] = MagicMock()
    namespace['output'].getJson.return_value = [{'label': label, 'endpoint': f'https://{host}/'} for host, label in CAPACITY_LABELS.items()]
    baseline = helpers.ProbeResult(200, None, None, True, CAPACITY_POOL, REQUEST_ID, 'global-standard.example.invalid')
    recovery = baseline if recovered else helpers.ProbeResult(429, 'UpstreamError', 'The upstream service rejected the request.', False, CAPACITY_POOL, REQUEST_ID)
    remote = MagicMock(return_value = helpers.CapacityEvidence(baseline, (), recovery, fallback, exhausted, 65))
    monkeypatch.setattr(helpers, 'exercise_capacity', remote)
    figure = plt.figure()
    plot = MagicMock(return_value = figure)
    show = MagicMock()
    monkeypatch.setattr(helpers, 'capacity_figure', plot, raising = False)
    monkeypatch.setattr('IPython.display.display', show)
    with pytest.raises(AssertionError, match = 'not demonstrated|recovery failed'):
        exec(compile(code['routing-capacity'], '<routing-capacity>', 'exec'), namespace)
    remote.assert_called_once()
    assert not namespace['capacity_results']
    assert len(namespace['capacity_observations']) == 1
    plot.assert_called_once()
    show.assert_called_once_with(figure)
    assert figure.number not in plt.get_fignums()


def test_notebook_charts_reuse_existing_capacity_evidence_without_requests(monkeypatch):
    """An earlier successful run can be graphed without redeploying or sending traffic."""
    namespace, code = initialized_notebook(monkeypatch)
    result = helpers.ProbeResult(200, None, None, True, CAPACITY_POOL, REQUEST_ID, 'global-standard.example.invalid')
    evidence = helpers.CapacityEvidence(result, (result,), result, True, True, 65)
    namespace['capacity_results'] = [('chat/completions/standard/gpt-5-mini', evidence)]
    namespace['backend_labels'] = CAPACITY_LABELS
    namespace['capacity_families'] = [('standard', 'secret', ('global-standard', 'consumption'), 'ptu')]
    figure = plt.figure()
    plot = MagicMock(return_value = figure)
    show = MagicMock()
    monkeypatch.setattr(helpers, 'capacity_figure', plot, raising = False)
    monkeypatch.setattr('IPython.display.display', show)
    exec(compile(code['routing-charts'], '<routing-charts>', 'exec'), namespace)
    plot.assert_called_once_with(
        'chat/completions/standard/gpt-5-mini', evidence, CAPACITY_LABELS,
        preferred_labels = ('global-standard', 'consumption'), fallback_label = 'ptu',
    )
    show.assert_called_once_with(figure)
    namespace['nb_helper'].create_apim_requests.assert_not_called()
    assert figure.number not in plt.get_fignums()


def test_notebook_charts_report_explicit_skip(monkeypatch):
    """A smoke-only run does not imply capacity evidence or try to render a graph."""
    namespace, code = initialized_notebook(monkeypatch)
    namespace['run_capacity_tests'] = False
    warning = MagicMock()
    plot = MagicMock()
    monkeypatch.setattr('console.print_warning', warning)
    monkeypatch.setattr(helpers, 'capacity_figure', plot, raising = False)
    exec(compile(code['routing-charts'], '<routing-charts>', 'exec'), namespace)
    warning.assert_called_once()
    assert 'skipped' in warning.call_args.args[0]
    plot.assert_not_called()


def test_notebook_chart_closes_figure_when_display_fails(monkeypatch):
    """Displaying a graph must not leave a figure open on failure."""
    namespace, code = initialized_notebook(monkeypatch)
    result = helpers.ProbeResult(200, None, None, True, CAPACITY_POOL, REQUEST_ID, 'global-standard.example.invalid')
    namespace['capacity_results'] = [('responses/standard/gpt-5-mini', helpers.CapacityEvidence(result, (), result, True, True, 65))]
    namespace['backend_labels'] = CAPACITY_LABELS
    namespace['capacity_families'] = [('standard', 'secret', ('global-standard', 'consumption'), 'ptu')]
    figure = plt.figure()
    monkeypatch.setattr(helpers, 'capacity_figure', MagicMock(return_value = figure))
    monkeypatch.setattr('IPython.display.display', MagicMock(side_effect = RuntimeError('display failed')))
    with pytest.raises(RuntimeError, match = 'display failed'):
        exec(compile(code['routing-charts'], '<routing-charts>', 'exec'), namespace)
    assert figure.number not in plt.get_fignums()


def test_notebook_report_does_not_claim_coverage_from_smoke_results_only(monkeypatch):
    """Skipping the capacity cell cannot make a full-run report look complete."""
    namespace, code = initialized_notebook(monkeypatch)
    namespace['results'] = [helpers.ProbeResult(200, None, None, True, CAPACITY_POOL, REQUEST_ID)]
    with pytest.raises(AssertionError, match = 'all four capacity cases'):
        exec(compile(code['routing-report'], '<routing-report>', 'exec'), namespace)


@pytest.mark.parametrize('infrastructure_exists,creation_succeeds', [(True, True), (False, True), (False, False)])
def test_notebook_deployment_creates_missing_infrastructure(monkeypatch, infrastructure_exists, creation_succeeds):
    """Run Cell 5 through the real helper without requiring pre-existing infrastructure."""
    helper_type = utils.NotebookHelper
    namespace, code = initialized_notebook(monkeypatch)
    helper = helper_type(
        namespace['sample_folder'], namespace['rg_name'], namespace['rg_location'],
        namespace['deployment'], namespace['supported_infras'],
        index = namespace['index'], apim_sku = namespace['apim_sku'],
    )
    namespace['nb_helper'] = helper
    infrastructure_factory = MagicMock()
    infrastructure_factory.return_value.create_infrastructure.return_value = creation_succeeds
    monkeypatch.setattr(utils, 'InfrastructureNotebookHelper', infrastructure_factory)
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda _rg: infrastructure_exists)
    monkeypatch.setattr(az, 'find_infrastructure_instances', lambda _infra: [])
    monkeypatch.setattr(az, 'migrate_legacy_apim_diagnostic_settings', MagicMock())
    output = MagicMock(success = True)
    values = {
        'apimServiceName': 'apim-test',
        'apimResourceGatewayURL': 'https://gateway.invalid',
        'prioritySubscriptionPrimaryKey': 'priority-key',
        'standardSubscriptionName': f'api-{namespace["apis"][2].name}',
        'prioritySubscriptionName': f'{namespace["sample_name"]}-priority',
        'recommendedPrioritySubscriptionPrimaryKey': 'recommended-priority-key',
        'recommendedStandardSubscriptionName': f'api-{namespace["apis"][3].name}',
        'recommendedPrioritySubscriptionName': f'{namespace["sample_name"]}-recommended-priority',
    }
    output.get.side_effect = lambda name, **_kwargs: values[name]
    output.getJson.return_value = [
        {'name': api.name, 'subscriptionPrimaryKey': f'{scenario}-key'}
        for scenario, api in zip(namespace['scenario_names'], namespace['apis'], strict = True)
    ]
    deploy = MagicMock(return_value = output)
    monkeypatch.setattr(utils, 'create_bicep_deployment_group_for_sample', deploy)

    if not infrastructure_exists and not creation_succeeds:
        with pytest.raises(SystemExit):
            exec(compile(code['routing-deploy'], '<routing-deploy>', 'exec'), namespace)
        infrastructure_factory.return_value.create_infrastructure.assert_called_once_with(True)
        deploy.assert_not_called()
        return

    exec(compile(code['routing-deploy'], '<routing-deploy>', 'exec'), namespace)
    if infrastructure_exists:
        infrastructure_factory.assert_not_called()
    else:
        infrastructure_factory.assert_called_once_with(
            namespace['rg_location'], namespace['deployment'], namespace['index'], namespace['apim_sku'],
        )
        infrastructure_factory.return_value.create_infrastructure.assert_called_once_with(True)
    deploy.assert_called_once_with(
        namespace['sample_folder'], namespace['rg_name'], namespace['rg_location'],
        namespace['bicep_parameters'], is_debug = False,
    )
    assert namespace['keys'] == {'body': 'body-key', 'header': 'header-key', 'subscription': 'subscription-key', 'recommended': 'recommended-key'}
    assert namespace['recommended_priority_key'] == 'recommended-priority-key'
    assert namespace['context'].apim_gateway_url == 'https://gateway.invalid'


def test_notebook_exercises_each_model_and_identical_subscription_requests(monkeypatch):
    """Execute the success cell to check scenario coverage and entitlement isolation."""
    namespace, code = initialized_notebook(monkeypatch)
    calls = []

    def fake_probe(factory, path, payload, *, headers):
        client = factory()
        key = client.key
        family = 'priority' if key in ('priority-key', 'recommended-priority-key') else 'standard'
        pool = f'{namespace["sample_name"]}-{payload["model"]}-{family}-pool'
        calls.append((path, payload.copy(), headers.copy(), key))

        return helpers.ProbeResult(200, None, None, True, pool, REQUEST_ID)

    namespace['nb_helper'].create_apim_requests.side_effect = lambda _url, key: MagicMock(key = key)
    monkeypatch.setattr(helpers, 'probe', fake_probe)
    exec(compile(code['routing-success'], '<routing-success>', 'exec'), namespace)
    assert len(calls) == len(namespace['model_configuration']) * 16
    for model in namespace['model_configuration']:
        selector = model['deploymentName']
        for pathway in ('chat/completions', 'responses'):
            model_calls = [call for call in calls if call[1]['model'] == selector and call[0].split('/openai/v1/')[1] == pathway]
            assert len(model_calls) == 8
            for call in model_calls:
                assert call[1] == {'model': selector, **namespace['request_payloads'][pathway]}
                if pathway == 'responses':
                    assert 'input' in call[1] and 'messages' not in call[1]
                    assert call[1]['store'] is False
                else:
                    assert 'messages' in call[1] and 'input' not in call[1]
            subscription_calls = [call for call in model_calls if call[0] == f'/{namespace["paths"]["subscription"]}/{pathway}']
            assert len(subscription_calls) == 2
            standard, priority = subscription_calls
            assert standard[:2] == priority[:2]  # Same path and body, not two different APIs.
            assert standard[3] != priority[3]
            assert standard[2] == {'x-priority': 'priority'}  # Spoofed header does not grant priority.
            header_call = next(call for call in model_calls if call[0] == f'/{namespace["paths"]["header"]}/{pathway}')
            assert header_call[2] == {'x-ai-model': selector}
            recommended_calls = [call for call in model_calls if call[0] == f'/{namespace["paths"]["recommended"]}/{pathway}']
            assert len(recommended_calls) == 4
            assert recommended_calls[0][:3] == recommended_calls[1][:3]
            assert recommended_calls[0][3] == 'recommended-standard-key'
            assert recommended_calls[1][3] == 'recommended-priority-key'
            assert recommended_calls[0][2] == {'x-ai-model': selector, 'x-priority': 'priority'}
            assert recommended_calls[2][2] == {'x-ai-model': ''}
            assert not recommended_calls[3][2]


@pytest.mark.parametrize('status,code,message', [
    (500, 'GatewayError', 'The gateway could not complete the request.'),
    (504, 'UpstreamTimeout', 'The upstream request timed out.'),
])
def test_notebook_success_failure_reports_sanitized_evidence_without_retry(monkeypatch, status, code, message):
    """A failed success probe exposes its correlation ID and error identity, not a bare assertion."""
    namespace, cells = initialized_notebook(monkeypatch)
    selector = namespace['model_configuration'][0]['deploymentName']
    pool = f'{namespace["sample_name"]}-{selector}-standard-pool'
    remote = MagicMock(side_effect = [
        helpers.ProbeResult(200, None, None, True, pool, REQUEST_ID),
        helpers.ProbeResult(status, code, message, False, '', REQUEST_ID),
    ])
    monkeypatch.setattr(helpers, 'probe', remote)
    with pytest.raises(AssertionError) as failure:
        exec(compile(cells['routing-success'], '<routing-success>', 'exec'), namespace)
    detail = str(failure.value)
    assert f'header/standard/{selector}' in detail
    assert f'status={status}' in detail and code in detail and REQUEST_ID in detail
    assert 'Reply with a short greeting.' not in detail
    assert remote.call_count == 2


@pytest.mark.parametrize('upstream_code', ['ModelNotAvailable', 'model_not_available', 'UpstreamError', 'InvalidRequest'])
def test_notebook_rejects_status_only_or_wrong_source_mismatch_evidence(monkeypatch, upstream_code):
    """A 404 from local routing is not accepted as a real backend mismatch result."""
    namespace, code = initialized_notebook(monkeypatch)
    pool = f'{namespace["sample_name"]}-{namespace["model_configuration"][0]["deploymentName"]}-standard-pool'
    monkeypatch.setattr(
        helpers, 'probe',
        lambda *_args, **_kwargs: helpers.ProbeResult(404, upstream_code, 'The upstream service rejected the request.', False, pool, REQUEST_ID),
    )
    with pytest.raises(AssertionError, match = 'real Azure deployment-not-found'):
        exec(compile(code['routing-upstream'], '<routing-upstream>', 'exec'), namespace)


def test_notebook_proves_header_bypass_on_header_and_recommended_routes(monkeypatch):
    """Both header-first routes send mismatched and non-object bodies unchanged upstream."""
    namespace, code = initialized_notebook(monkeypatch)
    calls = []

    def fake_probe(_factory, path, payload, *, headers):
        calls.append((path, payload, headers))
        pool = f'{namespace["sample_name"]}-{headers["x-ai-model"]}-standard-pool'
        if isinstance(payload, dict):
            assert payload['model'] == 'not-deployed-on-any-account'
            return helpers.ProbeResult(404, 'DeploymentNotFound', 'The upstream service rejected the request.', False, pool, REQUEST_ID)

        assert payload == 'not-an-object'
        return helpers.ProbeResult(400, 'InvalidRequestError', 'The upstream service rejected the request.', False, pool, REQUEST_ID)

    monkeypatch.setattr(helpers, 'probe', fake_probe)
    exec(compile(code['routing-upstream'], '<routing-upstream>', 'exec'), namespace)
    for pathway in ('chat/completions', 'responses'):
        for scenario in ('header', 'recommended'):
            selected = [call for call in calls if call[0] == f'/{namespace["paths"][scenario]}/{pathway}']
            selector = namespace['model_configuration'][0]['deploymentName']
            assert [(payload, headers) for _, payload, headers in selected] == [
                ({**namespace['request_payloads'][pathway], 'model': 'not-deployed-on-any-account'}, {'x-ai-model': selector}),
                ('not-an-object', {'x-ai-model': selector}),
            ]


@pytest.mark.parametrize('deferred_failure', [False, True])
def test_notebook_missing_route_acceptance_gate_is_not_status_only(monkeypatch, deferred_failure):
    """Run rejection assertions: a deferred gateway failure cannot masquerade as graceful resolution."""
    namespace, code = initialized_notebook(monkeypatch)
    missing_route = helpers.ProbeResult(404, 'model_not_available', 'The specified model is not available for use', False, '', REQUEST_ID)
    missing_selector = helpers.ProbeResult(404, 'ModelNotAvailable', missing_route.error_message, False, '', REQUEST_ID)
    invalid = helpers.ProbeResult(400, 'InvalidRequest', 'The request payload is invalid.', False, '', REQUEST_ID)
    pool = f'{namespace["sample_name"]}-{namespace["model_configuration"][0]["deploymentName"]}-standard-pool'
    success = helpers.ProbeResult(200, None, None, True, pool, REQUEST_ID)
    rows = [
        missing_route, missing_selector, invalid, invalid, invalid, invalid,  # Body.
        missing_route, missing_route, missing_route,  # Other APIs' body-based resolution.
        success, missing_route, missing_selector,  # Header.
        missing_route, missing_selector,  # Recommended's empty header is checked in the success cell.
    ] * 2
    if deferred_failure:
        rows[0] = helpers.ProbeResult(500, 'GatewayError', 'The gateway could not complete the request.', False, '', REQUEST_ID)
    remaining = iter(rows)

    def checked_probe(*args, **kwargs):
        requests.Request('POST', 'https://gateway.invalid', headers = kwargs.get('headers')).prepare()
        return next(remaining)

    remote = MagicMock(side_effect = checked_probe)
    monkeypatch.setattr(helpers, 'probe', remote)
    if deferred_failure:
        with pytest.raises(AssertionError):
            exec(compile(code['routing-rejections'], '<routing-rejections>', 'exec'), namespace)
        assert remote.call_count == 1
    else:
        exec(compile(code['routing-rejections'], '<routing-rejections>', 'exec'), namespace)
        assert remote.call_count == 28
        assert namespace['results'][0].error_code == 'model_not_available'
        for pathway in ('chat/completions', 'responses'):
            by_scenario = {
                scenario: [call for call in remote.call_args_list if call.args[1] == f'/{namespace["paths"][scenario]}/{pathway}']
                for scenario in namespace['scenario_names']
            }
            assert [len(by_scenario[scenario]) for scenario in namespace['scenario_names']] == [6, 4, 1, 3]
            for calls in by_scenario.values():
                assert calls[0].args[2]['model'] == 'unknown-model'
                assert not calls[0].kwargs.get('headers')
            for scenario, expected_headers in (
                ('header', ['', 'unknown-model', '../invalid']),
                ('recommended', ['unknown-model', '../invalid']),
            ):
                assert [call.kwargs['headers']['x-ai-model'] for call in by_scenario[scenario][1:]] == expected_headers


def parse_policy(path: Path) -> ET.Element:
    """Encode raw expression attributes only for structural tests, never deployment."""
    source = path.read_text(encoding = 'utf-8')
    xml = re.sub(
        r"""(?P<prefix>\b[\w-]+\s*=\s*)(?P<quote>['"])(?P<expression>@(?:\([\s\S]*?\)|\{[\s\S]*?\}))(?P=quote)""",
        lambda match: f'{match["prefix"]}"{escape(match["expression"], quote = True)}"',
        source,
    )

    return ET.fromstring(xml)


@pytest.mark.parametrize('expression', [
    '@(context.Request.Body.As<JObject>(preserveContent: true)["model"])',
    '@{\n    var body = context.Request.Body.As<JObject>(preserveContent: true);\n    return body != null && body.Count >= 1 && body.Count < 10;\n}',
])
def test_structural_parser_preserves_raw_expression_characters(tmp_path, expression):
    """Structural checks must see the exact C# deployed with APIM rawxml."""
    path = tmp_path / 'policy.xml'
    path.write_text(f'<fragment><set-variable name="result" value=\'{expression}\' /></fragment>', encoding = 'utf-8')

    root = parse_policy(path)

    assert root.find('set-variable').attrib['value'] == expression.replace('\n', ' ')


def test_structural_parser_does_not_hide_malformed_policy_markup(tmp_path):
    """Escaping C# must not turn broken policy structure into a successful parse."""
    path = tmp_path / 'policy.xml'
    path.write_text('<fragment><set-variable name="result" value="@(1 < 2)"></fragment>', encoding = 'utf-8')

    with pytest.raises(ET.ParseError):
        parse_policy(path)


def policy(scenario = 'recommended'):
    """Expand single-level XML includes for structural checks, not APIM expression execution."""
    root = parse_policy(SAMPLE / 'apim-policies' / f'{scenario}.xml')
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag != 'include-fragment':
                continue
            name = child.attrib['fragment-id'].removeprefix('aoai-v1-routing-1-')
            fragment = parse_policy(SAMPLE / 'apim-policies' / 'fragments' / f'{name}.xml')
            assert fragment.tag == 'fragment' and fragment.find('.//include-fragment') is None
            index = list(parent).index(child)
            parent.remove(child)
            for offset, node in enumerate(fragment):
                parent.insert(index + offset, node)
    return root


@pytest.mark.parametrize('scenario', ['body', 'header', 'subscription', 'recommended'])
def test_request_body_is_processed_in_one_csharp_block(scenario):
    """Keep payload parsing, validation and selection in one block with a compact result."""
    root = policy(scenario)
    readers = [
        node for node in root.findall('.//set-variable')
        if 'context.Request.Body.As<' in node.attrib['value']
    ]
    assert len(readers) == 1
    reader = readers[0]
    assert reader.attrib['name'] == 'bodySelection'
    assert reader.attrib['value'].count('context.Request.Body.As<') == 1
    assert 'preserveContent: true' in reader.attrib['value']
    assert 'JTokenType.Boolean' in reader.attrib['value']
    assert 'JTokenType.String' in reader.attrib['value']
    assert 'result["model"]' in reader.attrib['value']
    assert 'result["errorCode"]' in reader.attrib['value']
    assert 'result["errorStatus"]' in reader.attrib['value']
    validation = root.find('.//set-variable[@name="bodyValidation"]')
    assert 'GetValueOrDefault<JObject>("bodySelection", null)["errorCode"]' in validation.attrib['value']
    selections = root.findall('.//set-variable[@name="model"]')
    assert any('GetValueOrDefault<JObject>("bodySelection", null)["model"]' in node.attrib['value'] for node in selections)
    fragment = parse_policy(SAMPLE / 'apim-policies' / 'fragments' / 'body-model.xml')
    assert len([node for node in fragment.findall('.//set-variable') if node.attrib['value'].startswith('@{')]) == 1
    assert '(JObject)' not in ET.tostring(fragment, encoding = 'unicode')


@pytest.mark.parametrize('scenario', ['header', 'recommended'])
def test_header_first_branch_cannot_parse_or_modify_request_body(scenario):
    """Structural scope proves the nonempty-header branch bypasses body mechanics."""
    root = policy(scenario)
    header_branch = root.find('./inbound/choose/when[@condition=\'@(!String.IsNullOrEmpty((string)context.Variables["headerModel"]))\']')
    assert header_branch is not None
    assert [element.tag for element in header_branch] == ['set-variable']
    assert header_branch[0].attrib['name'] == 'model'
    assert 'headerModel' in header_branch[0].attrib['value']
    body_reader = root.find('./inbound/choose/otherwise/set-variable[@name="bodySelection"]')
    assert body_reader is not None and 'preserveContent: true' in body_reader.attrib['value']
    assert 'JTokenType.Boolean' in body_reader.attrib['value']
    assert 'JTokenType.String' in body_reader.attrib['value']
    assert 'body?["model"]' in body_reader.attrib['value']
    assert 'body["messages"]' not in body_reader.attrib['value']
    assert 'body["input"]' not in body_reader.attrib['value']
    parents = {child: parent for parent in root.iter() for child in parent}
    assert all(parents[node].tag == 'return-response' for node in root.findall('./inbound//set-body'))
    header_selector = root.find('./inbound/set-variable[@name="headerModel"]').attrib['value']
    assert 'foreach' in header_selector and 'IsNullOrWhiteSpace' in header_selector
    assert 'Body' not in header_selector
    assert [element.tag for element in root.find('backend')] == ['forward-request']
    assert not root.findall('.//retry')
    assert root.find('./backend/forward-request').attrib['timeout'] == '60'
    assert root.find('./backend/forward-request').attrib['buffer-response'] == 'false'


@pytest.mark.parametrize('scenario', ['body', 'header', 'subscription', 'recommended'])
def test_convention_selection_has_no_model_specific_policy_branches(scenario):
    """Policy selection is generic when the configured model list changes."""
    root = policy(scenario)
    text = ET.tostring(root, encoding = 'unicode')
    assert all(model.model_name not in text for model in ApprovedModel)
    selectors = root.findall('.//set-backend-service')
    assert len(selectors) == 1
    assert selectors[0].attrib['backend-id'] == '@((string)context.Variables["backendPool"])'
    pool_expression = root.find('./inbound/set-variable[@name="backendPool"]').attrib['value']
    assert pool_expression == '@($"aoai-v1-routing-1-{(string)context.Variables["model"]}-{(string)context.Variables["family"]}-pool")'
    assert 'context.Variables["model"]' in pool_expression and 'context.Variables["family"]' in pool_expression
    assert '-pool' in pool_expression
    assert root.find('./inbound/set-variable[@name="scenario"]').attrib['value'] == scenario
    rewrite = root.find('./inbound/rewrite-uri')
    assert rewrite.attrib == {'template': '@(context.Operation.UrlTemplate)', 'copy-unmatched-params': 'false'}
    assert all('scenario' not in node.attrib['condition'] for node in root.findall('.//when'))
    assert all('"scenario"' not in node.attrib['value'] for node in root.findall('.//set-variable'))
    subscription_conditions = [node.attrib['condition'] for node in root.findall('./inbound/choose/when')]
    if scenario in ('subscription', 'recommended'):
        assert any('context.Subscription.Id == (string)context.Variables["prioritySubscriptionId"]' in condition for condition in subscription_conditions)
        assert any('context.Subscription.Id != (string)context.Variables["standardSubscriptionId"]' in condition for condition in subscription_conditions)
        assert root.find('./inbound/set-variable[@name="standardSubscriptionId"]').attrib['value'] == f'api-aoai-v1-routing-1-{scenario}'
        priority_id = 'aoai-v1-routing-1-priority' if scenario == 'subscription' else 'aoai-v1-routing-1-recommended-priority'
        assert root.find('./inbound/set-variable[@name="prioritySubscriptionId"]').attrib['value'] == priority_id
    else:
        assert 'context.Subscription' not in text
    if scenario in ('body', 'subscription'):
        assert root.find('./inbound/set-variable[@name="headerModel"]') is None
        assert all('Request.Headers' not in node.attrib['value'] for node in root.findall('.//set-variable'))
        assert root.find('./inbound/set-variable[@name="bodyValidation"]') is not None
    assert 'context.Subscription.Name' not in text and 'context.Subscription.Key' not in text


@pytest.mark.parametrize('scenario', ['body', 'header', 'subscription', 'recommended'])
def test_every_early_return_has_safe_trace_and_errors_remain_distinct(scenario):
    """Local responses do not silently bypass telemetry, unlike outbound-only logging."""
    root = policy(scenario)
    parents = {child: parent for parent in root.iter() for child in parent}
    for early_return in root.findall('.//return-response'):
        siblings = list(parents[early_return])
        assert any(element.tag == 'trace' for element in siblings[:siblings.index(early_return)])
        assert early_return.find('./set-header[@name="x-routing-request-id"]') is not None
    for trace in root.findall('.//trace'):
        assert trace.attrib == {'source': 'aoai-v1-routing', 'severity': 'error'}
        expected = {'requestId', 'scenario', 'errorKind', 'status'}
        if trace is root.find('./on-error/trace'):
            expected.add('reason')
        assert {item.attrib['name'] for item in trace.findall('metadata')} == expected
        assert not re.search(r'Body|Headers|LastError|Variables\["model"\]', ET.tostring(trace, encoding = 'unicode'))
    outbound = root.find('outbound')
    assert not outbound.findall('.//set-status')  # Preserve real backend status.
    assert outbound.find('.//trace') is not None
    classification = root.find('./on-error/set-variable[@name="gatewayCode"]').attrib['value']
    assert 'LastError.PolicyId == "resolve-model-pool"' in classification
    assert 'BackendConnectionFailure' in classification
    assert 'model_not_available' in classification and 'UpstreamUnavailable' in classification
    assert 'ModelNotAvailable' not in classification and 'LastError.Message' not in classification
    assert root.find('./inbound/base') is not None
    assert root.find('./inbound/authentication-managed-identity').attrib['resource'] == 'https://cognitiveservices.azure.com'


@pytest.mark.parametrize('scenario', ['body', 'header', 'subscription', 'recommended'])
def test_missing_pool_classification_is_scoped_to_prevalidated_resolver(scenario):
    """Only the tiny resolver phase is eligible; later auth/forward errors are excluded."""
    root = policy(scenario)
    inbound = list(root.find('inbound'))
    resolver = root.find('./inbound/set-backend-service')
    index = inbound.index(resolver)
    assert resolver.attrib == {'id': 'resolve-model-pool', 'backend-id': '@((string)context.Variables["backendPool"])'}
    assert inbound[index - 1].attrib == {'name': 'routePhase', 'value': 'resolve'}
    assert inbound[index + 1].attrib == {'name': 'routePhase', 'value': 'resolved'}
    validation = inbound[index - 2]
    assert validation.tag == 'choose'
    guard = validation.find('when').attrib['condition']
    assert 'Regex.IsMatch((string)context.Variables["backendPool"]' in guard
    assert '{0,79}' in guard
    assert validation.find('.//return-response/set-status').attrib['code'] == '404'
    classifier = root.find('./on-error/set-variable[@name="gatewayCode"]').attrib['value']
    assert classifier.index('BackendConnectionFailure') < classifier.index('resolve-model-pool')
    assert re.search(
        r'context\.LastError\.Reason == "BackendConnectionFailure"\s*\|\|\s*'
        r'context\.LastError\.Reason == "PoolIsInactive"\s*\?\s*"UpstreamUnavailable"',
        classifier,
    )
    assert re.search(r'context\.LastError\.Reason == "Timeout"\s*&&\s*context\.LastError\.Section == "backend"\s*\?\s*"UpstreamTimeout"', classifier)
    assert 'context.LastError.Section == "inbound"' in classifier
    assert 'GetValueOrDefault<string>("routePhase", "") == "resolve"' in classifier
    assert '&&' in classifier
    assert 'context.LastError.Source' not in classifier  # No undocumented Source-string assumption.
    safe_reason = root.find('./on-error/set-variable[@name="safeReason"]').attrib['value']
    assert 'context.LastError.Reason' in safe_reason and '{0,63}' in safe_reason and '"Other"' in safe_reason
    assert 'LastError.Message' not in ET.tostring(root, encoding = 'unicode')
    status_expression = root.find('./on-error/set-variable[@name="gatewayStatus"]').attrib['value']
    assert '"model_not_available" ? 404' in status_expression
    assert '"UpstreamUnavailable" ? 503' in status_expression
    assert '"UpstreamTimeout" ? 504 : 500' in status_expression
    status_reason = root.find('./on-error/return-response/set-status').attrib['reason']
    assert '== 404 ? "Not Found"' in status_reason
    assert '== 503 ? "Service Unavailable"' in status_reason
    assert '== 504 ? "Gateway Timeout" : "Internal Server Error"' in status_reason
    bicep = (SAMPLE / 'main.bicep').read_text(encoding = 'utf-8')
    assert 'availableModels' not in bicep and '__AVAILABLE_MODELS__' not in bicep


def test_policy_literal_contract_and_safe_bicep_wiring():
    """Policies deploy unchanged; shared modules keep topology and authentication."""
    bicep = (SAMPLE / 'main.bicep').read_text(encoding = 'utf-8')
    xml = '\n'.join(path.read_text(encoding = 'utf-8') for path in (SAMPLE / 'apim-policies').rglob('*.xml'))
    assert not re.search(r'__[A-Z_]+__', xml)
    assert not re.search(r'&(?:lt|gt|amp);', xml)
    assert 'replace(' not in bicep
    assert 'policyFragmentValue: fragment.xml' in bicep
    assert 'policyXml: policyDefinitions[i]' in bicep
    assert "var sampleName = 'aoai-v1-routing-1'" in bicep
    assert 'param sampleName' not in bicep
    for module in ('api', 'backend', 'backend-pool', 'policy-fragment'):
        assert f'shared/bicep/modules/apim/v1/{module}.bicep' in bicep
    assert "param modelSku string = 'GlobalStandard'" in bicep
    assert "@allowed(['GlobalStandard', 'Standard'])" in bicep
    assert 'subscriptionRequired: true' in bicep and 'enableLlmLogging: false' in bicep
    assert 'appInsightsInstrumentationKey:' not in bicep  # Shared default captures bodies.
    assert "verbosity: 'verbose'" in bicep and 'body: { bytes: 0 }' in bicep
    assert 'loggerId: resourceId(' in bicep
    # Backend creation depends only on concrete destination; pool family never enters the name.
    destination_expression = bicep.split('var destinations =', 1)[1].split('var families =', 1)[0]
    assert 'family' not in destination_expression
    assert 'model.deploymentName' in destination_expression and 'accountIndex' in destination_expression
    assert 'members: map(range(0, length(accounts))' in bicep
    assert "name: '${sampleName}-${model.deploymentName}-${accounts[i].label}'" in bicep
    assert 'backends: pool.members' in bicep
    account_module = (SAMPLE / 'foundry-account.bicep').read_text(encoding = 'utf-8')
    assert "name: 'S0'" in account_module and 'disableLocalAuth: true' in account_module
    assert 'name: model.deploymentName' in account_module
    assert 'name: modelSku' in account_module and '@batchSize(1)' in account_module


def test_backend_evidence_overrides_upstream_headers_without_exposing_full_urls():
    """A concrete resolved host, not a caller/upstream header or pool name, is evidence."""
    root = parse_policy(SAMPLE / 'apim-policies' / 'fragments' / 'safe-response.xml')
    header = root.find('./set-header[@name="x-routing-backend-host"]')
    assert header.attrib['exists-action'] == 'override'
    assert header.find('value').text == '@(context.Request.Url.Host)'
    bicep = (SAMPLE / 'main.bicep').read_text(encoding = 'utf-8')
    assert 'endpoint: foundryAccounts[i].outputs.endpoint' in bicep


def test_fragment_composition_is_deployable_and_each_endpoint_is_explicit():
    """Fragments cannot nest, contain sections or inherit base policies."""
    directory = SAMPLE / 'apim-policies'
    bicep = (SAMPLE / 'main.bicep').read_text(encoding = 'utf-8')
    fragments = {f'aoai-v1-routing-1-{path.stem}': path for path in (directory / 'fragments').glob('*.xml')}
    for path in fragments.values():
        root = parse_policy(path)
        assert root.tag == 'fragment'
        assert not any(node.tag in {'include-fragment', 'base', 'inbound', 'backend', 'outbound', 'on-error'} for node in root.iter())
        assert f"loadTextContent('apim-policies/fragments/{path.name}')" in bicep
    for scenario in ('body', 'header', 'subscription', 'recommended'):
        root = parse_policy(directory / f'{scenario}.xml')
        assert f"loadTextContent('apim-policies/{scenario}.xml')" in bicep
        assert all(node.attrib['fragment-id'] in fragments for node in root.findall('.//include-fragment'))
        assert [node.tag for node in root.find('backend')] == ['forward-request']
        inbound = list(root.find('inbound'))
        assert inbound[0].tag == 'base'
        assert inbound[1].attrib == {'name': 'scenario', 'value': scenario}
        assert list(root.find('on-error'))[0].attrib == {'name': 'scenario', 'value': scenario}
    assert not (directory / 'routing.xml').exists()
    assert '__SCENARIO__' not in bicep
    assert 'dependsOn: [pools, policyFragmentModule]' in bicep
    assert "scope: '/apis/${apis[2].name}'" in bicep
    assert "scope: '/apis/${apis[3].name}'" in bicep
    assert "var recommendedPrioritySubscriptionId = '${sampleName}-recommended-priority'" in bicep


def test_foundry_hosting_preserves_account_identity_and_openai_inference_contract():
    """Upgrade existing accounts without changing deployment selectors or broadening APIM access."""
    account_module = (SAMPLE / 'foundry-account.bicep').read_text(encoding = 'utf-8')
    bicep = (SAMPLE / 'main.bicep').read_text(encoding = 'utf-8')
    assert "kind: 'AIServices'" in account_module and 'allowProjectManagement: true' in account_module
    assert re.search(r"identity:\s*\{\s*type: 'SystemAssigned'\s*\}", account_module)
    assert "output endpoint string = account.properties.endpoints['Azure OpenAI Legacy API - Latest moniker']" in account_module
    assert "url: uri(foundryAccounts[destination.accountIndex].outputs.endpoint, 'openai/v1')" in bicep
    assert "name: '${sampleName}-${account.label}-account'" in bicep
    assert "accountName: 'oai-r-${uniqueString(resourceGroup().id, sampleName, account.label)}'" in bicep
    assert 'customSubDomainName: accountName' in account_module
    assert 'name: guid(account.id, principalId, openAiUserRole)' in account_module
    assert "'5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'" in account_module
    assert "format: 'OpenAI'" in account_module
    assert 'Microsoft.CognitiveServices/accounts/projects' not in account_module


def test_notebook_initialization_and_scenario_contract(monkeypatch):
    """Execute visible initialization with mocked orchestration, not Azure resources."""
    notebook = json.loads((SAMPLE / 'create.ipynb').read_text(encoding = 'utf-8'))
    cells = [cell for cell in notebook['cells'] if cell['cell_type'] == 'code']
    for cell in cells:
        assert cell['execution_count'] is None and not cell['outputs']
        tree = ast.parse(''.join(cell['source']))
        seen_nonimport = False
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                assert not seen_nonimport, 'Imports must precede all executable cell statements.'
            else:
                seen_nonimport = True
    monkeypatch.setattr('utils.NotebookHelper', MagicMock())
    namespace = {}
    exec(compile(''.join(cells[0]['source']), '<routing-initialization>', 'exec'), namespace)
    assert len(namespace['supported_infras']) == 5
    utils.NotebookHelper.assert_called_once_with(
        namespace['sample_folder'], namespace['rg_name'], namespace['rg_location'],
        namespace['deployment'], namespace['supported_infras'],
        index = namespace['index'], apim_sku = namespace['apim_sku'],
    )
    assert namespace['tags'] == ['aoai-v1-routing', 'ai-scenarios']
    assert 'sampleName' not in namespace['bicep_parameters']
    apis = namespace['bicep_parameters']['apis']['value']
    assert [api['name'].rsplit('-', 1)[-1] for api in apis] == ['body', 'header', 'subscription', 'recommended']
    assert all(api['subscriptionRequired'] and len(api['operations']) == 2 for api in apis)
    for api in apis:
        assert [(operation['name'], operation['method'], operation['urlTemplate']) for operation in api['operations']] == [
            ('chat-completions', 'POST', '/chat/completions'), ('responses', 'POST', '/responses'),
        ]
        assert all(not operation['policyXml'] for operation in api['operations'])
    for api in apis[2:]:
        scenario = api['name'].removeprefix('aoai-v1-routing-1-')
        root = policy(scenario)
        assert root.find('./inbound/set-variable[@name="standardSubscriptionId"]').attrib['value'] == f'api-{api["name"]}'
        priority_id = f'{namespace["sample_name"]}-priority' if scenario == 'subscription' else f'{api["name"]}-priority'
        assert root.find('./inbound/set-variable[@name="prioritySubscriptionId"]').attrib['value'] == priority_id
    all_code = '\n'.join(''.join(cell['source']) for cell in cells)
    assert 'require_existing_infrastructure' not in all_code
    assert "result.error_code in ('DeploymentNotFound', 'model_not_found')" in all_code
    assert "result.error_message == 'The upstream service rejected the request.'" in all_code
    assert 'results.append(result)' in all_code
