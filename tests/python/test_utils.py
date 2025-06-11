import pytest
from apimtypes import INFRASTRUCTURE
import os
import builtins
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
    result = utils.read_policy_xml('dummy.xml')
    assert result == xml_content

def test_read_policy_xml_file_not_found(monkeypatch):
    """Test reading a missing XML file raises FileNotFoundError."""
    def raise_fnf(*args, **kwargs):
        raise FileNotFoundError('File not found')
    monkeypatch.setattr(builtins, 'open', raise_fnf)
    with pytest.raises(FileNotFoundError):
        utils.read_policy_xml('missing.xml')

def test_read_policy_xml_empty_file(monkeypatch):
    """Test reading an empty XML file returns an empty string."""
    m = mock_open(read_data='')
    monkeypatch.setattr(builtins, 'open', m)
    result = utils.read_policy_xml('empty.xml')
    assert result == ''
    
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
    
    bicep_params = {
        'apiManagementName': {'value': 'test-apim'},
        'location': {'value': 'eastus'}
    }
    
    utils.create_bicep_deployment_group(
        'test-rg', 'eastus', INFRASTRUCTURE.APIM_ACA, bicep_params, 'custom-params.json'
    )
    
    # Verify file was opened for writing
    mock_open_func.assert_called_once_with('custom-params.json', 'w')
    
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
    
    bicep_params = {'param1': {'value': 'test'}}
    
    result = utils.create_bicep_deployment_group('test-rg', 'eastus', 'test-deployment', bicep_params)
    
    # Should still create resource group
    mock_create_rg.assert_called_once()
    
    # Result should indicate failure
    assert result.success is False

# ------------------------------
#    ADDITIONAL COVERAGE TESTS
# ------------------------------

def test_build_infrastructure_tags_basic():
    """Test basic infrastructure tags creation."""
    result = utils.build_infrastructure_tags(INFRASTRUCTURE.SIMPLE_APIM)
    assert "infrastructure" in result
    assert result["infrastructure"] == "simple-apim"

def test_build_infrastructure_tags_with_custom():
    """Test infrastructure tags with custom tags."""
    custom = {"environment": "test", "owner": "team"}
    result = utils.build_infrastructure_tags(INFRASTRUCTURE.SIMPLE_APIM, custom)
    assert result["infrastructure"] == "simple-apim"
    assert result["environment"] == "test"
    assert result["owner"] == "team"

def test_get_azure_role_guid_valid_role(monkeypatch):
    """Test getting valid Azure role GUID."""
    mock_open_func = mock_open(read_data='{"Contributor": "role-guid-123"}')
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(os.path, 'exists', lambda x: True)
    
    result = utils.get_azure_role_guid("Contributor")
    assert result == "role-guid-123"

def test_get_azure_role_guid_invalid_role(monkeypatch):
    """Test getting invalid Azure role GUID."""
    mock_open_func = mock_open(read_data='{"Contributor": "role-guid-123"}')
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(os.path, 'exists', lambda x: True)
    
    result = utils.get_azure_role_guid("NonExistentRole")
    assert result is None

def test_get_azure_role_guid_file_not_found(monkeypatch):
    """Test getting Azure role GUID when file doesn't exist."""
    monkeypatch.setattr(os.path, 'exists', lambda x: False)
    
    result = utils.get_azure_role_guid("Contributor")
    assert result is None

def test_create_bicep_deployment_group_success(monkeypatch):
    """Test successful Bicep deployment group creation."""
    mock_output = MagicMock(success=True, json_data={"id": "deployment-id"})
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: mock_output)
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: True)
    
    result = utils.create_bicep_deployment_group(
        "test-rg", "eastus", INFRASTRUCTURE.SIMPLE_APIM, {"param1": "value1"}
    )
    assert result.success is True

def test_create_bicep_deployment_group_creates_rg(monkeypatch):
    """Test Bicep deployment creates resource group if not exists."""
    mock_output = MagicMock(success=True, json_data={"id": "deployment-id"})
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: mock_output)
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: False)
    monkeypatch.setattr(utils, 'create_resource_group', lambda *a, **kw: None)
    
    result = utils.create_bicep_deployment_group(
        "test-rg", "eastus", INFRASTRUCTURE.SIMPLE_APIM, {"param1": "value1"}
    )
    assert result.success is True

def test_create_resource_group_with_tags(monkeypatch):
    """Test creating resource group with tags."""
    mock_output = MagicMock(success=True)
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: mock_output)
    
    utils.create_resource_group("test-rg", "eastus", {"env": "test"})
    # Test passes if no exception is raised

def test_read_and_modify_policy_xml_success(monkeypatch):
    """Test reading and modifying policy XML."""
    xml_content = "<policy><backend-url>{OLD_URL}</backend-url></policy>"
    mock_open_func = mock_open(read_data=xml_content)
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    
    replacements = {"OLD_URL": "https://new-url.com"}
    result = utils.read_and_modify_policy_xml("test.xml", replacements)
    assert "https://new-url.com" in result
    assert "{OLD_URL}" not in result

def test_read_and_modify_policy_xml_no_replacements(monkeypatch):
    """Test reading policy XML with no replacements."""
    xml_content = "<policy><backend-url>https://api.com</backend-url></policy>"
    mock_open_func = mock_open(read_data=xml_content)
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    
    result = utils.read_and_modify_policy_xml("test.xml", {})
    assert result == xml_content

def test_cleanup_infra_deployments_multiple_indexes(monkeypatch):
    """Test cleanup of multiple infrastructure deployments."""
    monkeypatch.setattr(utils, '_cleanup_resources', lambda x, y: None)
    monkeypatch.setattr(utils, 'get_infra_rg_name', lambda x, y: f"rg-{y}")
    
    # Should not raise exception
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1, 2, 3])

def test_cleanup_deployment_string_input(monkeypatch):
    """Test cleanup deployment with string deployment name."""
    monkeypatch.setattr(utils, '_cleanup_resources', lambda x, y: None)
    monkeypatch.setattr(utils, 'get_rg_name', lambda x, y: f"rg-{y}")
    
    # Should not raise exception
    utils.cleanup_deployment("test-deployment", 1)

def test_print_functions_output(capsys):
    """Test various print utility functions."""
    utils.print_ok("Success message")
    utils.print_error("Error message")
    utils.print_info("Info message")
    utils.print_val("Label", "Value message")
    
    captured = capsys.readouterr()
    assert "Success message" in captured.out
    assert "Error message" in captured.out
    assert "Info message" in captured.out
    assert "Label" in captured.out
    assert "Value message" in captured.out

def test_print_functions_with_options(capsys):
    """Test print functions with formatting options."""
    utils.print_ok("Test", blank_above=True)
    utils.print_val("Label", "Test", val_below=True)
    
    captured = capsys.readouterr()
    assert "Test" in captured.out
