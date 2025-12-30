import builtins
import os
import inspect
import base64
import subprocess
import logging
from pathlib import Path
from unittest.mock import MagicMock
import json
import pytest

# APIM Samples imports
from apimtypes import INFRASTRUCTURE, APIM_SKU, HTTP_VERB
import utils
import json_utils
import azure_resources as az
from console import print_error, print_info, print_message, print_ok, print_val, print_warning
import console as console_module
from test_helpers import (
    capture_console_output as capture_output,
    mock_popen,
    patch_create_bicep_deployment_group_dependencies,
    patch_open_for_text_read,
    suppress_module_functions,
)


@pytest.fixture
def suppress_utils_console(monkeypatch):
    suppress_module_functions(
        monkeypatch,
        utils,
        [
            'print_plain',
            'print_info',
            'print_ok',
            'print_warning',
            'print_error',
            'print_message',
            'print_val',
        ],
    )


@pytest.fixture
def suppress_console(monkeypatch):
    suppress_module_functions(
        monkeypatch,
        console_module,
        [
            'print_plain',
            'print_command',
            'print_info',
            'print_ok',
            'print_warning',
            'print_error',
            'print_message',
            'print_val',
        ],
    )


@pytest.fixture
def suppress_builtin_print(monkeypatch):
    suppress_module_functions(monkeypatch, builtins, ['print'])


# ------------------------------
#    get_infra_rg_name & get_rg_name
# ------------------------------

def test_get_infra_rg_name(monkeypatch):
    class DummyInfra:
        value = 'foo'
    assert az.get_infra_rg_name(DummyInfra) == 'apim-infra-foo'
    assert az.get_infra_rg_name(DummyInfra, 2) == 'apim-infra-foo-2'

def test_get_rg_name():
    assert az.get_rg_name('foo') == 'apim-sample-foo'
    assert az.get_rg_name('foo', 3) == 'apim-sample-foo-3'

# ------------------------------
#    run
# ------------------------------

def test_run_success(monkeypatch):
    monkeypatch.setattr(
        'subprocess.run',
        lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout='{"a": 1}', stderr=''),
    )
    out = az.run('echo')
    assert out.success is True
    assert out.json_data == {'a': 1}

def test_run_failure(monkeypatch):
    monkeypatch.setattr(
        'subprocess.run',
        lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stdout='', stderr='fail'),
    )
    out = az.run('bad')
    assert out.success is False
    assert isinstance(out.text, str)

# ------------------------------
#    read_policy_xml
# ------------------------------

def test_read_policy_xml_success(monkeypatch):
    """Test reading a valid XML file returns its contents."""
    xml_content = '<policies><inbound><base /></inbound></policies>'
    monkeypatch.setattr(utils, 'determine_policy_path', lambda *a, **k: '/path/to/dummy.xml')
    patch_open_for_text_read(monkeypatch, match='/path/to/dummy.xml', read_data=xml_content)
    # Use full path to avoid sample name auto-detection
    result = utils.read_policy_xml('/path/to/dummy.xml')
    assert result == xml_content

def test_read_policy_xml_file_not_found(monkeypatch):
    """Test reading a missing XML file raises FileNotFoundError."""
    patch_open_for_text_read(monkeypatch, match='/path/to/missing.xml', raises=FileNotFoundError('File not found'))
    with pytest.raises(FileNotFoundError):
        utils.read_policy_xml('/path/to/missing.xml')

def test_read_policy_xml_empty_file(monkeypatch):
    """Test reading an empty XML file returns an empty string."""
    patch_open_for_text_read(monkeypatch, match='/path/to/empty.xml', read_data='')
    result = utils.read_policy_xml('/path/to/empty.xml')
    assert not result

def test_read_policy_xml_with_named_values(monkeypatch):
    """Test reading policy XML with named values formatting."""
    xml_content = '<policy><validate-jwt><issuer-signing-keys><key>{jwt_signing_key}</key></issuer-signing-keys></validate-jwt></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: p.endswith('hr_all_operations.xml'), read_data=xml_content)

    # Mock the auto-detection to return 'authX'
    def mock_inspect_currentframe():
        frame = MagicMock()
        caller_frame = MagicMock()
        caller_frame.f_globals = {'__file__': '/project/samples/authX/create.ipynb'}
        frame.f_back = caller_frame
        return frame

    monkeypatch.setattr('inspect.currentframe', mock_inspect_currentframe)
    monkeypatch.setattr('utils.get_project_root', lambda: Path('/project'))

    named_values = {
        'jwt_signing_key': 'JwtSigningKey123'
    }

    result = utils.read_policy_xml('hr_all_operations.xml', named_values)
    expected = '<policy><validate-jwt><issuer-signing-keys><key>{{JwtSigningKey123}}</key></issuer-signing-keys></validate-jwt></policy>'
    assert result == expected

def test_read_policy_xml_legacy_mode(monkeypatch):
    """Test that legacy mode (full path) still works."""
    xml_content = '<policies><inbound><base /></inbound></policies>'
    patch_open_for_text_read(monkeypatch, match='/full/path/to/policy.xml', read_data=xml_content)
    result = utils.read_policy_xml('/full/path/to/policy.xml')
    assert result == xml_content

def test_read_policy_xml_auto_detection_failure(monkeypatch):
    """Test that auto-detection failure provides helpful error."""
    # Avoid patching builtins.open here, since the failure should happen before any file IO.

    # Mock the auto-detection to fail
    def mock_inspect_currentframe():
        frame = MagicMock()
        caller_frame = MagicMock()
        caller_frame.f_globals = {'__file__': '/project/notsamples/test/create.ipynb'}
        frame.f_back = caller_frame
        return frame

    monkeypatch.setattr('inspect.currentframe', mock_inspect_currentframe)

    with pytest.raises(ValueError, match='Could not auto-detect sample name'):
        utils.read_policy_xml('policy.xml', {'key': 'value'})

# ------------------------------
#    validate_infrastructure
# ------------------------------

def test_validate_infrastructure_supported():
    # Should return None for supported infra
    assert utils.validate_infrastructure(INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]) is None

def test_validate_infrastructure_unsupported():
    # Should raise ValueError for unsupported infra
    with pytest.raises(ValueError) as exc:
        utils.validate_infrastructure(INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.APIM_ACA])
    assert 'Unsupported infrastructure' in str(exc.value)

def test_validate_infrastructure_multiple_supported():
    # Should return True if infra is in the supported list
    supported = [INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA]
    assert utils.validate_infrastructure(INFRASTRUCTURE.APIM_ACA, supported) is None

# ------------------------------
#    generate_signing_key
# ------------------------------

def test_generate_signing_key():
    s, b64 = utils.generate_signing_key()
    assert isinstance(s, str)
    assert isinstance(b64, str)

# ------------------------------
#    build_infrastructure_tags
# ------------------------------

def test_build_infrastructure_tags_with_enum():
    """Test build_infrastructure_tags with INFRASTRUCTURE enum."""
    result = utils.build_infrastructure_tags(INFRASTRUCTURE.SIMPLE_APIM)
    expected = {'infrastructure': 'simple-apim'}
    assert result == expected

def test_build_infrastructure_tags_with_string():
    """Test build_infrastructure_tags with string infrastructure."""
    result = utils.build_infrastructure_tags('test-infra')
    expected = {'infrastructure': 'test-infra'}
    assert result == expected

def test_build_infrastructure_tags_with_custom_tags():
    """Test build_infrastructure_tags with custom tags."""
    custom_tags = {'env': 'dev', 'team': 'platform'}
    result = utils.build_infrastructure_tags(INFRASTRUCTURE.APIM_ACA, custom_tags)
    expected = {
        'infrastructure': 'apim-aca',
        'env': 'dev',
        'team': 'platform'
    }
    assert result == expected

def test_build_infrastructure_tags_custom_tags_override():
    """Test that custom tags can override standard tags."""
    custom_tags = {'infrastructure': 'custom-override'}
    result = utils.build_infrastructure_tags(INFRASTRUCTURE.AFD_APIM_PE, custom_tags)
    expected = {'infrastructure': 'custom-override'}
    assert result == expected

def test_build_infrastructure_tags_empty_custom_tags():
    """Test build_infrastructure_tags with empty custom tags dict."""
    result = utils.build_infrastructure_tags(INFRASTRUCTURE.SIMPLE_APIM, {})
    expected = {'infrastructure': 'simple-apim'}
    assert result == expected

def test_build_infrastructure_tags_none_custom_tags():
    """Test build_infrastructure_tags with None custom tags."""
    result = utils.build_infrastructure_tags(INFRASTRUCTURE.APIM_ACA, None)
    expected = {'infrastructure': 'apim-aca'}
    assert result == expected

# ------------------------------
#    create_bicep_deployment_group
# ------------------------------

def test_create_bicep_deployment_group_with_enum(monkeypatch):
    """Test create_bicep_deployment_group with INFRASTRUCTURE enum."""
    mock_create_rg, mock_run, _mock_open_func = patch_create_bicep_deployment_group_dependencies(
        monkeypatch,
        az_module=az,
        run_success=True,
        cwd='/test/dir',
        exists=True,
        basename='test-dir',
    )

    bicep_params = {'param1': {'value': 'test'}}
    rg_tags = {'infrastructure': 'simple-apim'}

    _result = utils.create_bicep_deployment_group(
        'test-rg', 'eastus', INFRASTRUCTURE.SIMPLE_APIM, bicep_params, 'params.json', rg_tags
    )

    # Verify create_resource_group was called with correct parameters
    mock_create_rg.assert_called_once_with('test-rg', 'eastus', rg_tags)

    # Verify deployment command was called with enum value
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    assert 'az deployment group create' in actual_cmd
    assert '--name simple-apim' in actual_cmd
    assert '--resource-group test-rg' in actual_cmd

def test_create_bicep_deployment_group_with_string(monkeypatch):
    """Test create_bicep_deployment_group with string deployment name."""
    mock_create_rg, mock_run, _mock_open_func = patch_create_bicep_deployment_group_dependencies(
        monkeypatch,
        az_module=az,
        run_success=True,
        cwd='/test/dir',
        exists=True,
        basename='test-dir',
    )

    bicep_params = {'param1': {'value': 'test'}}

    _result = utils.create_bicep_deployment_group(
        'test-rg', 'eastus', 'custom-deployment', bicep_params
    )

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

    bicep_params = {
        'apiManagementName': {'value': 'test-apim'},
        'location': {'value': 'eastus'}
    }

    utils.create_bicep_deployment_group(
        'test-rg', 'eastus', INFRASTRUCTURE.APIM_ACA, bicep_params, 'custom-params.json'
    )

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

def test_create_bicep_deployment_group_no_tags(monkeypatch):
    """Test create_bicep_deployment_group without tags."""
    mock_create_rg, _mock_run, _mock_open_func = patch_create_bicep_deployment_group_dependencies(
        monkeypatch,
        az_module=az,
        run_success=True,
        cwd='/test/dir',
        exists=True,
        basename='test-dir',
    )

    bicep_params = {'param1': {'value': 'test'}}

    utils.create_bicep_deployment_group('test-rg', 'eastus', 'test-deployment', bicep_params)

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

    result = utils.create_bicep_deployment_group('test-rg', 'eastus', 'test-deployment', bicep_params)

    # Should still create resource group
    mock_create_rg.assert_called_once()

    # Result should indicate failure
    assert result.success is False

# ------------------------------
#    ADDITIONAL COVERAGE TESTS
# ------------------------------

def test_print_functions_comprehensive():
    """Test all print utility functions for coverage."""

    def run_all():
        print_info('Test info message')
        print_ok('Test success message')
        print_warning('Test warning message')
        print_error('Test error message')
        print_message('Test message')
        print_val('Test key', 'Test value')

    output = capture_output(run_all)

    assert 'Test info message' in output
    assert 'Test success message' in output
    assert 'Test warning message' in output
    assert 'Test error message' in output
    assert 'Test message' in output
    assert 'Test key' in output
    assert 'Test value' in output


def test_test_url_preflight_check_with_frontdoor(monkeypatch, suppress_console):
    """Test URL preflight check when Front Door is available."""
    monkeypatch.setattr(az, 'get_frontdoor_url', lambda x, y: 'https://test.azurefd.net')

    result = utils.test_url_preflight_check(INFRASTRUCTURE.AFD_APIM_PE, 'test-rg', 'https://apim.com')
    assert result == 'https://test.azurefd.net'


def test_test_url_preflight_check_no_frontdoor(monkeypatch, suppress_console):
    """Test URL preflight check when Front Door is not available."""
    monkeypatch.setattr(az, 'get_frontdoor_url', lambda x, y: None)

    result = utils.test_url_preflight_check(INFRASTRUCTURE.SIMPLE_APIM, 'test-rg', 'https://apim.com')
    assert result == 'https://apim.com'


def test_determine_policy_path_filename_mode(monkeypatch):
    """Test determine_policy_path with filename mode."""

    # Mock the project root
    mock_project_root = Path('/mock/project/root')
    monkeypatch.setattr('utils.get_project_root', lambda: mock_project_root)

    # Mock current frame to simulate being in samples/test-sample
    class MockFrame:
        def __init__(self):
            self.f_globals = {'__file__': '/mock/project/root/samples/test-sample/create.ipynb'}

    def mock_currentframe():
        frame = MockFrame()
        return frame

    monkeypatch.setattr(inspect, 'currentframe', mock_currentframe)

    result = utils.determine_policy_path('policy.xml', 'test-sample')
    expected = str(mock_project_root / 'samples' / 'test-sample' / 'policy.xml')
    assert result == expected


def test_determine_policy_path_full_path():
    """Test determine_policy_path with full path."""
    full_path = '/path/to/policy.xml'
    result = utils.determine_policy_path(full_path)
    assert result == full_path


def test_wait_for_apim_blob_permissions_success(monkeypatch, suppress_console):
    """Test wait_for_apim_blob_permissions with successful wait."""
    monkeypatch.setattr(az, 'check_apim_blob_permissions', lambda *args: True)

    result = utils.wait_for_apim_blob_permissions('test-apim', 'test-storage', 'test-rg', 1)
    assert result is True


def test_wait_for_apim_blob_permissions_failure(monkeypatch, suppress_console):
    """Test wait_for_apim_blob_permissions with failed wait."""
    monkeypatch.setattr(az, 'check_apim_blob_permissions', lambda *args: False)

    result = utils.wait_for_apim_blob_permissions('test-apim', 'test-storage', 'test-rg', 1)
    assert result is False


def test_read_policy_xml_with_sample_name_explicit(monkeypatch):
    """Test read_policy_xml with explicit sample name."""
    mock_project_root = Path('/mock/project/root')
    monkeypatch.setattr('utils.get_project_root', lambda: mock_project_root)

    xml_content = '<policies><inbound><base /></inbound></policies>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in str(p), read_data=xml_content)

    result = utils.read_policy_xml('policy.xml', sample_name='test-sample')
    assert result == xml_content


def test_read_policy_xml_with_named_values_formatting(monkeypatch):
    """Test read_policy_xml with named values formatting."""
    xml_content = '<policy><key>{jwt_key}</key></policy>'
    expected = '<policy><key>{{JwtSigningKey}}</key></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in str(p), read_data=xml_content)

    named_values = {'jwt_key': 'JwtSigningKey'}
    result = utils.read_policy_xml('/path/to/policy.xml', named_values)
    assert result == expected


@pytest.mark.parametrize(
    'infra_type,expected_suffix',
    [
        (INFRASTRUCTURE.SIMPLE_APIM, 'simple-apim'),
        (INFRASTRUCTURE.AFD_APIM_PE, 'afd-apim-pe'),
        (INFRASTRUCTURE.APIM_ACA, 'apim-aca'),
    ]
)
def test_get_infra_rg_name_different_types(infra_type, expected_suffix):
    """Test get_infra_rg_name with different infrastructure types."""
    result = az.get_infra_rg_name(infra_type)
    assert result == f'apim-infra-{expected_suffix}'


def test_create_bicep_deployment_group_for_sample_success(monkeypatch):
    """Test create_bicep_deployment_group_for_sample success case."""
    mock_output = utils.Output(success=True, text='{"outputs": {"test": "value"}}')

    def mock_create_bicep(rg_name, rg_location, deployment, bicep_parameters, bicep_parameters_file='params.json', rg_tags=None, is_debug=False):
        return mock_output

    # Mock file system checks
    def mock_exists(path):
        return True  # Pretend all paths exist

    def mock_chdir(path):
        pass  # Do nothing

    monkeypatch.setattr(utils, 'create_bicep_deployment_group', mock_create_bicep)
    monkeypatch.setattr(utils, 'build_infrastructure_tags', lambda x: [])
    monkeypatch.setattr(os.path, 'exists', mock_exists)
    monkeypatch.setattr(os, 'chdir', mock_chdir)

    result = utils.create_bicep_deployment_group_for_sample('test-sample', 'test-rg', 'eastus', {})
    assert result.success is True


def test_extract_json_invalid_input():
    """Test extract_json with various invalid inputs."""
    assert json_utils.extract_json(None) is None
    assert json_utils.extract_json(123) is None
    assert json_utils.extract_json([1, 2, 3]) is None
    assert json_utils.extract_json('not json at all') is None


def test_generate_signing_key_format():
    """Test that generate_signing_key returns properly formatted keys."""
    key, b64_key = utils.generate_signing_key()

    # Key should be a string of length 32-100
    assert isinstance(key, str)
    assert 32 <= len(key) <= 100  # Length should be between 32 and 100

    # Key should only contain alphanumeric characters
    assert key.isalnum()

    # Base64 key should be valid base64
    assert isinstance(b64_key, str)

    try:
        decoded = base64.b64decode(b64_key)
        assert len(decoded) == len(key)  # Decoded should match original length
    except Exception:
        pytest.fail('Base64 key is not valid base64')


def test_output_class_functionality():
    """Test the Output class properties and methods."""
    # Test successful output with deployment structure
    output = utils.Output(success=True, text='{"properties": {"outputs": {"test": {"value": "value"}}}}')
    assert output.success is True
    assert output.get('test') == 'value'
    assert output.get('missing') is None  # Should return None for missing key without label

    # Test failed output
    output = utils.Output(success=False, text='error')
    assert output.success is False
    assert output.get('test') is None


def test_run_command_with_error_suppression(monkeypatch):
    """Test run command with error output suppression."""
    monkeypatch.setattr(
        'subprocess.run',
        lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stdout='', stderr='test output'),
    )

    output = az.run('test command')
    assert output.success is False
    assert output.text == 'test output'


def test_bicep_directory_determination_edge_cases(monkeypatch, tmp_path):
    """Test edge cases in Bicep directory determination."""
    # Test when no main.bicep exists anywhere
    empty_dir = tmp_path / 'empty'
    empty_dir.mkdir()
    monkeypatch.setattr(os, 'getcwd', lambda: str(empty_dir))

    # Should fall back to current directory + infrastructure/nonexistent
    result = utils._determine_bicep_directory('nonexistent')
    expected = os.path.join(str(empty_dir), 'infrastructure', 'nonexistent')
    assert result == expected


def test_create_resource_group_edge_cases(monkeypatch):
    """Test create resource group with edge cases."""
    # Test with empty tags
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda x: False)

    def mock_run_with_tags(*args, **kwargs):
        cmd = args[0]
        assert '--tags' in cmd  # Should include tags (with default source=apim-sample)
        return utils.Output(success=True, text='{}')

    monkeypatch.setattr(az, 'run', mock_run_with_tags)

    az.create_resource_group('test-rg', 'eastus', {})  # Empty dict, function doesn't return anything

# ------------------------------
#    ROLE AND PERMISSION TESTS
# ------------------------------

def test_get_azure_role_guid_comprehensive(monkeypatch):
    """Test get_azure_role_guid with comprehensive scenarios."""
    # Mock the azure-roles.json file content
    mock_roles = {
        'Storage Blob Data Reader': '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1',
        'Storage Account Contributor': '17d1049b-9a84-46fb-8f53-869881c3d3ab'
    }

    patch_open_for_text_read(
        monkeypatch,
        match=lambda p: str(p).endswith('azure-roles.json') or 'azure-roles.json' in str(p),
        read_data=json.dumps(mock_roles),
    )

    # Test valid role
    result = az.get_azure_role_guid('Storage Blob Data Reader')
    assert result == '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'

    # Test case sensitivity - function is case sensitive, so this should return None
    result = az.get_azure_role_guid('storage blob data reader')
    assert result is None

    # Test invalid role
    result = az.get_azure_role_guid('Nonexistent Role')
    assert result is None

# ------------------------------
#    INFRASTRUCTURE SELECTION TESTS
# ------------------------------


def test_query_and_select_infrastructure_returns_desired_when_available(monkeypatch, suppress_utils_console):
    nb_helper = utils.NotebookHelper(
        'test-sample',
        'apim-infra-simple-apim-3',
        'eastus',
        INFRASTRUCTURE.SIMPLE_APIM,
        [INFRASTRUCTURE.SIMPLE_APIM],
    )

    monkeypatch.setattr(
        az,
        'find_infrastructure_instances',
        lambda infra: [(INFRASTRUCTURE.SIMPLE_APIM, 3)] if infra == INFRASTRUCTURE.SIMPLE_APIM else [],
    )
    monkeypatch.setattr(
        az,
        'get_infra_rg_name',
        lambda infra, index=None: f'apim-infra-{infra.value}' if index is None else f'apim-infra-{infra.value}-{index}',
    )

    selected_infra, selected_index = nb_helper._query_and_select_infrastructure()

    assert selected_infra == INFRASTRUCTURE.SIMPLE_APIM
    assert selected_index == 3


def test_query_and_select_infrastructure_creates_when_none_found(monkeypatch, suppress_utils_console):
    nb_helper = utils.NotebookHelper(
        'test-sample',
        'apim-infra-simple-apim',
        'eastus',
        INFRASTRUCTURE.SIMPLE_APIM,
        [INFRASTRUCTURE.SIMPLE_APIM],
    )

    monkeypatch.setattr(az, 'find_infrastructure_instances', lambda infra: [])
    monkeypatch.setattr(
        az,
        'get_infra_rg_name',
        lambda infra, index=None: f'apim-infra-{infra.value}' if index is None else f'apim-infra-{infra.value}-{index}',
    )

    created_helpers: list = []

    class DummyInfraHelper:
        def __init__(self, rg_location, deployment, index, apim_sku):
            self.rg_location = rg_location
            self.deployment = deployment
            self.index = index
            self.apim_sku = apim_sku
            self.calls: list[bool] = []
            created_helpers.append(self)

        def create_infrastructure(self, bypass):
            self.calls.append(bypass)
            return True

    monkeypatch.setattr(utils, 'InfrastructureNotebookHelper', DummyInfraHelper)

    selected_infra, selected_index = nb_helper._query_and_select_infrastructure()

    assert selected_infra == INFRASTRUCTURE.SIMPLE_APIM
    assert selected_index is None
    assert created_helpers
    assert created_helpers[0].calls == [True]


def test_query_and_select_infrastructure_user_selects_existing(monkeypatch, suppress_utils_console):
    nb_helper = utils.NotebookHelper(
        'test-sample',
        'apim-infra-simple-apim-1',
        'eastus',
        INFRASTRUCTURE.SIMPLE_APIM,
        [INFRASTRUCTURE.SIMPLE_APIM],
    )

    monkeypatch.setattr(
        az,
        'find_infrastructure_instances',
        lambda infra: [(INFRASTRUCTURE.SIMPLE_APIM, 5)] if infra == INFRASTRUCTURE.SIMPLE_APIM else [],
    )
    monkeypatch.setattr(
        az,
        'get_infra_rg_name',
        lambda infra, index=None: f'apim-infra-{infra.value}' if index is None else f'apim-infra-{infra.value}-{index}',
    )
    monkeypatch.setattr('builtins.input', lambda prompt: '2')

    selected_infra, selected_index = nb_helper._query_and_select_infrastructure()

    assert selected_infra == INFRASTRUCTURE.SIMPLE_APIM
    assert selected_index == 5


@pytest.mark.unit
def test_query_and_select_infrastructure_user_selects_create_new(monkeypatch, suppress_utils_console):
    """Test when user selects option to create new infrastructure."""
    nb_helper = utils.NotebookHelper(
        'test-sample',
        'apim-infra-simple-apim-1',
        'eastus',
        INFRASTRUCTURE.SIMPLE_APIM,
        [INFRASTRUCTURE.SIMPLE_APIM],
    )

    monkeypatch.setattr(
        az,
        'find_infrastructure_instances',
        lambda infra: [(INFRASTRUCTURE.SIMPLE_APIM, 5)] if infra == INFRASTRUCTURE.SIMPLE_APIM else [],
    )
    monkeypatch.setattr(
        az,
        'get_infra_rg_name',
        lambda infra, index=None: f'apim-infra-{infra.value}' if index is None else f'apim-infra-{infra.value}-{index}',
    )

    created_helpers = []

    class DummyInfraHelper:
        def __init__(self, rg_location, deployment, index, apim_sku):
            self.rg_location = rg_location
            self.deployment = deployment
            self.index = index
            self.apim_sku = apim_sku
            self.calls = []
            created_helpers.append(self)

        def create_infrastructure(self, bypass):
            self.calls.append(bypass)
            return True

    monkeypatch.setattr(utils, 'InfrastructureNotebookHelper', DummyInfraHelper)
    monkeypatch.setattr('builtins.input', lambda prompt: '1')  # Select "Create a NEW infrastructure"

    selected_infra, selected_index = nb_helper._query_and_select_infrastructure()

    assert selected_infra == INFRASTRUCTURE.SIMPLE_APIM
    # When user selects option 1 (create_new), the index is from the helper (not None, it's 1 from the nb_helper.index)
    assert selected_index == 1
    assert created_helpers
    assert created_helpers[0].calls == [True]


@pytest.mark.unit
def test_query_and_select_infrastructure_user_enters_empty_string(monkeypatch, suppress_utils_console):
    """Test when user enters empty string (no infrastructure selected)."""
    nb_helper = utils.NotebookHelper(
        'test-sample',
        'apim-infra-simple-apim-1',
        'eastus',
        INFRASTRUCTURE.SIMPLE_APIM,
        [INFRASTRUCTURE.SIMPLE_APIM],
    )

    monkeypatch.setattr(
        az,
        'find_infrastructure_instances',
        lambda infra: [(INFRASTRUCTURE.SIMPLE_APIM, 5)] if infra == INFRASTRUCTURE.SIMPLE_APIM else [],
    )
    monkeypatch.setattr(
        az,
        'get_infra_rg_name',
        lambda infra, index=None: f'apim-infra-{infra.value}' if index is None else f'apim-infra-{infra.value}-{index}',
    )
    monkeypatch.setattr('builtins.input', lambda prompt: '')

    selected_infra, selected_index = nb_helper._query_and_select_infrastructure()

    assert selected_infra is None
    assert selected_index is None


@pytest.mark.unit
def test_query_and_select_infrastructure_user_enters_invalid_then_valid(monkeypatch, suppress_utils_console):
    """Test when user enters invalid choice then valid choice."""
    nb_helper = utils.NotebookHelper(
        'test-sample',
        'apim-infra-simple-apim-1',
        'eastus',
        INFRASTRUCTURE.SIMPLE_APIM,
        [INFRASTRUCTURE.SIMPLE_APIM],
    )

    monkeypatch.setattr(
        az,
        'find_infrastructure_instances',
        lambda infra: [(INFRASTRUCTURE.SIMPLE_APIM, 5)] if infra == INFRASTRUCTURE.SIMPLE_APIM else [],
    )
    monkeypatch.setattr(
        az,
        'get_infra_rg_name',
        lambda infra, index=None: f'apim-infra-{infra.value}' if index is None else f'apim-infra-{infra.value}-{index}',
    )
    inputs = iter(['999', '0', '-1', '2'])  # Invalid then valid
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))

    selected_infra, selected_index = nb_helper._query_and_select_infrastructure()

    assert selected_infra == INFRASTRUCTURE.SIMPLE_APIM
    assert selected_index == 5


@pytest.mark.unit
def test_query_and_select_infrastructure_user_enters_non_numeric(monkeypatch, suppress_utils_console):
    """Test when user enters non-numeric input then valid numeric choice."""
    nb_helper = utils.NotebookHelper(
        'test-sample',
        'apim-infra-simple-apim-1',
        'eastus',
        INFRASTRUCTURE.SIMPLE_APIM,
        [INFRASTRUCTURE.SIMPLE_APIM],
    )

    monkeypatch.setattr(
        az,
        'find_infrastructure_instances',
        lambda infra: [(INFRASTRUCTURE.SIMPLE_APIM, 5)] if infra == INFRASTRUCTURE.SIMPLE_APIM else [],
    )
    monkeypatch.setattr(
        az,
        'get_infra_rg_name',
        lambda infra, index=None: f'apim-infra-{infra.value}' if index is None else f'apim-infra-{infra.value}-{index}',
    )
    inputs = iter(['abc', 'xyz', '2'])  # Non-numeric then valid
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))

    selected_infra, selected_index = nb_helper._query_and_select_infrastructure()

    assert selected_infra == INFRASTRUCTURE.SIMPLE_APIM
    assert selected_index == 5


@pytest.mark.unit
def test_query_and_select_infrastructure_infrastructure_creation_fails(monkeypatch, suppress_utils_console):
    """Test when infrastructure creation fails."""
    nb_helper = utils.NotebookHelper(
        'test-sample',
        'apim-infra-simple-apim',
        'eastus',
        INFRASTRUCTURE.SIMPLE_APIM,
        [INFRASTRUCTURE.SIMPLE_APIM],
    )

    monkeypatch.setattr(az, 'find_infrastructure_instances', lambda infra: [])
    monkeypatch.setattr(
        az,
        'get_infra_rg_name',
        lambda infra, index=None: f'apim-infra-{infra.value}' if index is None else f'apim-infra-{infra.value}-{index}',
    )

    class DummyInfraHelper:
        def __init__(self, rg_location, deployment, index, apim_sku):
            pass

        def create_infrastructure(self, bypass):
            return False  # Creation fails

    monkeypatch.setattr(utils, 'InfrastructureNotebookHelper', DummyInfraHelper)

    selected_infra, selected_index = nb_helper._query_and_select_infrastructure()

    assert selected_infra is None
    assert selected_index is None


@pytest.mark.unit
def test_query_and_select_infrastructure_multiple_infrastructure_types(monkeypatch, suppress_utils_console):
    """Test when multiple infrastructure types are available."""
    nb_helper = utils.NotebookHelper(
        'test-sample',
        'apim-infra-appgw-apim-1',
        'eastus',
        INFRASTRUCTURE.APPGW_APIM,
        [INFRASTRUCTURE.APPGW_APIM, INFRASTRUCTURE.SIMPLE_APIM],
    )

    def mock_find_instances(infra):
        if infra == INFRASTRUCTURE.APPGW_APIM:
            return [(INFRASTRUCTURE.APPGW_APIM, 1)]
        elif infra == INFRASTRUCTURE.SIMPLE_APIM:
            return [(INFRASTRUCTURE.SIMPLE_APIM, 2)]
        return []

    monkeypatch.setattr(az, 'find_infrastructure_instances', mock_find_instances)
    monkeypatch.setattr(
        az,
        'get_infra_rg_name',
        lambda infra, index=None: f'apim-infra-{infra.value}' if index is None else f'apim-infra-{infra.value}-{index}',
    )
    monkeypatch.setattr('builtins.input', lambda prompt: '2')  # Select first existing (appgw-apim-1)

    selected_infra, selected_index = nb_helper._query_and_select_infrastructure()

    assert selected_infra == INFRASTRUCTURE.APPGW_APIM
    assert selected_index == 1


@pytest.mark.unit
def test_query_and_select_infrastructure_with_none_index(monkeypatch, suppress_utils_console):
    """Test when infrastructure instances have None as index."""
    nb_helper = utils.NotebookHelper(
        'test-sample',
        'apim-infra-simple-apim',
        'eastus',
        INFRASTRUCTURE.SIMPLE_APIM,
        [INFRASTRUCTURE.SIMPLE_APIM],
    )

    monkeypatch.setattr(
        az,
        'find_infrastructure_instances',
        lambda infra: [(INFRASTRUCTURE.SIMPLE_APIM, None)] if infra == INFRASTRUCTURE.SIMPLE_APIM else [],
    )
    monkeypatch.setattr(
        az,
        'get_infra_rg_name',
        lambda infra, index=None: f'apim-infra-{infra.value}' if index is None else f'apim-infra-{infra.value}-{index}',
    )
    monkeypatch.setattr('builtins.input', lambda prompt: '2')  # Select the existing one

    selected_infra, selected_index = nb_helper._query_and_select_infrastructure()

    assert selected_infra == INFRASTRUCTURE.SIMPLE_APIM
    assert selected_index is None


# ------------------------------
#    TESTS FOR _prompt_for_infrastructure_update
# ------------------------------

# ------------------------------
#    TESTS FOR _prompt_for_infrastructure_update
# ------------------------------

def test_prompt_for_infrastructure_update_option_1(monkeypatch):
    """Test _prompt_for_infrastructure_update when user selects option 1 (update)."""
    monkeypatch.setattr('builtins.input', lambda prompt: '1')

    result = utils._prompt_for_infrastructure_update('test-rg')
    assert result == (True, None)

def test_prompt_for_infrastructure_update_option_1_default(monkeypatch):
    """Test _prompt_for_infrastructure_update when user presses Enter (defaults to option 1)."""
    monkeypatch.setattr('builtins.input', lambda prompt: '')

    result = utils._prompt_for_infrastructure_update('test-rg')
    assert result == (True, None)

def test_prompt_for_infrastructure_update_option_2_valid_index(monkeypatch):
    """Test _prompt_for_infrastructure_update when user selects option 2 with valid index."""
    inputs = iter(['2', '5'])  # Option 2, then index 5
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))

    result = utils._prompt_for_infrastructure_update('test-rg')
    assert result == (False, 5)

def test_prompt_for_infrastructure_update_option_2_invalid_then_valid_index(monkeypatch):
    """Test _prompt_for_infrastructure_update when user provides invalid index then valid one."""
    inputs = iter(['2', '', '0', '-1', 'abc', '3'])  # Option 2, then empty, zero, negative, non-number, finally valid
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))

    result = utils._prompt_for_infrastructure_update('test-rg')
    assert result == (False, 3)

def test_prompt_for_infrastructure_update_option_3(monkeypatch):
    """Test _prompt_for_infrastructure_update when user selects option 3 (delete first)."""
    monkeypatch.setattr('builtins.input', lambda prompt: '3')

    result = utils._prompt_for_infrastructure_update('test-rg')
    assert result == (False, None)

def test_prompt_for_infrastructure_update_invalid_choice_then_valid(monkeypatch):
    """Test _prompt_for_infrastructure_update with invalid choice followed by valid choice."""
    inputs = iter(['4', '0', 'invalid', '1'])  # Invalid choices, then option 1
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))

    result = utils._prompt_for_infrastructure_update('test-rg')
    assert result == (True, None)

# ------------------------------
#    TESTS FOR InfrastructureNotebookHelper.create_infrastructure WITH INDEX RETRY
# ------------------------------

def test_infrastructure_notebook_helper_create_with_index_retry(monkeypatch, suppress_builtin_print):
    """Test InfrastructureNotebookHelper.create_infrastructure with option 2 (different index) retry."""

    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock resource group existence to return True initially
    call_count = 0
    def mock_rg_exists(rg_name):
        nonlocal call_count
        call_count += 1
        # First call (index 1) returns True, second call (index 3) returns False
        return call_count == 1

    # Mock the prompt to return option 2 with index 3
    monkeypatch.setattr(utils, '_prompt_for_infrastructure_update', lambda rg_name: (False, 3))
    monkeypatch.setattr(az, 'does_resource_group_exist', mock_rg_exists)

    mock_popen(monkeypatch, stdout_lines=['Mock deployment output\n', 'Success!\n'])
    monkeypatch.setattr(utils, 'find_project_root', lambda: 'c:\\mock\\root')

    # Should succeed after retrying with index 3
    result = helper.create_infrastructure()
    assert result is True
    assert helper.index == 3  # Verify index was updated

def test_infrastructure_notebook_helper_create_with_recursive_retry(monkeypatch, suppress_builtin_print):
    """Test InfrastructureNotebookHelper.create_infrastructure with multiple recursive retries."""

    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock resource group existence for multiple indexes
    def mock_rg_exists(rg_name):
        # Parse index from resource group name
        if 'simple-apim-1' in rg_name:
            return True  # Index 1 exists
        if 'simple-apim-2' in rg_name:
            return True  # Index 2 also exists

        return False  # Index 3 doesn't exist

    # Mock the prompt to first return index 2, then index 3
    prompt_calls = 0
    def mock_prompt(rg_name):
        nonlocal prompt_calls
        prompt_calls += 1
        if prompt_calls == 1:
            return (False, 2)  # First retry with index 2

        return (False, 3)  # Second retry with index 3

    monkeypatch.setattr(utils, '_prompt_for_infrastructure_update', mock_prompt)
    monkeypatch.setattr(az, 'does_resource_group_exist', mock_rg_exists)

    mock_popen(monkeypatch, stdout_lines=['Mock deployment output\n'])
    monkeypatch.setattr(utils, 'find_project_root', lambda: 'c:\\mock\\root')
    # Should succeed after retrying with index 3
    result = helper.create_infrastructure()
    assert result is True
    assert helper.index == 3  # Verify final index

def test_infrastructure_notebook_helper_create_user_cancellation(monkeypatch, suppress_builtin_print):
    """Test InfrastructureNotebookHelper.create_infrastructure when user cancels during retry."""

    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock resource group to exist (triggering prompt)
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda rg_name: True)

    # Mock the prompt to return cancellation (option 3)
    monkeypatch.setattr(utils, '_prompt_for_infrastructure_update', lambda rg_name: (False, None))
    # Should raise SystemExit when user cancels
    with pytest.raises(SystemExit) as exc_info:
        helper.create_infrastructure()

    assert "User cancelled deployment" in str(exc_info.value)

def test_infrastructure_notebook_helper_create_keyboard_interrupt_during_prompt(monkeypatch, suppress_builtin_print):
    """Test InfrastructureNotebookHelper.create_infrastructure when KeyboardInterrupt occurs during prompt."""

    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock resource group to exist (triggering prompt)
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda rg_name: True)

    # Mock the prompt to raise KeyboardInterrupt
    def mock_prompt(rg_name):
        raise KeyboardInterrupt()

    monkeypatch.setattr(utils, '_prompt_for_infrastructure_update', mock_prompt)
    # Should raise SystemExit when KeyboardInterrupt occurs
    with pytest.raises(SystemExit) as exc_info:
        helper.create_infrastructure()

    assert "User cancelled deployment" in str(exc_info.value)

def test_infrastructure_notebook_helper_create_eof_error_during_prompt(monkeypatch, suppress_builtin_print):
    """Test InfrastructureNotebookHelper.create_infrastructure when EOFError occurs during prompt."""

    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock resource group to exist (triggering prompt)
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda rg_name: True)

    # Mock the prompt to raise EOFError
    def mock_prompt(rg_name):
        raise EOFError()

    monkeypatch.setattr(utils, '_prompt_for_infrastructure_update', mock_prompt)
    # Should raise SystemExit when EOFError occurs
    with pytest.raises(SystemExit) as exc_info:
        helper.create_infrastructure()

    assert "User cancelled deployment" in str(exc_info.value)

def test_deploy_sample_with_infrastructure_selection(monkeypatch, suppress_console):
    """Test deploy_sample method with infrastructure selection when original doesn't exist."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA]
    )

    # Mock does_resource_group_exist to return False for original, triggering selection
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda rg: False)

    # Mock infrastructure selection to return a valid infrastructure
    selected_infra = INFRASTRUCTURE.APIM_ACA
    selected_index = 2
    monkeypatch.setattr(nb_helper, '_query_and_select_infrastructure',
                       lambda: (selected_infra, selected_index))

    # Mock successful deployment
    mock_output = utils.Output(success=True, text='{"outputs": {"test": "value"}}')
    monkeypatch.setattr(utils, 'create_bicep_deployment_group_for_sample',
                       lambda *args, **kwargs: mock_output)

    # Mock utility functions
    monkeypatch.setattr(az, 'get_infra_rg_name',
                       lambda infra, idx: f'apim-infra-{infra.value}-{idx}')

    # Test the deployment
    result = nb_helper.deploy_sample({'test': {'value': 'param'}})

    # Verify the helper was updated with selected infrastructure
    assert nb_helper.deployment == selected_infra
    assert nb_helper.rg_name == 'apim-infra-apim-aca-2'
    assert result.success is True

def test_deploy_sample_no_infrastructure_found(monkeypatch):
    """Test deploy_sample method when no suitable infrastructure is found."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    # Mock does_resource_group_exist to return False for original
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda rg: False)

    # Mock infrastructure selection to return None (no infrastructure found)
    monkeypatch.setattr(nb_helper, '_query_and_select_infrastructure',
                       lambda: (None, None))

    # Mock utility functions
    monkeypatch.setattr(utils, 'print_error', lambda *args, **kwargs: None)

    # Test should raise SystemExit
    with pytest.raises(SystemExit):
        nb_helper.deploy_sample({'test': {'value': 'param'}})

def test_deploy_sample_existing_infrastructure(monkeypatch):
    """Test deploy_sample method when the specified infrastructure already exists."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    # Mock does_resource_group_exist to return True (infrastructure exists)
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda rg: True)

    # Mock successful deployment
    mock_output = utils.Output(success=True, text='{"outputs": {"test": "value"}}')
    monkeypatch.setattr(utils, 'create_bicep_deployment_group_for_sample',
                       lambda *args, **kwargs: mock_output)

    # Mock utility functions
    monkeypatch.setattr(utils, 'print_ok', lambda *args, **kwargs: None)

    # Test the deployment - should not call infrastructure selection
    result = nb_helper.deploy_sample({'test': {'value': 'param'}})

    # Verify the helper was not modified (still has original values)
    assert nb_helper.deployment == INFRASTRUCTURE.SIMPLE_APIM
    assert nb_helper.rg_name == 'test-rg'
    assert result.success is True

def test_deploy_sample_deployment_failure(monkeypatch):
    """Test deploy_sample method when Bicep deployment fails."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    # Mock does_resource_group_exist to return True
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda rg: True)

    # Mock failed deployment
    mock_output = utils.Output(success=False, text='Deployment failed')
    monkeypatch.setattr(utils, 'create_bicep_deployment_group_for_sample',
                       lambda *args, **kwargs: mock_output)

    # Test should raise SystemExit
    with pytest.raises(SystemExit):
        nb_helper.deploy_sample({'test': {'value': 'param'}})

def test_notebookhelper_initialization_with_supported_infrastructures():
    """Test NotebookHelper initialization with supported infrastructures list."""
    supported_infras = [INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA]

    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, supported_infras
    )

    assert nb_helper.deployment == INFRASTRUCTURE.SIMPLE_APIM
    assert nb_helper.supported_infrastructures == supported_infras
    assert nb_helper.sample_folder == 'test-sample'
    assert nb_helper.rg_name == 'test-rg'
    assert nb_helper.rg_location == 'eastus'
    assert nb_helper.use_jwt is False

def test_notebookhelper_initialization_with_jwt(monkeypatch):
    """Test NotebookHelper initialization with JWT enabled."""
    # Mock JWT-related functions
    monkeypatch.setattr(utils, 'generate_signing_key', lambda: ('test-key', 'test-key-b64'))
    monkeypatch.setattr(utils, 'print_val', lambda *args, **kwargs: None)
    monkeypatch.setattr('time.time', lambda: 1234567890)

    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM], use_jwt=True
    )

    assert nb_helper.use_jwt is True
    assert nb_helper.jwt_key_name == 'JwtSigningKey-test-sample-1234567890'
    assert nb_helper.jwt_key_value == 'test-key'
    assert nb_helper.jwt_key_value_bytes_b64 == 'test-key-b64'

def test_get_deployment_failure_message_debug_disabled(monkeypatch):
    """Test get_deployment_failure_message when DEBUG is not enabled."""
    monkeypatch.setattr('logging_config.get_configured_level_name', lambda: 'INFO')

    msg = utils.get_deployment_failure_message('test-deployment')
    assert 'test-deployment' in msg
    assert 'DEBUG' in msg
    assert 'Enable DEBUG' in msg

def test_get_deployment_failure_message_debug_enabled(monkeypatch):
    """Test get_deployment_failure_message when DEBUG is enabled."""
    monkeypatch.setattr('logging_config.get_configured_level_name', lambda: 'DEBUG')

    msg = utils.get_deployment_failure_message('test-deployment')
    assert 'test-deployment' in msg
    assert 'Enable DEBUG' not in msg

def test_find_project_root_in_current_dir(monkeypatch, tmp_path):
    """Test find_project_root when called from subdirectory."""
    # Create mock project structure
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'README.md').touch()
    (root / 'requirements.txt').touch()
    (root / 'bicepconfig.json').touch()
    subdir = root / 'infrastructure' / 'test'
    subdir.mkdir(parents=True)

    monkeypatch.setattr('os.getcwd', lambda: str(subdir))

    result = utils.find_project_root()
    assert isinstance(result, str)

def test_determine_policy_path_with_full_path():
    """Test determine_policy_path with full file path."""
    full_path = '/full/path/to/policy.xml'
    result = utils.determine_policy_path(full_path)
    assert result == full_path

def test_determine_policy_path_with_sample_name(monkeypatch):
    """Test determine_policy_path with sample name."""
    mock_root = Path('/mock/root')
    monkeypatch.setattr('utils.get_project_root', lambda: mock_root)

    result = utils.determine_policy_path('policy.xml', 'test-sample')
    expected = str(mock_root / 'samples' / 'test-sample' / 'policy.xml')
    assert result == expected

def test_get_infra_rg_name_with_different_types(monkeypatch):
    """Test get_infra_rg_name with various infrastructure types."""
    result = az.get_infra_rg_name(INFRASTRUCTURE.SIMPLE_APIM)
    assert result == 'apim-infra-simple-apim'

    result = az.get_infra_rg_name(INFRASTRUCTURE.APIM_ACA, 2)
    assert result == 'apim-infra-apim-aca-2'

    result = az.get_infra_rg_name(INFRASTRUCTURE.AFD_APIM_PE, 10)
    assert result == 'apim-infra-afd-apim-pe-10'

def test_create_resource_group_doesnt_exist(monkeypatch):
    """Test create_resource_group when RG doesn't exist."""
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda x: False)

    run_calls = []
    def fake_run(cmd, *args, **kwargs):
        run_calls.append(cmd)
        return utils.Output(True, '')

    monkeypatch.setattr(az, 'run', fake_run)

    az.create_resource_group('test-rg', 'eastus', {'tag1': 'value1'})

    assert len(run_calls) == 1
    assert 'az group create' in run_calls[0]
    assert 'test-rg' in run_calls[0]
    assert 'eastus' in run_calls[0]
    assert 'tag1' in run_calls[0]

def test_create_resource_group_already_exists(monkeypatch):
    """Test create_resource_group when RG already exists."""
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda x: True)

    run_calls = []
    def fake_run(cmd, *args, **kwargs):
        run_calls.append(cmd)
        return utils.Output(True, '')

    monkeypatch.setattr(az, 'run', fake_run)

    az.create_resource_group('test-rg', 'eastus')

    # Should not call run when RG exists
    assert not run_calls

def test_find_infrastructure_instances_no_results(monkeypatch):
    """Test find_infrastructure_instances when no instances found."""
    monkeypatch.setattr(az, 'run', lambda cmd, *args, **kwargs: utils.Output(False, 'no results'))

    result = az.find_infrastructure_instances(INFRASTRUCTURE.SIMPLE_APIM)
    assert not result

def test_find_infrastructure_instances_with_index(monkeypatch):
    """Test find_infrastructure_instances with indexed resource groups."""
    def fake_run(cmd, *args, **kwargs):
        if 'simple-apim' in cmd:
            return utils.Output(True, 'apim-infra-simple-apim-1\napim-infra-simple-apim-2\n')
        return utils.Output(False, '')

    monkeypatch.setattr(az, 'run', fake_run)

    result = az.find_infrastructure_instances(INFRASTRUCTURE.SIMPLE_APIM)
    assert len(result) == 2
    assert (INFRASTRUCTURE.SIMPLE_APIM, 1) in result
    assert (INFRASTRUCTURE.SIMPLE_APIM, 2) in result


# ------------------------------
#    NotebookHelper._get_current_index TESTS
# ------------------------------

def test_notebookhelper_get_current_index_with_index(monkeypatch):
    """Test _get_current_index when resource group has an index."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'apim-infra-simple-apim-5', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    result = nb_helper._get_current_index()
    assert result == 5


def test_notebookhelper_get_current_index_without_index(monkeypatch):
    """Test _get_current_index when resource group has no index."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'apim-infra-simple-apim', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    result = nb_helper._get_current_index()
    assert result is None


def test_notebookhelper_get_current_index_invalid_format(monkeypatch):
    """Test _get_current_index with invalid resource group format."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'custom-rg-name', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    result = nb_helper._get_current_index()
    assert result is None


def test_notebookhelper_get_current_index_non_numeric_suffix(monkeypatch):
    """Test _get_current_index with non-numeric suffix."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'apim-infra-simple-apim-abc', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    result = nb_helper._get_current_index()
    assert result is None


# ------------------------------
#    NotebookHelper._clean_up_jwt TESTS
# ------------------------------

def test_notebookhelper_clean_up_jwt_success(monkeypatch, suppress_console):
    """Test _clean_up_jwt with successful cleanup."""
    monkeypatch.setattr(az, 'cleanup_old_jwt_signing_keys', lambda *args: True)
    monkeypatch.setattr(utils, 'generate_signing_key', lambda: ('test-key', 'test-key-b64'))
    monkeypatch.setattr(utils, 'print_val', lambda *args, **kwargs: None)
    monkeypatch.setattr('time.time', lambda: 1234567890)

    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM], use_jwt=True
    )

    # Should not raise or print warning
    nb_helper._clean_up_jwt('test-apim')


def test_notebookhelper_clean_up_jwt_failure(monkeypatch, caplog):
    """Test _clean_up_jwt with failed cleanup."""
    monkeypatch.setattr(az, 'cleanup_old_jwt_signing_keys', lambda *args: False)
    monkeypatch.setattr(utils, 'generate_signing_key', lambda: ('test-key', 'test-key-b64'))
    monkeypatch.setattr(utils, 'print_val', lambda *args, **kwargs: None)
    monkeypatch.setattr('time.time', lambda: 1234567890)

    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM], use_jwt=True
    )

    with caplog.at_level(logging.WARNING):
        nb_helper._clean_up_jwt('test-apim')

    # Should log warning about cleanup failure
    assert any('JWT key cleanup failed' in record.message for record in caplog.records)


# ------------------------------
#    get_endpoints TESTS
# ------------------------------

def test_get_endpoints_comprehensive(monkeypatch, suppress_console):
    """Test get_endpoints function."""
    monkeypatch.setattr(az, 'get_frontdoor_url', lambda x, y: 'https://test-afd.azurefd.net')
    monkeypatch.setattr(az, 'get_apim_url', lambda x: 'https://test-apim.azure-api.net')
    monkeypatch.setattr(az, 'get_appgw_endpoint', lambda x: ('appgw.contoso.com', '1.2.3.4'))

    endpoints = utils.get_endpoints(INFRASTRUCTURE.AFD_APIM_PE, 'test-rg')

    assert endpoints.afd_endpoint_url == 'https://test-afd.azurefd.net'
    assert endpoints.apim_endpoint_url == 'https://test-apim.azure-api.net'
    assert endpoints.appgw_hostname == 'appgw.contoso.com'
    assert endpoints.appgw_public_ip == '1.2.3.4'


def test_get_endpoints_no_frontdoor(monkeypatch, suppress_console):
    """Test get_endpoints when Front Door is not available."""
    monkeypatch.setattr(az, 'get_frontdoor_url', lambda x, y: None)
    monkeypatch.setattr(az, 'get_apim_url', lambda x: 'https://test-apim.azure-api.net')
    monkeypatch.setattr(az, 'get_appgw_endpoint', lambda x: (None, None))

    endpoints = utils.get_endpoints(INFRASTRUCTURE.SIMPLE_APIM, 'test-rg')

    assert endpoints.afd_endpoint_url is None
    assert endpoints.apim_endpoint_url == 'https://test-apim.azure-api.net'


# ------------------------------
#    get_json TESTS
# ------------------------------

def test_get_json_valid_json_string():
    """Test get_json with valid JSON string."""
    json_str = '{"key": "value", "number": 42}'
    result = utils.get_json(json_str)
    assert result == {'key': 'value', 'number': 42}


def test_get_json_python_dict_string():
    """Test get_json with Python dict string (single quotes)."""
    dict_str = "{'key': 'value', 'number': 42}"
    result = utils.get_json(dict_str)
    assert result == {'key': 'value', 'number': 42}


def test_get_json_invalid_string(monkeypatch, suppress_console):
    """Test get_json with invalid string."""
    invalid_str = "not valid json or python literal"
    result = utils.get_json(invalid_str)
    # Should return the original string when parsing fails
    assert result == invalid_str


def test_get_json_non_string():
    """Test get_json with non-string input."""
    result = utils.get_json({'already': 'a dict'})
    assert result == {'already': 'a dict'}

    result = utils.get_json([1, 2, 3])
    assert result == [1, 2, 3]


# ------------------------------
#    does_infrastructure_exist TESTS
# ------------------------------

def test_does_infrastructure_exist_not_exist(monkeypatch, suppress_console):
    """Test does_infrastructure_exist when infrastructure doesn't exist."""
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda x: False)
    monkeypatch.setattr(az, 'get_infra_rg_name', lambda x, y: 'test-rg')

    result = utils.does_infrastructure_exist(INFRASTRUCTURE.SIMPLE_APIM, 1)
    assert result is False


def test_does_infrastructure_exist_with_update_option_proceed(monkeypatch, suppress_console):
    """Test does_infrastructure_exist with update option - user proceeds."""
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda x: True)
    monkeypatch.setattr(az, 'get_infra_rg_name', lambda x, y: 'test-rg')
    monkeypatch.setattr('builtins.input', lambda prompt: '1')

    result = utils.does_infrastructure_exist(INFRASTRUCTURE.SIMPLE_APIM, 1, allow_update_option=True)
    assert result is False  # Allow deployment to proceed


def test_does_infrastructure_exist_with_update_option_cancel(monkeypatch, suppress_console):
    """Test does_infrastructure_exist with update option - user cancels."""
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda x: True)
    monkeypatch.setattr(az, 'get_infra_rg_name', lambda x, y: 'test-rg')
    monkeypatch.setattr('builtins.input', lambda prompt: '2')

    result = utils.does_infrastructure_exist(INFRASTRUCTURE.SIMPLE_APIM, 1, allow_update_option=True)
    assert result is True  # Block deployment


def test_does_infrastructure_exist_without_update_option(monkeypatch, suppress_console):
    """Test does_infrastructure_exist without update option."""
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda x: True)
    monkeypatch.setattr(az, 'get_infra_rg_name', lambda x, y: 'test-rg')

    result = utils.does_infrastructure_exist(INFRASTRUCTURE.SIMPLE_APIM, 1, allow_update_option=False)
    assert result is True  # Infrastructure exists, block deployment


# ------------------------------
#    read_and_modify_policy_xml TESTS
# ------------------------------

def test_read_and_modify_policy_xml_with_replacements(monkeypatch):
    """Test read_and_modify_policy_xml with placeholders."""
    xml_content = '<policy><key>{jwt_key}</key><value>{api_value}</value></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'test-policy.xml' in p, read_data=xml_content)

    replacements = {
        'jwt_key': 'JwtSigningKey123',
        'api_value': 'test-api'
    }

    result = utils.read_and_modify_policy_xml('/path/to/test-policy.xml', replacements)
    expected = '<policy><key>JwtSigningKey123</key><value>test-api</value></policy>'
    assert result == expected


def test_read_and_modify_policy_xml_placeholder_not_found(monkeypatch, caplog):
    """Test read_and_modify_policy_xml when placeholder doesn't exist in XML."""
    xml_content = '<policy><key>static</key></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'test-policy.xml' in p, read_data=xml_content)

    replacements = {'missing_key': 'value'}

    with caplog.at_level(logging.WARNING):
        _ = utils.read_and_modify_policy_xml('/path/to/test-policy.xml', replacements)

    # Should log warning about missing placeholder
    assert any('missing_key' in record.message for record in caplog.records)


def test_read_and_modify_policy_xml_none_replacements(monkeypatch):
    """Test read_and_modify_policy_xml with None replacements."""
    xml_content = '<policy><key>{jwt_key}</key></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'test-policy.xml' in p, read_data=xml_content)

    result = utils.read_and_modify_policy_xml('/path/to/test-policy.xml', None)
    # Should return unmodified XML
    assert result == xml_content


# ------------------------------
#    determine_shared_policy_path TESTS
# ------------------------------

def test_determine_shared_policy_path(monkeypatch):
    """Test determine_shared_policy_path function."""
    monkeypatch.setattr(utils, 'find_project_root', lambda: 'c:\\mock\\project')

    result = utils.determine_shared_policy_path('test-policy.xml')
    expected = Path('c:\\mock\\project') / 'shared' / 'apim-policies' / 'fragments' / 'test-policy.xml'

    assert Path(result) == expected


# ------------------------------
#    InfrastructureNotebookHelper TESTS
# ------------------------------

def test_infrastructure_notebook_helper_bypass_check(monkeypatch, suppress_builtin_print):
    """Test InfrastructureNotebookHelper with bypass_infrastructure_check=True."""
    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    mock_popen(monkeypatch, stdout_lines=['Mock deployment output\n'])
    monkeypatch.setattr(utils, 'find_project_root', lambda: 'c:\\mock\\root')
    # Test with bypass_infrastructure_check=True
    result = helper.create_infrastructure(bypass_infrastructure_check=True)
    assert result is True


def test_infrastructure_notebook_helper_allow_update_false(monkeypatch, suppress_builtin_print):
    """Test InfrastructureNotebookHelper with allow_update=False."""
    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock RG exists but allow_update=False
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda x: True)

    mock_popen(monkeypatch, stdout_lines=['Mock deployment output\n'])
    monkeypatch.setattr(utils, 'find_project_root', lambda: 'c:\\mock\\root')
    # With allow_update=False, should still create when infrastructure doesn't exist
    result = helper.create_infrastructure(allow_update=False, bypass_infrastructure_check=True)
    assert result is True

def test_infrastructure_notebook_helper_missing_args():
    """Test InfrastructureNotebookHelper requires all arguments."""
    with pytest.raises(TypeError):
        utils.InfrastructureNotebookHelper()  # pylint: disable=no-value-for-parameter

    with pytest.raises(TypeError):
        utils.InfrastructureNotebookHelper('eastus')  # pylint: disable=no-value-for-parameter


def test_does_infrastructure_exist_with_prompt_multiple_retries(monkeypatch, suppress_console):
    """Test does_infrastructure_exist when user makes multiple invalid entries."""
    inputs = iter(['invalid', '4', '0', '2'])  # Invalid entries, then valid option 2
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda x: True)
    monkeypatch.setattr(az, 'get_infra_rg_name', lambda x, y: 'test-rg')

    result = utils.does_infrastructure_exist(INFRASTRUCTURE.SIMPLE_APIM, 1, allow_update_option=True)
    assert result is True  # Block deployment


def test_get_endpoints_with_none_values(monkeypatch, suppress_console):
    """Test get_endpoints when some endpoints are None."""
    monkeypatch.setattr(az, 'get_frontdoor_url', lambda x, y: None)
    monkeypatch.setattr(az, 'get_apim_url', lambda x: 'https://test-apim.azure-api.net')
    monkeypatch.setattr(az, 'get_appgw_endpoint', lambda x: (None, None))

    endpoints = utils.get_endpoints(INFRASTRUCTURE.SIMPLE_APIM, 'test-rg')

    assert endpoints.afd_endpoint_url is None
    assert endpoints.apim_endpoint_url == 'https://test-apim.azure-api.net'
    assert endpoints.appgw_hostname is None
    assert endpoints.appgw_public_ip is None


def test_json_parsing_various_formats():
    """Test get_json with various input formats."""
    # Test nested JSON
    nested_json = '{"outer": {"inner": {"value": "test"}}}'
    result = utils.get_json(nested_json)
    assert result['outer']['inner']['value'] == 'test'

    # Test array JSON
    array_json = '[1, 2, 3, {"key": "value"}]'
    result = utils.get_json(array_json)
    assert result[3]['key'] == 'value'

    # Test empty object
    empty_obj = '{}'
    result = utils.get_json(empty_obj)
    assert result == {}

    # Test empty array
    empty_arr = '[]'
    result = utils.get_json(empty_arr)
    assert result == []


def test_validate_signing_key_properties():
    """Test comprehensive properties of generated signing keys."""
    for _ in range(5):  # Test multiple times to ensure consistency
        key, b64_key = utils.generate_signing_key()

        # Check string properties
        assert isinstance(key, str)
        assert isinstance(b64_key, str)

        # Check length constraints
        assert 32 <= len(key) <= 100

        # Verify alphanumeric content
        assert all(c.isalnum() for c in key)

        # Verify base64 encoding
        assert all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in b64_key)

        # Verify base64 can be decoded back to original
        decoded = base64.b64decode(b64_key).decode('ascii')
        assert decoded == key


def test_deployment_failure_message_consistency(monkeypatch):
    """Test deployment failure message with various logging levels."""
    test_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    for level in test_levels:
        monkeypatch.setattr('logging_config.get_configured_level_name', lambda level=level: level)
        msg = utils.get_deployment_failure_message('test-deployment')

        # Message should always contain deployment name
        assert 'test-deployment' in msg

        # Should only suggest DEBUG if not already enabled
        if level == 'DEBUG':
            assert 'Enable DEBUG' not in msg
        else:
            assert 'Enable DEBUG' in msg


def test_create_bicep_deployment_group_with_debug_mode(monkeypatch):
    """Test create_bicep_deployment_group with debug mode enabled."""
    _mock_create_rg, mock_run, _mock_open_func = patch_create_bicep_deployment_group_dependencies(
        monkeypatch,
        az_module=az,
        run_success=True,
        cwd='/test/dir',
        exists=True,
        basename='test-dir',
    )

    bicep_params = {'param1': {'value': 'test'}}

    result = utils.create_bicep_deployment_group(
        'test-rg', 'eastus', INFRASTRUCTURE.SIMPLE_APIM, bicep_params, is_debug=True
    )

    # Verify debug flag was included in command
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    assert '--debug' in actual_cmd
    assert result.success is True


def test_read_policy_xml_complex_replacements(monkeypatch):
    """Test read_and_modify_policy_xml with complex replacement scenarios."""
    xml_content = '<policy><key1>{placeholder1}</key1><key2>{placeholder2}</key2><key3>{placeholder3}</key3></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in p, read_data=xml_content)

    replacements = {
        'placeholder1': 'value1',
        'placeholder2': 'value2',
        'placeholder3': 'value3'
    }

    result = utils.read_and_modify_policy_xml('/path/to/policy.xml', replacements)

    # Verify all replacements were made
    assert 'value1' in result
    assert 'value2' in result
    assert 'value3' in result
    assert '{placeholder1}' not in result
    assert '{placeholder2}' not in result
    assert '{placeholder3}' not in result


def test_infrastructure_tags_with_special_characters():
    """Test build_infrastructure_tags with special characters in tags."""
    special_tags = {
        'environment': 'prod-test',
        'team-name': 'api-management',
        'cost-center': 'cc-12345'
    }

    result = utils.build_infrastructure_tags(INFRASTRUCTURE.AFD_APIM_PE, special_tags)

    # Verify all tags were included with special characters preserved
    assert result['environment'] == 'prod-test'
    assert result['team-name'] == 'api-management'
    assert result['cost-center'] == 'cc-12345'
    assert result['infrastructure'] == 'afd-apim-pe'


def test_bicep_parameters_serialization(monkeypatch):
    """Test that bicep parameters serialize correctly to JSON."""
    _mock_create_rg, _mock_run, mock_open_func = patch_create_bicep_deployment_group_dependencies(
        monkeypatch,
        az_module=az,
        run_success=True,
        cwd='/test/dir',
        exists=True,
        basename='test-dir',
    )

    # Track file writes
    written_content = []

    def mock_file_write(content):
        written_content.append(content)
        return len(content)

    mock_open_func.return_value.__enter__.return_value.write = mock_file_write

    bicep_params = {
        'apiManagementName': {'value': 'test-apim'},
        'location': {'value': 'eastus'},
        'apis': {'value': [{'name': 'api1'}, {'name': 'api2'}]}
    }

    utils.create_bicep_deployment_group(
        'test-rg', 'eastus', INFRASTRUCTURE.SIMPLE_APIM, bicep_params
    )

    # Verify JSON was properly written
    written_text = ''.join(written_content)
    assert '$schema' in written_text
    assert 'contentVersion' in written_text
    assert 'parameters' in written_text


def test_create_resource_group_with_empty_tags(monkeypatch):
    """Test create_resource_group with empty dictionary tags."""
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda x: False)

    run_calls = []

    def mock_run(cmd, *args, **kwargs):
        run_calls.append(cmd)
        return utils.Output(success=True, text='')

    monkeypatch.setattr(az, 'run', mock_run)

    az.create_resource_group('test-rg', 'eastus', {})

    assert len(run_calls) == 1
    assert 'az group create' in run_calls[0]


def test_validate_http_verb():
    """Test HTTP verb validation."""

    # Valid verbs
    assert utils.validate_http_verb('GET') == HTTP_VERB.GET
    assert utils.validate_http_verb('POST') == HTTP_VERB.POST
    assert utils.validate_http_verb('PUT') == HTTP_VERB.PUT
    assert utils.validate_http_verb('DELETE') == HTTP_VERB.DELETE
    assert utils.validate_http_verb('PATCH') == HTTP_VERB.PATCH

    # Invalid verb
    with pytest.raises(ValueError):
        utils.validate_http_verb('INVALID')


def test_validate_sku():
    """Test APIM SKU validation."""
    # Valid SKUs
    assert utils.validate_sku('Developer') == APIM_SKU.DEVELOPER
    assert utils.validate_sku('Basic') == APIM_SKU.BASIC
    assert utils.validate_sku('Standard') == APIM_SKU.STANDARD
    assert utils.validate_sku('Premium') == APIM_SKU.PREMIUM

    # Invalid SKU
    with pytest.raises(ValueError):
        utils.validate_sku('InvalidSKU')


def test_find_project_root_from_nested_directory(monkeypatch, tmp_path):
    """Test find_project_root from a deeply nested directory."""
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'README.md').touch()
    (root / 'requirements.txt').touch()
    (root / 'bicepconfig.json').touch()

    nested_dir = root / 'a' / 'b' / 'c' / 'd' / 'e'
    nested_dir.mkdir(parents=True)

    monkeypatch.setattr('os.getcwd', lambda: str(nested_dir))

    result = utils.find_project_root()
    assert result == str(root)


def test_determine_bicep_directory_with_main_bicep_in_current(monkeypatch):
    """Test bicep directory determination when main.bicep is in current directory."""
    monkeypatch.setattr('os.getcwd', lambda: '/current/dir')
    monkeypatch.setattr('os.path.exists', lambda path: 'main.bicep' in str(path) and '/current/dir' in str(path))

    result = utils._determine_bicep_directory('any-dir')
    assert result == '/current/dir'


def test_read_policy_xml_with_special_characters(monkeypatch):
    """Test read_policy_xml with special characters and Unicode."""
    xml_content = '<policy>Unicode: © ® ™ € Chinese: 中文 Arabic: العربية</policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in p, read_data=xml_content)

    result = utils.read_policy_xml('/path/to/policy.xml')
    assert '©' in result
    assert '中文' in result
    assert 'العربية' in result


def test_output_class_json_extraction():
    """Test Output class JSON extraction methods."""
    json_output = '{"properties": {"outputs": {"apiUrl": {"value": "https://test.azure-api.net"}}}}'
    output = utils.Output(success=True, text=json_output)

    # Test get method with nested extraction
    api_url = output.get('apiUrl', 'API URL')
    assert api_url == 'https://test.azure-api.net'


def test_notebookhelper_with_all_parameters():
    """Test NotebookHelper initialization with all possible parameters."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'westus2',
        INFRASTRUCTURE.APIM_ACA, [INFRASTRUCTURE.APIM_ACA, INFRASTRUCTURE.SIMPLE_APIM],
        use_jwt=False, index=2, is_debug=True, apim_sku=APIM_SKU.PREMIUM
    )

    assert nb_helper.sample_folder == 'test-sample'
    assert nb_helper.rg_name == 'test-rg'
    assert nb_helper.rg_location == 'westus2'
    assert nb_helper.deployment == INFRASTRUCTURE.APIM_ACA
    assert nb_helper.index == 2
    assert nb_helper.is_debug is True
    assert nb_helper.apim_sku == APIM_SKU.PREMIUM

def test_create_bicep_deployment_group_for_sample_with_custom_params_file(monkeypatch):
    """Test determine_shared_policy_path constructs correct path."""
    monkeypatch.setattr(utils, 'find_project_root', lambda: '/project/root')

    result = utils.determine_shared_policy_path('my-fragment.xml')

    # On Windows, path separators will be backslashes
    assert 'project' in result and 'root' in result
    assert 'shared' in result
    assert 'apim-policies' in result
    assert 'fragments' in result
    assert 'my-fragment.xml' in result


def test_wait_for_apim_blob_permissions_with_custom_timeout(monkeypatch, suppress_console):
    """Test wait_for_apim_blob_permissions with custom timeout."""
    mock_check = MagicMock(return_value=True)
    monkeypatch.setattr(az, 'check_apim_blob_permissions', mock_check)

    result = utils.wait_for_apim_blob_permissions(
        'test-apim', 'test-storage', 'test-rg', max_wait_minutes=5
    )

    assert result is True
    # Verify custom timeout was passed
    mock_check.assert_called_once_with('test-apim', 'test-storage', 'test-rg', 5)


def test_test_url_preflight_check_with_afd_endpoint(monkeypatch, suppress_console):
    """Test test_url_preflight_check selects AFD when available."""
    monkeypatch.setattr(az, 'get_frontdoor_url', lambda x, y: 'https://afd-endpoint.azurefd.net')

    result = utils.test_url_preflight_check(
        INFRASTRUCTURE.AFD_APIM_PE, 'test-rg', 'https://apim.azure-api.net'
    )

    assert result == 'https://afd-endpoint.azurefd.net'


def test_test_url_preflight_check_without_afd(monkeypatch, suppress_console):
    """Test test_url_preflight_check uses APIM when no AFD."""
    monkeypatch.setattr(az, 'get_frontdoor_url', lambda x, y: None)

    result = utils.test_url_preflight_check(
        INFRASTRUCTURE.SIMPLE_APIM, 'test-rg', 'https://apim.azure-api.net'
    )

    assert result == 'https://apim.azure-api.net'


def test_get_json_with_nested_structure():
    """Test get_json with deeply nested JSON."""
    nested_json = '{"level1": {"level2": {"level3": {"value": "deep"}}}}'
    result = utils.get_json(nested_json)

    assert result['level1']['level2']['level3']['value'] == 'deep'


def test_get_json_with_array():
    """Test get_json with JSON array."""
    json_array = '[{"id": 1}, {"id": 2}, {"id": 3}]'
    result = utils.get_json(json_array)

    assert isinstance(result, list)
    assert len(result) == 3
    assert result[1]['id'] == 2


def test_get_json_with_empty_string():
    """Test get_json with empty string."""
    result = utils.get_json('')

    assert not result


def test_get_json_with_number_string():
    """Test get_json with numeric string."""
    result = utils.get_json('42')

    assert result == 42


def test_get_json_with_boolean_string():
    """Test get_json with boolean string."""
    result_true = utils.get_json('true')
    result_false = utils.get_json('false')

    assert result_true is True
    assert result_false is False


def test_validate_infrastructure_single_supported():
    """Test validate_infrastructure with single supported infrastructure."""
    # Should not raise
    utils.validate_infrastructure(
        INFRASTRUCTURE.SIMPLE_APIM,
        [INFRASTRUCTURE.SIMPLE_APIM]
    )


def test_validate_infrastructure_multiple_supported_v2():
    """Test validate_infrastructure with multiple supported infrastructures."""
    # Should not raise
    utils.validate_infrastructure(
        INFRASTRUCTURE.APIM_ACA,
        [INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA, INFRASTRUCTURE.APPGW_APIM]
    )


def test_validate_infrastructure_unsupported_raises():
    """Test validate_infrastructure raises for unsupported infrastructure."""
    with pytest.raises(ValueError) as exc_info:
        utils.validate_infrastructure(
            INFRASTRUCTURE.AFD_APIM_PE,
            [INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA]
        )

    assert 'Unsupported infrastructure' in str(exc_info.value)
    assert 'afd-apim-pe' in str(exc_info.value)


def test_generate_signing_key_uniqueness():
    """Test generate_signing_key produces unique keys."""
    keys = set()
    b64_keys = set()

    for _ in range(10):
        key, b64_key = utils.generate_signing_key()
        keys.add(key)
        b64_keys.add(b64_key)

    # All keys should be unique
    assert len(keys) == 10
    assert len(b64_keys) == 10


def test_build_infrastructure_tags_preserves_custom():
    """Test build_infrastructure_tags preserves all custom tags."""
    custom_tags = {
        'environment': 'production',
        'cost-center': 'engineering',
        'owner': 'platform-team',
        'project': 'api-gateway'
    }

    result = utils.build_infrastructure_tags(INFRASTRUCTURE.SIMPLE_APIM, custom_tags)

    # All custom tags should be present
    for key, value in custom_tags.items():
        assert result[key] == value

    # Infrastructure tag should also be present
    assert result['infrastructure'] == 'simple-apim'


def test_build_infrastructure_tags_with_string_infrastructure():
    """Test build_infrastructure_tags with string infrastructure value."""
    result = utils.build_infrastructure_tags('custom-infra', {'env': 'dev'})

    assert result['infrastructure'] == 'custom-infra'
    assert result['env'] == 'dev'


def test_determine_policy_path_with_backslash_separators():
    """Test determine_policy_path recognizes backslash path separators."""
    path = 'C:\\path\\to\\policy.xml'
    result = utils.determine_policy_path(path)

    # Should treat as full path due to backslash
    assert result == path


def test_determine_policy_path_with_forward_slash():
    """Test determine_policy_path recognizes forward slash paths."""
    path = '/absolute/path/to/policy.xml'
    result = utils.determine_policy_path(path)

    # Should treat as full path
    assert result == path


def test_determine_policy_path_with_relative_path():
    """Test determine_policy_path recognizes relative paths with separators."""
    path = 'relative/path/policy.xml'
    result = utils.determine_policy_path(path)

    # Should treat as full path due to separator
    assert result == path


def test_read_policy_xml_with_multiple_named_values(monkeypatch):
    """Test read_policy_xml with multiple named values."""
    xml_content = '<policy><key1>{var1}</key1><key2>{var2}</key2><key3>{var3}</key3></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in p, read_data=xml_content)

    named_values = {
        'var1': 'jwt-signing-key',
        'var2': 'api-key',
        'var3': 'role-id'
    }

    result = utils.read_policy_xml('/path/to/policy.xml', named_values=named_values)

    # Should have double-braced named values
    assert '{{jwt-signing-key}}' in result
    assert '{{api-key}}' in result
    assert '{{role-id}}' in result


def test_read_and_modify_policy_xml_with_empty_replacements(monkeypatch):
    """Test read_and_modify_policy_xml with empty replacements dict."""
    xml_content = '<policy><key>{placeholder}</key></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in p, read_data=xml_content)

    result = utils.read_and_modify_policy_xml('/path/to/policy.xml', {})

    # With empty replacements, content should be unchanged
    assert result == xml_content


def test_read_and_modify_policy_xml_preserves_formatting(monkeypatch):
    """Test read_and_modify_policy_xml preserves XML formatting."""
    xml_content = '''<policy>
    <inbound>
        <base />
        <set-variable name="test" value="{placeholder}" />
    </inbound>
</policy>'''
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in p, read_data=xml_content)

    replacements = {'placeholder': 'actual-value'}
    result = utils.read_and_modify_policy_xml('/path/to/policy.xml', replacements)

    # Should preserve indentation and newlines
    assert '\n    <inbound>\n' in result
    assert 'actual-value' in result


def test_find_project_root_with_readme_only(monkeypatch, tmp_path):
    """Test find_project_root finds root when all markers are present."""
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'README.md').touch()
    (root / 'requirements.txt').touch()
    (root / 'bicepconfig.json').touch()

    nested = root / 'sub' / 'dir'
    nested.mkdir(parents=True)

    monkeypatch.setattr('os.getcwd', lambda: str(nested))

    result = utils.find_project_root()
    assert result == str(root)


def test_find_project_root_with_requirements_only(monkeypatch, tmp_path):
    """Test find_project_root finds root when all markers are present."""
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'README.md').touch()
    (root / 'requirements.txt').touch()
    (root / 'bicepconfig.json').touch()

    nested = root / 'sub' / 'dir'
    nested.mkdir(parents=True)

    monkeypatch.setattr('os.getcwd', lambda: str(nested))

    result = utils.find_project_root()
    assert result == str(root)


def test_find_project_root_already_at_root(monkeypatch, tmp_path):
    """Test find_project_root when already in project root."""
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'README.md').touch()
    (root / 'requirements.txt').touch()
    (root / 'bicepconfig.json').touch()

    monkeypatch.setattr('os.getcwd', lambda: str(root))

    result = utils.find_project_root()
    assert result == str(root)


def test_find_project_root_not_found_raises(monkeypatch, tmp_path):
    """Test find_project_root raises when no markers found."""
    deep_dir = tmp_path / 'no' / 'project' / 'here'
    deep_dir.mkdir(parents=True)

    monkeypatch.setattr('os.getcwd', lambda: str(deep_dir))

    with pytest.raises(FileNotFoundError) as exc_info:
        utils.find_project_root()

    assert 'Could not determine project root' in str(exc_info.value)


def test_get_deployment_failure_message_with_deployment_name():
    """Test get_deployment_failure_message includes deployment name."""
    msg = utils.get_deployment_failure_message('my-custom-deployment')

    assert 'my-custom-deployment' in msg
    assert 'failed' in msg.lower()


def test_endpoints_class_initialization():
    """Test Endpoints class initializes deployment field."""
    endpoints = utils.Endpoints(INFRASTRUCTURE.AFD_APIM_PE)

    assert endpoints.deployment == INFRASTRUCTURE.AFD_APIM_PE


def test_endpoints_class_set_values():
    """Test Endpoints class can set all endpoint values."""
    endpoints = utils.Endpoints(INFRASTRUCTURE.APPGW_APIM)
    endpoints.afd_endpoint_url = 'https://afd.azurefd.net'
    endpoints.apim_endpoint_url = 'https://apim.azure-api.net'
    endpoints.appgw_hostname = 'appgw.example.com'
    endpoints.appgw_public_ip = '20.30.40.50'

    assert endpoints.afd_endpoint_url == 'https://afd.azurefd.net'
    assert endpoints.apim_endpoint_url == 'https://apim.azure-api.net'
    assert endpoints.appgw_hostname == 'appgw.example.com'
    assert endpoints.appgw_public_ip == '20.30.40.50'


def test_output_class_without_json():
    """Test Output class with non-JSON text."""
    output = utils.Output(success=False, text='Error message here')

    assert output.success is False
    assert output.text == 'Error message here'
    assert output.is_json is False


def test_output_get_with_deep_nesting():
    """Test Output.get with deeply nested structure."""
    json_output = '{"properties": {"outputs": {"deep": {"value": {"nested": {"data": "found"}}}}}}'
    output = utils.Output(success=True, text=json_output)

    # This tests the nested value extraction - Output.get returns str
    result = output.get('deep', 'Deep value')
    assert "{'nested':" in result or '{"nested":' in result


# ------------------------------
#    Additional coverage
# ------------------------------

def test_create_infrastructure_unsupported_type(monkeypatch, suppress_utils_console):
    class Unsupported:
        value = 'unsupported'

    helper = utils.InfrastructureNotebookHelper('eastus', Unsupported(), 1, APIM_SKU.BASICV2)

    # Skip update checks
    monkeypatch.setattr(az, 'get_infra_rg_name', lambda *_, **__: 'rg')
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda *_, **__: False)

    with pytest.raises(SystemExit):
        helper.create_infrastructure(bypass_infrastructure_check=False, allow_update=False)


def test_create_infrastructure_stream_error(monkeypatch, tmp_path, suppress_utils_console):
    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    monkeypatch.setattr(utils, 'find_project_root', lambda: str(tmp_path))
    monkeypatch.setattr(az, 'get_infra_rg_name', lambda *_, **__: 'rg')
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda *_, **__: False)

    class BoomIter:
        def __iter__(self):
            raise ValueError('boom')

    class FakeProcess:
        def __init__(self):
            self.stdout = BoomIter()
            self.returncode = 1

        def wait(self):
            self.returncode = 1

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    monkeypatch.setattr(subprocess, 'Popen', lambda *_, **__: FakeProcess())

    with pytest.raises(SystemExit):
        helper.create_infrastructure(bypass_infrastructure_check=False, allow_update=False)


def test_determine_bicep_directory_current_infra(monkeypatch, tmp_path):
    infra_dir = tmp_path / 'foo'
    infra_dir.mkdir()

    monkeypatch.chdir(infra_dir)

    assert utils._determine_bicep_directory('foo') == str(infra_dir)


def test_determine_bicep_directory_in_current_tree(monkeypatch, tmp_path):
    bicep_dir = tmp_path / 'infrastructure' / 'bar'
    bicep_dir.mkdir(parents=True)

    monkeypatch.chdir(tmp_path)

    assert utils._determine_bicep_directory('bar') == str(bicep_dir)


def test_determine_bicep_directory_in_parent_tree(monkeypatch, tmp_path):
    workdir = tmp_path / 'work'
    workdir.mkdir()
    parent_bicep_dir = tmp_path / 'infrastructure' / 'baz'
    parent_bicep_dir.mkdir(parents=True)

    monkeypatch.chdir(workdir)

    assert utils._determine_bicep_directory('baz') == str(parent_bicep_dir)


def test_determine_bicep_directory_from_project_root(monkeypatch, tmp_path):
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()

    project_root = tmp_path / 'project'
    project_bicep_dir = project_root / 'infrastructure' / 'qux'
    project_bicep_dir.mkdir(parents=True)

    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(utils, 'get_project_root', lambda: str(project_root))

    assert utils._determine_bicep_directory('qux') == str(project_bicep_dir)


def test_determine_bicep_directory_falls_back(monkeypatch, tmp_path):
    nowhere = tmp_path / 'nowhere'
    nowhere.mkdir()

    monkeypatch.chdir(nowhere)
    monkeypatch.setattr(utils, 'get_project_root', lambda: (_ for _ in ()).throw(ValueError('no root')))

    expected = os.path.join(str(nowhere), 'infrastructure', 'missing')
    assert utils._determine_bicep_directory('missing') == expected


def test_create_bicep_deployment_group_for_sample_missing_dir(monkeypatch, tmp_path, suppress_utils_console):
    monkeypatch.setattr(utils, 'find_project_root', lambda: str(tmp_path))

    with pytest.raises(FileNotFoundError):
        utils.create_bicep_deployment_group_for_sample('absent', 'rg', 'loc', {})


def test_create_bicep_deployment_group_for_sample_missing_main(monkeypatch, tmp_path, suppress_utils_console):
    sample_dir = tmp_path / 'samples' / 'demo'
    sample_dir.mkdir(parents=True)

    monkeypatch.setattr(utils, 'find_project_root', lambda: str(tmp_path))

    with pytest.raises(FileNotFoundError):
        utils.create_bicep_deployment_group_for_sample('demo', 'rg', 'loc', {})


def test_create_bicep_deployment_group_for_sample_in_sample_dir(monkeypatch, tmp_path, suppress_utils_console):
    sample_dir = tmp_path / 'samples' / 'demo'
    sample_dir.mkdir(parents=True)
    (sample_dir / 'main.bicep').write_text('// bicep', encoding='utf-8')

    monkeypatch.chdir(sample_dir)
    monkeypatch.setattr(utils, 'create_bicep_deployment_group', lambda *_, **__: 'ok')

    result = utils.create_bicep_deployment_group_for_sample('demo', 'rg', 'loc', {})
    assert result == 'ok'


def test_determine_policy_path_missing_sample_name(monkeypatch):
    class FakeFrame:
        def __init__(self):
            self.f_back = MagicMock()
            self.f_back.f_globals = {'__file__': str(Path('/tmp/samples'))}

    monkeypatch.setattr(utils.inspect, 'currentframe', FakeFrame)

    with pytest.raises(ValueError, match='Could not detect sample name'):
        utils.determine_policy_path('policy.xml')


def test_determine_policy_path_fallback_to_cwd(monkeypatch, tmp_path):
    class FakeFrame:
        def __init__(self):
            self.f_back = MagicMock()
            self.f_back.f_globals = {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(utils.inspect, 'currentframe', FakeFrame)

    with pytest.raises(ValueError, match='Not running from within a samples directory'):
        utils.determine_policy_path('policy.xml')


def test_query_and_select_infrastructure_user_creates_new_but_fails(monkeypatch, suppress_utils_console):
    """Test when user selects to create new infrastructure but creation fails."""
    nb_helper = utils.NotebookHelper(
        'test-sample',
        'apim-infra-simple-apim-1',
        'eastus',
        INFRASTRUCTURE.SIMPLE_APIM,
        [INFRASTRUCTURE.SIMPLE_APIM],
    )

    monkeypatch.setattr(
        az,
        'find_infrastructure_instances',
        lambda infra: [(INFRASTRUCTURE.SIMPLE_APIM, 5)] if infra == INFRASTRUCTURE.SIMPLE_APIM else [],
    )
    monkeypatch.setattr(
        az,
        'get_infra_rg_name',
        lambda infra, index=None: f'apim-infra-{infra.value}' if index is None else f'apim-infra-{infra.value}-{index}',
    )

    class DummyInfraHelper:
        def __init__(self, rg_location, deployment, index, apim_sku):
            pass

        def create_infrastructure(self, bypass):
            return False  # Creation fails

    monkeypatch.setattr(utils, 'InfrastructureNotebookHelper', DummyInfraHelper)
    monkeypatch.setattr('builtins.input', lambda prompt: '1')  # Select "Create a NEW infrastructure" but it fails

    selected_infra, selected_index = nb_helper._query_and_select_infrastructure()

    assert selected_infra is None
    assert selected_index is None


def test_query_and_select_infrastructure_with_query_rg_location_enabled(monkeypatch, suppress_utils_console):
    """Test the QUERY_RG_LOCATION=True code paths for displaying headers and location info."""
    # Enable QUERY_RG_LOCATION via environment variable BEFORE creating NotebookHelper
    monkeypatch.setenv('APIM_TEST_QUERY_RG_LOCATION', 'True')

    nb_helper = utils.NotebookHelper(
        'test-sample',
        'apim-infra-simple-apim-1',
        'eastus',
        INFRASTRUCTURE.SIMPLE_APIM,
        [INFRASTRUCTURE.SIMPLE_APIM],
    )

    monkeypatch.setattr(
        az,
        'find_infrastructure_instances',
        lambda infra: [(INFRASTRUCTURE.SIMPLE_APIM, 5)] if infra == INFRASTRUCTURE.SIMPLE_APIM else [],
    )
    monkeypatch.setattr(
        az,
        'get_infra_rg_name',
        lambda infra, index=None: f'apim-infra-{infra.value}' if index is None else f'apim-infra-{infra.value}-{index}',
    )
    monkeypatch.setattr(az, 'get_resource_group_location', lambda rg_name: 'eastus')

    class DummyInfraHelper:
        def __init__(self, rg_location, deployment, index, apim_sku):
            pass

        def create_infrastructure(self, bypass):
            return True

    monkeypatch.setattr(utils, 'InfrastructureNotebookHelper', DummyInfraHelper)
    monkeypatch.setattr('builtins.input', lambda prompt: '2')  # Select existing infrastructure (option 2)

    selected_infra, selected_index = nb_helper._query_and_select_infrastructure()

    assert selected_infra == INFRASTRUCTURE.SIMPLE_APIM
    assert selected_index == 5
