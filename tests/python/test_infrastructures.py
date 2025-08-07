"""
Unit tests for infrastructures.py.
"""

import pytest
from unittest.mock import Mock, patch, call, MagicMock
import json
import os
from pathlib import Path

import infrastructures
from apimtypes import INFRASTRUCTURE, APIM_SKU, APIMNetworkMode, API, PolicyFragment, HTTP_VERB, GET_APIOperation


# ------------------------------
#    CONSTANTS
# ------------------------------

TEST_LOCATION = 'eastus2'
TEST_INDEX = 1
TEST_APIM_SKU = APIM_SKU.BASICV2
TEST_NETWORK_MODE = APIMNetworkMode.PUBLIC


# ------------------------------
#    FIXTURES
# ------------------------------

@pytest.fixture
def mock_utils():
    """Mock the utils module to avoid external dependencies."""
    with patch('infrastructures.utils') as mock_utils:
        mock_utils.get_infra_rg_name.return_value = 'rg-test-infrastructure-01'
        mock_utils.build_infrastructure_tags.return_value = {'environment': 'test', 'project': 'apim-samples'}
        mock_utils.read_policy_xml.return_value = '<policies><inbound><base /></inbound></policies>'
        mock_utils.determine_shared_policy_path.return_value = '/mock/path/policy.xml'
        mock_utils.create_resource_group.return_value = None
        mock_utils.verify_infrastructure.return_value = True
        
        # Mock the run command with proper return object
        mock_output = Mock()
        mock_output.success = True
        mock_output.json_data = {'outputs': 'test'}
        mock_output.get.return_value = 'https://test-apim.azure-api.net'
        mock_output.getJson.return_value = ['api1', 'api2']
        mock_utils.run.return_value = mock_output
        
        yield mock_utils

@pytest.fixture
def mock_policy_fragments():
    """Provide mock policy fragments for testing."""
    return [
        PolicyFragment('Test-Fragment-1', '<policy>test1</policy>', 'Test fragment 1'),
        PolicyFragment('Test-Fragment-2', '<policy>test2</policy>', 'Test fragment 2')
    ]

@pytest.fixture
def mock_apis():
    """Provide mock APIs for testing."""
    return [
        API('test-api-1', 'Test API 1', '/test1', 'Test API 1 description', '<policy>api1</policy>'),
        API('test-api-2', 'Test API 2', '/test2', 'Test API 2 description', '<policy>api2</policy>')
    ]


# ------------------------------
#    BASE INFRASTRUCTURE CLASS TESTS
# ------------------------------

@pytest.mark.unit
def test_infrastructure_creation_basic(mock_utils):
    """Test basic Infrastructure creation with default values."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )
    
    assert infra.infra == INFRASTRUCTURE.SIMPLE_APIM
    assert infra.index == TEST_INDEX
    assert infra.rg_location == TEST_LOCATION
    assert infra.apim_sku == APIM_SKU.BASICV2  # default value
    assert infra.networkMode == APIMNetworkMode.PUBLIC  # default value
    assert infra.rg_name == 'rg-test-infrastructure-01'
    assert infra.rg_tags == {'environment': 'test', 'project': 'apim-samples'}

@pytest.mark.unit
def test_infrastructure_creation_with_custom_values(mock_utils):
    """Test Infrastructure creation with custom values."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.APIM_ACA,
        index=2,
        rg_location='westus2',
        apim_sku=APIM_SKU.PREMIUM,
        networkMode=APIMNetworkMode.EXTERNAL_VNET
    )
    
    assert infra.infra == INFRASTRUCTURE.APIM_ACA
    assert infra.index == 2
    assert infra.rg_location == 'westus2'
    assert infra.apim_sku == APIM_SKU.PREMIUM
    assert infra.networkMode == APIMNetworkMode.EXTERNAL_VNET

@pytest.mark.unit
def test_infrastructure_creation_with_custom_policy_fragments(mock_utils, mock_policy_fragments):
    """Test Infrastructure creation with custom policy fragments."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION,
        infra_pfs=mock_policy_fragments
    )
    
    # Initialize policy fragments
    pfs = infra._define_policy_fragments()
    
    # Should have base policy fragments + custom ones
    assert len(pfs) == 8  # 6 base + 2 custom
    assert any(pf.name == 'Test-Fragment-1' for pf in pfs)
    assert any(pf.name == 'Test-Fragment-2' for pf in pfs)
    assert any(pf.name == 'AuthZ-Match-All' for pf in pfs)

@pytest.mark.unit
def test_infrastructure_creation_with_custom_apis(mock_utils, mock_apis):
    """Test Infrastructure creation with custom APIs."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION,
        infra_apis=mock_apis
    )
    
    # Initialize APIs
    apis = infra._define_apis()
    
    # Should have base APIs + custom ones
    assert len(apis) == 3  # 1 base (hello-world) + 2 custom
    assert any(api.name == 'test-api-1' for api in infra.apis)
    assert any(api.name == 'test-api-2' for api in apis)
    assert any(api.name == 'hello-world' for api in apis)

@pytest.mark.unit
def test_infrastructure_creation_calls_utils_functions(mock_utils):
    """Test that Infrastructure creation calls expected utility functions."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )
    
    mock_utils.get_infra_rg_name.assert_called_once_with(INFRASTRUCTURE.SIMPLE_APIM, TEST_INDEX)
    mock_utils.build_infrastructure_tags.assert_called_once_with(INFRASTRUCTURE.SIMPLE_APIM)
    
    # Initialize policy fragments to trigger utils calls
    infra._define_policy_fragments()
    infra._define_apis()
    
    # Should call read_policy_xml for base policy fragments and APIs
    assert mock_utils.read_policy_xml.call_count >= 6  # 5 base policy fragments + 1 hello-world API
    assert mock_utils.determine_shared_policy_path.call_count >= 5

@pytest.mark.unit
def test_infrastructure_base_policy_fragments_creation(mock_utils):
    """Test that base policy fragments are created correctly."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )
    
    # Initialize policy fragments
    infra._define_policy_fragments()
    
    # Check that all base policy fragments are created
    expected_fragment_names = [
        'AuthZ-Match-All',
        'AuthZ-Match-Any',
        'Http-Response-200',
        'Product-Match-Any',
        'Remove-Request-Headers'
    ]
    
    base_fragment_names = [pf.name for pf in infra.base_pfs]
    for expected_name in expected_fragment_names:
        assert expected_name in base_fragment_names

@pytest.mark.unit
def test_infrastructure_base_apis_creation(mock_utils):
    """Test that base APIs are created correctly."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )
    
    # Initialize APIs
    infra._define_apis()
    
    # Check that hello-world API is created
    assert len(infra.base_apis) == 1
    hello_world_api = infra.base_apis[0]
    assert hello_world_api.name == 'hello-world'
    assert hello_world_api.displayName == 'Hello World'
    assert hello_world_api.path == ''
    assert len(hello_world_api.operations) == 1
    assert hello_world_api.operations[0].method == HTTP_VERB.GET


# ------------------------------
#    POLICY FRAGMENT TESTS
# ------------------------------

@pytest.mark.unit
def test_define_policy_fragments_with_none_input(mock_utils):
    """Test _define_policy_fragments with None input."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION,
        infra_pfs=None
    )
    
    # Initialize policy fragments
    pfs = infra._define_policy_fragments()
    
    # Should only have base policy fragments
    assert len(pfs) == 6
    assert all(pf.name in ['Api-Id', 'AuthZ-Match-All', 'AuthZ-Match-Any', 'Http-Response-200', 'Product-Match-Any', 'Remove-Request-Headers'] for pf in pfs)

@pytest.mark.unit
def test_define_policy_fragments_with_custom_input(mock_utils, mock_policy_fragments):
    """Test _define_policy_fragments with custom input."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION,
        infra_pfs=mock_policy_fragments
    )
    
    # Initialize policy fragments
    pfs = infra._define_policy_fragments()
    
    # Should have base + custom policy fragments
    assert len(pfs) == 8  # 6 base + 2 custom
    fragment_names = [pf.name for pf in infra.pfs]
    assert 'Test-Fragment-1' in fragment_names
    assert 'Test-Fragment-2' in fragment_names
    assert 'AuthZ-Match-All' in fragment_names


# ------------------------------
#    API TESTS
# ------------------------------

@pytest.mark.unit
def test_define_apis_with_none_input(mock_utils):
    """Test _define_apis with None input."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION,
        infra_apis=None
    )
    
    # Initialize APIs
    apis = infra._define_apis()
    
    # Should only have base APIs
    assert len(apis) == 1
    assert apis[0].name == 'hello-world'

@pytest.mark.unit
def test_define_apis_with_custom_input(mock_utils, mock_apis):
    """Test _define_apis with custom input."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION,
        infra_apis=mock_apis
    )
    
    # Initialize APIs
    apis = infra._define_apis()
    
    # Should have base + custom APIs
    assert len(apis) == 3  # 1 base + 2 custom
    api_names = [api.name for api in apis]
    assert 'test-api-1' in api_names
    assert 'test-api-2' in api_names
    assert 'hello-world' in api_names


# ------------------------------
#    BICEP PARAMETERS TESTS
# ------------------------------

@pytest.mark.unit
def test_define_bicep_parameters(mock_utils):
    """Test _define_bicep_parameters method."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )
    
    # Initialize APIs and policy fragments first
    infra._define_policy_fragments()
    infra._define_apis()
    
    bicep_params = infra._define_bicep_parameters()
    
    assert 'apimSku' in bicep_params
    assert bicep_params['apimSku']['value'] == APIM_SKU.BASICV2.value
    
    assert 'apis' in bicep_params
    assert isinstance(bicep_params['apis']['value'], list)
    assert len(bicep_params['apis']['value']) == 1  # hello-world API
    
    assert 'policyFragments' in bicep_params
    assert isinstance(bicep_params['policyFragments']['value'], list)
    assert len(bicep_params['policyFragments']['value']) == 6  # base policy fragments


# ------------------------------
#    INFRASTRUCTURE VERIFICATION TESTS
# ------------------------------

@pytest.mark.unit
def test_base_infrastructure_verification_success(mock_utils):
    """Test base infrastructure verification success."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )
    
    # Mock successful resource group check
    mock_utils.does_resource_group_exist.return_value = True
    
    # Mock successful APIM service check
    mock_apim_output = Mock()
    mock_apim_output.success = True
    mock_apim_output.json_data = {'name': 'test-apim'}
    
    # Mock successful API count check
    mock_api_output = Mock()
    mock_api_output.success = True
    mock_api_output.text = '5'  # 5 APIs
    
    # Mock successful subscription check
    mock_sub_output = Mock()
    mock_sub_output.success = True
    mock_sub_output.text = 'test-subscription-key'
    
    mock_utils.run.side_effect = [mock_apim_output, mock_api_output, mock_sub_output]
    
    result = infra._verify_infrastructure('test-rg')
    
    assert result is True
    mock_utils.does_resource_group_exist.assert_called_once_with('test-rg')
    assert mock_utils.run.call_count >= 2  # At least APIM list and API count

@pytest.mark.unit
def test_base_infrastructure_verification_missing_rg(mock_utils):
    """Test base infrastructure verification with missing resource group."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )
    
    # Mock missing resource group
    mock_utils.does_resource_group_exist.return_value = False
    
    result = infra._verify_infrastructure('test-rg')
    
    assert result is False
    mock_utils.does_resource_group_exist.assert_called_once_with('test-rg')

@pytest.mark.unit
def test_base_infrastructure_verification_missing_apim(mock_utils):
    """Test base infrastructure verification with missing APIM service."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )
    
    # Mock successful resource group check
    mock_utils.does_resource_group_exist.return_value = True
    
    # Mock failed APIM service check
    mock_apim_output = Mock()
    mock_apim_output.success = False
    mock_apim_output.json_data = None
    
    mock_utils.run.return_value = mock_apim_output
    
    result = infra._verify_infrastructure('test-rg')
    
    assert result is False

@pytest.mark.unit
def test_infrastructure_specific_verification_base(mock_utils):
    """Test the base infrastructure-specific verification method."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )
    
    # Base implementation should always return True
    result = infra._verify_infrastructure_specific('test-rg')
    
    assert result is True

# ------------------------------
#    APIM-ACA INFRASTRUCTURE SPECIFIC TESTS
# ------------------------------

@pytest.mark.unit
def test_apim_aca_infrastructure_verification_success(mock_utils):
    """Test APIM-ACA infrastructure-specific verification success."""
    infra = infrastructures.ApimAcaInfrastructure(
        rg_location=TEST_LOCATION,
        index=TEST_INDEX,
        apim_sku=APIM_SKU.BASICV2
    )
    
    # Mock successful Container Apps check
    mock_aca_output = Mock()
    mock_aca_output.success = True
    mock_aca_output.text = '3'  # 3 Container Apps
    
    mock_utils.run.return_value = mock_aca_output
    
    result = infra._verify_infrastructure_specific('test-rg')
    
    assert result is True
    mock_utils.run.assert_called_once_with(
        'az containerapp list -g test-rg --query "length(@)"', 
        print_command_to_run=False, 
        print_errors=False
    )

@pytest.mark.unit
def test_apim_aca_infrastructure_verification_failure(mock_utils):
    """Test APIM-ACA infrastructure-specific verification failure."""
    infra = infrastructures.ApimAcaInfrastructure(
        rg_location=TEST_LOCATION,
        index=TEST_INDEX,
        apim_sku=APIM_SKU.BASICV2
    )
    
    # Mock failed Container Apps check
    mock_aca_output = Mock()
    mock_aca_output.success = False
    
    mock_utils.run.return_value = mock_aca_output
    
    result = infra._verify_infrastructure_specific('test-rg')
    
    assert result is False


# ------------------------------
#    AFD-APIM-PE INFRASTRUCTURE SPECIFIC TESTS
# ------------------------------

@pytest.mark.unit
def test_afd_apim_infrastructure_verification_success(mock_utils):
    """Test AFD-APIM-PE infrastructure-specific verification success."""
    infra = infrastructures.AfdApimAcaInfrastructure(
        rg_location=TEST_LOCATION,
        index=TEST_INDEX,
        apim_sku=APIM_SKU.STANDARDV2
    )
    
    # Mock successful Front Door check
    mock_afd_output = Mock()
    mock_afd_output.success = True
    mock_afd_output.json_data = {'name': 'test-afd'}
    
    # Mock successful Container Apps check
    mock_aca_output = Mock()
    mock_aca_output.success = True
    mock_aca_output.text = '2'  # 2 Container Apps
    
    # Mock successful APIM check for private endpoints (optional third call)
    mock_apim_output = Mock()
    mock_apim_output.success = True
    mock_apim_output.text = 'apim-resource-id'
    
    mock_utils.run.side_effect = [mock_afd_output, mock_aca_output, mock_apim_output]
    
    result = infra._verify_infrastructure_specific('test-rg')
    
    assert result is True
    # Allow for 2-3 calls (3rd call is optional for private endpoint verification)
    assert mock_utils.run.call_count >= 2

@pytest.mark.unit
def test_afd_apim_infrastructure_verification_no_afd(mock_utils):
    """Test AFD-APIM-PE infrastructure-specific verification with missing AFD."""
    infra = infrastructures.AfdApimAcaInfrastructure(
        rg_location=TEST_LOCATION,
        index=TEST_INDEX,
        apim_sku=APIM_SKU.STANDARDV2
    )
    
    # Mock failed Front Door check
    mock_afd_output = Mock()
    mock_afd_output.success = False
    mock_afd_output.json_data = None
    
    mock_utils.run.return_value = mock_afd_output
    
    result = infra._verify_infrastructure_specific('test-rg')
    
    assert result is False

@pytest.mark.unit
def test_afd_apim_infrastructure_bicep_parameters(mock_utils):
    """Test AFD-APIM-PE specific Bicep parameters."""
    # Test with custom APIs (should enable ACA)
    custom_apis = [
        API('test-api', 'Test API', '/test', 'Test API description')
    ]
    
    infra = infrastructures.AfdApimAcaInfrastructure(
        rg_location=TEST_LOCATION,
        index=TEST_INDEX,
        apim_sku=APIM_SKU.STANDARDV2,
        infra_apis=custom_apis
    )
    
    # Initialize components
    infra._define_policy_fragments()
    infra._define_apis()
    
    bicep_params = infra._define_bicep_parameters()
    
    # Check AFD-specific parameters
    assert 'apimPublicAccess' in bicep_params
    assert bicep_params['apimPublicAccess']['value'] is True
    assert 'useACA' in bicep_params
    assert bicep_params['useACA']['value'] is True  # Should be True due to custom APIs
    
    # Test without custom APIs (should disable ACA)
    infra_no_apis = infrastructures.AfdApimAcaInfrastructure(
        rg_location=TEST_LOCATION,
        index=TEST_INDEX,
        apim_sku=APIM_SKU.STANDARDV2
    )
    
    # Initialize components
    infra_no_apis._define_policy_fragments()
    infra_no_apis._define_apis()
    
    bicep_params_no_apis = infra_no_apis._define_bicep_parameters()
    
    # Should disable ACA when no custom APIs
    assert bicep_params_no_apis['useACA']['value'] is False


# ------------------------------
#    INFRASTRUCTURE CLASS CONSISTENCY TESTS
# ------------------------------

@pytest.mark.unit
def test_all_concrete_infrastructure_classes_have_verification(mock_utils):
    """Test that all concrete infrastructure classes have verification methods."""
    # Test Simple APIM (uses base verification)
    simple_infra = infrastructures.SimpleApimInfrastructure(TEST_LOCATION, TEST_INDEX)
    assert hasattr(simple_infra, '_verify_infrastructure_specific')
    assert callable(simple_infra._verify_infrastructure_specific)
    
    # Test APIM-ACA (has custom verification)
    aca_infra = infrastructures.ApimAcaInfrastructure(TEST_LOCATION, TEST_INDEX)
    assert hasattr(aca_infra, '_verify_infrastructure_specific')
    assert callable(aca_infra._verify_infrastructure_specific)
    
    # Test AFD-APIM-PE (has custom verification)
    afd_infra = infrastructures.AfdApimAcaInfrastructure(TEST_LOCATION, TEST_INDEX)
    assert hasattr(afd_infra, '_verify_infrastructure_specific')
    assert callable(afd_infra._verify_infrastructure_specific)


# ------------------------------
#    DEPLOYMENT TESTS
# ------------------------------

@pytest.mark.unit
@patch('os.getcwd')
@patch('os.chdir') 
@patch('pathlib.Path')
def test_deploy_infrastructure_success(mock_path_class, mock_chdir, mock_getcwd, mock_utils):
    """Test successful infrastructure deployment."""
    # Setup mocks
    mock_getcwd.return_value = '/original/path'
    mock_infra_dir = Mock()
    mock_path_instance = Mock()
    mock_path_instance.parent = mock_infra_dir
    mock_path_class.return_value = mock_path_instance
    
    # Create a concrete subclass for testing
    class TestInfrastructure(infrastructures.Infrastructure):
        def verify_infrastructure(self) -> bool:
            return True
    
    # Mock file writing and JSON dumps to avoid MagicMock serialization issues
    mock_open = MagicMock()
    
    with patch('builtins.open', mock_open), \
         patch('json.dumps', return_value='{"mocked": "params"}') as mock_json_dumps:
        
        infra = TestInfrastructure(
            infra=INFRASTRUCTURE.SIMPLE_APIM,
            index=TEST_INDEX,
            rg_location=TEST_LOCATION
        )
        
        result = infra.deploy_infrastructure()
    
    # Verify the deployment process
    mock_utils.create_resource_group.assert_called_once()
    # The utils.run method is now called multiple times (deployment + verification steps)
    assert mock_utils.run.call_count >= 1  # At least one call for deployment
    # Note: utils.verify_infrastructure is currently commented out in the actual code
    # mock_utils.verify_infrastructure.assert_called_once()
    
    # Verify directory changes - just check that chdir was called twice (to infra dir and back)
    assert mock_chdir.call_count == 2
    # Second call should restore original path
    mock_chdir.assert_any_call('/original/path')
    
    # Verify file writing (open will be called multiple times - for reading policies and writing params)
    assert mock_open.call_count >= 1  # At least called once for writing params.json
    mock_json_dumps.assert_called_once()
    
    assert result.success is True

@pytest.mark.unit
@patch('os.getcwd')
@patch('os.chdir')
@patch('pathlib.Path')
def test_deploy_infrastructure_failure(mock_path_class, mock_chdir, mock_getcwd, mock_utils):
    """Test infrastructure deployment failure."""
    # Setup mocks for failure scenario
    mock_getcwd.return_value = '/original/path'
    mock_infra_dir = Mock()
    mock_path_instance = Mock()
    mock_path_instance.parent = mock_infra_dir
    mock_path_class.return_value = mock_path_instance
    
    # Mock failed deployment
    mock_output = Mock()
    mock_output.success = False
    mock_utils.run.return_value = mock_output
    
    # Create a concrete subclass for testing
    class TestInfrastructure(infrastructures.Infrastructure):
        def verify_infrastructure(self) -> bool:
            return True
    
    # Mock file operations to prevent actual file writes and JSON serialization issues
    with patch('builtins.open', MagicMock()), \
         patch('json.dumps', return_value='{"mocked": "params"}'):
        
        infra = TestInfrastructure(
            infra=INFRASTRUCTURE.SIMPLE_APIM,
            index=TEST_INDEX,
            rg_location=TEST_LOCATION
        )
        
        result = infra.deploy_infrastructure()
    
    # Verify the deployment process was attempted
    mock_utils.create_resource_group.assert_called_once()
    mock_utils.run.assert_called_once()
    # Note: utils.verify_infrastructure is currently commented out in the actual code
    # mock_utils.verify_infrastructure.assert_not_called()  # Should not be called on failure
    
    # Verify directory changes (should restore even on failure) 
    assert mock_chdir.call_count == 2
    # Second call should restore original path
    mock_chdir.assert_any_call('/original/path')
    
    assert result.success is False


# ------------------------------
#    CONCRETE INFRASTRUCTURE CLASSES TESTS
# ------------------------------

@pytest.mark.unit
def test_simple_apim_infrastructure_creation(mock_utils):
    """Test SimpleApimInfrastructure creation."""
    infra = infrastructures.SimpleApimInfrastructure(
        rg_location=TEST_LOCATION,
        index=TEST_INDEX,
        apim_sku=APIM_SKU.DEVELOPER
    )
    
    assert infra.infra == INFRASTRUCTURE.SIMPLE_APIM
    assert infra.index == TEST_INDEX
    assert infra.rg_location == TEST_LOCATION
    assert infra.apim_sku == APIM_SKU.DEVELOPER
    assert infra.networkMode == APIMNetworkMode.PUBLIC

@pytest.mark.unit
def test_simple_apim_infrastructure_defaults(mock_utils):
    """Test SimpleApimInfrastructure with default values."""
    infra = infrastructures.SimpleApimInfrastructure(
        rg_location=TEST_LOCATION,
        index=TEST_INDEX
    )
    
    assert infra.apim_sku == APIM_SKU.BASICV2  # default value

@pytest.mark.unit
def test_apim_aca_infrastructure_creation(mock_utils):
    """Test ApimAcaInfrastructure creation."""
    infra = infrastructures.ApimAcaInfrastructure(
        rg_location=TEST_LOCATION,
        index=TEST_INDEX,
        apim_sku=APIM_SKU.STANDARD
    )
    
    assert infra.infra == INFRASTRUCTURE.APIM_ACA
    assert infra.index == TEST_INDEX
    assert infra.rg_location == TEST_LOCATION
    assert infra.apim_sku == APIM_SKU.STANDARD
    assert infra.networkMode == APIMNetworkMode.PUBLIC

@pytest.mark.unit
def test_afd_apim_aca_infrastructure_creation(mock_utils):
    """Test AfdApimAcaInfrastructure creation."""
    infra = infrastructures.AfdApimAcaInfrastructure(
        rg_location=TEST_LOCATION,
        index=TEST_INDEX,
        apim_sku=APIM_SKU.PREMIUM
    )
    
    assert infra.infra == INFRASTRUCTURE.AFD_APIM_PE
    assert infra.index == TEST_INDEX
    assert infra.rg_location == TEST_LOCATION
    assert infra.apim_sku == APIM_SKU.PREMIUM
    assert infra.networkMode == APIMNetworkMode.PUBLIC


# ------------------------------
#    INTEGRATION TESTS
# ------------------------------

@pytest.mark.unit
def test_infrastructure_end_to_end_simple(mock_utils):
    """Test end-to-end Infrastructure creation with SimpleApim."""
    infra = infrastructures.SimpleApimInfrastructure(
        rg_location='eastus',
        index=1,
        apim_sku=APIM_SKU.DEVELOPER
    )
    
    # Initialize components
    infra._define_policy_fragments()
    infra._define_apis()
    
    # Verify all components are created correctly
    assert infra.infra == INFRASTRUCTURE.SIMPLE_APIM
    assert len(infra.base_pfs) == 6
    assert len(infra.pfs) == 6
    assert len(infra.base_apis) == 1
    assert len(infra.apis) == 1
    
    # Verify bicep parameters
    bicep_params = infra._define_bicep_parameters()
    assert bicep_params['apimSku']['value'] == 'Developer'
    assert len(bicep_params['apis']['value']) == 1
    assert len(bicep_params['policyFragments']['value']) == 6

@pytest.mark.unit
def test_infrastructure_with_all_custom_components(mock_utils, mock_policy_fragments, mock_apis):
    """Test Infrastructure creation with all custom components."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.APIM_ACA,
        index=2,
        rg_location='westus2',
        apim_sku=APIM_SKU.PREMIUM,
        networkMode=APIMNetworkMode.EXTERNAL_VNET,
        infra_pfs=mock_policy_fragments,
        infra_apis=mock_apis
    )
    
    # Initialize components
    infra._define_policy_fragments()
    infra._define_apis()
    
    # Verify all components are combined correctly
    assert len(infra.base_pfs) == 6
    assert len(infra.pfs) == 8  # 6 base + 2 custom
    assert len(infra.base_apis) == 1
    assert len(infra.apis) == 3  # 1 base + 2 custom
    
    # Verify bicep parameters include all components
    bicep_params = infra._define_bicep_parameters()
    assert bicep_params['apimSku']['value'] == 'Premium'
    assert len(bicep_params['apis']['value']) == 3
    assert len(bicep_params['policyFragments']['value']) == 8


# ------------------------------
#    ERROR HANDLING TESTS
# ------------------------------

@pytest.mark.unit
def test_infrastructure_missing_required_params():
    """Test Infrastructure creation with missing required parameters."""
    with pytest.raises(TypeError):
        infrastructures.Infrastructure()
    
    with pytest.raises(TypeError):
        infrastructures.Infrastructure(infra=INFRASTRUCTURE.SIMPLE_APIM)

@pytest.mark.unit
def test_concrete_infrastructure_missing_params():
    """Test concrete infrastructure classes with missing parameters."""
    with pytest.raises(TypeError):
        infrastructures.SimpleApimInfrastructure()
    
    with pytest.raises(TypeError):
        infrastructures.SimpleApimInfrastructure(rg_location=TEST_LOCATION)


# ------------------------------
#    EDGE CASES AND COVERAGE TESTS
# ------------------------------

@pytest.mark.unit
def test_infrastructure_empty_custom_lists(mock_utils):
    """Test Infrastructure with empty custom lists."""
    empty_pfs = []
    empty_apis = []
    
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION,
        infra_pfs=empty_pfs,
        infra_apis=empty_apis
    )
    
    # Initialize components
    infra._define_policy_fragments()
    infra._define_apis()
    
    # Empty lists should behave the same as None
    assert len(infra.pfs) == 6  # Only base policy fragments
    assert len(infra.apis) == 1  # Only base APIs

@pytest.mark.unit
def test_infrastructure_attribute_access(mock_utils):
    """Test that all Infrastructure attributes are accessible."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )
    
    # Test constructor attributes are accessible
    assert hasattr(infra, 'infra')
    assert hasattr(infra, 'index')
    assert hasattr(infra, 'rg_location')
    assert hasattr(infra, 'apim_sku')
    assert hasattr(infra, 'networkMode')
    assert hasattr(infra, 'rg_name')
    assert hasattr(infra, 'rg_tags')
    
    # Initialize components to create the lazily-loaded attributes
    infra._define_policy_fragments()
    infra._define_apis()
    
    # Test that lazy-loaded attributes are now accessible
    assert hasattr(infra, 'base_pfs')
    assert hasattr(infra, 'pfs')
    assert hasattr(infra, 'base_apis')
    assert hasattr(infra, 'apis')
    # bicep_parameters is only created during deployment via _define_bicep_parameters()
    infra._define_bicep_parameters()
    assert hasattr(infra, 'bicep_parameters')

@pytest.mark.unit
def test_infrastructure_string_representation(mock_utils):
    """Test Infrastructure string representation."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )
    
    # Test that the object can be converted to string without error
    str_repr = str(infra)
    assert isinstance(str_repr, str)
    assert 'Infrastructure' in str_repr

@pytest.mark.unit
def test_all_infrastructure_types_coverage(mock_utils):
    """Test that all infrastructure types can be instantiated."""
    # Test all concrete infrastructure classes
    simple_infra = infrastructures.SimpleApimInfrastructure(TEST_LOCATION, TEST_INDEX)
    assert simple_infra.infra == INFRASTRUCTURE.SIMPLE_APIM
    
    aca_infra = infrastructures.ApimAcaInfrastructure(TEST_LOCATION, TEST_INDEX)
    assert aca_infra.infra == INFRASTRUCTURE.APIM_ACA
    
    afd_infra = infrastructures.AfdApimAcaInfrastructure(TEST_LOCATION, TEST_INDEX)
    assert afd_infra.infra == INFRASTRUCTURE.AFD_APIM_PE

@pytest.mark.unit
def test_policy_fragment_creation_robustness(mock_utils):
    """Test that policy fragment creation is robust."""
    # Test with various mock return values
    mock_utils.read_policy_xml.side_effect = [
        '<policy1/>',
        '<policy2/>',
        '<policy3/>',
        '<policy4/>',
        '<policy5/>',
        '<policy6/>',  # Added for the new Api-Id policy fragment
        '<hello-world-policy/>'
    ]
    
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )
    
    # Initialize policy fragments
    infra._define_policy_fragments()
    infra._define_apis()
    
    # Verify all policy fragments were created with different XML
    policy_xmls = [pf.policyXml for pf in infra.base_pfs]
    assert '<policy1/>' in policy_xmls
    assert '<policy2/>' in policy_xmls
    assert '<policy3/>' in policy_xmls
    assert '<policy4/>' in policy_xmls
    assert '<policy5/>' in policy_xmls
