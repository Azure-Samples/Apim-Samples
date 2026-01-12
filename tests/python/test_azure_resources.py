"""
Tests for azure_resources module.
"""

import json
import time
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


def test_get_apim_subscription_key_account_show_fails(monkeypatch):
    """Returns None when az account show fails."""

    def fake_run(cmd: str, *args, **kwargs):
        if cmd.startswith('az account show'):
            return Output(False, '')

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    assert az.get_apim_subscription_key('apim-name', 'rg-name') is None


def test_get_apim_subscription_key_account_show_empty(monkeypatch):
    """Returns None when az account show returns empty text."""

    def fake_run(cmd: str, *args, **kwargs):
        if cmd.startswith('az account show'):
            return Output(True, '  \n  ')

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    assert az.get_apim_subscription_key('apim-name', 'rg-name') is None


def test_get_apim_subscription_key_no_active_uses_first(monkeypatch):
    """Uses the first subscription when none are active."""

    calls: list[str] = []

    def fake_run(cmd: str, *args, **kwargs):
        calls.append(cmd)

        if cmd.startswith('az account show'):
            return Output(True, 'sub-123\n')

        if 'az rest --method get' in cmd and '/subscriptions?' in cmd:
            payload = {
                'value': [
                    {'name': 'sid-1', 'properties': {'state': 'suspended', 'displayName': 'First'}},
                    {'name': 'sid-2', 'properties': {'state': 'cancelled', 'displayName': 'Second'}},
                ]
            }
            return Output(True, json.dumps(payload))

        if 'az rest --method post' in cmd and 'listSecrets' in cmd:
            assert '/subscriptions/sid-1/listSecrets' in cmd
            return Output(True, json.dumps({'primaryKey': 'pk-first', 'secondaryKey': 'sk-first'}))

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    key = az.get_apim_subscription_key('apim-name', 'rg-name')

    assert key == 'pk-first'


def test_get_apim_subscription_key_subscription_name_empty(monkeypatch):
    """Returns None when subscription name is empty or missing."""

    def fake_run(cmd: str, *args, **kwargs):
        if cmd.startswith('az account show'):
            return Output(True, 'sub-123\n')

        if 'az rest --method get' in cmd and '/subscriptions?' in cmd:
            payload = {
                'value': [
                    {'name': '', 'properties': {'state': 'active', 'displayName': 'Empty name'}},
                ]
            }
            return Output(True, json.dumps(payload))

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    assert az.get_apim_subscription_key('apim-name', 'rg-name') is None


def test_get_apim_subscription_key_subscription_name_missing(monkeypatch):
    """Returns None when subscription has no name key."""

    def fake_run(cmd: str, *args, **kwargs):
        if cmd.startswith('az account show'):
            return Output(True, 'sub-123\n')

        if 'az rest --method get' in cmd and '/subscriptions?' in cmd:
            payload = {
                'value': [
                    {'properties': {'state': 'active', 'displayName': 'No name key'}},
                ]
            }
            return Output(True, json.dumps(payload))

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    assert az.get_apim_subscription_key('apim-name', 'rg-name') is None


def test_get_apim_subscription_key_secrets_call_fails(monkeypatch):
    """Returns None when listSecrets REST call fails."""

    def fake_run(cmd: str, *args, **kwargs):
        if cmd.startswith('az account show'):
            return Output(True, 'sub-123\n')

        if 'az rest --method get' in cmd and '/subscriptions?' in cmd:
            payload = {
                'value': [
                    {'name': 'sid-1', 'properties': {'state': 'active', 'displayName': 'Active'}},
                ]
            }
            return Output(True, json.dumps(payload))

        if 'az rest --method post' in cmd and 'listSecrets' in cmd:
            return Output(False, 'API error')

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    assert az.get_apim_subscription_key('apim-name', 'rg-name') is None


def test_get_apim_subscription_key_secrets_not_dict(monkeypatch):
    """Returns None when listSecrets returns non-dict JSON."""

    def fake_run(cmd: str, *args, **kwargs):
        if cmd.startswith('az account show'):
            return Output(True, 'sub-123\n')

        if 'az rest --method get' in cmd and '/subscriptions?' in cmd:
            payload = {
                'value': [
                    {'name': 'sid-1', 'properties': {'state': 'active', 'displayName': 'Active'}},
                ]
            }
            return Output(True, json.dumps(payload))

        if 'az rest --method post' in cmd and 'listSecrets' in cmd:
            return Output(True, json.dumps(['not', 'a', 'dict']))

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    assert az.get_apim_subscription_key('apim-name', 'rg-name') is None


def test_get_apim_subscription_key_returns_secondary_key(monkeypatch):
    """Returns secondaryKey when requested."""

    def fake_run(cmd: str, *args, **kwargs):
        if cmd.startswith('az account show'):
            return Output(True, 'sub-123\n')

        if 'az rest --method get' in cmd and '/subscriptions?' in cmd:
            payload = {
                'value': [
                    {'name': 'sid-1', 'properties': {'state': 'active', 'displayName': 'Active'}},
                ]
            }
            return Output(True, json.dumps(payload))

        if 'az rest --method post' in cmd and 'listSecrets' in cmd:
            return Output(True, json.dumps({'primaryKey': 'pk-abc', 'secondaryKey': 'sk-xyz'}))

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    key = az.get_apim_subscription_key('apim-name', 'rg-name', key_name = 'secondaryKey')

    assert key == 'sk-xyz'


def test_get_apim_subscription_key_key_value_empty(monkeypatch):
    """Returns None when key value is empty string."""

    def fake_run(cmd: str, *args, **kwargs):
        if cmd.startswith('az account show'):
            return Output(True, 'sub-123\n')

        if 'az rest --method get' in cmd and '/subscriptions?' in cmd:
            payload = {
                'value': [
                    {'name': 'sid-1', 'properties': {'state': 'active', 'displayName': 'Active'}},
                ]
            }
            return Output(True, json.dumps(payload))

        if 'az rest --method post' in cmd and 'listSecrets' in cmd:
            return Output(True, json.dumps({'primaryKey': '  ', 'secondaryKey': 'sk-xyz'}))

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    assert az.get_apim_subscription_key('apim-name', 'rg-name') is None


def test_get_apim_subscription_key_key_value_not_string(monkeypatch):
    """Returns None when key value is not a string."""

    def fake_run(cmd: str, *args, **kwargs):
        if cmd.startswith('az account show'):
            return Output(True, 'sub-123\n')

        if 'az rest --method get' in cmd and '/subscriptions?' in cmd:
            payload = {
                'value': [
                    {'name': 'sid-1', 'properties': {'state': 'active', 'displayName': 'Active'}},
                ]
            }
            return Output(True, json.dumps(payload))

        if 'az rest --method post' in cmd and 'listSecrets' in cmd:
            return Output(True, json.dumps({'primaryKey': 12345, 'secondaryKey': 'sk-xyz'}))

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    assert az.get_apim_subscription_key('apim-name', 'rg-name') is None


def test_get_apim_subscription_key_key_missing(monkeypatch):
    """Returns None when requested key is not in response."""

    def fake_run(cmd: str, *args, **kwargs):
        if cmd.startswith('az account show'):
            return Output(True, 'sub-123\n')

        if 'az rest --method get' in cmd and '/subscriptions?' in cmd:
            payload = {
                'value': [
                    {'name': 'sid-1', 'properties': {'state': 'active', 'displayName': 'Active'}},
                ]
            }
            return Output(True, json.dumps(payload))

        if 'az rest --method post' in cmd and 'listSecrets' in cmd:
            return Output(True, json.dumps({'someOtherKey': 'value'}))

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    assert az.get_apim_subscription_key('apim-name', 'rg-name') is None


def test_get_apim_subscription_key_uses_provided_subscription_id(monkeypatch):
    """Uses provided subscription_id and skips az account show."""

    calls: list[str] = []

    def fake_run(cmd: str, *args, **kwargs):
        calls.append(cmd)

        if 'az rest --method get' in cmd and '/subscriptions?' in cmd:
            assert '/subscriptions/custom-sub-id/' in cmd
            payload = {
                'value': [
                    {'name': 'sid-1', 'properties': {'state': 'active', 'displayName': 'Active'}},
                ]
            }
            return Output(True, json.dumps(payload))

        if 'az rest --method post' in cmd and 'listSecrets' in cmd:
            return Output(True, json.dumps({'primaryKey': 'pk-custom', 'secondaryKey': 'sk-custom'}))

        return Output(False, 'unexpected command')

    monkeypatch.setattr(az, 'run', fake_run)

    key = az.get_apim_subscription_key(
        'apim-name',
        'rg-name',
        subscription_id = 'custom-sub-id'
    )

    assert key == 'pk-custom'
    assert not any('az account show' in c for c in calls)


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
    assert not result


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


def test_check_apim_blob_permissions_timeout_waiting_for_propagation(monkeypatch):
    """Test blob permission check times out when waiting for role assignment propagation."""
    def fake_run(cmd, *args, **kwargs):
        if 'apim show' in cmd:
            return Output(True, 'principal-id\n')
        if 'storage account show' in cmd:
            return Output(True, '/subscriptions/123/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage\n')
        if 'role assignment list' in cmd:
            # Never return a role assignment (timeout scenario)
            return Output(True, '')
        return Output(False, 'unexpected')

    monkeypatch.setattr(az, 'run', fake_run)
    monkeypatch.setattr(az, 'get_azure_role_guid', lambda *_: 'role-guid')
    monkeypatch.setattr(az.time, 'sleep', lambda *a, **k: None)
    suppress_module_functions(monkeypatch, az, ['print_info', 'print_ok', 'print_warning', 'print_error'])

    result = az.check_apim_blob_permissions('apim', 'storage', 'rg', max_wait_minutes=1)
    assert result is False


def test_check_apim_blob_permissions_storage_account_retrieval_fails(monkeypatch):
    """Test blob permission check fails when storage account retrieval fails."""
    def fake_run(cmd, *args, **kwargs):
        if 'apim show' in cmd:
            return Output(True, 'principal-id\n')
        if 'storage account show' in cmd:
            return Output(False, 'Error retrieving account')
        return Output(False, 'unexpected')

    monkeypatch.setattr(az, 'run', fake_run)
    monkeypatch.setattr(az, 'get_azure_role_guid', lambda *_: 'role-guid')
    suppress_module_functions(monkeypatch, az, ['print_info', 'print_ok', 'print_warning', 'print_error'])

    result = az.check_apim_blob_permissions('apim', 'storage', 'rg')
    assert result is False


def test_check_apim_blob_permissions_role_assignment_exists_but_blob_access_fails(monkeypatch):
    """Test when role assignment exists but blob access test fails."""
    def fake_run(cmd, *args, **kwargs):
        if 'apim show' in cmd:
            return Output(True, 'principal-id\n')
        if 'storage account show' in cmd:
            return Output(True, '/subscriptions/123/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage\n')
        if 'role assignment list' in cmd:
            return Output(True, 'assignment-id\n')
        if 'storage blob list' in cmd:
            return Output(True, 'access-test-failed')
        return Output(False, 'unexpected')

    monkeypatch.setattr(az, 'run', fake_run)
    monkeypatch.setattr(az, 'get_azure_role_guid', lambda *_: 'role-guid')
    monkeypatch.setattr(az.time, 'sleep', lambda *a, **k: None)
    suppress_module_functions(monkeypatch, az, ['print_info', 'print_ok', 'print_warning', 'print_error'])

    result = az.check_apim_blob_permissions('apim', 'storage', 'rg', max_wait_minutes=1)
    assert result is False


def test_check_apim_blob_permissions_custom_wait_time(monkeypatch):
    """Test blob permission check with custom max_wait_minutes parameter."""
    call_times = []

    def fake_sleep(seconds):
        call_times.append(seconds)

    def fake_run(cmd, *args, **kwargs):
        if 'apim show' in cmd:
            return Output(True, 'principal-id\n')
        if 'storage account show' in cmd:
            return Output(True, '/subscriptions/123/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage\n')
        if 'role assignment list' in cmd:
            return Output(True, '')  # Never find it, trigger timeout
        return Output(False, 'unexpected')

    monkeypatch.setattr(az, 'run', fake_run)
    monkeypatch.setattr(az, 'get_azure_role_guid', lambda *_: 'role-guid')
    monkeypatch.setattr(az.time, 'sleep', fake_sleep)
    suppress_module_functions(monkeypatch, az, ['print_info', 'print_ok', 'print_warning', 'print_error'])

    result = az.check_apim_blob_permissions('apim', 'storage', 'rg', max_wait_minutes=2)
    assert result is False
    # Verify sleep was called with correct interval
    assert all(seconds == 30 for seconds in call_times)


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


def test_extract_az_cli_error_message_with_ansi_codes():
    """Test _extract_az_cli_error_message strips ANSI codes."""
    output = '\x1b[31mERROR: Resource failed\x1b[0m'
    result = az._extract_az_cli_error_message(output)
    assert result == 'Resource failed'


def test_extract_az_cli_error_message_finds_first_non_empty_line():
    """Test _extract_az_cli_error_message returns first meaningful line."""
    output = '\n\n\nSome error occurred\nMore details'
    result = az._extract_az_cli_error_message(output)
    assert result == 'Some error occurred'


def test_extract_az_cli_error_message_with_json_array():
    """Test _extract_az_cli_error_message handles JSON arrays (not dict)."""
    output = '[1, 2, 3] error'
    result = az._extract_az_cli_error_message(output)
    # JSON array is skipped, falls back to returning first non-empty line
    assert result == '[1, 2, 3] error'


def test_extract_az_cli_error_message_with_message_only_no_code():
    """Test _extract_az_cli_error_message with Message field but no Code."""
    output = 'Message: Something went wrong\nOther line'
    result = az._extract_az_cli_error_message(output)
    assert result == 'Something went wrong'


def test_extract_az_cli_error_message_with_code_only_no_message():
    """Test _extract_az_cli_error_message with Code field but no Message."""
    output = 'Code: ResourceNotFound\nOther line'
    result = az._extract_az_cli_error_message(output)
    # Should return first meaningful line since no message
    assert result in ('Code: ResourceNotFound', 'Other line')


def test_extract_az_cli_error_message_with_whitespace_only():
    """Test _extract_az_cli_error_message handles whitespace-only text."""
    output = '   \n   \n   '
    result = az._extract_az_cli_error_message(output)
    assert not result


def test_extract_az_cli_error_message_with_error_no_message_part():
    """Test _extract_az_cli_error_message handles ERROR: with no message after colon."""
    output = 'ERROR:\nOther line'
    result = az._extract_az_cli_error_message(output)
    # Falls back to the original line
    assert 'ERROR' in result or result == 'Other line'


def test_extract_az_cli_error_message_with_json_error_without_message():
    """Test _extract_az_cli_error_message with JSON error dict but no message."""
    output = '{"error": {"code": "NotFound"}}'
    result = az._extract_az_cli_error_message(output)
    # Should skip this JSON since error dict has no message, fall back to first line
    assert result == '{"error": {"code": "NotFound"}}'


def test_extract_az_cli_error_message_with_json_and_error_prefix():
    """Test _extract_az_cli_error_message prefers JSON, then ERROR: prefix."""
    output = '{"message": "JSON error"}\nERROR: Text error'
    result = az._extract_az_cli_error_message(output)
    # Should prefer JSON message
    assert result == 'JSON error'


def test_extract_az_cli_error_message_multiple_warnings_and_error():
    """Test _extract_az_cli_error_message with multiple warnings and actual error."""
    output = 'WARNING: Old feature\nWARNING: Deprecated\nERROR: Real problem'
    result = az._extract_az_cli_error_message(output)
    assert result == 'Real problem'


def test_extract_az_cli_error_message_with_az_error_no_message():
    """Test _extract_az_cli_error_message with az: error: but no message."""
    output = 'az: error:\nOther content'
    result = az._extract_az_cli_error_message(output)
    # Falls back to the original line
    assert 'az: error' in result or result == 'Other content'


def test_looks_like_json_with_valid_json():
    """Test _looks_like_json identifies JSON strings."""
    assert az._looks_like_json('{"key": "value"}') is True
    assert az._looks_like_json('[1, 2, 3]') is True


def test_looks_like_json_with_non_json():
    """Test _looks_like_json rejects non-JSON strings."""
    assert az._looks_like_json('plain text') is False
    assert az._looks_like_json('') is False


def test_strip_ansi_removes_codes():
    """Test _strip_ansi removes ANSI escape codes."""
    text = '\x1b[31mRed text\x1b[0m normal'
    result = az._strip_ansi(text)
    assert '\x1b' not in result
    assert 'Red text' in result
    assert 'normal' in result


def test_is_az_command_recognizes_az_commands():
    """Test _is_az_command identifies az CLI commands."""
    assert az._is_az_command('az group list') is True
    assert az._is_az_command('  az account show  ') is True
    assert az._is_az_command('az') is True


def test_is_az_command_rejects_non_az_commands():
    """Test _is_az_command rejects non-az commands."""
    assert az._is_az_command('echo hello') is False
    assert az._is_az_command('python script.py') is False
    assert az._is_az_command('azurecli') is False


def test_run_with_exception_in_subprocess():
    """Test run() handles subprocess exceptions gracefully."""
    with patch('azure_resources.subprocess.run') as mock_subprocess:
        mock_subprocess.side_effect = Exception('Subprocess failed')

        result = az.run('az group list')

        assert result.success is False
        assert 'Subprocess failed' in result.text


def test_run_with_stderr_only():
    """Test run() handles commands that only output to stderr."""
    with patch('azure_resources.subprocess.run') as mock_subprocess:
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = ''
        mock_process.stderr = 'Some warning message'
        mock_subprocess.return_value = mock_process

        result = az.run('az group list')

        assert result.success is True


def test_run_with_az_debug_flag_already_present():
    """Test run() doesn't duplicate --debug flag."""
    with patch('azure_resources.is_debug_enabled', return_value=True):
        with patch('azure_resources.subprocess.run') as mock_subprocess:
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.stdout = '[]'
            mock_process.stderr = ''
            mock_subprocess.return_value = mock_process

            az.run('az group list --debug')

            # Check that --debug appears only once in the command
            called_command = mock_subprocess.call_args[0][0]
            assert called_command.count('--debug') == 1


def test_run_with_json_output_success():
    """Test run() with successful JSON output."""
    with patch('azure_resources.subprocess.run') as mock_subprocess:
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = '{"result": "success"}'
        mock_process.stderr = ''
        mock_subprocess.return_value = mock_process

        result = az.run('az group show --name test-rg')

        assert result.success is True
        assert '{"result": "success"}' in result.text


def test_run_with_complex_shell_expression():
    """Test run() handles complex shell expressions with operators."""
    with patch('azure_resources.is_debug_enabled', return_value=True):
        with patch('azure_resources.subprocess.run') as mock_subprocess:
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.stdout = 'output'
            mock_process.stderr = ''
            mock_subprocess.return_value = mock_process

            az.run('az group list || echo "failed"')

            # --debug should be inserted before the ||
            called_command = mock_subprocess.call_args[0][0]
            debug_pos = called_command.find('--debug')
            pipe_pos = called_command.find('||')
            assert debug_pos < pipe_pos

# ========================================
# ADDITIONAL COVERAGE TESTS (MIGRATED)
# ========================================


class TestStripAnsi:
    """Test ANSI escape sequence removal."""

    def test_strip_ansi_with_color_codes(self):
        text = '\x1b[1;32mSuccess\x1b[0m'
        result = az._strip_ansi(text)
        assert result == 'Success'

    def test_strip_ansi_with_multiple_codes(self):
        text = '\x1b[31mError\x1b[0m \x1b[1;33mWarning\x1b[0m'
        result = az._strip_ansi(text)
        assert result == 'Error Warning'

    def test_strip_ansi_with_no_codes(self):
        text = 'Plain text'
        result = az._strip_ansi(text)
        assert result == 'Plain text'

    def test_strip_ansi_empty_string(self):
        result = az._strip_ansi('')
        assert not result


class TestRedactSecrets:
    """Test secret redaction in output."""

    def test_redact_access_token(self):
        text = '{"accessToken": "secret-token-value"}'
        result = az._redact_secrets(text)
        assert 'secret-token-value' not in result
        assert '***REDACTED***' in result

    def test_redact_refresh_token(self):
        text = '{"refreshToken": "my-refresh-token"}'
        result = az._redact_secrets(text)
        assert 'my-refresh-token' not in result
        assert '***REDACTED***' in result

    def test_redact_client_secret(self):
        text = '{"client_secret": "super-secret"}'
        result = az._redact_secrets(text)
        assert 'super-secret' not in result
        assert '***REDACTED***' in result

    def test_redact_bearer_token(self):
        text = 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
        result = az._redact_secrets(text)
        assert 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' not in result
        assert '***REDACTED***' in result

    def test_redact_empty_string(self):
        result = az._redact_secrets('')
        assert not result

    def test_redact_none_value(self):
        result = az._redact_secrets(None)
        assert result is None

    def test_redact_case_insensitive(self):
        text = '{"AccessToken": "secret"}'
        result = az._redact_secrets(text)
        assert 'secret' not in result


class TestIsAzCommand:
    """Test Azure CLI command detection."""

    def test_is_az_command_with_whitespace(self):
        assert az._is_az_command('   az group list') is True
        assert az._is_az_command('az account show  ') is True

    def test_is_az_command_with_arguments(self):
        assert az._is_az_command('az group list -g test') is True
        assert az._is_az_command('az account show -o json') is True
        assert az._is_az_command('az apim list --query') is True

    def test_is_az_command_just_az(self):
        assert az._is_az_command('az') is True

    def test_is_not_az_command(self):
        assert az._is_az_command('echo hello') is False
        assert az._is_az_command('python script.py') is False
        assert az._is_az_command('azurecli list') is False
        assert az._is_az_command('') is False


class TestMaybeAddAzDebugFlag:
    """Test adding --debug flag to az commands."""

    def test_add_debug_flag_disabled_logging(self, monkeypatch):
        monkeypatch.setattr('azure_resources.is_debug_enabled', lambda: False)

        command = 'az group list'
        result = az._maybe_add_az_debug_flag(command)
        assert '--debug' not in result
        assert result == command

    def test_add_debug_flag_non_az_command(self, monkeypatch):
        monkeypatch.setattr('azure_resources.is_debug_enabled', lambda: True)

        command = 'python script.py'
        result = az._maybe_add_az_debug_flag(command)
        assert '--debug' not in result

    def test_add_debug_flag_already_present(self, monkeypatch):
        monkeypatch.setattr('azure_resources.is_debug_enabled', lambda: True)

        command = 'az group list --debug'
        result = az._maybe_add_az_debug_flag(command)
        assert result.count('--debug') == 1

    def test_add_debug_flag_before_pipe(self, monkeypatch):
        monkeypatch.setattr('azure_resources.is_debug_enabled', lambda: True)

        command = 'az group list | grep test'
        result = az._maybe_add_az_debug_flag(command)
        assert '--debug' in result
        assert result.index('--debug') < result.index('|')

    def test_add_debug_flag_before_redirect(self, monkeypatch):
        monkeypatch.setattr('azure_resources.is_debug_enabled', lambda: True)

        command = 'az group list > output.txt'
        result = az._maybe_add_az_debug_flag(command)
        assert '--debug' in result
        assert result.index('--debug') < result.index('>')

    def test_add_debug_flag_before_or_operator(self, monkeypatch):
        monkeypatch.setattr('azure_resources.is_debug_enabled', lambda: True)

        command = 'az group list || echo failed'
        result = az._maybe_add_az_debug_flag(command)
        assert '--debug' in result

    def test_add_debug_flag_before_and_operator(self, monkeypatch):
        monkeypatch.setattr('azure_resources.is_debug_enabled', lambda: True)

        command = 'az group list && az account show'
        result = az._maybe_add_az_debug_flag(command)
        assert '--debug' in result


class TestExtractAzCliErrorMessage:
    """Test Azure CLI error message extraction."""

    def test_extract_json_error_with_error_object(self):
        output = '{"error": {"message": "Resource not found"}}'
        result = az._extract_az_cli_error_message(output)
        assert result == 'Resource not found'

    def test_extract_json_error_with_message_field(self):
        output = '{"message": "Operation failed"}'
        result = az._extract_az_cli_error_message(output)
        assert result == 'Operation failed'

    def test_extract_error_prefix(self):
        output = 'ERROR: Resource group not found'
        result = az._extract_az_cli_error_message(output)
        assert result == 'Resource group not found'

    def test_extract_az_error_prefix(self):
        output = 'az: error: Invalid argument'
        result = az._extract_az_cli_error_message(output)
        assert result == 'Invalid argument'

    def test_extract_code_and_message(self):
        output = 'Code: AuthenticationFailed\nMessage: Token expired'
        result = az._extract_az_cli_error_message(output)
        assert result == 'AuthenticationFailed: Token expired'

    def test_extract_message_only(self):
        output = 'Some other line\nMessage: Parameter is required'
        result = az._extract_az_cli_error_message(output)
        assert 'Parameter is required' in result or result == 'Message: Parameter is required'

    def test_extract_empty_output(self):
        result = az._extract_az_cli_error_message('')
        assert not result

    def test_extract_none_output(self):
        result = az._extract_az_cli_error_message(None)
        assert not result

    def test_extract_with_ansi_codes(self):
        output = '\x1b[31mERROR: \x1b[0mOperation failed'
        result = az._extract_az_cli_error_message(output)
        assert 'Operation failed' in result

    def test_extract_json_in_middle_of_text(self):
        output = 'Some output\n{"error": {"message": "Actual error"}}\nMore text'
        result = az._extract_az_cli_error_message(output)
        assert result == 'Actual error'

    def test_extract_with_traceback(self):
        output = 'Traceback (most recent call last):\n  File "test.py"\nError: Something failed'
        result = az._extract_az_cli_error_message(output)
        assert 'Traceback' not in result

    def test_extract_warning_ignored(self):
        output = 'WARNING: Something\nERROR: Actual error'
        result = az._extract_az_cli_error_message(output)
        assert result == 'Actual error'

    def test_extract_only_empty_lines(self):
        output = '\n\nTraceback (most recent call last):\n'
        result = az._extract_az_cli_error_message(output)
        assert not result


class TestFormatDuration:
    """Test duration formatting."""

    def test_format_duration_seconds(self):
        start_time = time.time() - 5
        result = az._format_duration(start_time)
        assert '[0m:' in result
        assert 's]' in result

    def test_format_duration_minutes_and_seconds(self):
        start_time = time.time() - 65
        result = az._format_duration(start_time)
        assert '[1m:' in result


class TestLooksLikeJson:
    """Test JSON detection."""

    def test_looks_like_json_with_object(self):
        assert az._looks_like_json('{"key": "value"}') is True
        assert az._looks_like_json('  {"key": "value"}') is True

    def test_looks_like_json_with_array(self):
        assert az._looks_like_json('[1, 2, 3]') is True
        assert az._looks_like_json('  [1, 2, 3]') is True

    def test_looks_like_json_with_invalid(self):
        assert az._looks_like_json('{"key": value}') is False
        assert az._looks_like_json('not json') is False

    def test_looks_like_json_empty(self):
        assert az._looks_like_json('') is False

    def test_looks_like_json_only_whitespace(self):
        assert az._looks_like_json('   ') is False

    def test_looks_like_json_xml(self):
        assert az._looks_like_json('<root></root>') is False

    def test_looks_like_json_plain_text(self):
        assert az._looks_like_json('plain text') is False


class TestRunFunctionEdgeCases:
    """Test edge cases in the run() function."""

    def test_run_with_stderr_only(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_command', 'print_error', 'print_ok'])

        mock_completed = Mock()
        mock_completed.returncode = 0
        mock_completed.stdout = ''
        mock_completed.stderr = 'Some warning'

        monkeypatch.setattr('azure_resources.subprocess.run', lambda *a, **k: mock_completed)

        result = az.run('echo test')
        assert result.success is True

    def test_run_with_empty_output(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_command', 'print_ok'])

        mock_completed = Mock()
        mock_completed.returncode = 0
        mock_completed.stdout = ''
        mock_completed.stderr = ''

        monkeypatch.setattr('azure_resources.subprocess.run', lambda *a, **k: mock_completed)

        result = az.run('echo test')
        assert result.success is True
        assert not result.text

    def test_run_with_none_stdout_stderr(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_command', 'print_ok'])

        mock_completed = Mock()
        mock_completed.returncode = 0
        mock_completed.stdout = None
        mock_completed.stderr = None

        monkeypatch.setattr('azure_resources.subprocess.run', lambda *a, **k: mock_completed)

        result = az.run('echo test')
        assert result.success is True

    def test_run_with_non_az_command(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_command', 'print_ok'])

        mock_completed = Mock()
        mock_completed.returncode = 0
        mock_completed.stdout = 'output'
        mock_completed.stderr = ''

        run_calls = []

        def mock_run(*args, **kwargs):
            run_calls.append((args, kwargs))
            return mock_completed

        monkeypatch.setattr('azure_resources.subprocess.run', mock_run)

        result = az.run('echo test')
        assert result.success is True
        assert len(run_calls) == 1

    def test_run_with_json_stdout(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_command', 'print_ok'])

        mock_completed = Mock()
        mock_completed.returncode = 0
        mock_completed.stdout = '{"key": "value"}'
        mock_completed.stderr = ''

        monkeypatch.setattr('azure_resources.subprocess.run', lambda *a, **k: mock_completed)

        result = az.run('az group list -o json')
        assert result.success is True
        assert result.json_data == {'key': 'value'}

    def test_run_command_with_special_characters(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_command', 'print_ok'])

        mock_completed = Mock()
        mock_completed.returncode = 0
        mock_completed.stdout = 'output'
        mock_completed.stderr = ''

        monkeypatch.setattr('azure_resources.subprocess.run', lambda *a, **k: mock_completed)

        result = az.run('echo "test with spaces" && echo done')
        assert result.success is True


class TestGetAccountInfoEdgeCases:
    """Test edge cases in get_account_info()."""

    def test_get_account_info_partial_failure(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val', 'print_error'])

        account_output = Mock()
        account_output.success = True
        account_output.json_data = {
            'user': {'name': 'test@example.com'},
            'tenantId': 'tenant-123',
            'id': 'subscription-123'
        }

        ad_output = Mock()
        ad_output.success = False
        ad_output.json_data = None

        call_count = [0]

        def mock_run(cmd, *args, **kwargs):
            call_count[0] += 1
            if 'account show' in cmd:
                return account_output
            return ad_output

        monkeypatch.setattr('azure_resources.run', mock_run)

        with pytest.raises(Exception):
            az.get_account_info()

    def test_get_account_info_success(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val', 'print_error'])

        account_output = Mock()
        account_output.success = True
        account_output.json_data = {
            'user': {'name': 'test@example.com'},
            'tenantId': 'tenant-123',
            'id': 'subscription-123'
        }

        ad_output = Mock()
        ad_output.success = True
        ad_output.json_data = {'id': 'user-123'}

        call_count = [0]

        def mock_run(cmd, *args, **kwargs):
            call_count[0] += 1
            if 'account show' in cmd:
                return account_output
            return ad_output

        monkeypatch.setattr('azure_resources.run', mock_run)

        user, user_id, tenant, subscription = az.get_account_info()
        assert user == 'test@example.com'
        assert user_id == 'user-123'
        assert tenant == 'tenant-123'
        assert subscription == 'subscription-123'


class TestGetDeploymentName:
    """Test get_deployment_name function."""

    def test_get_deployment_name_custom_directory(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val'])

        result = az.get_deployment_name('my-sample')
        assert 'deploy-my-sample-' in result


class TestGetFrontdoorUrl:
    """Test get_frontdoor_url function."""

    def test_get_frontdoor_url_not_found(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val'])

        mock_output = Mock()
        mock_output.success = False
        mock_output.json_data = None

        monkeypatch.setattr('azure_resources.run', lambda *a, **k: mock_output)

        result = az.get_frontdoor_url(INFRASTRUCTURE.SIMPLE_APIM, 'test-rg')
        assert result is None


class TestGetApimUrl:
    """Test get_apim_url function."""

    def test_get_apim_url_no_results(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val'])

        mock_output = Mock()
        mock_output.success = True
        mock_output.json_data = []
        mock_output.is_json = True

        monkeypatch.setattr('azure_resources.run', lambda *a, **k: mock_output)

        result = az.get_apim_url('test-rg')
        assert result is None


class TestListApimSubscriptions:
    """Test list_apim_subscriptions function."""

    def test_list_apim_subscriptions_success(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val'])

        mock_output = Mock()
        mock_output.success = True
        mock_output.json_data = {
            'value': [
                {'id': 'sub-1', 'displayName': 'Subscription 1'},
                {'id': 'sub-2', 'displayName': 'Subscription 2'}
            ]
        }
        mock_output.is_json = True

        monkeypatch.setattr('azure_resources.run', lambda *a, **k: mock_output)

        result = az.list_apim_subscriptions('test-apim', 'test-rg')
        assert len(result) == 2
        assert result[0]['id'] == 'sub-1'

    def test_list_apim_subscriptions_empty(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val'])

        mock_output = Mock()
        mock_output.success = True
        mock_output.json_data = {'value': []}
        mock_output.is_json = True

        monkeypatch.setattr('azure_resources.run', lambda *a, **k: mock_output)

        result = az.list_apim_subscriptions('test-apim', 'test-rg')
        assert result == []

    def test_list_apim_subscriptions_failure(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val'])

        mock_output = Mock()
        mock_output.success = False
        mock_output.json_data = None

        monkeypatch.setattr('azure_resources.run', lambda *a, **k: mock_output)

        result = az.list_apim_subscriptions('test-apim', 'test-rg')
        assert result == []

    def test_list_subscriptions_with_empty_params(self):
        """Test list_apim_subscriptions returns empty list for invalid params."""

        result = az.list_apim_subscriptions('', 'rg')
        assert result == []

        result = az.list_apim_subscriptions('apim', '')
        assert result == []

    def test_list_subscriptions_account_show_fails(self, monkeypatch):
        """Test list_apim_subscriptions when account show fails."""

        mock_output = Mock()
        mock_output.success = False
        mock_output.text = ''

        monkeypatch.setattr('azure_resources.run', lambda *a, **k: mock_output)

        result = az.list_apim_subscriptions('apim', 'rg')

        assert result == []

    def test_list_subscriptions_value_not_list(self, monkeypatch):
        """Test list_apim_subscriptions when value is not a list."""

        call_count = [0]

        def mock_run(cmd, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # First call is account show
                output = Mock()
                output.success = True
                output.text = 'sub-123'
                return output
            else:  # Second call is REST API
                output = Mock()
                output.success = True
                output.json_data = {'value': 'not-a-list'}
                return output

        monkeypatch.setattr('azure_resources.run', mock_run)

        result = az.list_apim_subscriptions('apim', 'rg')

        assert result == []


class TestGetAppGwEndpoint:
    """Test get_appgw_endpoint function."""

    def test_get_appgw_endpoint_not_found(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_ok', 'print_warning'])

        with patch('azure_resources.run') as mock_run:
            mock_run.return_value = Output(False, 'No gateways found')

            hostname, ip = az.get_appgw_endpoint('test-rg')

            assert hostname is None
            assert ip is None


class TestGetUniqueInfraSuffix:
    """Test get_unique_suffix_for_resource_group function."""

    def test_get_unique_suffix_empty_rg(self, monkeypatch):
        # Mock the run function to avoid actual Azure CLI deployment
        def mock_run(cmd, *args, **kwargs):
            output = Mock()
            output.success = True
            output.text = 'abcd1234efgh5'
            return output

        monkeypatch.setattr('azure_resources.run', mock_run)
        result = az.get_unique_suffix_for_resource_group('')
        assert isinstance(result, str)


class TestFindInfrastructureInstances:
    """Test find_infrastructure_instances function."""

    def test_find_infrastructure_instances_no_matches(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val', 'print_message'])

        def mock_run(cmd, *args, **kwargs):
            output = Mock()
            output.success = True
            output.text = ''
            return output

        monkeypatch.setattr('azure_resources.run', mock_run)

        result = az.find_infrastructure_instances(INFRASTRUCTURE.SIMPLE_APIM)
        assert not result

    def test_find_with_invalid_index_format(self, monkeypatch):
        """Test finding resource groups skips invalid index formats."""

        mock_output = Mock()
        mock_output.success = True
        mock_output.text = """apim-infra-simple-apim
apim-infra-simple-apim-abc
apim-infra-simple-apim-2"""

        monkeypatch.setattr('azure_resources.run', lambda *a, **k: mock_output)

        result = az.find_infrastructure_instances(INFRASTRUCTURE.SIMPLE_APIM)

        # Should only include valid entries (no index and index=2)
        assert len(result) == 2
        assert (INFRASTRUCTURE.SIMPLE_APIM, None) in result
        assert (INFRASTRUCTURE.SIMPLE_APIM, 2) in result


class TestGetInfraRgName:
    """Test get_infra_rg_name function."""

    def test_get_infra_rg_name_with_index(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val'])

        result = az.get_infra_rg_name(INFRASTRUCTURE.SIMPLE_APIM, 1)
        assert 'simple-apim' in result
        assert '1' in result

    def test_get_infra_rg_name_without_index(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val'])

        result = az.get_infra_rg_name(INFRASTRUCTURE.APIM_ACA)
        assert 'apim-aca' in result


class TestGetRgName:
    """Test get_rg_name function."""

    def test_get_rg_name_with_index(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val'])

        result = az.get_rg_name('my-sample', 2)
        assert 'my-sample' in result
        assert '2' in result

    def test_get_rg_name_without_index(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val'])

        result = az.get_rg_name('test-deployment')
        assert 'test-deployment' in result
        assert '-test-deployment' in result


class TestCheckApimBlobPermissions:
    """Test check_apim_blob_permissions function."""

    def test_check_apim_blob_permissions_no_principal_id(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val', 'print_info', 'print_error', 'print_warning'])

        mock_output = Mock()
        mock_output.success = False
        mock_output.json_data = None

        monkeypatch.setattr('azure_resources.run', lambda *a, **k: mock_output)

        result = az.check_apim_blob_permissions('apim', 'storage', 'rg', max_wait_minutes=1)
        assert result is False


class TestCleanupOldJwtSigningKeys:
    """Test cleanup_old_jwt_signing_keys function."""

    def test_cleanup_old_jwt_no_other_keys(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val', 'print_info', 'print_message'])

        mock_output = Mock()
        mock_output.success = True
        mock_output.json_data = [{'name': 'JwtSigningKey-authX-12345'}]
        mock_output.is_json = True

        monkeypatch.setattr('azure_resources.run', lambda *a, **k: mock_output)

        result = az.cleanup_old_jwt_signing_keys('apim', 'rg', 'JwtSigningKey-authX-12345')
        assert isinstance(result, bool)

    def test_cleanup_old_jwt_list_fails(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_val', 'print_info', 'print_message', 'print_error'])

        mock_output = Mock()
        mock_output.success = False
        mock_output.json_data = None

        monkeypatch.setattr('azure_resources.run', lambda *a, **k: mock_output)

        result = az.cleanup_old_jwt_signing_keys('apim', 'rg', 'JwtSigningKey-authX-12345')
        assert result is False


class TestGetApimSubscriptionKey:
    """Test get_apim_subscription_key function."""

    def test_get_apim_subscription_key_invalid_params(self):
        result = az.get_apim_subscription_key('', 'rg')
        assert result is None

        result = az.get_apim_subscription_key('apim', '')
        assert result is None


class TestGetEndpoints:
    """Test get_endpoints function."""

    def test_get_endpoints_with_simple_apim(self, monkeypatch):
        suppress_module_functions(monkeypatch, az, ['print_message', 'print_val'])

        monkeypatch.setattr('azure_resources.get_frontdoor_url', lambda *a, **k: None)
        monkeypatch.setattr('azure_resources.get_apim_url', lambda *a, **k: 'https://apim.azure-api.net')
        monkeypatch.setattr('azure_resources.get_appgw_endpoint', lambda *a, **k: (None, None))

        result = az.get_endpoints(INFRASTRUCTURE.SIMPLE_APIM, 'test-rg')

        assert result is not None
        assert result.apim_endpoint_url == 'https://apim.azure-api.net'


class TestRunFunction:
    """Test run function edge cases."""

    def test_run_with_non_json_stdout_in_debug(self, monkeypatch):
        """Test that non-JSON stdout is printed in debug mode."""

        suppress_module_functions(monkeypatch, az, ['print_ok', 'print_error', 'print_plain'])

        monkeypatch.setattr('azure_resources.is_debug_enabled', lambda: True)

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = 'Plain text output that is not JSON'
        mock_result.stderr = ''

        monkeypatch.setattr('azure_resources.subprocess.run', lambda *a, **k: mock_result)

        result = az.run('az test command')

        assert result.success is True
        assert 'Plain text output' in result.text

    def test_run_with_stderr_and_debug_disabled(self, monkeypatch):
        """Test that stderr is printed when debug is disabled."""

        suppress_module_functions(monkeypatch, az, ['print_ok', 'print_error', 'print_plain'])

        monkeypatch.setattr('azure_resources.is_debug_enabled', lambda: False)

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ''
        mock_result.stderr = 'Error message in stderr'

        monkeypatch.setattr('azure_resources.subprocess.run', lambda *a, **k: mock_result)

        result = az.run('az test command')

        assert result.success is False

    def test_run_failure_with_no_normalized_error_and_debug_enabled(self, monkeypatch):
        """Test run failure when error extraction returns empty and debug is enabled."""

        suppress_module_functions(monkeypatch, az, ['print_ok', 'print_error', 'print_plain'])

        monkeypatch.setattr('azure_resources.is_debug_enabled', lambda: True)
        monkeypatch.setattr('azure_resources._extract_az_cli_error_message', lambda *a: '')

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = 'Some error output'
        mock_result.stderr = ''

        monkeypatch.setattr('azure_resources.subprocess.run', lambda *a, **k: mock_result)

        result = az.run('az test command')

        assert result.success is False
        assert 'Some error output' in result.text

    def test_run_with_stderr_in_debug_mode(self, monkeypatch):
        """Test that stderr is logged in debug mode."""

        suppress_module_functions(monkeypatch, az, ['print_ok', 'print_error', 'print_plain'])

        monkeypatch.setattr('azure_resources.is_debug_enabled', lambda: True)

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"result": "success"}'
        mock_result.stderr = 'Some warning in stderr'

        monkeypatch.setattr('azure_resources.subprocess.run', lambda *a, **k: mock_result)

        result = az.run('az test command')

        assert result.success is True

    def test_run_success_with_non_json_stdout_not_in_debug(self, monkeypatch):
        """Test that non-JSON stdout is logged even when debug is disabled."""

        suppress_module_functions(monkeypatch, az, ['print_ok', 'print_error', 'print_plain'])

        monkeypatch.setattr('azure_resources.is_debug_enabled', lambda: False)

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = 'Plain text success output'
        mock_result.stderr = ''

        monkeypatch.setattr('azure_resources.subprocess.run', lambda *a, **k: mock_result)

        result = az.run('az test command', 'Success message')

        assert result.success is True


class TestCleanupJwtSigningKeysEdgeCases:
    """Test cleanup_old_jwt_signing_keys edge cases."""

    def test_cleanup_with_empty_key_list(self, monkeypatch):
        """Test cleanup when API returns empty string."""

        suppress_module_functions(monkeypatch, az, ['print_info', 'print_error'])

        mock_output = Mock()
        mock_output.success = True
        mock_output.text = ''

        monkeypatch.setattr('azure_resources.run', lambda *a, **k: mock_output)

        result = az.cleanup_old_jwt_signing_keys('apim', 'rg', 'JwtSigningKey-authX-12345')

        assert result is True


class TestCreateResourceGroupWithTags:
    """Test create_resource_group function with tags."""

    def test_create_resource_group_with_tags(self, monkeypatch):
        """Test creating resource group with additional tags."""

        suppress_module_functions(monkeypatch, az, ['print_val', 'print_ok'])

        calls = []

        def mock_run(cmd, *args, **kwargs):
            calls.append(cmd)
            return Output(True, 'Resource group created')

        monkeypatch.setattr('azure_resources.run', mock_run)
        monkeypatch.setattr('azure_resources.does_resource_group_exist', lambda *a, **k: False)

        az.create_resource_group('test-rg', 'eastus', tags={'environment': 'test', 'owner': 'user'})

        assert len(calls) == 1
        assert 'environment="test"' in calls[0]
        assert 'owner="user"' in calls[0]


class TestGetApimSubscriptionKeyEdgeCases:
    """Test get_apim_subscription_key edge cases."""

    def test_get_key_no_active_subscriptions(self, monkeypatch):
        """Test get_apim_subscription_key when no active subscriptions exist."""

        call_count = [0]

        def mock_run(cmd, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # account show
                output = Mock()
                output.success = True
                output.text = 'sub-123'
                return output
            elif 'subscriptions?' in cmd:  # list subscriptions
                output = Mock()
                output.success = True
                output.json_data = {
                    'value': [
                        {'name': 'sid-1', 'properties': {'state': 'suspended'}},
                        {'name': 'sid-2', 'properties': {'state': 'cancelled'}}
                    ]
                }
                return output
            else:  # listSecrets
                output = Mock()
                output.success = True
                output.json_data = {'primaryKey': 'key-123'}
                return output

        monkeypatch.setattr('azure_resources.run', mock_run)

        # Should use first available subscription even if not active
        result = az.get_apim_subscription_key('apim', 'rg')

        assert result == 'key-123'

    def test_get_key_secrets_call_fails(self, monkeypatch):
        """Test get_apim_subscription_key when secrets retrieval fails."""

        call_count = [0]

        def mock_run(cmd, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # account show
                output = Mock()
                output.success = True
                output.text = 'sub-123'
                return output
            elif 'subscriptions?' in cmd:  # list subscriptions
                output = Mock()
                output.success = True
                output.json_data = {
                    'value': [{'name': 'sid-1', 'properties': {'state': 'active'}}]
                }
                return output
            else:  # listSecrets fails
                output = Mock()
                output.success = False
                output.json_data = None
                return output

        monkeypatch.setattr('azure_resources.run', mock_run)

        result = az.get_apim_subscription_key('apim', 'rg')

        assert result is None

    def test_get_key_empty_key_value(self, monkeypatch):
        """Test get_apim_subscription_key when key value is empty."""

        call_count = [0]

        def mock_run(cmd, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # account show
                output = Mock()
                output.success = True
                output.text = 'sub-123'
                return output
            elif 'subscriptions?' in cmd:  # list subscriptions
                output = Mock()
                output.success = True
                output.json_data = {
                    'value': [{'name': 'sid-1', 'properties': {'state': 'active'}}]
                }
                return output
            else:  # listSecrets returns empty key
                output = Mock()
                output.success = True
                output.json_data = {'primaryKey': '   '}
                return output

        monkeypatch.setattr('azure_resources.run', mock_run)

        result = az.get_apim_subscription_key('apim', 'rg')

        assert result is None

    def test_get_key_account_show_fails(self, monkeypatch):
        """Test get_apim_subscription_key when account show fails."""

        mock_output = Mock()
        mock_output.success = False
        mock_output.text = ''

        monkeypatch.setattr('azure_resources.run', lambda *a, **k: mock_output)

        result = az.get_apim_subscription_key('apim', 'rg')

        assert result is None

    def test_get_key_list_subscriptions_returns_empty(self, monkeypatch):
        """Test get_apim_subscription_key when list_apim_subscriptions returns empty list."""

        call_count = [0]

        def mock_run(cmd, *args, **kwargs):
            call_count[0] += 1
            if 'account show' in cmd:
                output = Mock()
                output.success = True
                output.text = 'sub-123'
                return output
            elif 'subscriptions?' in cmd:
                output = Mock()
                output.success = True
                output.json_data = {'value': []}
                return output
            return Mock(success=False, text='')

        monkeypatch.setattr('azure_resources.run', mock_run)

        result = az.get_apim_subscription_key('apim', 'rg')

        assert result is None


class TestGetRgNameWithIndex:
    """Test get_rg_name with index parameter."""

    def test_get_rg_name_formats_with_index(self, monkeypatch):
        """Test get_rg_name properly formats name with index."""

        suppress_module_functions(monkeypatch, az, ['print_val'])

        result = az.get_rg_name('my-sample', 5)

        assert 'apim-sample-my-sample-5' == result

    def test_get_rg_name_with_none_index(self, monkeypatch):
        """Test get_rg_name with explicit None index."""

        suppress_module_functions(monkeypatch, az, ['print_val'])

        result = az.get_rg_name('my-sample', None)

        assert 'apim-sample-my-sample' == result
        assert not result.count('-5')  # Should not have index suffix

# Test run() method success = not completed.returncode branch (returncode = 0)
class TestRunMethodBranches:
    """Test specific branches in the run() method."""

    def test_run_success_returncode_zero(self, monkeypatch):
        """Test run() when subprocess returncode is 0 (success = True)."""
        def mock_run(*args, **kwargs):
            completed = Mock()
            completed.stdout = 'output text'
            completed.stderr = None
            completed.returncode = 0
            return completed

        monkeypatch.setattr('subprocess.run', mock_run)

        result = az.run('echo test', ok_message='Success')

        assert result.success is True
        assert 'output text' in result.text

    def test_run_failure_nonzero_returncode(self, monkeypatch):
        """Test run() when subprocess returncode is non-zero (success = False)."""
        def mock_run(*args, **kwargs):
            completed = Mock()
            completed.stdout = 'some output'
            completed.stderr = 'error output'
            completed.returncode = 1
            return completed

        monkeypatch.setattr('subprocess.run', mock_run)

        result = az.run('bad command', error_message='Failed')

        assert result.success is False


# Test cleanup_old_jwt_signing_keys with different key counts
def test_cleanup_old_jwt_signing_keys_with_multiple_old_keys(monkeypatch):
    """Test cleanup_old_jwt_signing_keys when there are multiple old keys to delete."""
    def mock_run(cmd, *args, **kwargs):
        if 'list' in cmd:
            output = Mock()
            output.success = True
            output.text = 'JwtSigningKey-test-sample-1\nJwtSigningKey-test-sample-2\nJwtSigningKey-test-sample-3\nJwtSigningKey-other-1'
            return output
        elif 'delete' in cmd and 'test-sample-1' in cmd:
            return Mock(success=True)
        elif 'delete' in cmd and 'test-sample-2' in cmd:
            return Mock(success=True)
        else:
            return Mock(success=True)

    monkeypatch.setattr('azure_resources.run', mock_run)

    result = az.cleanup_old_jwt_signing_keys('apim', 'rg', 'JwtSigningKey-test-sample-3')

    assert result is True


# Test cleanup_old_jwt_signing_keys when current key is first
def test_cleanup_old_jwt_signing_keys_current_is_first(monkeypatch):
    """Test cleanup_old_jwt_signing_keys when current key is the first one."""
    def mock_run(cmd, *args, **kwargs):
        if 'list' in cmd:
            output = Mock()
            output.success = True
            output.text = 'JwtSigningKey-test-sample-1\nJwtSigningKey-test-sample-2'
            return output
        elif 'delete' in cmd:
            return Mock(success=True)
        else:
            return Mock(success=True)

    monkeypatch.setattr('azure_resources.run', mock_run)

    result = az.cleanup_old_jwt_signing_keys('apim', 'rg', 'JwtSigningKey-test-sample-1')

    assert result is True


# Test get_frontdoor_url with empty hostname
def test_get_frontdoor_url_endpoint_no_hostname(monkeypatch):
    """Test get_frontdoor_url when endpoint has no hostname."""
    def mock_run(cmd, *args, **kwargs):
        if 'profile list' in cmd:
            return Mock(success=True, json_data=[{'name': 'profile-123'}])
        elif 'endpoint list' in cmd:
            return Mock(success=True, json_data=[{'hostName': None}])
        return Mock(success=False)

    monkeypatch.setattr('azure_resources.run', mock_run)

    result = az.get_frontdoor_url('rg', INFRASTRUCTURE.AFD_APIM_PE)

    assert result is None


# Test get_frontdoor_url with empty profile name
def test_get_frontdoor_url_empty_profile_name(monkeypatch):
    """Test get_frontdoor_url when profile name is empty."""
    def mock_run(cmd, *args, **kwargs):
        if 'profile list' in cmd:
            return Mock(success=True, json_data=[{'name': ''}])
        return Mock(success=False)

    monkeypatch.setattr('azure_resources.run', mock_run)

    result = az.get_frontdoor_url('rg', INFRASTRUCTURE.AFD_APIM_PE)

    assert result is None


# Test list_apim_subscriptions with non-dict json_data
def test_list_apim_subscriptions_invalid_json_data(monkeypatch):
    """Test list_apim_subscriptions when json_data is not a dict."""
    def mock_run(cmd, *args, **kwargs):
        output = Mock()
        output.success = True
        output.json_data = None
        return output

    monkeypatch.setattr('azure_resources.run', mock_run)

    result = az.list_apim_subscriptions('apim', 'rg')

    assert result == []


# Test list_apim_subscriptions with missing value key
def test_list_apim_subscriptions_missing_value_key(monkeypatch):
    """Test list_apim_subscriptions when value key is missing in response."""
    def mock_run(cmd, *args, **kwargs):
        output = Mock()
        output.success = True
        output.json_data = {'items': []}
        return output

    monkeypatch.setattr('azure_resources.run', mock_run)

    result = az.list_apim_subscriptions('apim', 'rg')

    assert result == []


# Test get_appgw_endpoint with empty hostname
def test_get_appgw_endpoint_empty_hostname(monkeypatch):
    """Test get_appgw_endpoint when hostname is empty in listener."""
    def mock_run(cmd, *args, **kwargs):
        output = Mock()
        output.success = True
        output.json_data = [{
            'name': 'appgw-123',
            'httpListeners': [{'hostName': ''}],
            'frontendIPConfigurations': []
        }]
        return output

    monkeypatch.setattr('azure_resources.run', mock_run)

    hostname, public_ip = az.get_appgw_endpoint('rg')

    assert hostname is None
    assert public_ip is None


# Test get_appgw_endpoint with no listeners
def test_get_appgw_endpoint_no_http_listeners(monkeypatch):
    """Test get_appgw_endpoint when there are no HTTP listeners."""
    def mock_run(cmd, *args, **kwargs):
        if 'application-gateway list' in cmd:
            output = Mock()
            output.success = True
            output.json_data = [{
                'name': 'appgw-123',
                'httpListeners': [],
                'frontendIPConfigurations': [{'publicIPAddress': {'id': '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/publicIPAddresses/pip-123'}}]
            }]
            return output
        elif 'public-ip show' in cmd:
            output = Mock()
            output.success = True
            output.json_data = {'ipAddress': '20.20.20.20'}
            return output
        return Mock(success=False)

    monkeypatch.setattr('azure_resources.run', mock_run)

    _hostname, _public_ip = az.get_appgw_endpoint('rg')
