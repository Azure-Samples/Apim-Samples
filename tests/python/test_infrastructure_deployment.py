"""Shared deployment contracts using real temporary files and mocked Azure."""

import json
import os
from pathlib import Path
from unittest.mock import Mock, call

import pytest

# APIM Samples imports
import infrastructures
from apimtypes import APIM_SKU, INFRASTRUCTURE, Output, Region

PREPARATION_STEPS = ['prepare_fragments', 'prepare_apis', 'prepare_parameters']


def _step_names(steps: Mock) -> list[str]:
    return [entry[0] for entry in steps.mock_calls]


@pytest.fixture(params=[INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA], ids=lambda value: value.value)
def shared_deployment(request, monkeypatch, tmp_path, mock_az, mock_utils):
    """Keep path resolution, parameter serialization, and resource cleanup real."""
    project = tmp_path / 'project with spaces'
    deployment_dir = project / 'infrastructure' / request.param.value
    deployment_dir.mkdir(parents=True)
    (deployment_dir / 'main.bicep').write_text('// Offline deployment fixture\n', encoding='utf-8')
    original_cwd = tmp_path / 'caller with spaces'
    original_cwd.mkdir()
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
    params_path = deployment_dir / 'params.json'
    documents = []

    def migrate(rg_name):
        assert rg_name == infra.rg_name
        assert Path.cwd() == deployment_dir
        documents.append(json.loads(params_path.read_text(encoding='utf-8')))

        return []

    steps.migrate.side_effect = migrate

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
    assert set(infra.bicep_parameters) == {'resourceSuffix', 'apimSku', 'apis', 'policyFragments'}
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
    command = f'az deployment group create --name {infra.infra.value} --resource-group {infra.rg_name} --template-file "{deployment_dir / "main.bicep"}" --parameters "{params_path}" --query "properties.outputs"'
    steps.deploy.assert_called_once_with(command, f"Deployment '{infra.infra.value}' succeeded", 'Deployment failed', timeout=1800)
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
        assert Path.cwd() == deployment_dir
        parameters.append(json.loads((deployment_dir / 'params.json').read_text(encoding='utf-8')))

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


def test_shared_deployment_restores_cwd_when_entering_directory_fails(shared_deployment, monkeypatch):
    infra, original_cwd, deployment_dir, steps = shared_deployment
    real_chdir = os.chdir
    error = OSError('Cannot enter deployment directory')

    def chdir(path):
        if Path(path) == deployment_dir:
            raise error
        real_chdir(path)

    change_directory = Mock(side_effect=chdir)
    monkeypatch.setattr(infrastructures.os, 'chdir', change_directory)

    with pytest.raises(OSError) as raised:
        infra.deploy_infrastructure()

    assert raised.value is error
    assert change_directory.call_args_list == [call(deployment_dir), call(str(original_cwd))]
    assert _step_names(steps) == PREPARATION_STEPS
    assert Path.cwd() == original_cwd
    assert not (deployment_dir / 'params.json').exists()


def test_shared_deployment_restores_cwd_when_parameter_file_cannot_open(shared_deployment, monkeypatch):
    infra, original_cwd, deployment_dir, steps = shared_deployment
    error = OSError('Cannot write parameters')
    open_file = Mock(side_effect=error)
    monkeypatch.setattr(infrastructures, 'open', open_file, raising=False)

    with pytest.raises(OSError) as raised:
        infra.deploy_infrastructure()

    assert raised.value is error
    open_file.assert_called_once_with(deployment_dir / 'params.json', 'w', encoding='utf-8')
    assert _step_names(steps) == PREPARATION_STEPS
    assert Path.cwd() == original_cwd


@pytest.mark.parametrize(
    'failure_stage, exception_type, message',
    [('serialization', TypeError, 'not JSON serializable'), ('write', OSError, 'Disk full')],
)
def test_shared_deployment_closes_parameter_file_on_failure(shared_deployment, monkeypatch, failure_stage, exception_type, message):
    infra, original_cwd, deployment_dir, steps = shared_deployment
    opened = []

    def open_file(path, mode, *, encoding):
        handle = open(path, mode, encoding=encoding)
        opened.append(handle)
        if failure_stage == 'write':
            monkeypatch.setattr(handle, 'write', Mock(side_effect=OSError('Disk full')))

        return handle

    def invalid_parameters():
        infra.bicep_parameters = {'invalid': object()}

    if failure_stage == 'serialization':
        steps.prepare_parameters.side_effect = invalid_parameters
    monkeypatch.setattr(infrastructures, 'open', open_file, raising=False)

    with pytest.raises(exception_type, match=message):
        infra.deploy_infrastructure()

    assert len(opened) == 1
    assert opened[0].closed
    assert (deployment_dir / 'params.json').exists()
    assert _step_names(steps) == PREPARATION_STEPS
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
