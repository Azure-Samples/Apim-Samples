"""Shared deployment contracts using real temporary files and mocked Azure."""

import json
import os
from pathlib import Path
from unittest.mock import Mock, call
from urllib.parse import parse_qs, urlsplit

import pytest

# APIM Samples imports
import infrastructures
import bicep_deployment
from apimtypes import APIM_SKU, INFRASTRUCTURE, Output, Region

PREPARATION_STEPS = ['prepare_fragments', 'prepare_apis', 'prepare_parameters']


@pytest.mark.parametrize(
    'infra_class',
    [
        infrastructures.SimpleApimInfrastructure,
        infrastructures.ApimAcaInfrastructure,
        infrastructures.AfdApimAcaInfrastructure,
        infrastructures.AppGwApimPeInfrastructure,
        infrastructures.AppGwApimInfrastructure,
    ],
)
@pytest.mark.parametrize('rg_exists', [None, False, True])
def test_infrastructure_construction_defers_azure_preparation(mock_az, infra_class, rg_exists):
    """All architectures capture configuration without creating or querying Azure resources."""
    infra = infra_class(Region.EAST_US_2, 1, rg_exists = rg_exists)

    mock_az.create_resource_group.assert_not_called()
    mock_az.get_unique_suffix_for_resource_group.assert_not_called()
    mock_az.get_account_info.assert_not_called()
    mock_az.run.assert_not_called()

    infra._prepare_deployment()
    infra._prepare_deployment()

    mock_az.create_resource_group.assert_called_once_with(infra.rg_name, infra.rg_location, infra.rg_tags, rg_exists = rg_exists)
    mock_az.get_unique_suffix_for_resource_group.assert_called_once_with(infra.rg_name)
    mock_az.get_account_info.assert_called_once_with()


def test_infrastructure_preparation_can_retry_after_partial_failure(mock_az):
    infra = infrastructures.SimpleApimInfrastructure(Region.EAST_US_2, 1)
    mock_az.get_unique_suffix_for_resource_group.side_effect = [RuntimeError('Suffix failed'), 'retry-suffix']

    with pytest.raises(RuntimeError, match = 'Suffix failed'):
        infra._prepare_deployment()

    mock_az.get_account_info.assert_not_called()
    assert not infra._deployment_prepared
    infra._prepare_deployment()
    assert infra._deployment_prepared
    assert infra.resource_suffix == 'retry-suffix'


@pytest.mark.parametrize('infra_class', [infrastructures.AppGwApimPeInfrastructure, infrastructures.AppGwApimInfrastructure])
def test_gateway_preparation_precedes_certificate_and_main_deployment(mock_az, mock_utils, monkeypatch, infra_class):
    mock_utils.Output.side_effect = Output
    infra = infra_class(Region.EAST_US_2, 1)
    steps = Mock()
    steps.attach_mock(mock_az.create_resource_group, 'create_rg')
    steps.attach_mock(mock_az.get_unique_suffix_for_resource_group, 'suffix')
    steps.attach_mock(mock_az.get_account_info, 'account')
    certificate = Mock(return_value = False)
    steps.attach_mock(certificate, 'certificate')
    monkeypatch.setattr(infra, '_prepare_keyvault_certificate', certificate)

    assert not infra.deploy_infrastructure().success

    assert [entry[0] for entry in steps.mock_calls] == ['create_rg', 'suffix', 'account', 'certificate']
    certificate.assert_called_once_with('kv-abc123def456')
    mock_az.run.assert_not_called()


def _step_names(steps: Mock) -> list[str]:
    return [entry[0] for entry in steps.mock_calls]


def _parameter_file(infra, deployment_dir: Path) -> Path:
    if infra._mockapi_credentials is None:
        return deployment_dir / 'params.json'

    return next((deployment_dir.parents[2] / 'parameters').glob('*/params.json'))


@pytest.fixture(params=[INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA], ids=lambda value: value.value)
def shared_deployment(request, monkeypatch, tmp_path, mock_az, mock_utils):
    """Keep path resolution, parameter serialization, and resource cleanup real."""
    project = tmp_path / 'project with spaces'
    deployment_dir = project / 'infrastructure' / request.param.value
    deployment_dir.mkdir(parents=True)
    (deployment_dir / 'main.bicep').write_text('// Offline deployment fixture\n', encoding='utf-8')
    original_cwd = tmp_path / 'caller with spaces'
    original_cwd.mkdir()
    parameter_directory = tmp_path / 'parameters'
    parameter_directory.mkdir()
    temporary_directory = bicep_deployment.tempfile.TemporaryDirectory
    monkeypatch.setattr(bicep_deployment.tempfile, 'TemporaryDirectory', lambda **kwargs: temporary_directory(dir = parameter_directory, **kwargs))
    monkeypatch.chdir(original_cwd)
    monkeypatch.setattr(infrastructures, '__file__', str(project / 'shared' / 'python' / 'infrastructures.py'))
    for name in ('print_plain', 'print_val', 'print_ok', 'print_error', 'print_warning'):
        monkeypatch.setattr(infrastructures, name, Mock())
    mock_utils.Output.side_effect = Output
    mock_utils.get_deployment_failure_message.return_value = 'Deployment failed'
    mock_az.migrate_legacy_apim_diagnostic_settings.return_value = []
    mock_az.run.return_value = Output(
        True,
        json.dumps(
            {
                'apimResourceGatewayURL': {'value': 'https://apim.example.com'},
                'apiOutputs': {'value': [{'name': 'hello-world'}]},
            }
        ),
    )
    infra = infrastructures.Infrastructure(request.param, 1, Region.EAST_US_2, APIM_SKU.BASICV2)
    infra._prepare_deployment()
    steps = Mock()
    for method, label in (
        ('_define_policy_fragments', 'prepare_fragments'),
        ('_define_apis', 'prepare_apis'),
        ('_define_bicep_parameters', 'prepare_parameters'),
    ):
        spy = Mock(wraps=getattr(infra, method))
        monkeypatch.setattr(infra, method, spy)
        steps.attach_mock(spy, label)
    verification = Mock(return_value=True)
    monkeypatch.setattr(infra, '_verify_infrastructure', verification)
    steps.attach_mock(mock_az.migrate_legacy_apim_diagnostic_settings, 'migrate')
    steps.attach_mock(mock_az.run, 'deploy')
    steps.attach_mock(verification, 'verify')

    return infra, original_cwd, deployment_dir, steps


@pytest.mark.parametrize('is_update', [False, True])
def test_shared_deployment_preserves_order_parameters_and_command(shared_deployment, mock_utils, is_update):
    """Freeze the complete command and serialized parameter contract for create/update."""
    infra, original_cwd, deployment_dir, steps = shared_deployment
    output = steps.deploy.return_value
    params_path = None
    documents = []

    def deploy(*args, **kwargs):
        nonlocal params_path
        assert Path.cwd() == original_cwd
        params_path = _parameter_file(infra, deployment_dir)
        documents.append(json.loads(params_path.read_text(encoding='utf-8')))

        return output

    steps.deploy.side_effect = deploy

    result = infra.deploy_infrastructure(is_update=is_update)

    assert result is output
    assert _step_names(steps) == PREPARATION_STEPS + ['migrate', 'deploy', 'verify']
    assert documents == [
        {
            '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#',
            'contentVersion': '1.0.0.0',
            'parameters': infra.bicep_parameters,
        }
    ]
    expected_keys = {'resourceSuffix', 'apimSku', 'apis', 'policyFragments'}
    if infra.infra == INFRASTRUCTURE.APIM_ACA:
        expected_keys.update(('mockApiCredentials', 'currentUserId'))
        assert not params_path.exists()
        assert not (deployment_dir / 'params.json').exists()
    assert set(infra.bicep_parameters) == expected_keys
    assert infra.bicep_parameters['resourceSuffix'] == {'value': 'abc123def456'}
    assert infra.bicep_parameters['apimSku'] == {'value': 'Basicv2'}
    assert [api['name'] for api in infra.bicep_parameters['apis']['value']] == ['hello-world']
    assert [fragment['name'] for fragment in infra.bicep_parameters['policyFragments']['value']] == [
        'Api-Id',
        'AuthZ-Match-All',
        'AuthZ-Match-Any',
        'Http-Response-200',
        'Product-Match-Any',
        'Remove-Request-Headers',
    ]
    command = [
        'az', 'deployment', 'group', 'create', '--name', infra.infra.value,
        '--resource-group', infra.rg_name, '--template-file', str(deployment_dir / 'main.bicep'),
        '--parameters', str(params_path), '--query', 'properties.outputs',
    ]
    steps.deploy.assert_called_once_with(
        command, f"Deployment '{infra.infra.value}' succeeded", 'Deployment failed', sensitive_output = infra._mockapi_credentials is not None, timeout=1800, retries = 0
    )
    mock_utils.get_deployment_failure_message.assert_called_once_with(infra.infra.value)
    steps.verify.assert_called_once_with(infra.rg_name)
    infrastructures.print_val.assert_any_call('Gateway URL', 'https://apim.example.com')
    infrastructures.print_val.assert_any_call('APIs Created', 1)
    first_message = infrastructures.print_plain.call_args_list[0].args[0]
    assert first_message.split(' ', 1)[1] == f'{"Updating" if is_update else "Creating"} infrastructure...\n'
    assert Path.cwd() == original_cwd
    assert not (original_cwd / 'params.json').exists()


@pytest.mark.parametrize('preflight_removed', [[], ['legacy-setting']], ids=['clean-preflight', 'preflight-cleanup'])
def test_shared_deployment_does_not_retry_without_removed_diagnostics(shared_deployment, preflight_removed):
    """Only recovery cleanup, not preflight cleanup, can authorize a retry."""
    infra, original_cwd, _, steps = shared_deployment
    failure = Output(False, 'Deployment rejected')
    steps.deploy.return_value = failure
    steps.migrate.side_effect = [preflight_removed, []]

    result = infra.deploy_infrastructure()

    assert result is failure
    assert _step_names(steps) == PREPARATION_STEPS + ['migrate', 'deploy', 'migrate']
    steps.migrate.assert_has_calls([call(infra.rg_name), call(infra.rg_name)])
    infrastructures.print_error.assert_called_once_with('Infrastructure creation failed!')
    infrastructures.print_warning.assert_not_called()
    assert Path.cwd() == original_cwd


@pytest.mark.parametrize('retry_success', [False, True])
def test_shared_deployment_retries_once_with_identical_command(shared_deployment, retry_success):
    """Recover diagnostics once, returning the final result even if retry also fails."""
    infra, original_cwd, deployment_dir, steps = shared_deployment
    failure = Output(False, 'First deployment failed')
    final = Output(retry_success, steps.deploy.return_value.text)
    outputs = iter([failure, final])
    parameters = []

    def deploy(*args, **kwargs):
        assert Path.cwd() == original_cwd
        parameters.append(json.loads(_parameter_file(infra, deployment_dir).read_text(encoding='utf-8')))

        return next(outputs)

    steps.deploy.side_effect = deploy
    steps.migrate.side_effect = [[], ['legacy-setting'], AssertionError('Recovery must not run a third time')]

    result = infra.deploy_infrastructure()

    assert result is final
    assert _step_names(steps) == PREPARATION_STEPS + ['migrate', 'deploy', 'migrate', 'deploy'] + (['verify'] if retry_success else [])
    assert steps.deploy.call_args_list[0] == steps.deploy.call_args_list[1]
    assert len(parameters) == 2
    assert parameters[0] == parameters[1]
    assert parameters[0]['parameters'] == infra.bicep_parameters
    assert steps.migrate.call_args_list == [call(infra.rg_name), call(infra.rg_name)]
    infrastructures.print_warning.assert_called_once_with('Legacy APIM diagnostic settings reappeared during deployment and were removed. Retrying infrastructure deployment once.')
    assert Path.cwd() == original_cwd


@pytest.mark.parametrize(
    'failure_stage, expected_steps',
    [
        ('prepare_fragments', ['prepare_fragments']),
        ('prepare_apis', ['prepare_fragments', 'prepare_apis']),
        ('prepare_parameters', PREPARATION_STEPS),
        ('preflight', PREPARATION_STEPS + ['migrate']),
        ('initial_deploy', PREPARATION_STEPS + ['migrate', 'deploy']),
        ('recovery', PREPARATION_STEPS + ['migrate', 'deploy', 'migrate']),
        ('retry_deploy', PREPARATION_STEPS + ['migrate', 'deploy', 'migrate', 'deploy']),
        ('verify', PREPARATION_STEPS + ['migrate', 'deploy', 'verify']),
    ],
)
def test_shared_deployment_propagates_exceptions_and_restores_cwd(shared_deployment, failure_stage, expected_steps):
    """Stop at the failing stage without hiding the original exception or continuing."""
    infra, original_cwd, deployment_dir, steps = shared_deployment
    error = RuntimeError(f'{failure_stage} failed')
    failure = Output(False, 'Deployment failed')
    if failure_stage in PREPARATION_STEPS:
        getattr(steps, failure_stage).side_effect = error
    elif failure_stage == 'preflight':
        steps.migrate.side_effect = error
    elif failure_stage == 'initial_deploy':
        steps.deploy.side_effect = error
    elif failure_stage == 'recovery':
        steps.deploy.return_value = failure
        steps.migrate.side_effect = [[], error]
    elif failure_stage == 'retry_deploy':
        steps.deploy.side_effect = [failure, error]
        steps.migrate.side_effect = [[], ['legacy-setting']]
    else:
        steps.verify.side_effect = error

    with pytest.raises(RuntimeError) as raised:
        infra.deploy_infrastructure()

    assert raised.value is error
    assert _step_names(steps) == expected_steps
    assert Path.cwd() == original_cwd
    if failure_stage in PREPARATION_STEPS:
        assert not (deployment_dir / 'params.json').exists()


def test_shared_deployment_never_changes_cwd(shared_deployment, monkeypatch):
    infra, original_cwd, deployment_dir, steps = shared_deployment
    change_directory = Mock(side_effect = AssertionError('Deployment must not change cwd'))
    monkeypatch.setattr(os, 'chdir', change_directory)

    assert infra.deploy_infrastructure().success
    change_directory.assert_not_called()
    assert _step_names(steps) == PREPARATION_STEPS + ['migrate', 'deploy', 'verify']
    assert Path.cwd() == original_cwd


def test_shared_deployment_restores_cwd_when_parameter_file_cannot_open(shared_deployment, monkeypatch):
    infra, original_cwd, deployment_dir, steps = shared_deployment
    error = OSError('Cannot write parameters')
    open_file = Mock(side_effect=error)
    monkeypatch.setattr(bicep_deployment, 'open', open_file, raising=False)

    with pytest.raises(OSError) as raised:
        infra.deploy_infrastructure()

    assert raised.value is error
    open_file.assert_called_once()
    path = open_file.call_args.args[0]
    path = Path(path)
    assert path.name == 'params.json'
    assert open_file.call_args.args[1:] == ('w',)
    assert open_file.call_args.kwargs == {'encoding': 'utf-8', 'newline': '\n'}
    if infra._mockapi_credentials is not None:
        assert not path.parent.exists()
    else:
        assert path == deployment_dir / 'params.json'
    assert _step_names(steps) == PREPARATION_STEPS + ['migrate']
    assert Path.cwd() == original_cwd


@pytest.mark.parametrize(
    'failure_stage, exception_type, message',
    [('serialization', TypeError, 'not JSON serializable'), ('write', OSError, 'Disk full')],
)
def test_shared_deployment_closes_parameter_file_on_failure(shared_deployment, monkeypatch, failure_stage, exception_type, message):
    infra, original_cwd, deployment_dir, steps = shared_deployment
    opened = []

    def open_file(path, mode, *, encoding, newline):
        handle = open(path, mode, encoding=encoding, newline=newline)
        opened.append(handle)
        if failure_stage == 'write':
            monkeypatch.setattr(handle, 'write', Mock(side_effect=OSError('Disk full')))

        return handle

    def invalid_parameters():
        infra.bicep_parameters = {'invalid': object()}

    if failure_stage == 'serialization':
        steps.prepare_parameters.side_effect = invalid_parameters
    monkeypatch.setattr(bicep_deployment, 'open', open_file, raising=False)

    with pytest.raises(exception_type, match=message):
        infra.deploy_infrastructure()

    assert len(opened) == 1
    assert opened[0].closed
    assert Path(opened[0].name).exists() is (infra._mockapi_credentials is None)
    assert _step_names(steps) == PREPARATION_STEPS + ['migrate']
    assert Path.cwd() == original_cwd


@pytest.mark.parametrize('text', ['', '{}', 'null'])
def test_shared_deployment_characterizes_empty_success_outputs(shared_deployment, text):
    """Current behavior returns success without verification when outputs are absent."""
    infra, original_cwd, _, steps = shared_deployment
    output = Output(True, text)
    steps.deploy.return_value = output

    result = infra.deploy_infrastructure()

    assert result is output
    assert result.success is True
    assert _step_names(steps) == PREPARATION_STEPS + ['migrate', 'deploy']
    assert Path.cwd() == original_cwd


@pytest.mark.parametrize('exception_type', [OSError, RuntimeError, ValueError])
def test_shared_deployment_reports_mockapi_initialization_failure(shared_deployment, monkeypatch, exception_type):
    infra, original_cwd, deployment_dir, steps = shared_deployment
    initialize = Mock(side_effect = exception_type('MockAPI startup rejected'))
    monkeypatch.setattr(infra, '_initialize_mockapi', initialize)

    result = infra.deploy_infrastructure()

    assert result.success is False
    assert result.text == 'MockAPI initialization failed'
    initialize.assert_called_once_with(steps.deploy.return_value)
    infrastructures.print_error.assert_called_once_with('MockAPI initialization failed: MockAPI startup rejected')
    infrastructures.print_ok.assert_not_called()
    steps.verify.assert_not_called()
    assert Path.cwd() == original_cwd
    if infra._mockapi_credentials is not None:
        assert not (deployment_dir / 'params.json').exists()
        assert not list((deployment_dir.parents[2] / 'parameters').iterdir())


@pytest.mark.parametrize(
    'outputs, missing_key',
    [
        ({'apiOutputs': {'value': []}}, 'apimResourceGatewayURL'),
        ({'apimResourceGatewayURL': {'value': 'https://apim.example.com'}}, 'apiOutputs'),
        ({'apimResourceGatewayURL': {}, 'apiOutputs': {'value': []}}, 'apimResourceGatewayURL'),
    ],
)
def test_shared_deployment_rejects_partial_outputs_before_verification(shared_deployment, outputs, missing_key):
    """Missing output values raise rather than reaching verification or being retried."""
    infra, original_cwd, _, steps = shared_deployment
    steps.deploy.return_value = Output(True, json.dumps(outputs))

    with pytest.raises(ValueError, match=missing_key):
        infra.deploy_infrastructure()

    assert _step_names(steps) == PREPARATION_STEPS + ['migrate', 'deploy']
    assert Path.cwd() == original_cwd


def test_shared_deployment_returns_failure_when_verification_fails(shared_deployment):
    infra, original_cwd, _, steps = shared_deployment
    output = steps.deploy.return_value
    steps.verify.return_value = False

    result = infra.deploy_infrastructure()

    assert result is not output
    assert result.success is False
    assert result.text == 'Infrastructure verification failed'
    assert _step_names(steps) == PREPARATION_STEPS + ['migrate', 'deploy', 'verify']
    steps.verify.assert_called_once_with(infra.rg_name)
    assert Path.cwd() == original_cwd


@pytest.mark.parametrize('dashboard_urls', [None, [], ['https://mockapi-1.example.com/', 'https://mockapi-2.example.com/']])
def test_shared_deployment_prints_available_mockapi_dashboards(shared_deployment, dashboard_urls):
    """Skip the tutorial in dashboard links without changing management API origins."""
    infra, _, _, steps = shared_deployment
    outputs = json.loads(steps.deploy.return_value.text)
    if dashboard_urls is not None:
        outputs['mockApiDashboardUrls'] = {'value': dashboard_urls}
    steps.deploy.return_value = Output(True, json.dumps(outputs))

    assert infra.deploy_infrastructure().success

    dashboard_calls = [entry for entry in infrastructures.print_val.call_args_list if entry.args[0].startswith('MockAPI Dashboard')]
    assert dashboard_calls == [call(f'MockAPI Dashboard {index}', f'{url}?tutorial=skip') for index, url in enumerate(dashboard_urls or [], 1)]
    for entry, origin in zip(dashboard_calls, dashboard_urls or [], strict = True):
        parsed = urlsplit(entry.args[1])
        assert parsed._replace(query = '') == urlsplit(origin)
        assert parse_qs(parsed.query) == {'tutorial': ['skip']}
    assert steps.deploy.return_value.json_data == outputs
    credential_calls = [entry for entry in infrastructures.print_val.call_args_list if entry.args[0] in ('MockAPI Username', 'MockAPI Password')]
    if dashboard_urls and infra._mockapi_credentials is not None:
        assert credential_calls == [
            call('MockAPI Username', 'admin'),
            call('MockAPI Password', infra._mockapi_credentials.dashboard_password),
        ]
        infrastructures.print_warning.assert_called_once_with(
            'Dashboard credentials below are sensitive. Clear notebook output before saving or sharing.'
        )
        printed_values = [entry.args[1] for entry in infrastructures.print_val.call_args_list]
        assert infra._mockapi_credentials.api_key not in printed_values
        assert infra._mockapi_credentials.dashboard_password_hash not in printed_values
    else:
        assert credential_calls == []
        infrastructures.print_warning.assert_not_called()


@pytest.mark.parametrize('dashboard_urls', ['https://mockapi.example.com/', [None]])
def test_shared_deployment_rejects_malformed_dashboard_outputs(shared_deployment, dashboard_urls):
    infra, original_cwd, _, steps = shared_deployment
    outputs = json.loads(steps.deploy.return_value.text)
    outputs['mockApiDashboardUrls'] = {'value': dashboard_urls}
    steps.deploy.return_value = Output(True, json.dumps(outputs))

    with pytest.raises(ValueError, match = 'MockAPI dashboard URL outputs are malformed'):
        infra.deploy_infrastructure()

    steps.verify.assert_not_called()
    assert Path.cwd() == original_cwd


@pytest.mark.parametrize('success', [True, False])
def test_lockdown_keeps_credentials_temporary_and_suppresses_cli_debug(shared_deployment, success):
    infra, original_cwd, deployment_dir, steps = shared_deployment
    infra._define_policy_fragments()
    infra._define_apis()
    infra._define_bicep_parameters()
    infra.bicep_parameters['apimPublicAccess'] = {'value': True}
    parameter_paths = []

    def deploy(command, *args, **kwargs):
        parameter_path = _parameter_file(infra, deployment_dir)
        parameter_paths.append(parameter_path)
        assert command[command.index('--parameters') + 1] == str(parameter_path)
        assert kwargs['sensitive_output'] is (infra._mockapi_credentials is not None)
        parameters = json.loads(parameter_path.read_text(encoding = 'utf-8'))['parameters']
        assert parameters['apimPublicAccess'] == {'value': False}
        if infra._mockapi_credentials is not None:
            assert parameters['mockApiCredentials'] == {'value': infra._mockapi_credentials.to_parameters()}
        return Output(success, '')

    steps.deploy.side_effect = deploy
    assert infra._disable_apim_public_access() is success
    assert len(parameter_paths) == 1
    assert parameter_paths[0].exists() is (infra._mockapi_credentials is None)
    assert Path.cwd() == original_cwd
