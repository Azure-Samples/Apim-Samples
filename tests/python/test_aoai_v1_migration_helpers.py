"""Offline smoke-test mechanics and lifecycle coverage for the PAYG migration lab."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

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


@pytest.mark.parametrize('values', [
    ('', 'Standard', 10),
    ('unrelated', 'Standard', 10),
    ('aoai-v1-migration-UPPER', 'Standard', 10),
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
    for values in ([], apis + [apis[0]], [{'name': 'legacy'}], [{'name': 'legacy', 'subscriptionPrimaryKey': 42}]):
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

    assert result == helpers.SmokeResult(expected_status, len(statuses), expected_status == 200)
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
    assert result == helpers.SmokeResult(500, 1, False)
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
    assert result == helpers.SmokeResult(200, 1, True, pool, snapshot)
    assert session.request.call_args.args == ('POST', f'https://offline.invalid{path}')
    assert session.request.call_args.kwargs['json'] == payload
    session.close.assert_called_once()
