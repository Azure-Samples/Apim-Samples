"""Tests for the extracted bicep_deployment capability."""

import json
import logging
import os
from pathlib import Path
from unittest.mock import Mock
import azure_resources as az
import pytest
from apimtypes import INFRASTRUCTURE, Output
from test_helpers import (
    patch_create_bicep_deployment_group_dependencies,
)
import bicep_deployment


@pytest.fixture
def deployment_dependencies(monkeypatch):
    """Share the default offline filesystem and Azure deployment boundary."""
    return patch_create_bicep_deployment_group_dependencies(monkeypatch, az_module=az)


def test_bicep_directory_determination_edge_cases(monkeypatch, tmp_path):
    """Fall back to the infrastructure directory when no template exists."""
    empty_dir = tmp_path / 'empty'
    empty_dir.mkdir()
    monkeypatch.setattr(os, 'getcwd', lambda: str(empty_dir))

    result = bicep_deployment._determine_bicep_directory('nonexistent')

    assert result == os.path.join(str(empty_dir), 'infrastructure', 'nonexistent')


def test_create_bicep_deployment_group_with_enum(deployment_dependencies):
    """Test create_bicep_deployment_group with INFRASTRUCTURE enum."""
    mock_create_rg, mock_run, _mock_open_func = deployment_dependencies

    bicep_params = {'param1': {'value': 'test'}}
    rg_tags = {'infrastructure': 'simple-apim'}

    bicep_deployment.create_bicep_deployment_group('test-rg', 'eastus', INFRASTRUCTURE.SIMPLE_APIM, bicep_params, 'params.json', rg_tags)

    # Verify create_resource_group was called with correct parameters
    mock_create_rg.assert_called_once_with('test-rg', 'eastus', rg_tags)

    # Verify deployment command was called with enum value
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    assert actual_cmd[:4] == ['az', 'deployment', 'group', 'create']
    assert actual_cmd[actual_cmd.index('--name') + 1] == 'simple-apim'
    assert actual_cmd[actual_cmd.index('--resource-group') + 1] == 'test-rg'


def test_create_bicep_deployment_group_with_string(deployment_dependencies):
    """Test create_bicep_deployment_group with string deployment name."""
    mock_create_rg, mock_run, _mock_open_func = deployment_dependencies

    bicep_params = {'param1': {'value': 'test'}}

    bicep_deployment.create_bicep_deployment_group('test-rg', 'eastus', 'custom-deployment', bicep_params)

    # Verify create_resource_group was called without tags
    mock_create_rg.assert_called_once_with('test-rg', 'eastus', None)

    # Verify deployment command uses string deployment name
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    assert actual_cmd[actual_cmd.index('--name') + 1] == 'custom-deployment'


def test_create_bicep_deployment_group_params_file_written(monkeypatch):
    """Test that bicep parameters are correctly written to file."""
    # For this test, we want to simulate being in an infrastructure directory

    def mock_exists(path):
        # Only return True for the main.bicep in the infrastructure directory, not in current dir
        path_str = str(path)  # Convert Path objects to strings
        if path_str.endswith('main.bicep') and 'infrastructure' in path_str:
            return True
        return False

    _mock_create_rg, _mock_run, mock_open_func = patch_create_bicep_deployment_group_dependencies(
        monkeypatch,
        az_module=az,
        run_success=True,
        cwd='/test/dir/infrastructure/apim-aca',
        exists=mock_exists,
        basename='apim-aca',
    )

    bicep_params = {'apiManagementName': {'value': 'test-apim'}, 'location': {'value': 'eastus'}}

    bicep_deployment.create_bicep_deployment_group('test-rg', 'eastus', INFRASTRUCTURE.APIM_ACA, bicep_params, 'custom-params.json')

    # With our new logic, when current directory name matches infrastructure_dir,
    # it should use the current directory
    expected_path = os.path.abspath(os.path.join('/test/dir/infrastructure/apim-aca', 'custom-params.json'))
    mock_open_func.assert_called_once_with(expected_path, 'w', encoding='utf-8', newline = '\n')

    # Verify the correct JSON structure was written
    written_content = ''.join(call.args[0] for call in mock_open_func().write.call_args_list)
    written_data = json.loads(written_content)

    assert written_data['$schema'] == 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'
    assert written_data['contentVersion'] == '1.0.0.0'
    assert written_data['parameters'] == bicep_params


def test_create_bicep_deployment_group_no_tags(deployment_dependencies):
    """Test create_bicep_deployment_group without tags."""
    mock_create_rg, _mock_run, _mock_open_func = deployment_dependencies

    bicep_params = {'param1': {'value': 'test'}}

    bicep_deployment.create_bicep_deployment_group('test-rg', 'eastus', 'test-deployment', bicep_params)

    # Verify create_resource_group was called with None tags
    mock_create_rg.assert_called_once_with('test-rg', 'eastus', None)


def test_create_bicep_deployment_group_deployment_failure(monkeypatch):
    """Test create_bicep_deployment_group when deployment fails."""
    mock_create_rg, _mock_run, _mock_open_func = patch_create_bicep_deployment_group_dependencies(
        monkeypatch,
        az_module=az,
        run_success=False,
        cwd='/test/dir',
        exists=True,
        basename='test-dir',
    )

    bicep_params = {'param1': {'value': 'test'}}

    result = bicep_deployment.create_bicep_deployment_group('test-rg', 'eastus', 'test-deployment', bicep_params)

    # Should still create resource group
    mock_create_rg.assert_called_once()

    # Result should indicate failure
    assert result.success is False


def test_create_bicep_deployment_group_for_sample_success(monkeypatch):
    """Test create_bicep_deployment_group_for_sample success case."""
    mock_output = Output(success=True, text='{"outputs": {"test": "value"}}')

    def mock_create_bicep(rg_name, rg_location, deployment, bicep_parameters, bicep_parameters_file='params.json', rg_tags=None, is_debug=False, *, template_path=None):
        return mock_output

    # Mock file system checks
    def mock_exists(path):
        return True  # Pretend all paths exist

    def mock_chdir(path):
        pass  # Do nothing

    monkeypatch.setattr(bicep_deployment, 'create_bicep_deployment_group', mock_create_bicep)
    monkeypatch.setattr(os.path, 'exists', mock_exists)
    monkeypatch.setattr(os.path, 'isfile', mock_exists)
    monkeypatch.setattr(os, 'chdir', mock_chdir)

    result = bicep_deployment.create_bicep_deployment_group_for_sample('test-sample', 'test-rg', 'eastus', {})
    assert result.success is True


def test_get_deployment_failure_message_debug_disabled(monkeypatch):
    """Test get_deployment_failure_message when DEBUG is not enabled."""
    monkeypatch.setattr('logging_config.get_configured_level_name', lambda: 'INFO')

    msg = bicep_deployment.get_deployment_failure_message('test-deployment')
    assert 'test-deployment' in msg
    assert 'DEBUG' in msg
    assert 'Enable DEBUG' in msg


def test_get_deployment_failure_message_debug_enabled(monkeypatch):
    """Test get_deployment_failure_message when DEBUG is enabled."""
    monkeypatch.setattr('logging_config.get_configured_level_name', lambda: 'DEBUG')

    msg = bicep_deployment.get_deployment_failure_message('test-deployment')
    assert 'test-deployment' in msg
    assert 'Enable DEBUG' not in msg


def test_create_bicep_deployment_group_with_debug_mode(deployment_dependencies):
    """Test create_bicep_deployment_group with debug mode enabled."""
    _mock_create_rg, mock_run, _mock_open_func = deployment_dependencies

    bicep_params = {'param1': {'value': 'test'}}

    result = bicep_deployment.create_bicep_deployment_group('test-rg', 'eastus', INFRASTRUCTURE.SIMPLE_APIM, bicep_params, is_debug=True)

    # Verify debug flag was included in command
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    assert '--debug' in actual_cmd
    assert result.success is True


def test_determine_bicep_directory_with_main_bicep_in_current(monkeypatch):
    """Test bicep directory determination when main.bicep is in current directory."""
    monkeypatch.setattr('os.getcwd', lambda: '/current/dir')
    monkeypatch.setattr('os.path.exists', lambda path: 'main.bicep' in str(path) and '/current/dir' in str(path))

    result = bicep_deployment._determine_bicep_directory('any-dir')
    assert result == '/current/dir'


def test_get_deployment_failure_message_with_deployment_name():
    """Test get_deployment_failure_message includes deployment name."""
    msg = bicep_deployment.get_deployment_failure_message('my-custom-deployment')

    assert 'my-custom-deployment' in msg
    assert 'failed' in msg.lower()


def test_determine_bicep_directory_current_infra(monkeypatch, tmp_path):
    infra_dir = tmp_path / 'foo'
    infra_dir.mkdir()

    monkeypatch.chdir(infra_dir)

    assert bicep_deployment._determine_bicep_directory('foo') == str(infra_dir)


def test_determine_bicep_directory_in_current_tree(monkeypatch, tmp_path):
    bicep_dir = tmp_path / 'infrastructure' / 'bar'
    bicep_dir.mkdir(parents=True)

    monkeypatch.chdir(tmp_path)

    assert bicep_deployment._determine_bicep_directory('bar') == str(bicep_dir)


def test_determine_bicep_directory_in_parent_tree(monkeypatch, tmp_path):
    workdir = tmp_path / 'work'
    workdir.mkdir()
    parent_bicep_dir = tmp_path / 'infrastructure' / 'baz'
    parent_bicep_dir.mkdir(parents=True)

    monkeypatch.chdir(workdir)

    assert bicep_deployment._determine_bicep_directory('baz') == str(parent_bicep_dir)


def test_determine_bicep_directory_from_project_root(monkeypatch, tmp_path):
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()

    project_root = tmp_path / 'project'
    project_bicep_dir = project_root / 'infrastructure' / 'qux'
    project_bicep_dir.mkdir(parents=True)

    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(bicep_deployment, 'get_project_root', lambda: str(project_root))

    assert bicep_deployment._determine_bicep_directory('qux') == str(project_bicep_dir)


@pytest.mark.parametrize('error_type', [OSError, RuntimeError, ValueError])
def test_determine_bicep_directory_falls_back(monkeypatch, tmp_path, caplog, error_type):
    """Expected root-discovery errors keep the fallback and emit diagnostics."""
    nowhere = tmp_path / 'nowhere'
    nowhere.mkdir()

    monkeypatch.chdir(nowhere)
    monkeypatch.setattr(bicep_deployment, 'get_project_root', lambda: (_ for _ in ()).throw(error_type('no root')))

    expected = os.path.join(str(nowhere), 'infrastructure', 'missing')
    with caplog.at_level(logging.DEBUG, logger='console'):
        assert bicep_deployment._determine_bicep_directory('missing') == expected

    assert 'Project-root lookup failed' in caplog.text
    assert 'no root' in caplog.text
    assert 'Falling back to the current directory.' in caplog.text
    assert all(record.levelno == logging.DEBUG for record in caplog.records)


def test_determine_bicep_directory_propagates_unexpected_errors(monkeypatch, tmp_path):
    """Do not disguise programming errors as a successful directory fallback."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bicep_deployment, 'get_project_root', lambda: (_ for _ in ()).throw(TypeError('invalid root contract')))

    with pytest.raises(TypeError, match='invalid root contract'):
        bicep_deployment._determine_bicep_directory('missing')


def test_create_bicep_deployment_group_for_sample_missing_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(bicep_deployment, 'find_project_root', lambda: str(tmp_path))

    with pytest.raises(FileNotFoundError):
        bicep_deployment.create_bicep_deployment_group_for_sample('absent', 'rg', 'loc', {})


def test_create_bicep_deployment_group_for_sample_missing_main(monkeypatch, tmp_path):
    sample_dir = tmp_path / 'samples' / 'demo'
    sample_dir.mkdir(parents=True)

    monkeypatch.setattr(bicep_deployment, 'find_project_root', lambda: str(tmp_path))

    with pytest.raises(FileNotFoundError):
        bicep_deployment.create_bicep_deployment_group_for_sample('demo', 'rg', 'loc', {})


def test_create_bicep_deployment_group_for_sample_in_sample_dir(monkeypatch, tmp_path):
    sample_dir = tmp_path / 'samples' / 'demo'
    sample_dir.mkdir(parents=True)
    (sample_dir / 'main.bicep').write_text('// bicep', encoding='utf-8')

    monkeypatch.chdir(sample_dir)
    monkeypatch.setattr(bicep_deployment, 'create_bicep_deployment_group', lambda *_, **__: 'ok')

    result = bicep_deployment.create_bicep_deployment_group_for_sample('demo', 'rg', 'loc', {})
    assert result == 'ok'


@pytest.mark.parametrize('sensitive, persistent', [(False, False), (False, True), (True, True)])
@pytest.mark.parametrize('success', [False, True])
def test_explicit_deployment_owns_parameters_and_preserves_cwd(monkeypatch, tmp_path, sensitive, persistent, success):
    """Keep explicit paths, exact JSON, debug behavior, and cleanup independent of cwd."""
    template_dir = tmp_path / 'template with spaces'
    template_dir.mkdir()
    template = template_dir / 'custom.bicep'
    template.write_text('// Offline template\n', encoding = 'utf-8')
    monkeypatch.chdir(tmp_path)
    chdir = Mock(side_effect = AssertionError('Must not change working directory'))
    monkeypatch.setattr(os, 'chdir', chdir)
    parameters = {'location': {'value': 'eastus2'}}
    persistent_path = template_dir / 'custom-params.json'
    captured_paths = []
    result = Output(success, '{}')

    def run(command, *args, **kwargs):
        path = Path(command[command.index('--parameters') + 1])
        captured_paths.append(path)
        assert path.is_absolute()
        assert command[command.index('--template-file') + 1] == str(template)
        assert ('--debug' in command) is (not sensitive)
        assert kwargs == {'sensitive_output': sensitive, 'timeout': 1800, 'retries': 0}
        assert json.loads(path.read_text(encoding = 'utf-8')) == {
            '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#',
            'contentVersion': '1.0.0.0',
            'parameters': parameters,
        }
        assert Path.cwd() == tmp_path
        return result

    runner = Mock(side_effect = run)
    actual = bicep_deployment.deploy_bicep_template(
        'test-rg', 'demo', template, parameters,
        parameters_path = persistent_path if persistent else None,
        sensitive_output = sensitive, is_debug = True, runner = runner,
    )

    assert actual is result
    runner.assert_called_once()
    chdir.assert_not_called()
    assert captured_paths[0].exists() is (persistent and not sensitive)
    if sensitive:
        assert not persistent_path.exists()
    if not persistent or sensitive:
        assert not captured_paths[0].parent.exists()


@pytest.mark.parametrize('failure_stage', ['deploy', 'recovery', 'serialization', 'write'])
def test_explicit_deployment_cleans_temporary_parameters_on_exception(monkeypatch, tmp_path, failure_stage):
    """Clean up even if serialization, writing, execution, or recovery raises."""
    template = tmp_path / 'main.bicep'
    template.write_text('// Offline template\n', encoding = 'utf-8')
    directories = []
    real_directory = bicep_deployment.tempfile.TemporaryDirectory

    def directory(**kwargs):
        temporary = real_directory(dir = tmp_path, **kwargs)
        directories.append(Path(temporary.name))
        return temporary

    monkeypatch.setattr(bicep_deployment.tempfile, 'TemporaryDirectory', directory)
    error = RuntimeError('Execution failed')
    runner = Mock(side_effect = error) if failure_stage == 'deploy' else Mock(return_value = Output(False, 'Rejected'))
    recover = Mock(side_effect = error)
    parameters = {'invalid': object()} if failure_stage == 'serialization' else {}
    if failure_stage == 'write':
        monkeypatch.setattr(bicep_deployment, 'open', Mock(side_effect = OSError('Disk full')), raising = False)
    expected_error = TypeError if failure_stage == 'serialization' else OSError if failure_stage == 'write' else RuntimeError

    with pytest.raises(expected_error):
        bicep_deployment.deploy_bicep_template('rg', 'demo', template, parameters, runner = runner, recover = recover)

    assert len(directories) == 1
    assert not directories[0].exists()
    if failure_stage in ('serialization', 'write'):
        runner.assert_not_called()
        recover.assert_not_called()


@pytest.mark.parametrize('recovered', [False, True])
@pytest.mark.parametrize('retry_success', [False, True])
def test_explicit_deployment_limits_recovery_to_one_retry(tmp_path, recovered, retry_success):
    """Recovery keeps one parameter file alive and never authorizes a third attempt."""
    template = tmp_path / 'main.bicep'
    template.write_text('// Offline template\n', encoding = 'utf-8')
    failure = Output(False, 'Rejected')
    final = Output(retry_success, '{}')
    runner = Mock(side_effect = [failure, final])
    recover = Mock(return_value = recovered)

    result = bicep_deployment.deploy_bicep_template('rg', 'demo', template, {}, runner = runner, recover = recover)

    assert result is (final if recovered else failure)
    recover.assert_called_once_with()
    assert runner.call_count == (2 if recovered else 1)
    if recovered:
        assert runner.call_args_list[0] == runner.call_args_list[1]


def test_explicit_deployment_rejects_missing_template_before_side_effects(tmp_path, monkeypatch):
    runner = Mock()
    create_rg = Mock()
    monkeypatch.setattr(az, 'create_resource_group', create_rg)
    parameters_path = tmp_path / 'params.json'

    with pytest.raises(FileNotFoundError, match = 'Bicep template not found'):
        bicep_deployment.create_bicep_deployment_group('rg', 'eastus2', 'demo', {}, template_path = tmp_path / 'missing.bicep')
    with pytest.raises(FileNotFoundError, match = 'Bicep template not found'):
        bicep_deployment.deploy_bicep_template('rg', 'demo', tmp_path / 'missing.bicep', {}, parameters_path = parameters_path, runner = runner)

    create_rg.assert_not_called()
    runner.assert_not_called()
    assert not parameters_path.exists()


@pytest.mark.parametrize('from_sample', [False, True])
def test_sample_deployment_resolves_explicit_paths_without_chdir(monkeypatch, tmp_path, from_sample):
    sample_dir = tmp_path / 'samples' / 'demo'
    sample_dir.mkdir(parents = True)
    (sample_dir / 'main.bicep').write_text('// Offline template\n', encoding = 'utf-8')
    caller_dir = sample_dir if from_sample else tmp_path
    monkeypatch.chdir(caller_dir)
    monkeypatch.setattr(bicep_deployment, 'find_project_root', lambda: str(tmp_path))
    monkeypatch.setattr(os, 'chdir', Mock(side_effect = AssertionError('Must not change cwd')))
    monkeypatch.setattr(az, 'create_resource_group', Mock())
    output = Output(True, '{}')

    def run(command, *args, **kwargs):
        assert command[command.index('--template-file') + 1] == str(sample_dir / 'main.bicep')
        assert command[command.index('--parameters') + 1] == str(sample_dir / 'params.json')
        assert Path.cwd() == caller_dir
        return output

    monkeypatch.setattr(az, 'run', run)

    assert bicep_deployment.create_bicep_deployment_group_for_sample('demo', 'rg', 'eastus2', {}) is output
    assert json.loads((sample_dir / 'params.json').read_text(encoding = 'utf-8'))['parameters'] == {}
    az.create_resource_group.assert_called_once_with('rg', 'eastus2', None)
