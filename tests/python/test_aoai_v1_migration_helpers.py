"""Offline smoke-test mechanics and lifecycle coverage for the PAYG migration lab."""

import importlib.util
import json
import math
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import matplotlib.pyplot as plt
import pytest

# APIM Samples imports
from apimrequests import ApimRequests
from apimtypes import SUBSCRIPTION_KEY_PARAMETER_NAME, AzureOpenAIModel
from test_helpers import create_mock_http_response, create_mock_session_with_response

SAMPLE = Path(__file__).resolve().parents[2] / 'samples' / 'aoai-v1-migration'
SPEC = importlib.util.spec_from_file_location('migration_helpers', SAMPLE / 'migration_helpers.py')
helpers = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = helpers
SPEC.loader.exec_module(helpers)


def response(status = 200, body = None):
    """Create the actual ApimRequests.multiPost result shape."""
    if body is None:
        body = {'choices': [{'message': {'content': 'Hello'}}]}

    return [{'status_code': status, 'response': json.dumps(body)}]


def client_for(*responses):
    """Build a context-managed remote boundary without HTTP or Azure."""
    client = MagicMock(spec = ApimRequests)
    client.__enter__.return_value = client
    client.multiPost.side_effect = responses

    return client


def test_valid_payg_defaults():
    """Usable configuration requires no inventory or approval inputs."""
    for sku in ('Standard', 'GlobalStandard'):
        helpers.validate_configuration(sample_name = 'aoai-v1-migration-1', model_sku = sku, capacity = 10)


def test_two_models_have_distinct_singleton_pool_names():
    """Model names drive deterministic deployment, backend and pool identifiers."""
    models = helpers.build_models('aoai-v1-migration-1', [AzureOpenAIModel.GPT_5_MINI, AzureOpenAIModel.GPT_5_NANO], 10)
    assert [item['name'] for item in models] == ['gpt-5-mini', 'gpt-5-nano']
    for item, model in zip(models, [AzureOpenAIModel.GPT_5_MINI, AzureOpenAIModel.GPT_5_NANO], strict = True):
        deployment = f'aoai-v1-migration-1-{model.value}'
        assert item == {
            'name': model.value, 'version': model.version, 'capacity': 10,
            'deploymentName': deployment, 'backendName': f'{deployment}-backend', 'poolName': f'{deployment}-pool',
        }


@pytest.mark.parametrize('models', [
    [], [AzureOpenAIModel.GPT_5_MINI], [AzureOpenAIModel.GPT_5_MINI] * 2,
    [AzureOpenAIModel.GPT_5_MINI, 'gpt-5-nano'],
    [AzureOpenAIModel.GPT_5_MINI, AzureOpenAIModel.GPT_5_NANO, AzureOpenAIModel.GPT_5_1],
])
def test_model_selection_requires_two_distinct_enum_models(models):
    """Reject an incomplete or ambiguous routing matrix before deployment."""
    with pytest.raises(ValueError, match = 'two different'):
        helpers.build_models('aoai-v1-migration-1', models, 10)


def test_model_name_normalization():
    """Dotted model names remain valid deployment and pool resource IDs."""
    models = helpers.build_models('aoai-v1-migration-1', [AzureOpenAIModel.GPT_5_1, AzureOpenAIModel.GPT_5_NANO], 10)
    assert models[0]['name'] == 'gpt-5.1'
    assert models[0]['poolName'] == 'aoai-v1-migration-1-gpt-5-1-pool'


@pytest.mark.parametrize('names,message', [
    (('gpt/unsafe', 'gpt-5-nano'), 'safe lowercase deployment identifiers'),
    (('gpt.5-mini', 'gpt-5-mini'), 'distinct after normalization'),
])
def test_future_catalog_entries_reject_unsafe_or_colliding_names(monkeypatch, names, message):
    """A future enum catalog update must not produce invalid or duplicate pools."""
    model_names = dict(zip((AzureOpenAIModel.GPT_5_MINI, AzureOpenAIModel.GPT_5_NANO), names, strict = True))
    monkeypatch.setattr(AzureOpenAIModel, 'value', property(lambda model: model_names[model]), raising = False)
    with pytest.raises(ValueError, match = message):
        helpers.build_models('aoai-v1-migration-1', [AzureOpenAIModel.GPT_5_MINI, AzureOpenAIModel.GPT_5_NANO], 10)


@pytest.mark.parametrize('values', [
    (None, 'Standard', 10),
    ('', 'Standard', 10),
    ('unrelated', 'Standard', 10),
    ('aoai-v1-migration-UPPER', 'Standard', 10),
    ('aoai-v1-migration-' + 'a' * 23, 'Standard', 10),
    ('aoai-v1-migration-1', 'ProvisionedManaged', 10),
    ('aoai-v1-migration-1', 'Standard', 0),
    ('aoai-v1-migration-1', 'Standard', True),
    ('aoai-v1-migration-1', 'Standard', '10'),
])
def test_configuration_rejects_invalid_inputs(values):
    """Reject collisions, policy injection and non-PAYG configuration."""
    with pytest.raises(ValueError):
        helpers.validate_configuration(*values)


def test_subscription_key_selection():
    """Select the matching API without accepting ambiguous output."""
    apis = [{'name': 'legacy', 'subscriptionPrimaryKey': 'secret'}, {'name': 'v1', 'subscriptionPrimaryKey': 'other'}]
    assert helpers.subscription_key(apis, 'legacy') == 'secret'
    for values in ([], apis + [apis[0]], [{'name': 'legacy'}], [{'name': 'legacy', 'subscriptionPrimaryKey': 42}],
                   [{'name': 'legacy', 'subscriptionPrimaryKey': ''}], [{'name': 'legacy', 'subscriptionPrimaryKey': '   '}]):
        with pytest.raises(ValueError):
            helpers.subscription_key(values, 'legacy')


def test_smoke_success_request_and_cleanup():
    """Use the established client contract and close it after success."""
    client = client_for(response())
    payload = {'messages': [{'role': 'user', 'content': 'Hi'}], 'stream': False}
    result = helpers.test(lambda: client, '/legacy?api-version=2024-10-21', payload)
    assert result == helpers.SmokeResult(200, 1, True)
    client.multiPost.assert_called_once_with('/legacy?api-version=2024-10-21', 1, data = payload, printResponse = False)
    client.__exit__.assert_called_once()
    assert 'secret' not in repr(result)


@pytest.mark.parametrize('header', ['x-migration-backend-pool', 'X-Migration-Backend-Pool'])
def test_smoke_requires_exact_pool_and_actual_response_model(header):
    """Status alone is insufficient evidence that the intended model/pool was exercised."""
    rows = response(body = {'model': 'gpt-5-mini-2025-08-07', 'choices': [{'message': {'content': 'Hello'}}]})
    rows[0]['headers'] = {header: 'sample-gpt-5-mini-pool'}
    client = client_for(rows)
    result = helpers.test(
        lambda: client, '/v1', {}, expected_pool = 'sample-gpt-5-mini-pool', expected_model = 'gpt-5-mini-2025-08-07',
    )
    assert result.backend_pool == 'sample-gpt-5-mini-pool'
    assert result.model == 'gpt-5-mini-2025-08-07'
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('pool,model', [
    ('wrong-pool', 'gpt-5-mini-2025-08-07'),
    ('sample-gpt-5-mini-pool', 'gpt-5-nano-2025-08-07'),
    (None, 'gpt-5-mini-2025-08-07'),
    ('sample-gpt-5-mini-pool', None),
])
def test_pool_or_model_mismatch_fails_even_on_http_200(pool, model):
    """Close clients and fail explicitly if routing evidence is absent or wrong."""
    rows = response(body = {'model': model, 'choices': [{'message': {'content': 'Hello'}}]})
    rows[0]['headers'] = {} if pool is None else {'x-migration-backend-pool': pool}
    client = client_for(rows)
    with pytest.raises(ValueError, match = 'Expected'):
        helpers.test(lambda: client, '/v1', {}, expected_pool = 'sample-gpt-5-mini-pool', expected_model = 'gpt-5-mini-2025-08-07')
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('headers,model', [
    ([], 'gpt-5-mini'), ({42: 'pool'}, 'gpt-5-mini'),
    ({'x-migration-backend-pool': 42}, 'gpt-5-mini'), ({}, 42),
])
def test_malformed_routing_evidence_closes_client(headers, model):
    """Do not normalize invalid metadata into successful routing evidence."""
    rows = response(body = {'model': model, 'choices': [{'message': {'content': 'Hello'}}]})
    rows[0]['headers'] = headers
    client = client_for(rows)
    with pytest.raises(ValueError, match = 'Malformed'):
        helpers.test(lambda: client, '/v1', {})
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('status', [401, 403, 404, 429, 500, 502, 503, 504])
def test_readiness_retry_is_bounded_and_injects_sleep(status):
    """Transient readiness is handled without real delays."""
    client = client_for(response(status), response())
    sleep = MagicMock()
    result = helpers.test(lambda: client, '/v1', {}, retry_delays = (3,), sleep = sleep)
    assert result.attempts == 2
    sleep.assert_called_once_with(3)
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('final_status', [200, 503])
def test_default_retry_budget_allows_exactly_six_attempts(final_status):
    """The documented retry schedule permits six calls and 180 seconds of waits."""
    client = client_for(*([response(503)] * 5), response(final_status))
    sleep = MagicMock()
    payload = {'messages': [{'role': 'user', 'content': 'Hi'}], 'stream': False}
    if final_status == 200:
        result = helpers.test(lambda: client, '/v1', payload, sleep = sleep)
        assert result.attempts == 6 and result.has_completion
    else:
        with pytest.raises(RuntimeError, match = 'HTTP 503 after 6 attempt'):
            helpers.test(lambda: client, '/v1', payload, sleep = sleep)
    assert client.multiPost.call_count == 6
    assert [call.args[0] for call in sleep.call_args_list] == [10, 20, 30, 60, 60]
    assert sum(call.args[0] for call in sleep.call_args_list) == 180
    assert all(call.kwargs['data'] == payload for call in client.multiPost.call_args_list)
    client.__exit__.assert_called_once()


def test_retry_wait_failure_propagates_and_closes_client():
    """Interrupted readiness waits cannot leak a session or make another call."""
    client = client_for(response(503))
    sleep = MagicMock(side_effect = OSError('wait interrupted'))
    with pytest.raises(OSError, match = 'wait interrupted'):
        helpers.test(lambda: client, '/v1', {}, sleep = sleep)
    client.multiPost.assert_called_once()
    client.__exit__.assert_called_once()


def test_warmup_discards_first_success_and_charts_second_request(tmp_path, monkeypatch):
    """Cold-start time and tokens never appear as the Legacy Before measurement."""
    warmup_rows = response(body = {
        'model': 'gpt-5-mini-snapshot', 'choices': [{'message': {'content': 'Warm-up completion'}}],
        'usage': {'prompt_tokens': 9000, 'completion_tokens': 500, 'total_tokens': 9500},
    })
    warmup_rows[0].update(response_time = 99, headers = {'x-migration-backend-pool': 'gpt-5-mini-pool'})
    measured_rows = response(body = {
        'model': 'gpt-5-mini-snapshot', 'choices': [{'message': {'content': 'Measured completion'}}],
        'usage': {'prompt_tokens': 1200, 'completion_tokens': 100, 'total_tokens': 1300},
    })
    measured_rows[0].update(response_time = 1.25, headers = {'x-migration-backend-pool': 'gpt-5-mini-pool'})
    client = client_for(warmup_rows, measured_rows)
    factory = MagicMock(return_value = client)
    payload = {'messages': [{'role': 'user', 'content': 'Hi'}], 'stream': False}
    result = helpers.test(
        factory, '/legacy?api-version=2024-10-21', payload,
        expected_pool = 'gpt-5-mini-pool', expected_model = 'gpt-5-mini-snapshot', warmup = True,
    )
    assert result == helpers.SmokeResult(200, 1, True, 'gpt-5-mini-pool', 'gpt-5-mini-snapshot', 1.25, 1200, 100, 1300)
    factory.assert_called_once()
    assert client.multiPost.call_count == 2
    assert client.multiPost.call_args_list[0] == client.multiPost.call_args_list[1]
    client.__enter__.assert_called_once()
    client.__exit__.assert_called_once()

    chart = MagicMock()
    chart.return_value.render.return_value = plt.figure()
    monkeypatch.setattr(helpers.charts, 'BarChart', chart)
    monkeypatch.setattr(helpers.plt, 'show', lambda: None)
    probes = [
        helpers.ProbeEvidence('Legacy Before', 'gpt-5-mini', result),
        helpers.ProbeEvidence('v1', 'gpt-5-mini', replace(result, response_time = 0.9)),
        helpers.ProbeEvidence('Legacy After', 'gpt-5-mini', replace(result, response_time = 1.1)),
    ]
    path = helpers.generate_report(probes, tmp_path / 'migration.html')
    chart.assert_called_once()
    assert [(row['run'], row['response_time']) for row in chart.call_args.args[3]] == [
        ('Legacy Before', 1.25), ('v1', 0.9), ('Legacy After', 1.1),
    ]
    document = path.read_text(encoding = 'utf-8')
    assert '1,250.0' in document and '1,300' in document
    assert '99,000.0' not in document and '9,500' not in document
    assert 'validated warm-up request' in document
    assert 'Warm-up completion' not in document and 'Measured completion' not in document


@pytest.mark.parametrize('warmup_retries,measured_retries', [(0, 0), (1, 0), (0, 1), (5, 5)])
def test_warmup_and_measurement_have_separate_bounded_retry_budgets(warmup_retries, measured_retries):
    """Warm-up retries are not counted as measured attempts or consume their budget."""
    client = client_for(*([response(503)] * warmup_retries), response(), *([response(503)] * measured_retries), response())
    sleep = MagicMock()
    result = helpers.test(lambda: client, '/legacy', {}, warmup = True, sleep = sleep)
    assert result.attempts == measured_retries + 1
    assert client.multiPost.call_count == warmup_retries + measured_retries + 2
    delays = [10, 20, 30, 60, 60]
    assert [call.args[0] for call in sleep.call_args_list] == delays[:warmup_retries] + delays[:measured_retries]
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('phase', ['warmup', 'measured'])
def test_warmup_or_measurement_retry_exhaustion_fails_and_closes_client(phase):
    """Neither phase can run beyond its readiness budget or return earlier success."""
    rows = ([response()] if phase == 'measured' else []) + [response(503)] * 6
    client = client_for(*rows)
    label = 'Warm-up' if phase == 'warmup' else 'Smoke test'
    sleep = MagicMock()
    with pytest.raises(RuntimeError, match = f'{label} failed with HTTP 503 after 6 attempt'):
        helpers.test(lambda: client, '/legacy', {}, warmup = True, sleep = sleep)
    assert client.multiPost.call_count == len(rows)
    assert [call.args[0] for call in sleep.call_args_list] == [10, 20, 30, 60, 60]
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('phase', ['warmup', 'measured'])
def test_warmup_or_measurement_must_validate_exact_routing(phase):
    """A successful HTTP code alone cannot validate warm-up or measured routing."""
    valid = response(body = {'model': 'snapshot', 'choices': [{'message': {'content': 'Hi'}}]})
    valid[0]['headers'] = {'x-migration-backend-pool': 'expected-pool'}
    invalid = response(body = {'model': 'snapshot', 'choices': [{'message': {'content': 'Hi'}}]})
    invalid[0]['headers'] = {'x-migration-backend-pool': 'wrong-pool'}
    rows = [valid, invalid] if phase == 'measured' else [invalid]
    client = client_for(*rows)
    with pytest.raises(ValueError, match = 'Expected backend pool'):
        helpers.test(lambda: client, '/legacy', {}, expected_pool = 'expected-pool', expected_model = 'snapshot', warmup = True)
    assert client.multiPost.call_count == len(rows)
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('phase', ['warmup', 'measured'])
def test_warmup_or_measurement_transport_failure_closes_client(phase):
    """No partial success escapes if either request raises a transport error."""
    rows = ([response()] if phase == 'measured' else []) + [OSError('transport interrupted')]
    client = client_for(*rows)
    with pytest.raises(OSError, match = 'transport interrupted'):
        helpers.test(lambda: client, '/legacy', {}, warmup = True)
    assert client.multiPost.call_count == len(rows)
    client.__exit__.assert_called_once()


def test_warmup_is_rejected_for_negative_probes_before_client_creation():
    """The intentional single-attempt rejection probe cannot warm up."""
    factory = MagicMock()
    with pytest.raises(ValueError, match = 'Warm-up requires a successful completion'):
        helpers.test(factory, '/v1', {}, expected_status = 500, warmup = True)
    factory.assert_not_called()


@pytest.mark.parametrize('status', [400, 404, 500])
def test_expected_model_rejection(status):
    """Accept backend validation errors and the gateway's missing-pool error without retries."""
    code = 'gateway_error' if status == 500 else 'invalid_model'
    client = client_for(response(status, {'error': {'code': code}}))
    assert helpers.test(lambda: client, '/v1', {}, expected_status = status, retry_delays = ()) == helpers.SmokeResult(status, 1, False)
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('status', [400, 403, 404, 429, 500, 502, 503, 504])
def test_native_gateway_error_matches_expected_http_status(status):
    """APIM-native errors are valid negative evidence, not OpenAI completions."""
    client = client_for(response(status, {'statusCode': status, 'message': 'Gateway request failed.'}))
    sleep = MagicMock()
    result = helpers.test(lambda: client, '/v1', {}, expected_status = status, retry_delays = (), sleep = sleep)
    assert result == helpers.SmokeResult(status, 1, False)
    assert client.multiPost.call_count == 1
    sleep.assert_not_called()
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('body', [
    {},
    {'statusCode': 400, 'message': 'Wrong status.'},
    {'statusCode': '500', 'message': 'Not a numeric status.'},
    {'statusCode': True, 'message': 'Not a status code.'},
    {'statusCode': 500},
    {'message': 'Missing status.'},
    {'statusCode': 500, 'message': ''},
    {'statusCode': 500, 'message': '   '},
    {'statusCode': 500, 'message': None},
    {'statusCode': 500, 'message': 42},
    {'statusCode': 500, 'message': ['Invalid message.']},
])
def test_malformed_native_gateway_error_is_not_valid_negative_evidence(body):
    """Do not accept arbitrary HTTP 500 JSON as a successful rejection probe."""
    client = client_for(response(500, body))
    with pytest.raises(ValueError, match = 'matching statusCode and a non-empty message'):
        helpers.test(lambda: client, '/v1', {}, expected_status = 500, retry_delays = ())
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('status,delays,calls', [(400, (1,), 1), (403, (1,), 2), (429, (), 1)])
def test_failure_closes_client(status, delays, calls):
    """Neither permanent failures nor exhausted retries leak a client."""
    client = client_for(*[response(status)] * calls)
    with pytest.raises(RuntimeError, match = f'HTTP {status}'):
        helpers.test(lambda: client, '/v1', {}, retry_delays = delays, sleep = MagicMock())
    assert client.multiPost.call_count == calls
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('rows', [
    [], [{}], [{'status_code': '200'}], response(200, []),
    response(200, {}), response(200, {'choices': [None]}),
    response(200, {'choices': [{'message': {'content': ''}}]}),
    [{'status_code': 200, 'response': '{invalid'}],
])
def test_malformed_response_closes_client(rows):
    """Reject malformed remote results and incomplete chat responses."""
    client = client_for(rows)
    with pytest.raises(ValueError):
        helpers.test(lambda: client, '/v1', {})
    client.__exit__.assert_called_once()


def test_error_response_shape_and_transport_failure_cleanup():
    """Cleanup also runs when parser or remote boundary raises."""
    for value, exception in [(response(400, {}), ValueError), (OSError('offline transport'), OSError)]:
        client = client_for(value)
        with pytest.raises(exception):
            helpers.test(lambda: client, '/v1', {}, expected_status = 400)
        client.__exit__.assert_called_once()


@pytest.mark.parametrize('path,payload,delays', [('relative', {}, ()), ('/v1', [], ()), ('/v1', {'stream': True}, ()), ('/v1', {}, (-1,))])
def test_bad_smoke_input_creates_no_client(path, payload, delays):
    """Input validation precedes resource acquisition."""
    factory = MagicMock()
    with pytest.raises(ValueError):
        helpers.test(factory, path, payload, retry_delays = delays)
    factory.assert_not_called()


@pytest.mark.parametrize('statuses', [(200,), (503, 200), (400,), (500,)])
def test_real_apim_client_contract(monkeypatch, statuses):
    """Exercise the real POST interface, retries and session cleanup offline."""
    expected_status = statuses[-1]
    body = (
        {'choices': [{'message': {'content': 'Hello'}}]} if expected_status == 200
        else {'error': {'code': 'gateway_error' if expected_status == 500 else 'invalid_model'}}
    )
    responses = [create_mock_http_response(status_code = status, json_data = body) for status in statuses]
    session = create_mock_session_with_response(responses[0])
    session.request.side_effect = responses
    monkeypatch.setattr('apimrequests.requests.Session', lambda: session)
    sleep = MagicMock()
    payload = {'stream': False}

    result = helpers.test(
        lambda: ApimRequests('https://offline.invalid', 'test-key'),
        '/chat/completions', payload, expected_status = expected_status, retry_delays = (1,), sleep = sleep,
    )

    assert replace(result, response_time = None) == helpers.SmokeResult(expected_status, len(statuses), expected_status == 200)
    assert math.isfinite(result.response_time) and result.response_time >= 0
    assert session.request.call_count == len(statuses)
    for call in session.request.call_args_list:
        assert call.args == ('POST', 'https://offline.invalid/chat/completions')
        assert call.kwargs['json'] == payload
        assert call.kwargs['headers'][SUBSCRIPTION_KEY_PARAMETER_NAME] == 'test-key'
    assert sleep.call_count == len(statuses) - 1
    session.close.assert_called_once()


def test_real_apim_client_native_gateway_error(monkeypatch):
    """Exercise the reported HTTP 500 shape through the actual POST client."""
    body = {'statusCode': 500, 'message': 'Internal server error'}
    http_response = create_mock_http_response(status_code = 500, json_data = body)
    session = create_mock_session_with_response(http_response)
    monkeypatch.setattr('apimrequests.requests.Session', lambda: session)
    payload = {'model': 'unknown-model', 'stream': False}
    sleep = MagicMock()
    result = helpers.test(
        lambda: ApimRequests('https://offline.invalid', 'test-key'), '/openai/v1/chat/completions', payload,
        expected_status = 500, retry_delays = (), sleep = sleep,
    )
    assert replace(result, response_time = None) == helpers.SmokeResult(500, 1, False)
    assert math.isfinite(result.response_time) and result.response_time >= 0
    session.request.assert_called_once()
    assert session.request.call_args.kwargs['json'] == payload
    sleep.assert_not_called()
    session.close.assert_called_once()


@pytest.mark.parametrize('model', [AzureOpenAIModel.GPT_5_MINI, AzureOpenAIModel.GPT_5_NANO])
@pytest.mark.parametrize('contract', ['legacy', 'v1'])
def test_real_client_retains_pool_and_model_evidence(monkeypatch, model, contract):
    """Verify both contracts/pools through the actual HTTP client without live inference."""
    deployment = f'aoai-v1-migration-1-{model.value}'
    pool = f'{deployment}-pool'
    snapshot = f'{model.value}-{model.version}'
    response_body = {'model': snapshot, 'choices': [{'message': {'content': 'Hello'}}]}
    http_response = create_mock_http_response(
        status_code = 200, json_data = response_body, headers = {'X-Migration-Backend-Pool': pool},
    )
    session = create_mock_session_with_response(http_response)
    monkeypatch.setattr('apimrequests.requests.Session', lambda: session)
    payload = {'messages': [{'role': 'user', 'content': 'Hi'}], 'stream': False}
    if contract == 'legacy':
        path = f'/aoai-v1-migration-1/openai/deployments/{deployment}/chat/completions?api-version=2024-10-21'
    else:
        path = '/aoai-v1-migration-1/openai/v1/chat/completions'
        payload['model'] = deployment
    result = helpers.test(
        lambda: ApimRequests('https://offline.invalid', 'test-key'), path, payload,
        expected_pool = pool, expected_model = snapshot,
    )
    assert replace(result, response_time = None) == helpers.SmokeResult(200, 1, True, pool, snapshot)
    assert math.isfinite(result.response_time) and result.response_time >= 0
    assert session.request.call_args.args == ('POST', f'https://offline.invalid{path}')
    assert session.request.call_args.kwargs['json'] == payload
    session.close.assert_called_once()


def test_smoke_retains_only_final_measured_latency_and_usage():
    """Earlier retry timing and tokens do not become final-response measurements."""
    rows = response(body = {
        'choices': [{'message': {'content': 'Private completion'}}],
        'usage': {'prompt_tokens': 1200, 'completion_tokens': 100, 'total_tokens': 1300},
    })
    rows[0]['response_time'] = 1.25
    earlier = response(503, {'error': {'message': 'Private error'}})
    earlier[0]['response_time'] = 5
    client = client_for(earlier, rows)
    result = helpers.test(lambda: client, '/v1', {}, retry_delays = (10,), sleep = MagicMock())
    assert result == helpers.SmokeResult(200, 2, True, response_time = 1.25, prompt_tokens = 1200, completion_tokens = 100, total_tokens = 1300)
    assert 'Private' not in repr(result)
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('usage,expected', [
    (None, (None, None, None)),
    ({}, (None, None, None)),
    ({'prompt_tokens': 0, 'total_tokens': 42}, (0, None, 42)),
])
def test_optional_usage_does_not_invent_missing_token_counts(usage, expected):
    """Missing usage stays empty while measured zero remains a valid number."""
    rows = response(body = {'choices': [{'message': {'content': 'Hi'}}], 'usage': usage})
    result = helpers.test(lambda: client_for(rows), '/v1', {})
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == expected


@pytest.mark.parametrize('timing', [-1, True, '1.2', float('nan'), float('inf')])
def test_invalid_response_time_fails_and_closes_client(timing):
    """Malformed measurements are not presented as successful evidence."""
    rows = response()
    rows[0]['response_time'] = timing
    client = client_for(rows)
    with pytest.raises(ValueError, match = 'response time'):
        helpers.test(lambda: client, '/v1', {})
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('usage', [[], 'tokens', {'total_tokens': -1}, {'prompt_tokens': True}, {'completion_tokens': 1.5}])
def test_invalid_usage_fails_and_closes_client(usage):
    """Usage must be an object with non-negative integer counts."""
    rows = response(body = {'choices': [{'message': {'content': 'Hi'}}], 'usage': usage})
    client = client_for(rows)
    with pytest.raises(ValueError, match = 'Malformed OpenAI'):
        helpers.test(lambda: client, '/v1', {})
    client.__exit__.assert_called_once()


def report_probes():
    """Build all seven sanitized observations with deterministic measurements."""
    return [
        helpers.ProbeEvidence(
            stage, model,
            helpers.SmokeResult(200, 1, True, f'{model}-pool', f'{model}-snapshot', 1.25, 1200, 100, 1300),
        )
        for stage in ('Legacy Before', 'v1', 'Legacy After')
        for model in ('gpt-5-mini', 'gpt-5-nano')
    ] + [helpers.ProbeEvidence('v1 Rejection', 'Unknown model', helpers.SmokeResult(500, 1, False, response_time = 0.1), 500)]


def test_report_shared_charts_tables_and_expected_rejection(tmp_path, monkeypatch, caplog):
    """Use real shared chart/report components without displaying a GUI."""
    caplog.set_level('INFO', logger = 'console')
    show = MagicMock()
    monkeypatch.setattr(helpers.plt, 'show', show)
    figures_before = plt.get_fignums()
    path = helpers.generate_report(report_probes(), tmp_path / 'migration.html')
    document = path.read_text(encoding = 'utf-8')
    assert show.call_count == 2
    assert plt.get_fignums() == figures_before
    assert document.count('data:image/png;base64,') == 2
    assert document.count('<th scope="col">') == 14
    assert 'Expected rejection' in document and '1,300' in document and '1,250.0' in document
    assert 'earlier readiness attempts and waits are excluded' in document
    assert 'gpt-5-mini-pool' in document and 'gpt-5-nano-snapshot' in document
    output = caplog.text
    assert 'Response Time (ms)' in output and 'Prompt Tokens' in output and 'Expected rejection' in output


def test_chart_input_contains_stage_labels_and_no_raw_response(tmp_path, monkeypatch):
    """Expected rejection is never colored as a failure in the success charts."""
    figures = []

    def render():
        figure = plt.figure()
        figures.append(figure)

        return figure

    chart = MagicMock()
    chart.return_value.render.side_effect = render
    monkeypatch.setattr(helpers.charts, 'BarChart', chart)
    monkeypatch.setattr(helpers.plt, 'show', lambda: None)
    helpers.generate_report(report_probes(), tmp_path / 'migration.html')
    assert chart.call_count == 2
    for call in chart.call_args_list:
        rows = call.args[3]
        assert [row['run'] for row in rows] == ['Legacy Before', 'v1', 'Legacy After']
        assert all(row['status_code'] == 200 and row['response_time'] == 1.25 for row in rows)
        assert all(json.loads(row['response']) == {'index': 1} for row in rows)
    assert all(not plt.fignum_exists(figure.number) for figure in figures)


def test_missing_measurements_are_empty_and_warn_before_skipping_chart(tmp_path, monkeypatch, caplog):
    """Do not graph missing latency as zero or invent token consumption."""
    probes = [replace(probe, result = replace(probe.result, response_time = None, prompt_tokens = None, completion_tokens = None, total_tokens = None))
              for probe in report_probes()]
    chart = MagicMock()
    monkeypatch.setattr(helpers.charts, 'BarChart', chart)
    path = helpers.generate_report(probes, tmp_path / 'migration.html')
    document = path.read_text(encoding = 'utf-8')
    assert '<td></td>' in document
    assert 'Missing response times' in document
    assert 'Latency chart unavailable for gpt-5-mini' in caplog.text
    chart.assert_not_called()


@pytest.mark.parametrize('probes', [
    [],
    [helpers.ProbeEvidence('v1', 'gpt-5-mini', helpers.SmokeResult(500, 1, False))],
    [helpers.ProbeEvidence('v1', 'gpt-5-mini', helpers.SmokeResult(200, 1, False))],
    [helpers.ProbeEvidence('v1 Rejection', 'Unknown model', helpers.SmokeResult(500, 1, True), 500)],
])
def test_report_rejects_empty_or_failed_evidence_before_writing(tmp_path, probes):
    """A failed probe cannot produce a success-shaped report."""
    path = tmp_path / 'migration.html'
    with pytest.raises(ValueError):
        helpers.generate_report(probes, path)
    assert not path.exists()


@pytest.mark.parametrize('boundary', ['add_figure', 'show', 'write'])
def test_report_errors_propagate_and_close_figures(tmp_path, monkeypatch, boundary):
    """Embedding, display and filesystem failures remain explicit without figure leaks."""
    failure = MagicMock(side_effect = OSError('report unavailable'))
    figure = plt.figure()
    chart = MagicMock()
    chart.return_value.render.return_value = figure
    monkeypatch.setattr(helpers.charts, 'BarChart', chart)
    monkeypatch.setattr(helpers.plt, 'show', lambda: None)
    if boundary == 'show':
        monkeypatch.setattr(helpers.plt, 'show', failure)
    else:
        monkeypatch.setattr(helpers.HtmlReport, boundary, failure)
    with pytest.raises(OSError, match = 'report unavailable'):
        helpers.generate_report(report_probes(), tmp_path / 'migration.html')
    assert not plt.fignum_exists(figure.number)
