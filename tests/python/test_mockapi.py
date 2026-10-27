"""Offline MockAPI credential, persistence, recovery and secret-logging contracts."""

import base64
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

# APIM Samples imports
import azure_resources as az
import infrastructures
import infrastructure_cli
import mockapi
from apimtypes import APIM_SKU, INFRASTRUCTURE, Output

_PREPARE_CREDENTIALS = infrastructures.Infrastructure._prepare_mockapi_credentials
_INITIALIZE_MOCKAPI = infrastructures.Infrastructure._initialize_mockapi
_APP_NAMES = ['ca-fixture-mockwebapi-1', 'ca-fixture-mockwebapi-2']


@pytest.fixture(scope = 'module')
def credentials():
    return mockapi.generate_credentials()


def _output(payload, *, success = True):
    return Output(success, json.dumps(payload))


def _secrets(credentials):
    return {
        'value': [
            {'name': name, 'value': value}
            for name, value in zip(
                ('dashboard-password', 'dashboard-password-hash', 'mock-api-key'),
                (credentials.dashboard_password, credentials.dashboard_password_hash, credentials.api_key),
            )
        ]
    }


def test_generated_credentials_meet_exact_lengths_and_hash_contract(credentials):
    assert re.fullmatch(r'[A-Za-z0-9_-]{16}', credentials.dashboard_password)
    assert re.fullmatch(r'[A-Za-z0-9_-]{43}', credentials.api_key)
    version, iterations, salt, digest = credentials.dashboard_password_hash.split('.')
    assert version == 'v1'
    assert int(iterations) == 600_000
    assert len(base64.b64decode(salt)) == 16
    expected = hashlib.pbkdf2_hmac('sha256', credentials.dashboard_password.encode(), base64.b64decode(salt), int(iterations))
    assert base64.b64decode(digest) == expected
    assert credentials.to_parameters() == {
        'dashboardPassword': credentials.dashboard_password,
        'dashboardPasswordHash': credentials.dashboard_password_hash,
        'apiKey': credentials.api_key,
    }
    assert credentials.dashboard_password not in repr(credentials)
    assert credentials.api_key not in repr(credentials)
    another = mockapi.generate_credentials()
    assert another.dashboard_password != credentials.dashboard_password
    assert another.api_key != credentials.api_key


@pytest.mark.parametrize('existing, saved', [([], []), (_APP_NAMES, [{'value': []}, {'value': []}])])
def test_prepare_generates_only_for_new_or_legacy_containers(monkeypatch, credentials, existing, saved):
    runner = Mock(side_effect = [_output(existing), *(_output(item) for item in saved), _output([])])
    generate = Mock(return_value = credentials)
    monkeypatch.setattr(mockapi, 'generate_credentials', generate)

    assert mockapi.prepare_credentials('rg', 'fixture', 'subscription', runner = runner) is credentials
    generate.assert_called_once_with()


@pytest.mark.parametrize('existing', [_APP_NAMES[:1], _APP_NAMES, ['ca-fixture-mockapi-1', 'ca-fixture-mockapi-2'], [*_APP_NAMES, 'ca-fixture-mockapi-1', 'ca-fixture-mockapi-2']])
def test_prepare_reuses_credentials_and_suppresses_secret_logging(monkeypatch, credentials, existing):
    runner = Mock(side_effect = [_output(existing), *(_output(_secrets(credentials)) for _ in existing)])
    generate = Mock(side_effect = AssertionError('Must not regenerate saved credentials'))
    monkeypatch.setattr(mockapi, 'generate_credentials', generate)

    assert mockapi.prepare_credentials('rg', 'fixture', 'subscription', runner = runner) == credentials
    for request in runner.call_args_list[1:]:
        assert request.kwargs == {'sensitive_output': True, 'log_command': False}
        assert credentials.api_key not in request.args[0]
        assert credentials.dashboard_password not in request.args[0]


@pytest.mark.parametrize(
    'responses, message',
    [
        ([Output(False, 'denied')], 'discover'),
        ([_output({})], 'name list'),
        ([_output([1])], 'name list'),
        ([_output(_APP_NAMES[:1]), Output(False, 'denied')], 'read existing'),
        ([_output(_APP_NAMES[:1]), _output([])], 'secrets document'),
        ([_output(_APP_NAMES[:1]), _output({'value': [1]})], 'secret entry'),
        ([_output(_APP_NAMES[:1]), _output({'value': [{'name': 'mock-api-key', 'value': ''}]})], 'missing values'),
        ([_output(_APP_NAMES[:1]), _output({'value': [{'name': 'mock-api-key', 'value': 'fixture'}]})], 'incomplete'),
        ([_output([]), Output(False, 'denied')], 'persistence'),
        ([_output([]), _output({})], 'account name list'),
        ([_output([]), _output([1])], 'account name list'),
        ([_output([]), _output(['stmockfixture'])], 'without recoverable credentials'),
    ],
)
def test_prepare_fails_closed_on_discovery_and_saved_secret_errors(monkeypatch, responses, message):
    generate = Mock(side_effect = AssertionError('Must not regenerate after an error'))
    monkeypatch.setattr(mockapi, 'generate_credentials', generate)
    with pytest.raises((RuntimeError, ValueError), match = message):
        mockapi.prepare_credentials('rg', 'fixture', 'subscription', runner = Mock(side_effect = responses))


def test_prepare_rejects_mismatched_backend_secrets(credentials):
    different = mockapi.MockApiCredentials(credentials.dashboard_password, credentials.dashboard_password_hash, 'b' * 43)
    runner = Mock(side_effect = [_output(_APP_NAMES), _output(_secrets(credentials)), _output(_secrets(different))])
    with pytest.raises(ValueError, match = 'different saved'):
        mockapi.prepare_credentials('rg', 'fixture', 'subscription', runner = runner)


def test_prepare_ignores_unrelated_container_secrets(credentials):
    payload = _secrets(credentials)
    payload['value'].append({'name': 'unrelated-secret'})
    runner = Mock(side_effect = [_output(_APP_NAMES[:1]), _output(payload)])

    assert mockapi.prepare_credentials('rg', 'fixture', 'subscription', runner = runner) == credentials


@pytest.mark.parametrize(
    'password, password_hash, key, message',
    [
        ('short', 'invalid', 'a' * 43, 'credentials are invalid'),
        ('a' * 16, 'invalid', 'short', 'credentials are invalid'),
        ('a' * 16, 'invalid', 'a' * 43, 'hash is malformed'),
        ('a' * 16, 'v1.600000.!.!', 'a' * 43, 'hash is malformed'),
        ('a' * 16, 'v1.1.YQ==.Yg==', 'a' * 43, 'hash is invalid'),
    ],
)
def test_prepare_rejects_invalid_credentials_without_exposing_them(password, password_hash, key, message):
    saved = mockapi.MockApiCredentials(password, password_hash, key)
    runner = Mock(side_effect = [_output(_APP_NAMES[:1]), _output(_secrets(saved))])
    with pytest.raises(ValueError, match = message) as error:
        mockapi.prepare_credentials('rg', 'fixture', 'subscription', runner = runner)
    assert password not in str(error.value)
    assert key not in str(error.value)


def test_prepare_rejects_inconsistent_password_hash(credentials):
    saved = mockapi.MockApiCredentials('z' * 16, credentials.dashboard_password_hash, credentials.api_key)
    runner = Mock(side_effect = [_output(_APP_NAMES[:1]), _output(_secrets(saved))])
    with pytest.raises(ValueError, match = 'do not match'):
        mockapi.prepare_credentials('rg', 'fixture', 'subscription', runner = runner)


@pytest.mark.parametrize('exists', [True, False])
def test_seed_preserves_existing_fixtures_and_recovers_partial_runs(exists):
    uploaded = []
    paths = []
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if command.startswith('az storage account show'):
            return Output(True, 'Enabled')
        if command.startswith('az storage blob exists'):
            assert '--auth-mode login' in command
            blob_name = command.split('--name ', 1)[1].split()[0]
            assert kwargs['error_message'] == f'Cannot inspect MockAPI configuration blob {blob_name}.'
            return Output(True, str(exists).lower())
        if command.startswith('az storage blob upload'):
            path = Path(re.search(r'--file "([^"]+)"', command).group(1))
            paths.append(path)
            uploaded.append(json.loads(path.read_text(encoding = 'utf-8')))
            assert '--overwrite false' in command
        if command.startswith('az containerapp show'):
            return Output(True, 'ca-fixture--revision')
        if command.startswith('az containerapp revision show'):
            return Output(True, 'Healthy')
        return Output(True, '')

    mockapi.seed_configuration('rg', 'stfixture', _APP_NAMES, runner = run)

    assert len(uploaded) == (0 if exists else 2)
    assert all(not path.exists() for path in paths)
    assert len([command for command in commands if command.startswith('az containerapp revision restart')]) == 2
    for index, fixture in enumerate(uploaded, 1):
        assert fixture['schemaVersion'] == '1.0'
        endpoint, = fixture['endpoints']
        assert endpoint['methods'] == ['GET']
        assert endpoint['path'] == '/hello'
        assert endpoint['response']['statusCode'] == 200
        assert endpoint['response']['headers']['X-Mock-Backend'] == [str(index)]
        assert json.loads(endpoint['response']['body']) == {'message': 'Hello from MockAPI'}


@pytest.mark.parametrize('storage, names', [('invalid account', _APP_NAMES), ('stfixture', []), ('stfixture', ['a', 'a']), ('stfixture', ['a', {}])])
def test_seed_validates_deployment_outputs(storage, names):
    runner = Mock()
    with pytest.raises(ValueError):
        mockapi.seed_configuration('rg', storage, names, runner = runner)
    runner.assert_not_called()


@pytest.mark.parametrize(
    'responses, message',
    [
        ([Output(False, '')], 'inspect'),
        ([Output(True, 'invalid')], 'existence'),
        ([Output(True, 'false'), Output(False, '')], 'seed'),
        ([Output(True, 'true'), Output(False, '')], 'identify'),
        ([Output(True, 'true'), Output(True, 'invalid revision')], 'identify'),
        ([Output(True, 'true'), Output(True, 'ca--revision'), Output(False, '')], 'restart'),
        ([Output(True, 'true'), Output(True, 'ca--revision'), Output(True, ''), Output(False, '')], 'verify'),
        ([Output(True, 'true'), Output(True, 'ca--revision'), Output(True, ''), Output(True, 'invalid')], 'unknown health'),
    ],
)
def test_seed_surfaces_remote_failures(responses, message):
    with pytest.raises((RuntimeError, ValueError), match = message):
        mockapi.seed_configuration('rg', 'stfixture', _APP_NAMES, runner = Mock(side_effect = [Output(True, 'Enabled'), *responses]))


@pytest.mark.parametrize(
    'result, message',
    [
        (Output(False, 'denied'), 'Cannot inspect MockAPI storage network access'),
        (Output(True, 'Disabled'), 'publicNetworkAccess=Disabled'),
        (Output(True, 'unexpected'), 'unknown public network access'),
    ],
)
def test_seed_fails_before_blob_retries_when_storage_network_is_unavailable(result, message):
    runner = Mock(return_value = result)
    with pytest.raises((RuntimeError, ValueError), match = message):
        mockapi.seed_configuration('rg', 'stfixture', _APP_NAMES, runner = runner)
    runner.assert_called_once_with(
        'az storage account show --resource-group rg --name stfixture --query publicNetworkAccess -o tsv',
        error_message = 'Cannot inspect MockAPI storage network access.',
    )


def test_seed_readiness_retries_are_bounded_and_injected():
    runner = Mock(side_effect = [Output(True, 'Enabled'), Output(True, 'true'), Output(True, 'ca--revision'), Output(True, ''), *([Output(True, 'Unhealthy')] * 60)])
    sleep = Mock()
    with pytest.raises(RuntimeError, match = 'did not become healthy'):
        mockapi.seed_configuration('rg', 'stfixture', _APP_NAMES, runner = runner, sleep = sleep)
    assert sleep.call_count == 59


def test_demo_policies_preserve_public_paths_and_rewrite_exact_backend_path():
    apis = infrastructure_cli.build_aca_hello_world_apis()
    assert [api.path for api in apis] == ['/aca-1', '/aca-2', '/aca-pool']
    for api, backend in zip(apis, ('aca-backend-1', 'aca-backend-2', 'aca-backend-pool')):
        policy = ET.fromstring(api.policyXml)
        assert policy.find('inbound/set-backend-service').attrib == {'backend-id': backend}
        assert policy.find('inbound/rewrite-uri').attrib == {'template': '/hello', 'copy-unmatched-params': 'false'}
        assert policy.find('inbound/set-header').attrib == {'name': 'X-MockAPI-Key', 'exists-action': 'delete'}
        assert [element.tag for element in policy.find('inbound')] == ['base', 'set-header', 'set-backend-service', 'rewrite-uri']


def test_infrastructure_credential_preparation_uses_existing_azure_boundary(mock_az, credentials, monkeypatch):
    infra = infrastructures.Infrastructure(INFRASTRUCTURE.APIM_ACA, 1, 'eastus2', APIM_SKU.BASICV2)
    prepare = Mock(return_value = credentials)
    monkeypatch.setattr(mockapi, 'prepare_credentials', prepare)
    infra._prepare_deployment()
    assert _PREPARE_CREDENTIALS(infra) is credentials
    prepare.assert_called_once_with(infra.rg_name, infra.resource_suffix, infra.subscription_id, runner = mock_az.run)


def test_infrastructure_parameters_reuse_prepared_credentials(mock_az, credentials):
    infra = infrastructures.Infrastructure(INFRASTRUCTURE.APIM_ACA, 1, 'eastus2', APIM_SKU.BASICV2)
    infra._mockapi_credentials = credentials
    infra.apis = []
    infra.pfs = []
    infra._prepare_mockapi_credentials.reset_mock()

    infra._prepare_deployment()
    parameters = infra._define_bicep_parameters()

    assert parameters['mockApiCredentials'] == {'value': credentials.to_parameters()}
    assert parameters['currentUserId'] == {'value': infra.current_user_id}
    infra._prepare_mockapi_credentials.assert_not_called()


def test_infrastructure_without_mockapi_credentials_skips_initialization(mock_az, monkeypatch):
    infra = infrastructures.Infrastructure(INFRASTRUCTURE.SIMPLE_APIM, 1, 'eastus2', APIM_SKU.BASICV2)
    seed = Mock()
    seed_dashboard = Mock()
    monkeypatch.setattr(mockapi, 'seed_configuration', seed)
    monkeypatch.setattr(mockapi, 'seed_dashboard_configuration', seed_dashboard)
    output = Mock()

    _INITIALIZE_MOCKAPI(infra, output)

    output.get.assert_not_called()
    output.getJson.assert_not_called()
    seed.assert_not_called()
    seed_dashboard.assert_not_called()


@pytest.mark.parametrize('dashboard_urls', [None, 'https://mockapi.example.com/', [None]])
def test_private_infrastructure_rejects_malformed_dashboard_urls(mock_az, credentials, monkeypatch, dashboard_urls):
    infra = infrastructures.Infrastructure(INFRASTRUCTURE.APIM_ACA, 1, 'eastus2', APIM_SKU.BASICV2)
    infra._mockapi_credentials = credentials
    seed_dashboard = Mock()
    monkeypatch.setattr(mockapi, 'seed_dashboard_configuration', seed_dashboard)
    output = _output({
        'mockApiStorageAccountName': {'value': 'stfixture'},
        'mockApiContainerAppNames': {'value': _APP_NAMES},
        'mockApiDashboardUrls': {'value': dashboard_urls},
    })

    with pytest.raises(ValueError, match = 'dashboard URLs are missing or malformed'):
        _INITIALIZE_MOCKAPI(infra, output)

    seed_dashboard.assert_not_called()


@pytest.mark.parametrize('infrastructure', [INFRASTRUCTURE.APIM_ACA, INFRASTRUCTURE.AFD_APIM_PE])
def test_infrastructure_initialization_wires_outputs_without_logging_secrets(mock_az, credentials, monkeypatch, infrastructure):
    infra = infrastructures.Infrastructure(infrastructure, 1, 'eastus2', APIM_SKU.BASICV2)
    infra._mockapi_credentials = credentials
    seed = Mock()
    seed_dashboard = Mock()
    monkeypatch.setattr(mockapi, 'seed_configuration', seed)
    monkeypatch.setattr(mockapi, 'seed_dashboard_configuration', seed_dashboard)
    dashboard_urls = ['https://mockapi-1.example.com/', 'https://mockapi-2.example.com/']
    output = _output({
        'mockApiStorageAccountName': {'value': 'stfixture'},
        'mockApiContainerAppNames': {'value': _APP_NAMES},
        'mockApiDashboardUrls': {'value': dashboard_urls},
    })
    _INITIALIZE_MOCKAPI(infra, output)
    if infrastructure == INFRASTRUCTURE.APIM_ACA:
        seed_dashboard.assert_called_once_with(infra.rg_name, _APP_NAMES, dashboard_urls, credentials.dashboard_password, runner = mock_az.run)
        seed.assert_not_called()
    else:
        seed.assert_called_once_with(infra.rg_name, 'stfixture', _APP_NAMES, runner = mock_az.run)
        seed_dashboard.assert_not_called()
    with pytest.raises(ValueError):
        _INITIALIZE_MOCKAPI(infra, _output({}))


def test_private_storage_seeding_uses_runtime_management_api_without_blob_access_or_restart(credentials):
    runner = Mock(side_effect = [Output(True, 'ca--revision'), Output(True, 'Healthy')] * 2)
    clients = [MagicMock(), MagicMock()]
    for client in clients:
        client.__enter__.return_value = client
    factory = Mock(side_effect = clients)
    urls = ['https://mockapi-1.example.com/', 'https://mockapi-2.example.com/']

    mockapi.seed_dashboard_configuration('rg', _APP_NAMES, urls, credentials.dashboard_password, runner = runner, client_factory = factory)

    assert [entry.args for entry in factory.call_args_list] == [(url, credentials.dashboard_password) for url in urls]
    for index, client in enumerate(clients, 1):
        endpoint = client.ensure_endpoint.call_args.args[0]
        assert endpoint['path'] == '/hello'
        assert endpoint['methods'] == ['GET']
        assert endpoint['response']['headers']['X-Mock-Backend'] == [str(index)]
        assert client.ensure_endpoint.call_args.kwargs == {'preserve_existing': True}
        client.__exit__.assert_called_once()
    assert all(entry.args[0].startswith('az containerapp ') and 'restart' not in entry.args[0] for entry in runner.call_args_list)


@pytest.mark.parametrize('names, urls', [([], []), (['a', 'a'], ['a', 'b']), (['a', {}], ['a', 'b']), (_APP_NAMES, [])])
def test_private_storage_seeding_rejects_malformed_outputs_before_remote_calls(names, urls):
    runner = Mock()
    with pytest.raises(ValueError):
        mockapi.seed_dashboard_configuration('rg', names, urls, 'password', runner = runner)
    runner.assert_not_called()


@pytest.mark.parametrize('success', [False, True])
def test_sensitive_cli_output_never_reaches_debug_logs(monkeypatch, success):
    secret = 'fixture-sensitive-response'
    execute = Mock(return_value = Mock(returncode = 0 if success else 1, stdout = secret, stderr = secret))
    monkeypatch.setattr(az.subprocess, 'run', execute)
    monkeypatch.setattr(az, 'is_debug_enabled', lambda: True)
    log = Mock()
    for name in ('print_plain', 'print_error', 'print_ok', 'print_command'):
        monkeypatch.setattr(az, name, log)
    result = az.run('az rest --method post --url /fixture', sensitive_output = True, retries = 0)
    assert secret in result.text
    assert secret not in str(log.call_args_list)
    assert '--debug' not in execute.call_args.args[0]
