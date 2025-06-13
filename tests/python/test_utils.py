import pytest
from apimtypes import INFRASTRUCTURE
import os
import builtins
from pathlib import Path
from unittest.mock import MagicMock, mock_open
import utils
from apimtypes import INFRASTRUCTURE

# ------------------------------
#    is_string_json
# ------------------------------

@pytest.mark.parametrize(
    "input_str,expected",
    [
        ("{\"a\": 1}", True),
        ("[1, 2, 3]", True),
        ("not json", False),
        ("{\"a\": 1", False),
        ("", False),
        (None, False),
        (123, False),
    ]
)
def test_is_string_json(input_str, expected):
    assert utils.is_string_json(input_str) is expected

# ------------------------------
#    get_account_info
# ------------------------------

def test_get_account_info_success(monkeypatch):
    mock_json = {
        'user': {'name': 'testuser'},
        'tenantId': 'tenant',
        'id': 'subid'
    }
    mock_output = MagicMock(success=True, json_data=mock_json)
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: mock_output)
    result = utils.get_account_info()
    assert result == ('testuser', 'tenant', 'subid')

def test_get_account_info_failure(monkeypatch):
    mock_output = MagicMock(success=False, json_data=None)
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: mock_output)
    with pytest.raises(Exception):
        utils.get_account_info()

# ------------------------------
#    get_deployment_name
# ------------------------------

def test_get_deployment_name(monkeypatch):
    monkeypatch.setattr(os, 'getcwd', lambda: '/foo/bar/baz')
    assert utils.get_deployment_name() == 'baz'

def test_get_deployment_name_error(monkeypatch):
    monkeypatch.setattr(os, 'getcwd', lambda: '')
    with pytest.raises(RuntimeError):
        utils.get_deployment_name()

# ------------------------------
#    get_frontdoor_url
# ------------------------------

def test_get_frontdoor_url_success(monkeypatch):
    mock_profile = [{"name": "afd1"}]
    mock_endpoints = [{"hostName": "foo.azurefd.net"}]
    def run_side_effect(cmd, *a, **kw):
        if 'profile list' in cmd:
            return MagicMock(success=True, json_data=mock_profile)
        if 'endpoint list' in cmd:
            return MagicMock(success=True, json_data=mock_endpoints)
        return MagicMock(success=False, json_data=None)
    monkeypatch.setattr(utils, 'run', run_side_effect)
    url = utils.get_frontdoor_url(INFRASTRUCTURE.AFD_APIM_PE, 'rg')
    assert url == 'https://foo.azurefd.net'

def test_get_frontdoor_url_none(monkeypatch):
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: MagicMock(success=False, json_data=None))
    url = utils.get_frontdoor_url(INFRASTRUCTURE.AFD_APIM_PE, 'rg')
    assert url is None

# ------------------------------
#    get_infra_rg_name & get_rg_name
# ------------------------------

def test_get_infra_rg_name(monkeypatch):
    class DummyInfra:
        value = 'foo'
    monkeypatch.setattr(utils, 'validate_infrastructure', lambda x: x)
    assert utils.get_infra_rg_name(DummyInfra) == 'apim-infra-foo'
    assert utils.get_infra_rg_name(DummyInfra, 2) == 'apim-infra-foo-2'

def test_get_rg_name():
    assert utils.get_rg_name('foo') == 'apim-sample-foo'
    assert utils.get_rg_name('foo', 3) == 'apim-sample-foo-3'

# ------------------------------
#    run
# ------------------------------

def test_run_success(monkeypatch):
    monkeypatch.setattr('subprocess.check_output', lambda *a, **kw: b'{"a": 1}')
    out = utils.run('echo', print_command_to_run=False)
    assert out.success is True
    assert out.json_data == {"a": 1}

def test_run_failure(monkeypatch):
    class DummyErr(Exception):
        output = b'fail'
    def fail(*a, **kw):
        raise DummyErr()
    monkeypatch.setattr('subprocess.check_output', fail)
    out = utils.run('bad', print_command_to_run=False)
    assert out.success is False
    assert isinstance(out.text, str)

# ------------------------------
#    create_resource_group & does_resource_group_exist
# ------------------------------

def test_does_resource_group_exist(monkeypatch):
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: MagicMock(success=True))
    assert utils.does_resource_group_exist('foo') is True
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: MagicMock(success=False))
    assert utils.does_resource_group_exist('foo') is False

def test_create_resource_group(monkeypatch):
    called = {}
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda rg: False)
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: called.setdefault('info', True))
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: called.setdefault('run', True))
    utils.create_resource_group('foo', 'bar')
    assert called['info'] and called['run']

# ------------------------------
#    read_policy_xml
# ------------------------------

def test_read_policy_xml_success(monkeypatch):
    """Test reading a valid XML file returns its contents."""
    xml_content = '<policies><inbound><base /></inbound></policies>'
    m = mock_open(read_data=xml_content)
    monkeypatch.setattr(builtins, 'open', m)
    # Use full path to avoid sample name auto-detection
    result = utils.read_policy_xml('/path/to/dummy.xml')
    assert result == xml_content

def test_read_policy_xml_file_not_found(monkeypatch):
    """Test reading a missing XML file raises FileNotFoundError."""
    def raise_fnf(*args, **kwargs):
        raise FileNotFoundError('File not found')
    monkeypatch.setattr(builtins, 'open', raise_fnf)
    with pytest.raises(FileNotFoundError):
        utils.read_policy_xml('/path/to/missing.xml')

def test_read_policy_xml_empty_file(monkeypatch):
    """Test reading an empty XML file returns an empty string."""
    m = mock_open(read_data='')
    monkeypatch.setattr(builtins, 'open', m)
    result = utils.read_policy_xml('/path/to/empty.xml')
    assert result == ''

def test_read_policy_xml_with_named_values(monkeypatch):
    """Test reading policy XML with named values formatting."""
    xml_content = '<policy><validate-jwt><issuer-signing-keys><key>{jwt_signing_key}</key></issuer-signing-keys></validate-jwt></policy>'
    m = mock_open(read_data=xml_content)
    monkeypatch.setattr(builtins, 'open', m)
    
    # Mock the auto-detection to return 'authX'
    def mock_inspect_currentframe():
        frame = MagicMock()
        caller_frame = MagicMock()
        caller_frame.f_globals = {'__file__': '/project/samples/authX/create.ipynb'}
        frame.f_back = caller_frame
        return frame
    
    monkeypatch.setattr('inspect.currentframe', mock_inspect_currentframe)
    monkeypatch.setattr('apimtypes._get_project_root', lambda: Path('/project'))
    
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
    monkeypatch.setattr(builtins, 'open', m)
    result = utils.read_policy_xml('/full/path/to/policy.xml')
    assert result == xml_content

def test_read_policy_xml_auto_detection_failure(monkeypatch):
    """Test that auto-detection failure provides helpful error."""
    xml_content = '<policy></policy>'
    m = mock_open(read_data=xml_content)
    monkeypatch.setattr(builtins, 'open', m)
    
    # Mock the auto-detection to fail
    def mock_inspect_currentframe():
        frame = MagicMock()
        caller_frame = MagicMock()
        caller_frame.f_globals = {'__file__': '/project/notsamples/test/create.ipynb'}
        frame.f_back = caller_frame
        return frame
    
    monkeypatch.setattr('inspect.currentframe', mock_inspect_currentframe)
    
    with pytest.raises(ValueError, match="Could not auto-detect sample name"):
        utils.read_policy_xml('policy.xml', {'key': 'value'})

# ------------------------------
#    cleanup_resources (smoke)
# ------------------------------

def test_cleanup_resources_smoke(monkeypatch):
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: MagicMock(success=True, json_data={}))
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_error', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_message', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_ok', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_warning', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_val', lambda *a, **kw: None)
    # Direct private method call for legacy test (should still work)
    utils._cleanup_resources(INFRASTRUCTURE.SIMPLE_APIM.value, 'rg')

def test_cleanup_infra_deployment_single(monkeypatch):
    monkeypatch.setattr(utils, '_cleanup_resources', lambda deployment_name, rg_name: None)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, None)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, 1)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1, 2])

def test_cleanup_deployment_single(monkeypatch):
    monkeypatch.setattr(utils, '_cleanup_resources', lambda deployment_name, rg_name: None)
    utils.cleanup_deployment('foo', None)
    utils.cleanup_deployment('foo', 1)
    utils.cleanup_deployment('foo', [1, 2])

# ------------------------------
#    EXTRACT_JSON EDGE CASES
# ------------------------------

@pytest.mark.parametrize(
    "input_val,expected",
    [
        (None, None),
        (123, None),
        ([], None),
        ("", None),
        ("   ", None),
        ("not json", None),
        ("{\"a\": 1}", {"a": 1}),
        ("[1, 2, 3]", [1, 2, 3]),
        ("  {\"a\": 1}  ", {"a": 1}),
        ("prefix {\"foo\": 42} suffix", {"foo": 42}),
        ("prefix [1, 2, 3] suffix", [1, 2, 3]),
        ("{\"a\": 1}{\"b\": 2}", {"a": 1}),  # Only first JSON object
        ("[1, 2, 3][4, 5, 6]", [1, 2, 3]),  # Only first JSON array
        ("{\"a\": 1,}", None),  # Trailing comma
        ("[1, 2,]", None),  # Trailing comma in array
        ("{\"a\": [1, 2, {\"b\": 3}]}", {"a": [1, 2, {"b": 3}]}),
        ("\n\t{\"a\": 1}\n", {"a": 1}),
        ("{\"a\": \"b \\u1234\"}", {"a": "b \u1234"}),
        ("{\"a\": 1} [2, 3]", {"a": 1}),  # Object before array
        ("[2, 3] {\"a\": 1}", [2, 3]),  # Array before object
        ("{\"a\": 1, \"b\": {\"c\": 2}}", {"a": 1, "b": {"c": 2}}),
        ("{\"a\": 1, \"b\": [1, 2, 3]}", {"a": 1, "b": [1, 2, 3]}),
        ("\n\n[\n1, 2, 3\n]\n", [1, 2, 3]),
        ("{\"a\": 1, \"b\": null}", {"a": 1, "b": None}),
        ("{\"a\": true, \"b\": false}", {"a": True, "b": False}),
        ("{\"a\": 1, \"b\": \"c\"}", {"a": 1, "b": "c"}),
        ("{\"a\": 1, \"b\": [1, 2, {\"c\": 3}]} ", {"a": 1, "b": [1, 2, {"c": 3}]}),
        ("{\"a\": 1, \"b\": [1, 2, {\"c\": 3, \"d\": [4, 5]}]} ", {"a": 1, "b": [1, 2, {"c": 3, "d": [4, 5]}]}),
    ]
)
def test_extract_json_edge_cases(input_val, expected):
    """Test extract_json with a wide range of edge cases and malformed input."""
    result = utils.extract_json(input_val)
    assert result == expected

def test_extract_json_large_object():
    """Test extract_json with a large JSON object."""
    large_obj = {"a": list(range(1000)), "b": {"c": "x" * 1000}}
    import json
    s = json.dumps(large_obj)
    assert utils.extract_json(s) == large_obj

def test_extract_json_multiple_json_types():
    """Test extract_json returns the first valid JSON (object or array) in the string."""
    s = '[1,2,3]{"a": 1}'
    assert utils.extract_json(s) == [1, 2, 3]
    s2 = '{"a": 1}[1,2,3]'
    assert utils.extract_json(s2) == {"a": 1}

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
    assert "Unsupported infrastructure" in str(exc.value)

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
    result = utils.build_infrastructure_tags("test-infra")
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
#    create_resource_group
# ------------------------------

def test_create_resource_group_not_exists_no_tags(monkeypatch):
    """Test create_resource_group when resource group doesn't exist and no tags provided."""
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: False)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', MagicMock())
    
    utils.create_resource_group('test-rg', 'eastus')
    
    # Verify the correct command was called
    expected_cmd = 'az group create --name test-rg --location eastus --tags source=apim-sample'
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    assert actual_cmd == expected_cmd

def test_create_resource_group_not_exists_with_tags(monkeypatch):
    """Test create_resource_group when resource group doesn't exist and tags are provided."""
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: False)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', MagicMock())
    
    tags = {'infrastructure': 'simple-apim', 'env': 'dev'}
    utils.create_resource_group('test-rg', 'eastus', tags)
    
    # Verify the correct command was called with tags
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    assert 'source=apim-sample' in actual_cmd
    assert 'infrastructure="simple-apim"' in actual_cmd
    assert 'env="dev"' in actual_cmd

def test_create_resource_group_already_exists(monkeypatch):
    """Test create_resource_group when resource group already exists."""
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: True)
    mock_run = MagicMock()
    monkeypatch.setattr(utils, 'run', mock_run)
    
    utils.create_resource_group('existing-rg', 'eastus')
    
    # Verify run was not called since RG already exists
    mock_run.assert_not_called()

def test_create_resource_group_tags_with_special_chars(monkeypatch):
    """Test create_resource_group with tags containing special characters."""
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: False)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', MagicMock())
    
    tags = {'description': 'This is a "test" environment', 'owner': 'john@company.com'}
    utils.create_resource_group('test-rg', 'eastus', tags)
    
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    # Check that quotes are properly escaped
    assert 'description="This is a \\"test\\" environment"' in actual_cmd
    assert 'owner="john@company.com"' in actual_cmd

def test_create_resource_group_tags_with_numeric_values(monkeypatch):
    """Test create_resource_group with tags containing numeric values."""
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: False)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', MagicMock())
    
    tags = {'cost-center': 12345, 'version': 1.0}
    utils.create_resource_group('test-rg', 'eastus', tags)
    
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    # Numeric values should be converted to strings
    assert 'cost-center="12345"' in actual_cmd
    assert 'version="1.0"' in actual_cmd


# ------------------------------
#    create_bicep_deployment_group
# ------------------------------

def test_create_bicep_deployment_group_with_enum(monkeypatch):
    """Test create_bicep_deployment_group with INFRASTRUCTURE enum."""
    mock_create_rg = MagicMock()
    monkeypatch.setattr(utils, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    mock_open_func = mock_open()
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(builtins, 'print', MagicMock())
    # Mock os functions for file path operations
    monkeypatch.setattr('os.getcwd', MagicMock(return_value='/test/dir'))
    monkeypatch.setattr('os.path.exists', MagicMock(return_value=True))
    monkeypatch.setattr('os.path.basename', MagicMock(return_value='test-dir'))
    
    bicep_params = {'param1': {'value': 'test'}}
    rg_tags = {'infrastructure': 'simple-apim'}
    
    result = utils.create_bicep_deployment_group(
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
    monkeypatch.setattr(utils, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    mock_open_func = mock_open()
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(builtins, 'print', MagicMock())
    # Mock os functions for file path operations
    monkeypatch.setattr('os.getcwd', MagicMock(return_value='/test/dir'))
    monkeypatch.setattr('os.path.exists', MagicMock(return_value=True))
    monkeypatch.setattr('os.path.basename', MagicMock(return_value='test-dir'))
    
    bicep_params = {'param1': {'value': 'test'}}
    
    result = utils.create_bicep_deployment_group(
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
    monkeypatch.setattr(utils, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    mock_open_func = mock_open()
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(builtins, 'print', MagicMock())
    
    # Mock os functions for file path operations
    # For this test, we want to simulate being in an infrastructure directory
    monkeypatch.setattr('os.getcwd', MagicMock(return_value='/test/dir/infrastructure/apim-aca'))
    
    def mock_exists(path):
        # Only return True for the main.bicep in the infrastructure directory, not in current dir
        if path.endswith('main.bicep') and 'infrastructure' in path:
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
    mock_open_func.assert_called_once_with(expected_path, 'w')
    
    # Verify the correct JSON structure was written
    written_content = ''.join(call.args[0] for call in mock_open_func().write.call_args_list)
    import json
    written_data = json.loads(written_content)
    
    assert written_data['$schema'] == "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#"
    assert written_data['contentVersion'] == "1.0.0.0"
    assert written_data['parameters'] == bicep_params

def test_create_bicep_deployment_group_no_tags(monkeypatch):
    """Test create_bicep_deployment_group without tags."""
    mock_create_rg = MagicMock()
    monkeypatch.setattr(utils, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
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
    monkeypatch.setattr(utils, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=False))
    monkeypatch.setattr(utils, 'run', mock_run)
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
    import io
    import sys
    
    # Capture stdout
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    try:
        # Test all print functions
        utils.print_info("Test info message")
        utils.print_success("Test success message")
        utils.print_warning("Test warning message")
        utils.print_error("Test error message")
        utils.print_message("Test message")
        utils.print_val("Test key", "Test value")
        
        output = captured_output.getvalue()
        assert "Test info message" in output
        assert "Test success message" in output
        assert "Test warning message" in output
        assert "Test error message" in output
        assert "Test message" in output
        assert "Test key" in output
        assert "Test value" in output
    finally:
        sys.stdout = sys.__stdout__


def test_test_url_preflight_check_with_frontdoor(monkeypatch):
    """Test URL preflight check when Front Door is available."""
    monkeypatch.setattr(utils, 'get_frontdoor_url', lambda x, y: 'https://test.azurefd.net')
    monkeypatch.setattr(utils, 'print_message', lambda x, **kw: None)
    
    result = utils.test_url_preflight_check(INFRASTRUCTURE.AFD_APIM_PE, 'test-rg', 'https://apim.com')
    assert result == 'https://test.azurefd.net'


def test_test_url_preflight_check_no_frontdoor(monkeypatch):
    """Test URL preflight check when Front Door is not available."""
    monkeypatch.setattr(utils, 'get_frontdoor_url', lambda x, y: None)
    monkeypatch.setattr(utils, 'print_message', lambda x, **kw: None)
    
    result = utils.test_url_preflight_check(INFRASTRUCTURE.SIMPLE_APIM, 'test-rg', 'https://apim.com')
    assert result == 'https://apim.com'


def test_determine_policy_path_filename_mode(monkeypatch):
    """Test determine_policy_path with filename mode."""
    import inspect
    from pathlib import Path
    
    # Mock the project root
    mock_project_root = Path('/mock/project/root')
    monkeypatch.setattr('apimtypes._get_project_root', lambda: mock_project_root)
    
    # Mock current frame to simulate being in samples/test-sample
    class MockFrame:
        def __init__(self):
            self.f_globals = {'__file__': '/mock/project/root/samples/test-sample/create.ipynb'}
    
    def mock_currentframe():
        frame = MockFrame()
        frame.f_back = frame
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


def test_check_apim_blob_permissions_success(monkeypatch):
    """Test check_apim_blob_permissions with successful permissions."""
    def mock_run_success(cmd, **kwargs):
        if 'az apim api operation' in cmd:
            return utils.Output(success=True, text='{"statusCode": 200}')
        return utils.Output(success=True, text='{}')

    monkeypatch.setattr(utils, 'run', mock_run_success)
    monkeypatch.setattr(utils, 'print_info', lambda x: None)
    monkeypatch.setattr(utils, 'print_success', lambda x: None)

    result = utils.check_apim_blob_permissions('test-apim', 'test-storage', 'test-rg', 1)
    assert result is True


def test_check_apim_blob_permissions_failure(monkeypatch):
    """Test check_apim_blob_permissions with failed permissions."""
    def mock_run_failure(cmd, **kwargs):
        if 'az apim api operation' in cmd:
            return utils.Output(success=True, text='{"statusCode": 403}')
        return utils.Output(success=True, text='{}')

    monkeypatch.setattr(utils, 'run', mock_run_failure)
    monkeypatch.setattr(utils, 'print_info', lambda x: None)
    monkeypatch.setattr(utils, 'print_warning', lambda x: None)
    monkeypatch.setattr('time.sleep', lambda x: None)

    result = utils.check_apim_blob_permissions('test-apim', 'test-storage', 'test-rg', 1)
    assert result is False


def test_wait_for_apim_blob_permissions_success(monkeypatch):
    """Test wait_for_apim_blob_permissions with successful wait."""
    monkeypatch.setattr(utils, 'check_apim_blob_permissions', lambda *args: True)
    monkeypatch.setattr(utils, 'print_info', lambda x: None)
    monkeypatch.setattr(utils, 'print_success', lambda x: None)
    monkeypatch.setattr(utils, 'print_error', lambda x: None)
    
    result = utils.wait_for_apim_blob_permissions('test-apim', 'test-storage', 'test-rg', 1)
    assert result is True


def test_wait_for_apim_blob_permissions_failure(monkeypatch):
    """Test wait_for_apim_blob_permissions with failed wait."""
    monkeypatch.setattr(utils, 'check_apim_blob_permissions', lambda *args: False)
    monkeypatch.setattr(utils, 'print_info', lambda x: None)
    monkeypatch.setattr(utils, 'print_success', lambda x: None)
    monkeypatch.setattr(utils, 'print_error', lambda x: None)
    
    result = utils.wait_for_apim_blob_permissions('test-apim', 'test-storage', 'test-rg', 1)
    assert result is False


def test_read_policy_xml_with_sample_name_explicit(monkeypatch):
    """Test read_policy_xml with explicit sample name."""
    from pathlib import Path
    mock_project_root = Path('/mock/project/root')
    monkeypatch.setattr('apimtypes._get_project_root', lambda: mock_project_root)
    
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
    "infra_type,expected_suffix",
    [
        (INFRASTRUCTURE.SIMPLE_APIM, "simple-apim"),
        (INFRASTRUCTURE.AFD_APIM_PE, "afd-apim-pe"),
        (INFRASTRUCTURE.APIM_ACA, "apim-aca"),
    ]
)
def test_get_infra_rg_name_different_types(infra_type, expected_suffix, monkeypatch):
    """Test get_infra_rg_name with different infrastructure types."""
    monkeypatch.setattr(utils, 'validate_infrastructure', lambda x: x)
    result = utils.get_infra_rg_name(infra_type)
    assert result == f'apim-infra-{expected_suffix}'


def test_create_bicep_deployment_group_for_sample_success(monkeypatch):
    """Test create_bicep_deployment_group_for_sample success case."""
    mock_output = utils.Output(success=True, text='{"outputs": {"test": "value"}}')
    
    def mock_create_bicep(sample_name, rg_name, location, params, tags=None):
        return mock_output
    
    monkeypatch.setattr(utils, 'create_bicep_deployment_group', mock_create_bicep)
    monkeypatch.setattr(utils, 'build_infrastructure_tags', lambda x: [])
    
    result = utils.create_bicep_deployment_group_for_sample('test-sample', 'test-rg', 'eastus', {})
    assert result.success is True


def test_extract_json_invalid_input():
    """Test extract_json with various invalid inputs."""
    assert utils.extract_json(None) is None
    assert utils.extract_json(123) is None
    assert utils.extract_json([1, 2, 3]) is None
    assert utils.extract_json("not json at all") is None


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
    import base64
    try:
        decoded = base64.b64decode(b64_key)
        assert len(decoded) == len(key)  # Decoded should match original length
    except Exception:
        pytest.fail("Base64 key is not valid base64")


def test_output_class_functionality():
    """Test the Output class properties and methods."""
    # Test successful output with deployment structure
    output = utils.Output(success=True, text='{"properties": {"outputs": {"test": {"value": "value"}}}}')
    assert output.success is True
    assert output.get('test') == 'value'
    assert output.get('missing', 'default') == 'default'
    
    # Test failed output
    output = utils.Output(success=False, text='error')
    assert output.success is False
    assert output.get('test') is None


def test_run_command_with_error_suppression(monkeypatch):
    """Test run command with error output suppression."""
    def mock_subprocess_run(cmd, **kwargs):
        class MockResult:
            returncode = 1
            stdout = "test output"
            stderr = "test error"
        return MockResult()
    
    monkeypatch.setattr('subprocess.run', mock_subprocess_run)
    
    output = utils.run("test command", print_errors=False, print_output=False)
    assert output.success is False
    assert output.text == "test output"


def test_bicep_directory_determination_edge_cases(monkeypatch, tmp_path):
    """Test edge cases in Bicep directory determination."""
    # Test when no main.bicep exists anywhere
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setattr(os, 'getcwd', lambda: str(empty_dir))
    
    # Should fall back to current directory + infrastructure/nonexistent
    result = utils._determine_bicep_directory("nonexistent")
    expected = os.path.join(str(empty_dir), "infrastructure", "nonexistent")
    assert result == expected


def test_create_resource_group_edge_cases(monkeypatch):
    """Test create resource group with edge cases."""
    # Test with empty tags
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: False)
    
    def mock_run_with_tags(*args, **kwargs):
        cmd = args[0]
        assert '--tags' in cmd  # Should include tags (with default source=apim-sample)
        return utils.Output(success=True, text='{}')
    
    monkeypatch.setattr(utils, 'run', mock_run_with_tags)
    
    utils.create_resource_group('test-rg', 'eastus', {})  # Empty dict, function doesn't return anything


# ------------------------------
#    ROLE AND PERMISSION TESTS
# ------------------------------

def test_get_azure_role_guid_comprehensive(monkeypatch):
    """Test get_azure_role_guid with comprehensive scenarios."""
    # Mock the azure-roles.json file content
    mock_roles = {
        "Storage Blob Data Reader": "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1",
        "Storage Account Contributor": "17d1049b-9a84-46fb-8f53-869881c3d3ab"
    }
    
    m = mock_open(read_data=json.dumps(mock_roles))
    monkeypatch.setattr(builtins, 'open', m)
    
    # Test valid role
    result = utils.get_azure_role_guid("Storage Blob Data Reader")
    assert result == "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1"
    
    # Test case sensitivity - function is case sensitive, so this should return None
    result = utils.get_azure_role_guid("storage blob data reader")
    assert result is None
    
    # Test invalid role
    result = utils.get_azure_role_guid("Nonexistent Role")
    assert result is None


def test_cleanup_functions_comprehensive(monkeypatch):
    """Test cleanup functions with various scenarios."""
    monkeypatch.setattr(utils, 'run', lambda x, **kw: utils.Output(success=True, text='{}'))
    
    # Test _cleanup_resources (private function)
    utils._cleanup_resources('test-deployment', 'test-rg')  # Should not raise
    
    # Test cleanup_deployment 
    utils.cleanup_deployment('test-deployment')  # Should not raise
    
    # Test cleanup_infra_deployment with string
    utils.cleanup_infra_deployment('test-deployment')  # Should not raise
    
    # Test cleanup_deployment with string
    utils.cleanup_deployment('test-deployment')  # Should not raise


import json
