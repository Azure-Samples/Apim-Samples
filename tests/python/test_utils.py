import os
import io
import builtins
import inspect
import base64
import subprocess
import logging
from pathlib import Path
from unittest.mock import MagicMock, mock_open
import json
import pytest

# APIM Samples imports
from apimtypes import INFRASTRUCTURE, APIM_SKU
import utils
import json_utils
import azure_resources as az
from console import print_error, print_info, print_message, print_ok, print_val, print_warning

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
    m = mock_open(read_data=xml_content)

    real_open = builtins.open

    def open_selector(file, *args, **kwargs):
        mode = kwargs.get('mode', args[0] if args else 'r')
        file_str = str(file)
        if file_str == '/path/to/dummy.xml' and 'b' not in mode:
            return m(file, *args, **kwargs)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', open_selector)
    # Use full path to avoid sample name auto-detection
    result = utils.read_policy_xml('/path/to/dummy.xml')
    assert result == xml_content

def test_read_policy_xml_file_not_found(monkeypatch):
    """Test reading a missing XML file raises FileNotFoundError."""

    real_open = builtins.open

    def open_selector(file, *args, **kwargs):
        mode = kwargs.get('mode', args[0] if args else 'r')
        file_str = str(file)
        if file_str == '/path/to/missing.xml' and 'b' not in mode:
            raise FileNotFoundError('File not found')
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', open_selector)
    with pytest.raises(FileNotFoundError):
        utils.read_policy_xml('/path/to/missing.xml')

def test_read_policy_xml_empty_file(monkeypatch):
    """Test reading an empty XML file returns an empty string."""
    m = mock_open(read_data='')

    real_open = builtins.open

    def open_selector(file, *args, **kwargs):
        mode = kwargs.get('mode', args[0] if args else 'r')
        file_str = str(file)
        if file_str == '/path/to/empty.xml' and 'b' not in mode:
            return m(file, *args, **kwargs)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', open_selector)
    result = utils.read_policy_xml('/path/to/empty.xml')
    assert not result

def test_read_policy_xml_with_named_values(monkeypatch):
    """Test reading policy XML with named values formatting."""
    xml_content = '<policy><validate-jwt><issuer-signing-keys><key>{jwt_signing_key}</key></issuer-signing-keys></validate-jwt></policy>'
    m = mock_open(read_data=xml_content)

    real_open = builtins.open

    def open_selector(file, *args, **kwargs):
        mode = kwargs.get('mode', args[0] if args else 'r')
        file_str = str(file)
        if file_str.endswith('hr_all_operations.xml') and 'b' not in mode:
            return m(file, *args, **kwargs)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', open_selector)

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
    m = mock_open(read_data=xml_content)

    real_open = builtins.open

    def open_selector(file, *args, **kwargs):
        mode = kwargs.get('mode', args[0] if args else 'r')
        file_str = str(file)
        if file_str == '/full/path/to/policy.xml' and 'b' not in mode:
            return m(file, *args, **kwargs)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', open_selector)
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
    mock_create_rg = MagicMock()
    monkeypatch.setattr(az, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(az, 'run', mock_run)
    mock_open_func = mock_open()
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(builtins, 'print', MagicMock())
    # Mock os functions for file path operations
    monkeypatch.setattr('os.getcwd', MagicMock(return_value='/test/dir'))
    monkeypatch.setattr('os.path.exists', MagicMock(return_value=True))
    monkeypatch.setattr('os.path.basename', MagicMock(return_value='test-dir'))

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
    mock_create_rg = MagicMock()
    monkeypatch.setattr(az, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(az, 'run', mock_run)
    mock_open_func = mock_open()
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(builtins, 'print', MagicMock())
    # Mock os functions for file path operations
    monkeypatch.setattr('os.getcwd', MagicMock(return_value='/test/dir'))
    monkeypatch.setattr('os.path.exists', MagicMock(return_value=True))
    monkeypatch.setattr('os.path.basename', MagicMock(return_value='test-dir'))

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
    mock_create_rg = MagicMock()
    monkeypatch.setattr(az, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(az, 'run', mock_run)
    mock_open_func = mock_open()
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(builtins, 'print', MagicMock())

    # Mock os functions for file path operations
    # For this test, we want to simulate being in an infrastructure directory
    monkeypatch.setattr('os.getcwd', MagicMock(return_value='/test/dir/infrastructure/apim-aca'))

    def mock_exists(path):
        # Only return True for the main.bicep in the infrastructure directory, not in current dir
        path_str = str(path)  # Convert Path objects to strings
        if path_str.endswith('main.bicep') and 'infrastructure' in path_str:
            return True
        return False

    monkeypatch.setattr('os.path.exists', mock_exists)
    monkeypatch.setattr('os.path.basename', MagicMock(return_value='apim-aca'))

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
    mock_create_rg = MagicMock()
    monkeypatch.setattr(az, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(az, 'run', mock_run)
    mock_open_func = mock_open()
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(builtins, 'print', MagicMock())
    # Mock os functions for file path operations
    monkeypatch.setattr('os.getcwd', MagicMock(return_value='/test/dir'))
    monkeypatch.setattr('os.path.exists', MagicMock(return_value=True))
    monkeypatch.setattr('os.path.basename', MagicMock(return_value='test-dir'))

    bicep_params = {'param1': {'value': 'test'}}

    utils.create_bicep_deployment_group('test-rg', 'eastus', 'test-deployment', bicep_params)

    # Verify create_resource_group was called with None tags
    mock_create_rg.assert_called_once_with('test-rg', 'eastus', None)

def test_create_bicep_deployment_group_deployment_failure(monkeypatch):
    """Test create_bicep_deployment_group when deployment fails."""
    mock_create_rg = MagicMock()
    monkeypatch.setattr(az, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=False))
    monkeypatch.setattr(az, 'run', mock_run)
    mock_open_func = mock_open()
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(builtins, 'print', MagicMock())
    # Mock os functions for file path operations
    monkeypatch.setattr('os.getcwd', MagicMock(return_value='/test/dir'))
    monkeypatch.setattr('os.path.exists', MagicMock(return_value=True))
    monkeypatch.setattr('os.path.basename', MagicMock(return_value='test-dir'))

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

    # Capture console logger output (console functions emit via stdlib logging)
    captured_output = io.StringIO()
    logger = logging.getLogger('console')
    previous_level = logger.level
    previous_handlers = list(logger.handlers)
    previous_propagate = logger.propagate

    handler = logging.StreamHandler(captured_output)
    handler.setFormatter(logging.Formatter('%(message)s'))

    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    try:
        print_info('Test info message')
        print_ok('Test success message')
        print_warning('Test warning message')
        print_error('Test error message')
        print_message('Test message')
        print_val('Test key', 'Test value')

        output = captured_output.getvalue()
        assert 'Test info message' in output
        assert 'Test success message' in output
        assert 'Test warning message' in output
        assert 'Test error message' in output
        assert 'Test message' in output
        assert 'Test key' in output
        assert 'Test value' in output
    finally:
        logger.handlers = previous_handlers
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate


def test_test_url_preflight_check_with_frontdoor(monkeypatch):
    """Test URL preflight check when Front Door is available."""
    monkeypatch.setattr(az, 'get_frontdoor_url', lambda x, y: 'https://test.azurefd.net')
    monkeypatch.setattr('console.print_message', lambda x, **kw: None)

    result = utils.test_url_preflight_check(INFRASTRUCTURE.AFD_APIM_PE, 'test-rg', 'https://apim.com')
    assert result == 'https://test.azurefd.net'


def test_test_url_preflight_check_no_frontdoor(monkeypatch):
    """Test URL preflight check when Front Door is not available."""
    monkeypatch.setattr(az, 'get_frontdoor_url', lambda x, y: None)
    monkeypatch.setattr('console.print_message', lambda x, **kw: None)

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


def test_wait_for_apim_blob_permissions_success(monkeypatch):
    """Test wait_for_apim_blob_permissions with successful wait."""
    monkeypatch.setattr(az, 'check_apim_blob_permissions', lambda *args: True)
    monkeypatch.setattr('console.print_info', lambda x: None)
    monkeypatch.setattr('console.print_ok', lambda x: None)
    monkeypatch.setattr('console.print_error', lambda x: None)

    result = utils.wait_for_apim_blob_permissions('test-apim', 'test-storage', 'test-rg', 1)
    assert result is True


def test_wait_for_apim_blob_permissions_failure(monkeypatch):
    """Test wait_for_apim_blob_permissions with failed wait."""
    monkeypatch.setattr(az, 'check_apim_blob_permissions', lambda *args: False)
    monkeypatch.setattr('console.print_info', lambda x: None)
    monkeypatch.setattr('console.print_ok', lambda x: None)
    monkeypatch.setattr('console.print_error', lambda x: None)

    result = utils.wait_for_apim_blob_permissions('test-apim', 'test-storage', 'test-rg', 1)
    assert result is False


def test_read_policy_xml_with_sample_name_explicit(monkeypatch):
    """Test read_policy_xml with explicit sample name."""
    mock_project_root = Path('/mock/project/root')
    monkeypatch.setattr('utils.get_project_root', lambda: mock_project_root)

    xml_content = '<policies><inbound><base /></inbound></policies>'
    m = mock_open(read_data=xml_content)
    monkeypatch.setattr(builtins, 'open', m)

    result = utils.read_policy_xml('policy.xml', sample_name='test-sample')
    assert result == xml_content


def test_read_policy_xml_with_named_values_formatting(monkeypatch):
    """Test read_policy_xml with named values formatting."""
    xml_content = '<policy><key>{jwt_key}</key></policy>'
    expected = '<policy><key>{{JwtSigningKey}}</key></policy>'
    m = mock_open(read_data=xml_content)
    monkeypatch.setattr(builtins, 'open', m)

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

    m = mock_open(read_data=json.dumps(mock_roles))
    monkeypatch.setattr(builtins, 'open', m)

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
#    Note: Tests for _find_infrastructure_instances and _query_and_select_infrastructure
#    removed as they test private implementation details. The standalone function
#    find_infrastructure_instances() is tested in test_azure_resources.py
# ------------------------------

# End of Infrastructure Selection Tests - NotebookHelper._query_and_select_infrastructure tests removed
# as they test private implementation details. The public behavior is tested through integration tests.

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

def test_infrastructure_notebook_helper_create_with_index_retry(monkeypatch):
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

    # Mock subprocess execution to succeed
    class MockProcess:
        def __init__(self, *args, **kwargs):
            self.returncode = 0
            self.stdout = iter(['Mock deployment output\n', 'Success!\n'])

        def wait(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr('subprocess.Popen', MockProcess)
    monkeypatch.setattr(utils, 'find_project_root', lambda: 'c:\\mock\\root')

    # Mock print functions to avoid output during testing
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Should succeed after retrying with index 3
    result = helper.create_infrastructure()
    assert result is True
    assert helper.index == 3  # Verify index was updated

def test_infrastructure_notebook_helper_create_with_recursive_retry(monkeypatch):
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

    # Mock subprocess execution to succeed
    class MockProcess:
        def __init__(self, *args, **kwargs):
            self.returncode = 0
            self.stdout = iter(['Mock deployment output\n'])

        def wait(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr('subprocess.Popen', MockProcess)
    monkeypatch.setattr(utils, 'find_project_root', lambda: 'c:\\mock\\root')
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Should succeed after retrying with index 3
    result = helper.create_infrastructure()
    assert result is True
    assert helper.index == 3  # Verify final index

def test_infrastructure_notebook_helper_create_user_cancellation(monkeypatch):
    """Test InfrastructureNotebookHelper.create_infrastructure when user cancels during retry."""

    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock resource group to exist (triggering prompt)
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda rg_name: True)

    # Mock the prompt to return cancellation (option 3)
    monkeypatch.setattr(utils, '_prompt_for_infrastructure_update', lambda rg_name: (False, None))
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Should raise SystemExit when user cancels
    with pytest.raises(SystemExit) as exc_info:
        helper.create_infrastructure()

    assert "User cancelled deployment" in str(exc_info.value)

def test_infrastructure_notebook_helper_create_keyboard_interrupt_during_prompt(monkeypatch):
    """Test InfrastructureNotebookHelper.create_infrastructure when KeyboardInterrupt occurs during prompt."""

    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock resource group to exist (triggering prompt)
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda rg_name: True)

    # Mock the prompt to raise KeyboardInterrupt
    def mock_prompt(rg_name):
        raise KeyboardInterrupt()

    monkeypatch.setattr(utils, '_prompt_for_infrastructure_update', mock_prompt)
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Should raise SystemExit when KeyboardInterrupt occurs
    with pytest.raises(SystemExit) as exc_info:
        helper.create_infrastructure()

    assert "User cancelled deployment" in str(exc_info.value)

def test_infrastructure_notebook_helper_create_eof_error_during_prompt(monkeypatch):
    """Test InfrastructureNotebookHelper.create_infrastructure when EOFError occurs during prompt."""

    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock resource group to exist (triggering prompt)
    monkeypatch.setattr(az, 'does_resource_group_exist', lambda rg_name: True)

    # Mock the prompt to raise EOFError
    def mock_prompt(rg_name):
        raise EOFError()

    monkeypatch.setattr(utils, '_prompt_for_infrastructure_update', mock_prompt)
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Should raise SystemExit when EOFError occurs
    with pytest.raises(SystemExit) as exc_info:
        helper.create_infrastructure()

    assert "User cancelled deployment" in str(exc_info.value)

def test_deploy_sample_with_infrastructure_selection(monkeypatch):
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
    monkeypatch.setattr('console.print_error', lambda *args, **kwargs: None)
    monkeypatch.setattr('console.print_ok', lambda *args, **kwargs: None)
    monkeypatch.setattr('console.print_val', lambda *args, **kwargs: None)

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

    def test_validate_infrastructure_supported():
        """Test validate_infrastructure with supported infrastructure."""
        # Should return None for supported infra
        result = utils.validate_infrastructure(INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM])
        assert result is None

    def test_validate_infrastructure_unsupported():
        """Test validate_infrastructure with unsupported infrastructure."""
        # Should raise ValueError for unsupported infra
        with pytest.raises(ValueError, match='Unsupported infrastructure'):
            utils.validate_infrastructure(INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.APIM_ACA])

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
        assert len(run_calls) == 0

    def test_find_infrastructure_instances_no_results(monkeypatch):
        """Test find_infrastructure_instances when no instances found."""
        monkeypatch.setattr(az, 'run', lambda cmd, *args, **kwargs: utils.Output(False, 'no results'))
    
        result = az.find_infrastructure_instances(INFRASTRUCTURE.SIMPLE_APIM)
        assert result == []

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
