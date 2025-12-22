"""
Tests for azure_resources module.
"""

import json
from unittest.mock import Mock, patch, mock_open, call
import pytest

# APIM Samples imports
import azure_resources as az
from apimtypes import INFRASTRUCTURE, Endpoints, Output


# ------------------------------
#    AZURE ROLE TESTS
# ------------------------------

def test_get_azure_role_guid_success():
    """Test successful retrieval of Azure role GUID."""

    mock_data = {'Contributor': 'role-guid-12345', 'Reader': 'role-guid-67890'}

    with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
        result = az.get_azure_role_guid('Contributor')

        assert result == 'role-guid-12345'


def test_get_azure_role_guid_failure():
    """Test get_azure_role_guid returns None when file not found."""

    # Mock os.path functions to return a non-existent path
    with patch('azure_resources.os.path.abspath', return_value='/nonexistent/path'):
        with patch('azure_resources.os.path.dirname', return_value='/nonexistent'):
            with patch('azure_resources.os.path.join', return_value='/nonexistent/azure-roles.json'):
                with patch('azure_resources.os.path.normpath', return_value='/nonexistent/azure-roles.json'):
                    result = az.get_azure_role_guid('NonExistentRole')

                    assert result is None

# ------------------------------
#    RESOURCE GROUP TESTS
# ------------------------------

def test_does_resource_group_exist_true():
    """Test checking if resource group exists - returns True."""

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(True, '{"name": "test-rg"}')

        result = az.does_resource_group_exist('test-rg')

        assert result is True
        mock_run.assert_called_once_with('az group show --name test-rg -o json')


def test_does_resource_group_exist_false():
    """Test checking if resource group exists - returns False."""

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(False, 'ResourceGroupNotFound')

        result = az.does_resource_group_exist('nonexistent-rg')

        assert result is False


def test_get_resource_group_location_success():
    """Test successful retrieval of resource group location."""

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(True, 'eastus2\n')

        result = az.get_resource_group_location('test-rg')

        assert result == 'eastus2'
        mock_run.assert_called_once_with('az group show --name test-rg --query "location" -o tsv')


def test_get_resource_group_location_failure():
    """Test get_resource_group_location returns None on failure."""

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(False, 'error message')

        result = az.get_resource_group_location('nonexistent-rg')

        assert result is None


def test_get_resource_group_location_empty():
    """Test get_resource_group_location returns None on empty response."""

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(True, '')

        result = az.get_resource_group_location('test-rg')

        assert result is None


# ------------------------------
#    ACCOUNT INFO TESTS
# ------------------------------

def test_get_account_info_success():
    """Test successful retrieval of account information."""

    with patch('azure_resources.run') as mock_run:
        account_output = Output(True, '{}')
        account_output.json_data = {
            'user': {'name': 'test.user@example.com'},
            'id': 'sub-12345',
            'tenantId': 'tenant-12345'
        }

        ad_user_output = Output(True, '{}')
        ad_user_output.json_data = {'id': 'user-id-12345'}

        mock_run.side_effect = [account_output, ad_user_output]

        current_user, current_user_id, tenant_id, subscription_id = az.get_account_info()

        assert current_user == 'test.user@example.com'
        assert current_user_id == 'user-id-12345'
        assert tenant_id == 'tenant-12345'
        assert subscription_id == 'sub-12345'


def test_get_account_info_failure():
    """Test get_account_info raises exception on failure."""

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(False, 'authentication error')

        with pytest.raises(Exception) as exc_info:
            az.get_account_info()

        assert 'Failed to retrieve account information' in str(exc_info.value)


def test_get_account_info_no_json():
    """Test get_account_info raises exception when no JSON data."""

    with patch('azure_resources.run') as mock_run:
        output = Output(True, 'some text')
        output.json_data = None
        mock_run.return_value = output

        with pytest.raises(Exception) as exc_info:
            az.get_account_info()

        assert 'Failed to retrieve account information' in str(exc_info.value)

# ------------------------------
#    JWT SIGNING KEY CLEANUP TESTS
# ------------------------------

def test_cleanup_old_jwt_signing_keys_success(monkeypatch):
    """Test successful cleanup of old JWT signing keys."""

    run_calls: list[str] = []

    def fake_run(cmd: str, *args, **kwargs):
        run_calls.append(cmd)

        if 'nv list' in cmd:
            return Output(True, 'JwtSigningKey-sample-123\nJwtSigningKey-sample-456\n')

        if 'nv delete' in cmd:
            # Only the non-current key should be deleted
            return Output(True, '')

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)
    monkeypatch.setattr(az, 'print_message', lambda *a, **k: None)
    monkeypatch.setattr(az, 'print_info', lambda *a, **k: None)
    monkeypatch.setattr(az, 'print_ok', lambda *a, **k: None)
    monkeypatch.setattr(az, 'print_error', lambda *a, **k: None)

    result = az.cleanup_old_jwt_signing_keys('apim', 'rg', 'JwtSigningKey-sample-456')

    assert result is True
    assert any('nv list' in c for c in run_calls)
    delete_calls = [c for c in run_calls if 'nv delete' in c]
    assert len(delete_calls) == 1
    assert 'JwtSigningKey-sample-123' in delete_calls[0]


def test_cleanup_old_jwt_signing_keys_invalid_pattern(monkeypatch):
    """Test cleanup when current key name does not match expected pattern."""

    monkeypatch.setattr(az, 'run', lambda *a, **k: pytest.fail('run should not be called'))
    monkeypatch.setattr(az, 'print_message', lambda *a, **k: None)
    monkeypatch.setattr(az, 'print_info', lambda *a, **k: None)
    monkeypatch.setattr(az, 'print_ok', lambda *a, **k: None)

    result = az.cleanup_old_jwt_signing_keys('apim', 'rg', 'invalid-key-name')

    assert result is False


# ------------------------------
#    APIM BLOB PERMISSIONS TESTS
# ------------------------------

def test_check_apim_blob_permissions_success(monkeypatch):
    """Test blob permission check succeeds when role assignment and access test succeed."""

    monkeypatch.setattr(az, 'get_azure_role_guid', lambda *_: 'role-guid')
    monkeypatch.setattr(az, 'print_info', lambda *a, **k: None)
    monkeypatch.setattr(az, 'print_ok', lambda *a, **k: None)
    monkeypatch.setattr(az, 'print_warning', lambda *a, **k: None)
    monkeypatch.setattr(az, 'print_error', lambda *a, **k: None)

    run_calls: list[str] = []

    def fake_run(cmd: str, *args, **kwargs):
        run_calls.append(cmd)

        if 'apim show' in cmd:
            return Output(True, 'principal-id\n')

        if 'storage account show' in cmd:
            return Output(True, 'notice\n/subscriptions/123/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage\n')

        if 'role assignment list' in cmd:
            return Output(True, 'assignment-id\n')

        if 'storage blob list' in cmd:
            return Output(True, 'blob-name\n')

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)
    monkeypatch.setattr(az.time, 'sleep', lambda *a, **k: None)

    result = az.check_apim_blob_permissions('apim', 'storage', 'rg', max_wait_minutes = 1)

    assert result is True
    assert any('role assignment list' in c for c in run_calls)
    assert any('storage blob list' in c for c in run_calls)


def test_check_apim_blob_permissions_missing_resource_id(monkeypatch):
    """Test blob permission check fails when storage account ID cannot be parsed."""

    monkeypatch.setattr(az, 'get_azure_role_guid', lambda *_: 'role-guid')
    monkeypatch.setattr(az, 'print_info', lambda *a, **k: None)
    monkeypatch.setattr(az, 'print_ok', lambda *a, **k: None)
    monkeypatch.setattr(az, 'print_warning', lambda *a, **k: None)
    monkeypatch.setattr(az, 'print_error', lambda *a, **k: None)

    def fake_run(cmd: str, *args, **kwargs):
        if 'apim show' in cmd:
            return Output(True, 'principal-id\n')

        if 'storage account show' in cmd:
            return Output(True, 'no matching id here')

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    result = az.check_apim_blob_permissions('apim', 'storage', 'rg')

    assert result is False


# ------------------------------
#    DEPLOYMENT NAME TESTS
# ------------------------------

@patch('azure_resources.time.time')
@patch('azure_resources.os.path.basename')
@patch('azure_resources.os.getcwd')
def test_get_deployment_name_with_directory(mock_getcwd, mock_basename, mock_time):
    """Test deployment name generation with explicit directory."""

    mock_time.return_value = 1234567890

    result = az.get_deployment_name('my-sample')

    assert result == 'deploy-my-sample-1234567890'
    mock_getcwd.assert_not_called()
    # Note: patching `os.path.basename` affects the shared `os.path` module, which is also
    # used by stdlib logging internals. Avoid strict call-count assertions here.


@patch('azure_resources.time.time')
@patch('azure_resources.os.path.basename')
@patch('azure_resources.os.getcwd')
def test_get_deployment_name_current_directory(mock_getcwd, mock_basename, mock_time):
    """Test deployment name generation using current directory."""

    mock_time.return_value = 1234567890
    mock_getcwd.return_value = '/path/to/current-folder'
    mock_basename.return_value = 'current-folder'

    result = az.get_deployment_name()

    assert result == 'deploy-current-folder-1234567890'
    mock_getcwd.assert_called_once()
    assert any(call_args.args == ('/path/to/current-folder',) for call_args in mock_basename.call_args_list)


# ------------------------------
#    FRONT DOOR TESTS
# ------------------------------

def test_get_frontdoor_url_afd_success():
    """Test successful Front Door URL retrieval."""

    with patch('azure_resources.run') as mock_run:
        # Create mock outputs
        profile_output = Output(True, '')
        profile_output.json_data = [{"name": "test-afd"}]

        endpoint_output = Output(True, '')
        endpoint_output.json_data = [{"hostName": "test.azurefd.net"}]

        mock_run.side_effect = [profile_output, endpoint_output]

        result = az.get_frontdoor_url(INFRASTRUCTURE.AFD_APIM_PE, 'test-rg')

        assert result == 'https://test.azurefd.net'

        expected_calls = [
            call('az afd profile list -g test-rg -o json'),
            call('az afd endpoint list -g test-rg --profile-name test-afd -o json')
        ]
        mock_run.assert_has_calls(expected_calls)


def test_get_frontdoor_url_wrong_infrastructure():
    """Test Front Door URL with wrong infrastructure type."""

    with patch('azure_resources.run') as mock_run:
        result = az.get_frontdoor_url(INFRASTRUCTURE.SIMPLE_APIM, 'test-rg')

        assert result is None
        mock_run.assert_not_called()


def test_get_frontdoor_url_no_profile():
    """Test Front Door URL when no profile found."""

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(False, 'No profiles found')

        result = az.get_frontdoor_url(INFRASTRUCTURE.AFD_APIM_PE, 'test-rg')

        assert result is None


def test_get_frontdoor_url_no_endpoints():
    """Test Front Door URL when profile exists but no endpoints."""

    with patch('azure_resources.run') as mock_run:
        profile_output = Output(True, '')
        profile_output.json_data = [{'name': 'test-afd'}]
        endpoint_output = Output(False, 'No endpoints found')
        mock_run.side_effect = [profile_output, endpoint_output]

        result = az.get_frontdoor_url(INFRASTRUCTURE.AFD_APIM_PE, 'test-rg')

        assert result is None


# ------------------------------
#    APIM URL TESTS
# ------------------------------

def test_get_apim_url_success():
    """Test successful APIM URL retrieval."""

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(True, '')
        mock_run.return_value.json_data = [{'name': 'test-apim', 'gatewayUrl': 'https://test-apim.azure-api.net'}]

        result = az.get_apim_url('test-rg')

        assert result == 'https://test-apim.azure-api.net'
        mock_run.assert_called_once_with('az apim list -g test-rg -o json')


def test_get_apim_url_failure():
    """Test APIM URL retrieval failure."""

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(False, 'No APIM services found')

        result = az.get_apim_url('test-rg')

        assert result is None


def test_get_apim_url_no_gateway():
    """Test APIM URL when service exists but no gateway URL."""

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(True, '')
        mock_run.return_value.json_data = [{'name': 'test-apim', 'gatewayUrl': None}]

        result = az.get_apim_url('test-rg')

        assert result is None


# ------------------------------
#    APPLICATION GATEWAY TESTS
# ------------------------------

def test_get_appgw_endpoint_success():
    """Test successful Application Gateway endpoint retrieval."""

    with patch('azure_resources.run') as mock_run:
        appgw_output = Output(True, '')
        appgw_output.json_data = [{
            'name': 'test-appgw',
            'httpListeners': [{'hostName': 'api.contoso.com'}],
            'frontendIPConfigurations': [{
                'publicIPAddress': {'id': '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/publicIPAddresses/test-pip'}
            }]
        }]
        ip_output = Output(True, '')
        ip_output.json_data = {'ipAddress': '1.2.3.4'}
        mock_run.side_effect = [appgw_output, ip_output]

        hostname, ip = az.get_appgw_endpoint('test-rg')

        assert hostname == 'api.contoso.com'
        assert ip == '1.2.3.4'

        expected_calls = [
            call('az network application-gateway list -g test-rg -o json'),
            call('az network public-ip show -g test-rg -n test-pip -o json')
        ]
        mock_run.assert_has_calls(expected_calls)


def test_get_appgw_endpoint_no_gateway():
    """Test Application Gateway endpoint when no gateway found."""

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(False, 'No gateways found')

        hostname, ip = az.get_appgw_endpoint('test-rg')

        assert hostname is None
        assert ip is None


def test_get_appgw_endpoint_no_listeners():
    """Test Application Gateway endpoint with no HTTP listeners."""

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(True, '')
        mock_run.return_value.json_data = [{
            'name': 'test-appgw',
            'httpListeners': [],
            'frontendIPConfigurations': []
        }]

        hostname, ip = az.get_appgw_endpoint('test-rg')

        assert hostname is None
        assert ip is None


# ------------------------------
#    NAMING FUNCTION TESTS
# ------------------------------

def test_get_infra_rg_name_without_index():
    """Test infrastructure resource group name generation without index."""

    result = az.get_infra_rg_name(INFRASTRUCTURE.SIMPLE_APIM)

    assert result == 'apim-infra-simple-apim'


def test_get_infra_rg_name_with_index():
    """Test infrastructure resource group name generation with index."""

    result = az.get_infra_rg_name(INFRASTRUCTURE.AFD_APIM_PE, 42)

    assert result == 'apim-infra-afd-apim-pe-42'


def test_get_rg_name_without_index():
    """Test sample resource group name generation without index."""

    result = az.get_rg_name('test-sample')

    assert result == 'apim-sample-test-sample'


def test_get_rg_name_with_index():
    """Test sample resource group name generation with index."""

    result = az.get_rg_name('test-sample', 5)

    assert result == 'apim-sample-test-sample-5'


# ------------------------------
#    UNIQUE SUFFIX TESTS
# ------------------------------

@patch('azure_resources.tempfile.NamedTemporaryFile')
@patch('azure_resources.time.time')
@patch('azure_resources.os.unlink')
def test_get_unique_suffix_for_resource_group_success(mock_unlink, mock_time, mock_tempfile):
    """Test successful unique suffix retrieval."""

    mock_time.return_value = 1234567890
    mock_file = Mock()
    mock_file.name = '/tmp/template.json'
    mock_tempfile.return_value.__enter__.return_value = mock_file

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(True, 'abc123def456\n')

        result = az.get_unique_suffix_for_resource_group('test-rg')

        assert result == 'abc123def456'
        mock_run.assert_called_once()
        mock_unlink.assert_called_once_with('/tmp/template.json')


@patch('azure_resources.tempfile.NamedTemporaryFile')
@patch('azure_resources.time.time')
@patch('azure_resources.os.unlink')
def test_get_unique_suffix_for_resource_group_failure(mock_unlink, mock_time, mock_tempfile):
    """Test unique suffix retrieval failure."""

    mock_time.return_value = 1234567890
    mock_file = Mock()
    mock_file.name = '/tmp/template.json'
    mock_tempfile.return_value.__enter__.return_value = mock_file

    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(False, 'Deployment failed')

        result = az.get_unique_suffix_for_resource_group('test-rg')

        assert not result
        mock_unlink.assert_called_once_with('/tmp/template.json')


# ------------------------------
#    ENDPOINTS TESTS
# ------------------------------

@patch('azure_resources.get_frontdoor_url')
@patch('azure_resources.get_apim_url')
@patch('azure_resources.get_appgw_endpoint')
def test_get_endpoints_success(mock_appgw, mock_apim, mock_afd):
    """Test successful endpoints retrieval."""

    mock_afd.return_value = 'https://test.azurefd.net'
    mock_apim.return_value = 'https://test-apim.azure-api.net'
    mock_appgw.return_value = ('api.contoso.com', '1.2.3.4')

    result = az.get_endpoints(INFRASTRUCTURE.AFD_APIM_PE, 'test-rg')

    assert isinstance(result, Endpoints)
    assert result.afd_endpoint_url == 'https://test.azurefd.net'
    assert result.apim_endpoint_url == 'https://test-apim.azure-api.net'
    assert result.appgw_hostname == 'api.contoso.com'
    assert result.appgw_public_ip == '1.2.3.4'

    mock_afd.assert_called_once_with(INFRASTRUCTURE.AFD_APIM_PE, 'test-rg')
    mock_apim.assert_called_once_with('test-rg')
    mock_appgw.assert_called_once_with('test-rg')
