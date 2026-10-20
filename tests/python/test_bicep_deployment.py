"""Tests for the extracted bicep_deployment capability."""

import json
import os
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

    _result = bicep_deployment.create_bicep_deployment_group('test-rg', 'eastus', INFRASTRUCTURE.SIMPLE_APIM, bicep_params, 'params.json', rg_tags)

    # Verify create_resource_group was called with correct parameters
    mock_create_rg.assert_called_once_with('test-rg', 'eastus', rg_tags)

    # Verify deployment command was called with enum value
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    assert 'az deployment group create' in actual_cmd
    assert '--name simple-apim' in actual_cmd
    assert '--resource-group test-rg' in actual_cmd


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
    assert '--name custom-deployment' in actual_cmd


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
    expected_path = os.path.join('/test/dir/infrastructure/apim-aca', 'custom-params.json')
    mock_open_func.assert_called_once_with(expected_path, 'w', encoding='utf-8')

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

    def mock_create_bicep(rg_name, rg_location, deployment, bicep_parameters, bicep_parameters_file='params.json', rg_tags=None, is_debug=False):
        return mock_output

    # Mock file system checks
    def mock_exists(path):
        return True  # Pretend all paths exist

    def mock_chdir(path):
        pass  # Do nothing

    monkeypatch.setattr(bicep_deployment, 'create_bicep_deployment_group', mock_create_bicep)
    monkeypatch.setattr(os.path, 'exists', mock_exists)
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


def test_determine_bicep_directory_falls_back(monkeypatch, tmp_path):
    nowhere = tmp_path / 'nowhere'
    nowhere.mkdir()

    monkeypatch.chdir(nowhere)
    monkeypatch.setattr(bicep_deployment, 'get_project_root', lambda: (_ for _ in ()).throw(ValueError('no root')))

    expected = os.path.join(str(nowhere), 'infrastructure', 'missing')
    assert bicep_deployment._determine_bicep_directory('missing') == expected


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
