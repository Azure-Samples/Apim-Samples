"""Offline configuration, request lifecycle, notebook and APIM policy contracts."""

import ast
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

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

    return [{'status_code': status, 'response': json.dumps(body), 'headers': headers}]


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
            assert len(selected) == len(namespace['model_configuration']) + 1
            assert selected[-1][1] == 'not-an-object'
            for call in selected[:-1]:
                assert call[1] == {**namespace['request_payloads'][pathway], 'model': 'not-deployed-on-any-account'}


@pytest.mark.parametrize('deferred_failure', [False, True])
def test_notebook_missing_route_acceptance_gate_is_not_status_only(monkeypatch, deferred_failure):
    """Run rejection assertions: a deferred gateway failure cannot masquerade as graceful resolution."""
    namespace, code = initialized_notebook(monkeypatch)
    missing_route = helpers.ProbeResult(404, 'model_not_available', 'The specified model is not available for use', False, '', REQUEST_ID)
    missing_selector = helpers.ProbeResult(404, 'ModelNotAvailable', missing_route.error_message, False, '', REQUEST_ID)
    invalid = helpers.ProbeResult(400, 'InvalidRequest', 'The request payload is invalid.', False, '', REQUEST_ID)
    rows = [missing_route, missing_selector, invalid, invalid, invalid, invalid] * len(namespace['scenario_names'])
    pool = f'{namespace["sample_name"]}-{namespace["model_configuration"][0]["deploymentName"]}-standard-pool'
    success = helpers.ProbeResult(200, None, None, True, pool, REQUEST_ID)
    rows.extend([success, missing_route, missing_selector] * 2)
    rows *= 2  # The same rejection and fallback contracts apply to both v1 operations.
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
        assert remote.call_count == len(rows)
        assert namespace['results'][0].error_code == 'model_not_available'
        assert remote.call_args.kwargs['headers'] == {'x-ai-model': '../invalid'}
        assert {call.args[1] for call in remote.call_args_list} == {
            f'/{namespace["paths"][scenario]}/{pathway}'
            for scenario in namespace['scenario_names'] for pathway in ('chat/completions', 'responses')
        }


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
