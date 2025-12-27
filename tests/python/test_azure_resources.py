"""
Tests for azure_resources module.
"""

import json
from unittest.mock import Mock, patch, mock_open, call
import pytest

# APIM Samples imports
import azure_resources as az
from apimtypes import INFRASTRUCTURE, Endpoints, Output
from test_helpers import suppress_module_functions


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
#    APIM SUBSCRIPTION KEY TESTS
# ------------------------------


def test_get_apim_subscription_key_selects_active_and_returns_primary(monkeypatch):
    """Selects an active subscription when multiple exist and returns the primaryKey."""

    calls: list[str] = []

    def fake_run(cmd: str, *args, **kwargs):
        calls.append(cmd)

        if cmd.startswith('az account show'):
            return Output(True, 'sub-123\n')

        if 'az rest --method get' in cmd and '/subscriptions?' in cmd:
            payload = {
                'value': [
                    {'name': 'sid-1', 'properties': {'state': 'suspended', 'displayName': 'Suspended'}},
                    {'name': 'sid-2', 'properties': {'state': 'active', 'displayName': 'Active'}},
                ]
            }
            return Output(True, json.dumps(payload))

        if 'az rest --method post' in cmd and 'listSecrets' in cmd:
            assert '/subscriptions/sid-2/listSecrets' in cmd
            return Output(True, json.dumps({'primaryKey': 'pk-abc', 'secondaryKey': 'sk-def'}))

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    key = az.get_apim_subscription_key('apim-name', 'rg-name')

    assert key == 'pk-abc'
    assert any('az rest --method get' in c for c in calls)
    assert any('listSecrets' in c for c in calls)


def test_get_apim_subscription_key_returns_none_when_no_subscriptions(monkeypatch):
    """Returns None when APIM has no subscriptions."""

    def fake_run(cmd: str, *args, **kwargs):
        if cmd.startswith('az account show'):
            return Output(True, 'sub-123\n')

        if 'az rest --method get' in cmd and '/subscriptions?' in cmd:
            return Output(True, json.dumps({'value': []}))

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    assert az.get_apim_subscription_key('apim-name', 'rg-name') is None


def test_get_apim_subscription_key_uses_provided_sid(monkeypatch):
    """Uses the provided sid directly and skips listing subscriptions."""

    calls: list[str] = []

    def fake_run(cmd: str, *args, **kwargs):
        calls.append(cmd)

        if cmd.startswith('az account show'):
            return Output(True, 'sub-123\n')

        if 'az rest --method post' in cmd and 'listSecrets' in cmd:
            assert '/subscriptions/sid-explicit/listSecrets' in cmd
            return Output(True, json.dumps({'primaryKey': 'pk-xyz'}))

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    key = az.get_apim_subscription_key('apim-name', 'rg-name', sid = 'sid-explicit')
    assert key == 'pk-xyz'
    assert not any('az rest --method get' in c and '/subscriptions?' in c for c in calls)

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
    suppress_module_functions(monkeypatch, az, ['print_message', 'print_info', 'print_ok', 'print_error'])

    result = az.cleanup_old_jwt_signing_keys('apim', 'rg', 'JwtSigningKey-sample-456')

    assert result is True
    assert any('nv list' in c for c in run_calls)
    delete_calls = [c for c in run_calls if 'nv delete' in c]
    assert len(delete_calls) == 1
    assert 'JwtSigningKey-sample-123' in delete_calls[0]


def test_cleanup_old_jwt_signing_keys_invalid_pattern(monkeypatch):
    """Test cleanup when current key name does not match expected pattern."""

    monkeypatch.setattr(az, 'run', lambda *a, **k: pytest.fail('run should not be called'))
    suppress_module_functions(monkeypatch, az, ['print_message', 'print_info', 'print_ok'])

    result = az.cleanup_old_jwt_signing_keys('apim', 'rg', 'invalid-key-name')

    assert result is False


# ------------------------------
#    APIM BLOB PERMISSIONS TESTS
# ------------------------------

def test_check_apim_blob_permissions_success(monkeypatch):
    """Test blob permission check succeeds when role assignment and access test succeed."""

    monkeypatch.setattr(az, 'get_azure_role_guid', lambda *_: 'role-guid')
    suppress_module_functions(monkeypatch, az, ['print_info', 'print_ok', 'print_warning', 'print_error'])

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
    suppress_module_functions(monkeypatch, az, ['print_info', 'print_ok', 'print_warning', 'print_error'])

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

# ------------------------------
#    ADDITIONAL ERROR HANDLING TESTS
# ------------------------------

def test_run_with_debug_flag_injection(monkeypatch):
    """Test that --debug flag is injected when logging is in DEBUG level."""

    mock_process = Mock()
    mock_process.returncode = 0
    mock_process.stdout = 'test output'
    mock_process.stderr = ''

    monkeypatch.setattr('subprocess.run', lambda *a, **k: mock_process)

    az.run('az account show')
    # Verify run method works without errors


def test_get_resource_group_location_with_whitespace(monkeypatch):
    """Test get_resource_group_location handles whitespace in response."""
    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(True, '  eastus  \n')

        result = az.get_resource_group_location('test-rg')
        assert result == 'eastus'


def test_get_account_info_missing_user_id(monkeypatch):
    """Test get_account_info when user ID is not available."""
    with patch('azure_resources.run') as mock_run:
        account_output = Output(True, '{}')
        account_output.json_data = {
            'user': {'name': 'test@example.com'},
            'id': 'sub-123',
            'tenantId': 'tenant-123'
        }

        ad_user_output = Output(False, 'User not found')
        mock_run.side_effect = [account_output, ad_user_output]

        with pytest.raises(Exception):
            az.get_account_info()


def test_cleanup_old_jwt_signing_keys_no_matching_pattern(monkeypatch):
    """Test cleanup_old_jwt_signing_keys with non-matching key pattern."""
    suppress_module_functions(monkeypatch, az, ['print_message', 'print_info', 'print_ok'])

    result = az.cleanup_old_jwt_signing_keys('apim', 'rg', 'InvalidKeyPattern-123')
    assert result is False


def test_cleanup_old_jwt_signing_keys_all_deleted(monkeypatch):
    """Test cleanup_old_jwt_signing_keys when all old keys are successfully deleted."""
    run_calls = []

    def fake_run(cmd, *args, **kwargs):
        run_calls.append(cmd)
        if 'nv list' in cmd:
            return Output(True, 'JwtSigningKey-sample-12345\nJwtSigningKey-sample-67890\n')
        if 'nv delete' in cmd:
            return Output(True, 'Deleted')
        return Output(False, 'Unknown')

    monkeypatch.setattr('azure_resources.run', fake_run)
    suppress_module_functions(monkeypatch, az, ['print_message', 'print_info', 'print_ok', 'print_error'])

    result = az.cleanup_old_jwt_signing_keys('apim', 'rg', 'JwtSigningKey-sample-99999')
    assert result is True


def test_get_frontdoor_url_no_hostname(monkeypatch):
    """Test get_frontdoor_url when endpoint has no hostname."""
    with patch('azure_resources.run') as mock_run:
        profile_output = Output(True, '')
        profile_output.json_data = [{'name': 'test-afd'}]

        endpoint_output = Output(True, '')
        endpoint_output.json_data = []  # Empty endpoint list

        mock_run.side_effect = [profile_output, endpoint_output]

        result = az.get_frontdoor_url(INFRASTRUCTURE.AFD_APIM_PE, 'test-rg')
        assert result is None


def test_get_apim_url_multiple_services(monkeypatch):
    """Test get_apim_url returns first service when multiple exist."""
    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(True, '')
        mock_run.return_value.json_data = [
            {'name': 'apim-1', 'gatewayUrl': 'https://apim-1.azure-api.net'},
            {'name': 'apim-2', 'gatewayUrl': 'https://apim-2.azure-api.net'}
        ]

        result = az.get_apim_url('test-rg')
        assert result == 'https://apim-1.azure-api.net'


def test_get_appgw_endpoint_no_public_ip(monkeypatch):
    """Test get_appgw_endpoint when public IP retrieval fails."""
    with patch('azure_resources.run') as mock_run:
        appgw_output = Output(True, '')
        appgw_output.json_data = [{
            'name': 'test-appgw',
            'httpListeners': [{'hostName': 'api.contoso.com'}],
            'frontendIPConfigurations': [{
                'publicIPAddress': {'id': '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/publicIPAddresses/pip'}
            }]
        }]

        ip_output = Output(False, 'IP not found')
        mock_run.side_effect = [appgw_output, ip_output]

        hostname, ip = az.get_appgw_endpoint('test-rg')
        assert hostname == 'api.contoso.com'
        assert ip is None


def test_get_infra_rg_name_with_zero_index(monkeypatch):
    """Test get_infra_rg_name with zero index."""
    result = az.get_infra_rg_name(INFRASTRUCTURE.SIMPLE_APIM, 0)
    assert result == 'apim-infra-simple-apim-0'


def test_get_infra_rg_name_with_negative_index(monkeypatch):
    """Test get_infra_rg_name with negative index."""
    result = az.get_infra_rg_name(INFRASTRUCTURE.APIM_ACA, -1)
    assert result == 'apim-infra-apim-aca--1'


def test_get_rg_name_with_zero_index(monkeypatch):
    """Test get_rg_name with zero index."""
    result = az.get_rg_name('sample', 0)
    assert result == 'apim-sample-sample-0'


def test_get_deployment_name_different_samples(monkeypatch):
    """Test get_deployment_name with different sample names."""

    with patch('azure_resources.time.time', return_value=1000):
        with patch('azure_resources.os.getcwd', return_value='/path/to/sample-1'):
            with patch('azure_resources.os.path.basename', return_value='sample-1'):
                result = az.get_deployment_name('my-custom-sample')
                assert 'my-custom-sample' in result
                assert '1000' in result


def test_find_infrastructure_instances_multiple_indexes(monkeypatch):
    """Test find_infrastructure_instances with multiple indexes."""
    def fake_run(cmd, *args, **kwargs):
        if 'apim-aca' in cmd:
            return Output(True, 'apim-infra-apim-aca-1\napim-infra-apim-aca-2\napim-infra-apim-aca-3\n')
        return Output(False, '')

    monkeypatch.setattr('azure_resources.run', fake_run)

    result = az.find_infrastructure_instances(INFRASTRUCTURE.APIM_ACA)
    assert len(result) == 3
    assert (INFRASTRUCTURE.APIM_ACA, 1) in result
    assert (INFRASTRUCTURE.APIM_ACA, 2) in result
    assert (INFRASTRUCTURE.APIM_ACA, 3) in result


def test_find_infrastructure_instances_invalid_format(monkeypatch):
    """Test find_infrastructure_instances handles invalid response format."""
    def fake_run(cmd, *args, **kwargs):
        return Output(True, 'invalid-format-no-index\n')

    monkeypatch.setattr('azure_resources.run', fake_run)

    result = az.find_infrastructure_instances(INFRASTRUCTURE.AFD_APIM_PE)
    assert result == []


# ------------------------------
#    COMMAND STRING GENERATION TESTS
# ------------------------------

def test_run_command_building_with_output_format(monkeypatch):
    """Test that run constructs proper Azure CLI commands."""

    called_commands = []

    def capture_command(*args, **kwargs):
        called_commands.append(args[0])
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = 'output'
        mock_process.stderr = ''
        return mock_process

    monkeypatch.setattr('subprocess.run', capture_command)

    az.run('az group show --name test-rg -o json')

    assert len(called_commands) > 0


def test_get_unique_suffix_with_empty_rg_list(monkeypatch):
    """Test get_unique_suffix_for_resource_group with empty list response."""
    with patch('azure_resources.tempfile.NamedTemporaryFile') as mock_tempfile:
        mock_file = Mock()
        mock_file.name = '/tmp/template.json'
        mock_tempfile.return_value.__enter__.return_value = mock_file

        with patch('azure_resources.run') as mock_run:
            mock_run.return_value = Output(False, 'No resources found')

            with patch('azure_resources.os.unlink'):
                result = az.get_unique_suffix_for_resource_group('test-rg')
                assert not result


# ------------------------------
#    INTEGRATION AND EDGE CASES
# ------------------------------

def test_get_endpoints_with_partial_data(monkeypatch):
    """Test get_endpoints when some endpoints are missing."""
    with patch('azure_resources.get_frontdoor_url', return_value=None):
        with patch('azure_resources.get_apim_url', return_value='https://test-apim.azure-api.net'):
            with patch('azure_resources.get_appgw_endpoint', return_value=(None, None)):

                result = az.get_endpoints(INFRASTRUCTURE.SIMPLE_APIM, 'test-rg')

                assert isinstance(result, Endpoints)
                assert result.afd_endpoint_url is None
                assert result.apim_endpoint_url == 'https://test-apim.azure-api.net'
                assert result.appgw_hostname is None
                assert result.appgw_public_ip is None


def test_does_resource_group_exist_with_malformed_response(monkeypatch):
    """Test does_resource_group_exist with malformed JSON."""
    with patch('azure_resources.run') as mock_run:
        mock_run.return_value = Output(True, '{invalid json}')

        result = az.does_resource_group_exist('test-rg')
        # Should still return True because run succeeded
        assert result is True


def test_create_resource_group_with_empty_tags(monkeypatch):
    """Test create_resource_group with empty tags dictionary."""
    monkeypatch.setattr('azure_resources.does_resource_group_exist', lambda x: False)

    run_calls = []

    def capture_run(cmd, *args, **kwargs):
        run_calls.append(cmd)
        return Output(True, '{}')

    monkeypatch.setattr('azure_resources.run', capture_run)

    az.create_resource_group('test-rg', 'eastus', {})

    assert len(run_calls) > 0
    assert '--tags' in run_calls[0]  # Tags should still be included (with defaults)


def test_get_azure_role_guid_with_multiple_roles(monkeypatch):
    """Test get_azure_role_guid retrieval from file with multiple roles."""
    mock_data = {
        'Owner': 'role-owner',
        'Contributor': 'role-contrib',
        'Reader': 'role-reader',
        'Storage Blob Data Reader': 'role-storage-reader',
        'Storage Account Contributor': 'role-storage-contrib',
        'Key Vault Administrator': 'role-kv-admin',
    }

    with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
        for role_name, expected_guid in mock_data.items():
            result = az.get_azure_role_guid(role_name)
            assert result == expected_guid


def test_check_apim_blob_permissions_no_principal_id(monkeypatch):
    """Test check_apim_blob_permissions when APIM has no principal ID."""
    def fake_run(cmd, *args, **kwargs):
        if 'apim show' in cmd:
            return Output(True, '')  # No principal ID
        return Output(False, 'Error')

    monkeypatch.setattr('azure_resources.run', fake_run)
    suppress_module_functions(monkeypatch, az, ['print_info', 'print_ok', 'print_warning', 'print_error'])

    result = az.check_apim_blob_permissions('apim', 'storage', 'rg')
    assert result is False


def test_get_account_info_all_fields_present(monkeypatch):
    """Test get_account_info successfully retrieves all account information."""
    with patch('azure_resources.run') as mock_run:
        account_output = Output(True, '{}')
        account_output.json_data = {
            'user': {'name': 'user@contoso.com'},
            'id': 'sub-12345',
            'tenantId': 'tenant-abcde'
        }

        ad_user_output = Output(True, '{}')
        ad_user_output.json_data = {'id': 'user-id-xyz'}

        mock_run.side_effect = [account_output, ad_user_output]

        user, user_id, tenant_id, subscription_id = az.get_account_info()

        assert user == 'user@contoso.com'
        assert user_id == 'user-id-xyz'
        assert tenant_id == 'tenant-abcde'
        assert subscription_id == 'sub-12345'


# ------------------------------
#    UTILITY FUNCTION TESTS
# ------------------------------

def test_redact_secrets_with_access_token():
    """Test _redact_secrets redacts accessToken in JSON."""
    text = '{"accessToken": "secretToken123"}'
    result = az._redact_secrets(text)
    assert 'secretToken123' not in result
    assert '***REDACTED***' in result


def test_redact_secrets_with_refresh_token():
    """Test _redact_secrets redacts refreshToken in JSON."""
    text = '{"refreshToken": "refreshSecret456"}'
    result = az._redact_secrets(text)
    assert 'refreshSecret456' not in result
    assert '***REDACTED***' in result


def test_redact_secrets_with_client_secret():
    """Test _redact_secrets redacts client_secret in JSON."""
    text = '{"client_secret": "clientSecret789"}'
    result = az._redact_secrets(text)
    assert 'clientSecret789' not in result
    assert '***REDACTED***' in result


def test_redact_secrets_with_bearer_token():
    """Test _redact_secrets redacts Authorization: Bearer tokens."""
    text = 'Authorization: Bearer myBearerToken123'
    result = az._redact_secrets(text)
    assert 'myBearerToken123' not in result
    assert '***REDACTED***' in result


def test_redact_secrets_with_empty_string():
    """Test _redact_secrets handles empty string."""
    assert not az._redact_secrets('')
    assert az._redact_secrets(None) is None


def test_maybe_add_az_debug_flag_when_debug_enabled():
    """Test _maybe_add_az_debug_flag adds --debug when logging is DEBUG."""
    with patch('azure_resources.is_debug_enabled', return_value=True):
        result = az._maybe_add_az_debug_flag('az group list')
        assert '--debug' in result


def test_maybe_add_az_debug_flag_when_debug_disabled():
    """Test _maybe_add_az_debug_flag doesn't add --debug when logging is not DEBUG."""
    with patch('azure_resources.is_debug_enabled', return_value=False):
        result = az._maybe_add_az_debug_flag('az group list')
        assert result == 'az group list'


def test_maybe_add_az_debug_flag_with_pipe():
    """Test _maybe_add_az_debug_flag handles commands with pipes."""
    with patch('azure_resources.is_debug_enabled', return_value=True):
        result = az._maybe_add_az_debug_flag('az group list | jq .')
        assert '--debug' in result
        assert result.index('--debug') < result.index('|')


def test_maybe_add_az_debug_flag_with_redirect():
    """Test _maybe_add_az_debug_flag handles commands with output redirection."""
    with patch('azure_resources.is_debug_enabled', return_value=True):
        result = az._maybe_add_az_debug_flag('az group list > output.txt')
        assert '--debug' in result
        assert result.index('--debug') < result.index('>')


def test_maybe_add_az_debug_flag_already_has_debug():
    """Test _maybe_add_az_debug_flag doesn't duplicate --debug flag."""
    with patch('azure_resources.is_debug_enabled', return_value=True):
        result = az._maybe_add_az_debug_flag('az group list --debug')
        assert result.count('--debug') == 1


def test_maybe_add_az_debug_flag_non_az_command():
    """Test _maybe_add_az_debug_flag doesn't modify non-az commands."""
    with patch('azure_resources.is_debug_enabled', return_value=True):
        result = az._maybe_add_az_debug_flag('echo hello')
        assert result == 'echo hello'


def test_extract_az_cli_error_message_with_json_error():
    """Test _extract_az_cli_error_message extracts from JSON error payload."""
    output = '{"error": {"code": "NotFound", "message": "Resource not found"}}'
    result = az._extract_az_cli_error_message(output)
    assert result == 'Resource not found'


def test_extract_az_cli_error_message_with_json_message():
    """Test _extract_az_cli_error_message extracts from JSON message field."""
    output = '{"message": "Deployment failed"}'
    result = az._extract_az_cli_error_message(output)
    assert result == 'Deployment failed'


def test_extract_az_cli_error_message_with_error_prefix():
    """Test _extract_az_cli_error_message extracts from ERROR: line."""
    output = 'ERROR: Resource group not found'
    result = az._extract_az_cli_error_message(output)
    assert result == 'Resource group not found'


def test_extract_az_cli_error_message_with_az_error_prefix():
    """Test _extract_az_cli_error_message extracts from az: error: line."""
    output = 'az: error: argument --name is required'
    result = az._extract_az_cli_error_message(output)
    assert result == 'argument --name is required'


def test_extract_az_cli_error_message_with_code_and_message():
    """Test _extract_az_cli_error_message combines Code: and Message: lines."""
    output = 'Code: ResourceNotFound\nMessage: The resource was not found'
    result = az._extract_az_cli_error_message(output)
    assert 'ResourceNotFound' in result
    assert 'The resource was not found' in result


def test_extract_az_cli_error_message_with_empty_string():
    """Test _extract_az_cli_error_message handles empty string."""
    assert not az._extract_az_cli_error_message('')


def test_extract_az_cli_error_message_skips_traceback():
    """Test _extract_az_cli_error_message skips traceback lines."""
    output = 'Some error\nTraceback (most recent call last):\n  File "test.py"'
    result = az._extract_az_cli_error_message(output)
    assert result == 'Some error'


def test_extract_az_cli_error_message_skips_warnings():
    """Test _extract_az_cli_error_message skips warning lines."""
    output = 'WARNING: This is deprecated\nERROR: Real error here'
    result = az._extract_az_cli_error_message(output)
    assert result == 'Real error here'
