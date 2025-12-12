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

    with patch('builtins.open', side_effect=FileNotFoundError('File not found')):
        result = az.get_azure_role_guid('NonExistentRole')

        assert result is None

# ------------------------------
#    RESOURCE GROUP TESTS
# ------------------------------

def test_does_resource_group_exist_true():
    """Test checking if resource group exists - returns True."""

    with patch('azure_resources._run') as mock_run:
        mock_run.return_value = Output(True, '{"name": "test-rg"}')

        result = az.does_resource_group_exist('test-rg')

        assert result is True
        mock_run.assert_called_once_with(
            'az group show --name test-rg -o json',
            print_command_to_run = False,
            print_errors = False
        )


def test_does_resource_group_exist_false():
    """Test checking if resource group exists - returns False."""

    with patch('azure_resources._run') as mock_run:
        mock_run.return_value = Output(False, 'ResourceGroupNotFound')

        result = az.does_resource_group_exist('nonexistent-rg')

        assert result is False


def test_get_resource_group_location_success():
    """Test successful retrieval of resource group location."""

    with patch('azure_resources._run') as mock_run:
        mock_run.return_value = Output(True, 'eastus2\n')

        result = az.get_resource_group_location('test-rg')

        assert result == 'eastus2'
        mock_run.assert_called_once_with(
            'az group show --name test-rg --query "location" -o tsv',
            print_command_to_run = False,
            print_errors = False
        )


def test_get_resource_group_location_failure():
    """Test get_resource_group_location returns None on failure."""

    with patch('azure_resources._run') as mock_run:
        mock_run.return_value = Output(False, 'error message')

        result = az.get_resource_group_location('nonexistent-rg')

        assert result is None


def test_get_resource_group_location_empty():
    """Test get_resource_group_location returns None on empty response."""

    with patch('azure_resources._run') as mock_run:
        mock_run.return_value = Output(True, '')

        result = az.get_resource_group_location('test-rg')

        assert result is None


# ------------------------------
#    ACCOUNT INFO TESTS
# ------------------------------

def test_get_account_info_success():
    """Test successful retrieval of account information."""

    with patch('azure_resources._run') as mock_run:
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

    with patch('azure_resources._run') as mock_run:
        mock_run.return_value = Output(False, 'authentication error')

        with pytest.raises(Exception) as exc_info:
            az.get_account_info()

        assert 'Failed to retrieve account information' in str(exc_info.value)


def test_get_account_info_no_json():
    """Test get_account_info raises exception when no JSON data."""

    with patch('azure_resources._run') as mock_run:
        output = Output(True, 'some text')
        output.json_data = None
        mock_run.return_value = output

        with pytest.raises(Exception) as exc_info:
            az.get_account_info()

        assert 'Failed to retrieve account information' in str(exc_info.value)

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
    mock_basename.assert_not_called()


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
    mock_basename.assert_called_once_with('/path/to/current-folder')


# ------------------------------
#    FRONT DOOR TESTS
# ------------------------------

def test_get_frontdoor_url_afd_success():
    """Test successful Front Door URL retrieval."""

    with patch('azure_resources._run') as mock_run:
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

    with patch('azure_resources._run') as mock_run:
        result = az.get_frontdoor_url(INFRASTRUCTURE.SIMPLE_APIM, 'test-rg')

        assert result is None
        mock_run.assert_not_called()


def test_get_frontdoor_url_no_profile():
    """Test Front Door URL when no profile found."""

    with patch('azure_resources._run') as mock_run:
        mock_run.return_value = Output(False, 'No profiles found')

        result = az.get_frontdoor_url(INFRASTRUCTURE.AFD_APIM_PE, 'test-rg')

        assert result is None


def test_get_frontdoor_url_no_endpoints():
    """Test Front Door URL when profile exists but no endpoints."""

    with patch('azure_resources._run') as mock_run:
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

    with patch('azure_resources._run') as mock_run:
        mock_run.return_value = Output(True, '')
        mock_run.return_value.json_data = [{'name': 'test-apim', 'gatewayUrl': 'https://test-apim.azure-api.net'}]

        result = az.get_apim_url('test-rg')

        assert result == 'https://test-apim.azure-api.net'
        mock_run.assert_called_once_with(
            'az apim list -g test-rg -o json',
            print_command_to_run = False
        )


def test_get_apim_url_failure():
    """Test APIM URL retrieval failure."""

    with patch('azure_resources._run') as mock_run:
        mock_run.return_value = Output(False, 'No APIM services found')

        result = az.get_apim_url('test-rg')

        assert result is None


def test_get_apim_url_no_gateway():
    """Test APIM URL when service exists but no gateway URL."""

    with patch('azure_resources._run') as mock_run:
        mock_run.return_value = Output(True, '')
        mock_run.return_value.json_data = [{'name': 'test-apim', 'gatewayUrl': None}]

        result = az.get_apim_url('test-rg')

        assert result is None


# ------------------------------
#    APPLICATION GATEWAY TESTS
# ------------------------------

def test_get_appgw_endpoint_success():
    """Test successful Application Gateway endpoint retrieval."""

    with patch('azure_resources._run') as mock_run:
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
            call('az network application-gateway list -g test-rg -o json', print_command_to_run = False),
            call('az network public-ip show -g test-rg -n test-pip -o json', print_command_to_run = False)
        ]
        mock_run.assert_has_calls(expected_calls)


def test_get_appgw_endpoint_no_gateway():
    """Test Application Gateway endpoint when no gateway found."""

    with patch('azure_resources._run') as mock_run:
        mock_run.return_value = Output(False, 'No gateways found')

        hostname, ip = az.get_appgw_endpoint('test-rg')

        assert hostname is None
        assert ip is None


def test_get_appgw_endpoint_no_listeners():
    """Test Application Gateway endpoint with no HTTP listeners."""

    with patch('azure_resources._run') as mock_run:
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

    with patch('azure_resources._run') as mock_run:
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

    with patch('azure_resources._run') as mock_run:
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
