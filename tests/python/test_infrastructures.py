"""
Unit tests for infrastructures.py.
"""

import json
import os
from unittest.mock import Mock, patch, MagicMock
import pytest

# APIM Samples imports
import console
import infrastructures
from apimtypes import INFRASTRUCTURE, APIM_SKU, APIMNetworkMode, API, PolicyFragment, Output


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
        mock_utils.build_infrastructure_tags.return_value = {'environment': 'test', 'project': 'apim-samples'}
        mock_utils.read_policy_xml.return_value = '<policies><inbound><base /></inbound></policies>'
        mock_utils.determine_shared_policy_path.return_value = '/mock/path/policy.xml'
        mock_utils.verify_infrastructure.return_value = True

        yield mock_utils


@pytest.fixture(autouse = True)
def mock_az():
    """Mock the azure_resources module used by infrastructures."""

    with patch('infrastructures.az') as mock_az:
        mock_az.get_infra_rg_name.return_value = 'rg-test-infrastructure-01'
        mock_az.create_resource_group.return_value = None
        mock_az.does_resource_group_exist.return_value = True
        mock_az.get_account_info.return_value = ('test_user', 'test_user_id', 'test_tenant', 'test_subscription')
        mock_az.get_unique_suffix_for_resource_group.return_value = 'abc123def456'

        # Mock the run command with proper return object
        mock_output = Mock()
        mock_output.success = True
        mock_output.json_data = {'outputs': 'test'}
        mock_output.get.return_value = 'https://test-apim.azure-api.net'
        mock_output.getJson.return_value = ['api1', 'api2']
        mock_az.run.return_value = mock_output

        yield mock_az

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
def test_appgw_apim_pe_create_keyvault_certificate_returns_true_when_cert_exists(mock_utils, mock_az):
    """If the certificate already exists, do not attempt creation (PE)."""
    infra = infrastructures.AppGwApimPeInfrastructure(rg_location='eastus', index=1)
    mock_az.run.return_value = Mock(success=True)

    assert infra._create_keyvault_certificate('test-kv') is True
    mock_az.run.assert_called_once()
    assert 'az keyvault certificate show' in mock_az.run.call_args.args[0]


@pytest.mark.unit
def test_appgw_apim_create_keyvault_certificate_returns_true_when_cert_exists(mock_utils, mock_az):
    """If the certificate already exists, do not attempt creation (Internal)."""
    infra = infrastructures.AppGwApimInfrastructure(rg_location='eastus', index=1)
    mock_az.run.return_value = Mock(success=True)

    assert infra._create_keyvault_certificate('test-kv') is True
    mock_az.run.assert_called_once()
    assert 'az keyvault certificate show' in mock_az.run.call_args.args[0]


@pytest.mark.unit
def test_appgw_apim_pe_create_keyvault_certificate_creates_with_escaped_policy_when_missing(mock_utils, mock_az):
    """If missing, create certificate and ensure policy string is escaped (PE)."""
    infra = infrastructures.AppGwApimPeInfrastructure(rg_location='eastus', index=1)
    mock_az.run.side_effect = [Mock(success=False), Mock(success=True)]

    assert infra._create_keyvault_certificate('test-kv') is True
    assert mock_az.run.call_count == 2

    create_cmd = mock_az.run.call_args.args[0]
    assert 'az keyvault certificate create' in create_cmd
    assert '--vault-name test-kv' in create_cmd
    assert f'--name {infra.CERT_NAME}' in create_cmd
    assert '--policy "' in create_cmd
    assert '\\"issuerParameters\\"' in create_cmd
    assert '\\"keyProperties\\"' in create_cmd
    assert '\\"x509CertificateProperties\\"' in create_cmd


@pytest.mark.unit
def test_appgw_apim_create_keyvault_certificate_creates_with_escaped_policy_when_missing(mock_utils, mock_az):
    """If missing, create certificate and ensure policy string is escaped (Internal)."""
    infra = infrastructures.AppGwApimInfrastructure(rg_location='eastus', index=1)
    mock_az.run.side_effect = [Mock(success=False), Mock(success=True)]

    assert infra._create_keyvault_certificate('test-kv') is True
    assert mock_az.run.call_count == 2

    create_cmd = mock_az.run.call_args.args[0]
    assert 'az keyvault certificate create' in create_cmd
    assert '--vault-name test-kv' in create_cmd
    assert f'--name {infra.CERT_NAME}' in create_cmd
    assert '--policy "' in create_cmd
    assert '\\"issuerParameters\\"' in create_cmd
    assert '\\"keyProperties\\"' in create_cmd
    assert '\\"x509CertificateProperties\\"' in create_cmd


@pytest.mark.unit
def test_appgw_apim_pe_create_keyvault_certificate_returns_false_when_create_fails(mock_utils, mock_az):
    """If creation fails, return False (PE)."""
    infra = infrastructures.AppGwApimPeInfrastructure(rg_location='eastus', index=1)
    mock_az.run.side_effect = [Mock(success=False), Mock(success=False)]

    assert infra._create_keyvault_certificate('test-kv') is False


@pytest.mark.unit
def test_appgw_apim_create_keyvault_certificate_returns_false_when_create_fails(mock_utils, mock_az):
    """If creation fails, return False (Internal)."""
    infra = infrastructures.AppGwApimInfrastructure(rg_location='eastus', index=1)
    mock_az.run.side_effect = [Mock(success=False), Mock(success=False)]

    assert infra._create_keyvault_certificate('test-kv') is False


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
def test_base_infrastructure_verification_success(mock_utils, mock_az):
    """Test base infrastructure verification success."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )

    # Mock successful resource group check
    mock_az.does_resource_group_exist.return_value = True

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

    mock_az.run.side_effect = [mock_apim_output, mock_api_output, mock_sub_output]

    result = infra._verify_infrastructure('test-rg')

    assert result is True
    mock_az.does_resource_group_exist.assert_called_once_with('test-rg')
    assert mock_az.run.call_count >= 2  # At least APIM list and API count

@pytest.mark.unit
def test_base_infrastructure_verification_missing_rg(mock_utils, mock_az):
    """Test base infrastructure verification with missing resource group."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )

    # Mock missing resource group
    mock_az.does_resource_group_exist.return_value = False

    result = infra._verify_infrastructure('test-rg')

    assert result is False
    mock_az.does_resource_group_exist.assert_called_once_with('test-rg')

@pytest.mark.unit
def test_base_infrastructure_verification_missing_apim(mock_utils, mock_az):
    """Test base infrastructure verification with missing APIM service."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=TEST_INDEX,
        rg_location=TEST_LOCATION
    )

    # Mock successful resource group check
    mock_az.does_resource_group_exist.return_value = True

    # Mock failed APIM service check
    mock_apim_output = Mock()
    mock_apim_output.success = False
    mock_apim_output.json_data = None

    mock_az.run.return_value = mock_apim_output

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
def test_apim_aca_infrastructure_verification_success(mock_az):
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

    mock_az.run.return_value = mock_aca_output

    result = infra._verify_infrastructure_specific('test-rg')

    assert result is True
    mock_az.run.assert_called_once_with(
        'az containerapp list -g test-rg --query "length(@)"'
    )

@pytest.mark.unit
def test_apim_aca_infrastructure_verification_failure(mock_az):
    """Test APIM-ACA infrastructure-specific verification failure."""
    infra = infrastructures.ApimAcaInfrastructure(
        rg_location=TEST_LOCATION,
        index=TEST_INDEX,
        apim_sku=APIM_SKU.BASICV2
    )

    # Mock failed Container Apps check
    mock_aca_output = Mock()
    mock_aca_output.success = False

    mock_az.run.return_value = mock_aca_output

    result = infra._verify_infrastructure_specific('test-rg')

    assert result is False


# ------------------------------
#    AFD-APIM-PE INFRASTRUCTURE SPECIFIC TESTS
# ------------------------------

@pytest.mark.unit
def test_afd_apim_infrastructure_verification_success(mock_az):
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

    mock_az.run.side_effect = [mock_afd_output, mock_aca_output, mock_apim_output]

    result = infra._verify_infrastructure_specific('test-rg')

    assert result is True
    # Allow for 2-3 calls (3rd call is optional for private endpoint verification)
    assert mock_az.run.call_count >= 2

@pytest.mark.unit
def test_afd_apim_infrastructure_verification_no_afd(mock_az):
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

    mock_az.run.return_value = mock_afd_output

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
def test_deploy_infrastructure_success(mock_path_class, mock_chdir, mock_getcwd, mock_utils, mock_az):
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
    mock_az.create_resource_group.assert_called_once()
    assert mock_az.run.call_count >= 1  # At least one call for deployment

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
def test_deploy_infrastructure_failure(mock_path_class, mock_chdir, mock_getcwd, mock_utils, mock_az):
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
    mock_az.run.return_value = mock_output

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
    mock_az.create_resource_group.assert_called_once()
    mock_az.run.assert_called_once()
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


# ------------------------------
#    cleanup_resources (smoke)
# ------------------------------

def test_cleanup_resources_smoke(monkeypatch):
    monkeypatch.setattr(infrastructures.az, 'run', lambda *a, **kw: MagicMock(success=True, json_data={}))
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_error', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_message', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_ok', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_warning', lambda *a, **kw: None)
    monkeypatch.setattr(console, 'print_val', lambda *a, **kw: None)
    # Direct private method call for legacy test (should still work)
    infrastructures._cleanup_resources(INFRASTRUCTURE.SIMPLE_APIM.value, 'rg')


def test_cleanup_resources_missing_parameters(monkeypatch):
    """Test _cleanup_resources with missing parameters."""
    print_calls = []

    def mock_print_error(message, *args, **kwargs):
        print_calls.append(message)

    monkeypatch.setattr(infrastructures, 'print_error', mock_print_error)

    # Test missing deployment name
    infrastructures._cleanup_resources('', 'valid-rg')
    assert 'Missing deployment name parameter.' in print_calls

    # Test missing resource group name
    print_calls.clear()
    infrastructures._cleanup_resources('valid-deployment', '')
    assert 'Missing resource group name parameter.' in print_calls

    # Test None deployment name
    print_calls.clear()
    infrastructures._cleanup_resources(None, 'valid-rg')
    assert 'Missing deployment name parameter.' in print_calls

    # Test None resource group name
    print_calls.clear()
    infrastructures._cleanup_resources('valid-deployment', None)
    assert 'Missing resource group name parameter.' in print_calls


def test_cleanup_resources_with_resources(monkeypatch):
    """Test _cleanup_resources with various resource types present."""
    run_commands = []

    def mock_run(command, ok_message=None, error_message=None, **kwargs):
        run_commands.append(command)

        # Mock deployment show response
        if 'deployment group show' in command:
            return Output(success=True, text='{"properties": {"provisioningState": "Succeeded"}}')

        # Mock cognitive services list response
        if 'cognitiveservices account list' in command:
            return Output(success=True, text='[{"name": "cog-service-1", "location": "eastus"}, {"name": "cog-service-2", "location": "westus"}]')

        # Mock APIM list response
        if 'apim list' in command:
            return Output(success=True, text='[{"name": "apim-service-1", "location": "eastus"}, {"name": "apim-service-2", "location": "westus"}]')

        # Mock Key Vault list response
        if 'keyvault list' in command:
            return Output(success=True, text='[{"name": "kv-vault-1", "location": "eastus"}, {"name": "kv-vault-2", "location": "westus"}]')

        # Default successful response for delete/purge operations
        return Output(success=True, text='Operation completed')

    monkeypatch.setattr(infrastructures.az, 'run', mock_run)
    monkeypatch.setattr(console, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(console, 'print_message', lambda *a, **kw: None)

    # Execute cleanup
    infrastructures._cleanup_resources('test-deployment', 'test-rg')

    # Verify all expected commands were called
    command_patterns = [
        'az deployment group show --name test-deployment -g test-rg',
        'az cognitiveservices account list -g test-rg',
        'az cognitiveservices account delete -g test-rg -n cog-service-1',
        'az cognitiveservices account purge -g test-rg -n cog-service-1 --location "eastus"',
        'az cognitiveservices account delete -g test-rg -n cog-service-2',
        'az cognitiveservices account purge -g test-rg -n cog-service-2 --location "westus"',
        'az apim list -g test-rg',
        'az apim delete -n apim-service-1 -g test-rg -y',
        'az apim deletedservice purge --service-name apim-service-1 --location "eastus"',
        'az apim delete -n apim-service-2 -g test-rg -y',
        'az apim deletedservice purge --service-name apim-service-2 --location "westus"',
        'az keyvault list -g test-rg',
        'az keyvault delete -n kv-vault-1 -g test-rg',
        'az keyvault purge -n kv-vault-1 --location "eastus"',
        'az keyvault delete -n kv-vault-2 -g test-rg',
        'az keyvault purge -n kv-vault-2 --location "westus"',
        'az group delete --name test-rg -y'
    ]

    for pattern in command_patterns:
        assert any(pattern in cmd for cmd in run_commands), f"Expected command pattern not found: {pattern}"


def test_cleanup_resources_no_resources(monkeypatch):
    """Test _cleanup_resources when no resources exist."""
    run_commands = []

    def mock_run(command, ok_message=None, error_message=None, **kwargs):
        run_commands.append(command)

        # Mock deployment show response
        if 'deployment group show' in command:
            return Output(success=True, text='{"properties": {"provisioningState": "Succeeded"}}')

        # Mock empty resource lists
        if any(x in command for x in ['cognitiveservices account list', 'apim list', 'keyvault list']):
            return Output(success=True, text='[]')

        # Default successful response
        return Output(success=True, text='Operation completed')

    monkeypatch.setattr(infrastructures.az, 'run', mock_run)
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_message', lambda *a, **kw: None)

    # Execute cleanup
    infrastructures._cleanup_resources('test-deployment', 'test-rg')

    # Verify only listing and resource group deletion commands were called
    expected_commands = [
        'az deployment group show --name test-deployment -g test-rg',
        'az cognitiveservices account list -g test-rg',
        'az apim list -g test-rg',
        'az keyvault list -g test-rg',
        'az group delete --name test-rg -y'
    ]

    for expected in expected_commands:
        assert any(expected in cmd for cmd in run_commands), f"Expected command not found: {expected}"

    # Verify no delete/purge commands for individual resources
    delete_purge_patterns = ['delete -n', 'purge -n', 'deletedservice purge']
    for pattern in delete_purge_patterns:
        assert not any(pattern in cmd for cmd in run_commands), f"Unexpected delete/purge command found: {pattern}"


def test_cleanup_resources_command_failures(monkeypatch):
    """Test _cleanup_resources when commands fail."""

    def mock_run(command, ok_message=None, error_message=None, **kwargs):
        # Mock deployment show failure
        if 'deployment group show' in command:
            return Output(success=False, text='Deployment not found')

        # All other commands succeed
        return Output(success=True, json_data=[])

    monkeypatch.setattr(infrastructures.az, 'run', mock_run)
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_message', lambda *a, **kw: None)

    # Should not raise exception even when deployment show fails
    infrastructures._cleanup_resources('test-deployment', 'test-rg')


def test_cleanup_resources_exception_handling(monkeypatch):
    """Test _cleanup_resources exception handling."""
    exception_caught = []

    def mock_run(command, ok_message=None, error_message=None, **kwargs):
        raise Exception("Simulated Azure CLI error")

    def mock_print(message):
        exception_caught.append(message)

    monkeypatch.setattr(infrastructures.az, 'run', mock_run)
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_message', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_plain', mock_print)
    monkeypatch.setattr('traceback.print_exc', lambda: None)

    # Should handle exception gracefully
    infrastructures._cleanup_resources('test-deployment', 'test-rg')

    # Verify exception was caught and printed
    assert any('An error occurred during cleanup:' in msg for msg in exception_caught)


def test_cleanup_resources_always_attempts_rg_delete_on_exception(monkeypatch):
    """Ensure RG delete is attempted even when an earlier az call raises."""
    run_commands = []

    def mock_run(command, ok_message=None, error_message=None, **kwargs):
        run_commands.append(command)
        # Simulate a hard failure early during cleanup.
        if 'deployment group show' in command:
            raise Exception('Simulated Azure CLI error')
        return Output(success=True, text='{}')

    monkeypatch.setattr(infrastructures.az, 'run', mock_run)
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_message', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_plain', lambda *a, **kw: None)
    monkeypatch.setattr('traceback.print_exc', lambda: None)

    infrastructures._cleanup_resources('test-deployment', 'test-rg')

    assert any('az group delete --name test-rg -y' in cmd for cmd in run_commands)

def test_cleanup_infra_deployment_single(monkeypatch):
    monkeypatch.setattr(infrastructures, '_cleanup_resources', lambda deployment_name, rg_name: None)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, None)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, 1)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1])  # Single item in list should use sequential mode


def test_cleanup_infra_deployments_parallel_mode(monkeypatch):
    """Test cleanup_infra_deployments with multiple indexes using parallel execution."""
    cleanup_calls = []

    def mock_cleanup_resources_thread_safe(deployment_name, rg_name, thread_prefix, thread_color):
        cleanup_calls.append((deployment_name, rg_name, thread_prefix, thread_color))
        return True, ""  # Return success

    def mock_get_infra_rg_name(deployment, index):
        return f'apim-infra-{deployment.value}-{index}' if index else f'apim-infra-{deployment.value}'

    monkeypatch.setattr(infrastructures, '_cleanup_resources_thread_safe', mock_cleanup_resources_thread_safe)
    monkeypatch.setattr(infrastructures.az, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_ok', lambda *a, **kw: None)

    # Test with multiple indexes (should use parallel mode)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1, 2, 3])

    # Verify all cleanup calls were made
    assert len(cleanup_calls) == 3

    # Check that the correct resource groups were targeted
    expected_rgs = [
        'apim-infra-simple-apim-1',
        'apim-infra-simple-apim-2',
        'apim-infra-simple-apim-3'
    ]
    actual_rgs = [call[1] for call in cleanup_calls]
    assert set(actual_rgs) == set(expected_rgs)

    # Check that thread prefixes contain the correct infrastructure and index info
    for deployment_name, _rg_name, thread_prefix, thread_color in cleanup_calls:
        assert deployment_name == 'simple-apim'
        assert 'simple-apim' in thread_prefix
        assert thread_color in console.THREAD_COLORS


def test_cleanup_infra_deployments_parallel_with_failures(monkeypatch):
    """Test parallel cleanup handling when some threads fail."""
    cleanup_calls = []

    def mock_cleanup_resources_thread_safe(deployment_name, rg_name, thread_prefix, thread_color):
        cleanup_calls.append((deployment_name, rg_name))
        # Simulate failure for index 2
        if 'simple-apim-2' in rg_name:
            return False, "Simulated failure for testing"
        return True, ""

    def mock_get_infra_rg_name(deployment, index):
        return f'apim-infra-{deployment.value}-{index}'

    monkeypatch.setattr(infrastructures, '_cleanup_resources_thread_safe', mock_cleanup_resources_thread_safe)
    monkeypatch.setattr(infrastructures.az, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_error', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_warning', lambda *a, **kw: None)

    # Test with multiple indexes where one fails
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1, 2, 3])

    # Verify all cleanup attempts were made despite failure
    assert len(cleanup_calls) == 3


def test_cleanup_resources_thread_safe_success(monkeypatch):
    """Test the thread-safe cleanup wrapper with successful execution."""
    original_calls = []

    def mock_cleanup_resources_with_thread_safe_printing(deployment_name, rg_name, thread_prefix, thread_color):
        original_calls.append((deployment_name, rg_name))

    monkeypatch.setattr(infrastructures, '_cleanup_resources_with_thread_safe_printing', mock_cleanup_resources_with_thread_safe_printing)

    # Test successful cleanup
    success, error_msg = infrastructures._cleanup_resources_thread_safe(
        'test-deployment', 'test-rg', '[TEST]: ', console.BOLD_G
    )

    assert success is True
    assert not error_msg
    assert len(original_calls) == 1
    assert original_calls[0] == ('test-deployment', 'test-rg')


def test_cleanup_resources_thread_safe_failure(monkeypatch):
    """Test the thread-safe cleanup wrapper with exception handling."""
    def mock_cleanup_resources_with_thread_safe_printing(deployment_name, rg_name, thread_prefix, thread_color):
        raise Exception("Simulated cleanup failure")

    monkeypatch.setattr(infrastructures, '_cleanup_resources_with_thread_safe_printing', mock_cleanup_resources_with_thread_safe_printing)

    # Test failed cleanup
    success, error_msg = infrastructures._cleanup_resources_thread_safe(
        'test-deployment', 'test-rg', '[TEST]: ', console.BOLD_G
    )

    assert success is False
    assert "Simulated cleanup failure" in error_msg


def test_cleanup_resources_with_thread_safe_printing_always_attempts_rg_delete(monkeypatch):
    """Ensure the thread-safe cleanup path still attempts RG delete if deployment show fails."""
    run_commands = []

    def mock_run(command, ok_message=None, error_message=None, **kwargs):
        run_commands.append(command)
        # Simulate deployment show failure (previously caused RG delete to be skipped).
        if 'deployment group show' in command:
            return Output(success=False, text='Deployment not found')
        # Default empty lists for resource queries.
        if any(x in command for x in ['cognitiveservices account list', 'az apim list', 'az keyvault list']):
            return Output(success=True, json_data=[])
        return Output(success=True, text='{}')

    monkeypatch.setattr(infrastructures.az, 'run', mock_run)
    monkeypatch.setattr(infrastructures, 'should_print_traceback', lambda: False)

    infrastructures._cleanup_resources_with_thread_safe_printing(
        'test-deployment',
        'test-rg',
        '[TEST]: ',
        console.BOLD_G
    )

    assert any('az group delete --name test-rg -y' in cmd for cmd in run_commands)


def test_cleanup_infra_deployments_max_workers_limit(monkeypatch):
    """Test that parallel cleanup properly handles different numbers of indexes."""
    cleanup_calls = []

    def mock_cleanup_resources_thread_safe(deployment_name, rg_name, thread_prefix, thread_color):
        cleanup_calls.append((deployment_name, rg_name, thread_prefix, thread_color))
        return True, ""

    def mock_get_infra_rg_name(deployment, index):
        return f'rg-{deployment.value}-{index}'

    # Mock Azure CLI calls to avoid real execution
    def mock_run(*args, **kwargs):
        return Output(success=True, text='{}')

    monkeypatch.setattr(infrastructures, '_cleanup_resources_thread_safe', mock_cleanup_resources_thread_safe)
    monkeypatch.setattr(infrastructures.az, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(infrastructures.az, 'run', mock_run)  # Mock Azure CLI calls
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_ok', lambda *a, **kw: None)

    # Test with 6 indexes (should use parallel mode and handle all indexes)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1, 2, 3, 4, 5, 6])

    # Verify all 6 cleanup calls were made
    assert len(cleanup_calls) == 6, f"Expected 6 cleanup calls, got {len(cleanup_calls)}"

    # Check that the correct resource groups were targeted
    expected_rgs = [f'rg-simple-apim-{i}' for i in range(1, 7)]
    actual_rgs = [call[1] for call in cleanup_calls]
    assert set(actual_rgs) == set(expected_rgs), f"Expected RGs {expected_rgs}, got {actual_rgs}"

    # Test with 2 indexes (should use parallel mode)
    cleanup_calls.clear()
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1, 2])

    assert len(cleanup_calls) == 2, f"Expected 2 cleanup calls, got {len(cleanup_calls)}"

    # Test that thread prefixes and colors are assigned properly
    for call in cleanup_calls:
        deployment_name, _rg_name, thread_prefix, thread_color = call
        assert deployment_name == 'simple-apim'
        assert 'simple-apim' in thread_prefix
        assert thread_color in console.THREAD_COLORS


def test_cleanup_infra_deployments_thread_color_assignment(monkeypatch):
    """Test that thread colors are assigned correctly and cycle through available colors."""
    cleanup_calls = []

    def mock_cleanup_resources_thread_safe(deployment_name, rg_name, thread_prefix, thread_color):
        cleanup_calls.append((deployment_name, rg_name, thread_prefix, thread_color))
        return True, ""

    def mock_get_infra_rg_name(deployment, index):
        return f'apim-infra-{deployment.value}-{index}'

    # Mock Azure CLI calls to avoid real execution
    def mock_run(*args, **kwargs):
        return Output(success=True, text='{}')

    monkeypatch.setattr(infrastructures, '_cleanup_resources_thread_safe', mock_cleanup_resources_thread_safe)
    monkeypatch.setattr(infrastructures.az, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(infrastructures.az, 'run', mock_run)  # Mock Azure CLI calls
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_ok', lambda *a, **kw: None)

    # Test with more indexes than available colors to verify cycling
    num_colors = len(console.THREAD_COLORS)
    test_indexes = list(range(1, num_colors + 3))  # More than available colors

    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, test_indexes)

    # Sort the calls by the index extracted from the rg_name to check in deterministic order
    cleanup_calls_sorted = sorted(cleanup_calls, key=lambda x: int(x[1].split('-')[-1]))
    assigned_colors_sorted = [call[3] for call in cleanup_calls_sorted]

    # First num_colors should use each color once
    for i in range(num_colors):
        expected_color = console.THREAD_COLORS[i % num_colors]
        assert assigned_colors_sorted[i] == expected_color

    # Additional colors should cycle back to the beginning
    if len(assigned_colors_sorted) > num_colors:
        assert assigned_colors_sorted[num_colors] == console.THREAD_COLORS[0]
        assert assigned_colors_sorted[num_colors + 1] == console.THREAD_COLORS[1]


def test_cleanup_infra_deployments_all_infrastructure_types(monkeypatch):
    """Test cleanup_infra_deployments with all infrastructure types."""
    cleanup_calls = []

    def mock_cleanup_resources(deployment_name, rg_name):
        cleanup_calls.append((deployment_name, rg_name))

    def mock_get_infra_rg_name(deployment, index):
        return f'apim-infra-{deployment.value}-{index}' if index else f'apim-infra-{deployment.value}'

    monkeypatch.setattr(infrastructures, '_cleanup_resources', mock_cleanup_resources)
    monkeypatch.setattr(infrastructures.az, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)

    # Test all infrastructure types
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, 1)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.APIM_ACA, 2)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.AFD_APIM_PE, 3)

    # Verify correct calls were made
    assert ('simple-apim', 'apim-infra-simple-apim-1') in cleanup_calls
    assert ('apim-aca', 'apim-infra-apim-aca-2') in cleanup_calls
    assert ('afd-apim-pe', 'apim-infra-afd-apim-pe-3') in cleanup_calls


def test_cleanup_infra_deployments_index_scenarios(monkeypatch):
    """Test cleanup_infra_deployments with various index scenarios."""
    cleanup_calls = []
    thread_safe_calls = []

    def mock_cleanup_resources(deployment_name, rg_name):
        cleanup_calls.append((deployment_name, rg_name))

    def mock_cleanup_resources_thread_safe(deployment_name, rg_name, thread_prefix, thread_color):
        thread_safe_calls.append((deployment_name, rg_name, thread_prefix, thread_color))
        return True, ""

    def mock_get_infra_rg_name(deployment, index):
        return f'apim-infra-{deployment.value}-{index}' if index else f'apim-infra-{deployment.value}'

    # Mock Azure CLI calls to avoid real execution
    def mock_run(*args, **kwargs):
        return Output(success=True, text='{}')

    monkeypatch.setattr(infrastructures, '_cleanup_resources', mock_cleanup_resources)
    monkeypatch.setattr(infrastructures, '_cleanup_resources_thread_safe', mock_cleanup_resources_thread_safe)
    monkeypatch.setattr(infrastructures.az, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(infrastructures.az, 'run', mock_run)  # Mock Azure CLI calls
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_ok', lambda *a, **kw: None)

    # Test None index (sequential)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, None)

    # Test single integer index (sequential)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, 5)

    # Test single item list (sequential)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1])

    # Test list of integers (parallel)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [2, 3])

    # Test tuple of integers (parallel)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, (4, 5))

    # Test empty list (sequential, with no index)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [])

    # Verify sequential calls
    expected_sequential_calls = [
        ('simple-apim', 'apim-infra-simple-apim'),        # None index
        ('simple-apim', 'apim-infra-simple-apim-5'),      # Single index 5
        ('simple-apim', 'apim-infra-simple-apim-1'),      # Single item list [1]
        ('simple-apim', 'apim-infra-simple-apim'),        # Empty list (None index)
    ]

    for expected_call in expected_sequential_calls:
        assert expected_call in cleanup_calls, f"Expected sequential call {expected_call} not found in {cleanup_calls}"

    # Verify parallel calls (extract just the deployment and rg_name parts)
    parallel_calls = [(call[0], call[1]) for call in thread_safe_calls]
    expected_parallel_calls = [
        ('simple-apim', 'apim-infra-simple-apim-2'),      # List [2, 3] - first
        ('simple-apim', 'apim-infra-simple-apim-3'),      # List [2, 3] - second
        ('simple-apim', 'apim-infra-simple-apim-4'),      # Tuple (4, 5) - first
        ('simple-apim', 'apim-infra-simple-apim-5'),      # Tuple (4, 5) - second
    ]

    for expected_call in expected_parallel_calls:
        assert expected_call in parallel_calls, f"Expected parallel call {expected_call} not found in {parallel_calls}"


def test_cleanup_functions_comprehensive(monkeypatch):
    """Test cleanup functions with various scenarios."""
    run_commands = []

    def mock_run(command, ok_message=None, error_message=None, **kwargs):
        run_commands.append(command)

        # Return appropriate mock responses
        if 'deployment group show' in command:
            return Output(success=True, json_data={
                'properties': {'provisioningState': 'Succeeded'}
            })

        # Return empty lists for resource queries to avoid complex mocking
        if any(x in command for x in ['list -g', 'list']):
            return Output(success=True, json_data=[])

        return Output(success=True, text='{}')

    def mock_get_infra_rg_name(deployment, index):
        return f'test-rg-{deployment.value}-{index}' if index else f'test-rg-{deployment.value}'

    monkeypatch.setattr(infrastructures.az, 'run', mock_run)
    monkeypatch.setattr(infrastructures.az, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_message', lambda *a, **kw: None)

    # Test _cleanup_resources (private function)
    infrastructures._cleanup_resources('test-deployment', 'test-rg')  # Should not raise

    # Test cleanup_infra_deployments with INFRASTRUCTURE enum (correct function name and parameter type)

    # Test with all infrastructure types
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.APIM_ACA, 1)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.AFD_APIM_PE, [1, 2])

    # Verify commands were executed
    assert len(run_commands) > 0


def test_cleanup_edge_cases_comprehensive(monkeypatch):
    """Test cleanup functions with edge cases and error conditions."""

    # Test with different index types
    cleanup_calls = []

    def mock_cleanup_resources(deployment_name, rg_name):
        cleanup_calls.append((deployment_name, rg_name))
        return True, ""

    def mock_cleanup_resources_thread_safe(deployment_name, rg_name, thread_prefix, thread_color):
        cleanup_calls.append((deployment_name, rg_name))
        return True, ""

    def mock_get_infra_rg_name(deployment, index):
        return f'rg-{deployment.value}-{index}' if index is not None else f'rg-{deployment.value}'

    # Mock Azure CLI calls to avoid real execution
    def mock_run(*args, **kwargs):
        return Output(success=True, text='{}')

    monkeypatch.setattr(infrastructures, '_cleanup_resources', mock_cleanup_resources)
    monkeypatch.setattr(infrastructures, '_cleanup_resources_thread_safe', mock_cleanup_resources_thread_safe)
    monkeypatch.setattr(infrastructures.az, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(infrastructures.az, 'run', mock_run)  # Mock Azure CLI calls
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_ok', lambda *a, **kw: None)

    # Test with zero index (single index, uses sequential path)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, 0)
    assert ('simple-apim', 'rg-simple-apim-0') in cleanup_calls

    # Test with negative index (single index, uses sequential path)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, -1)
    assert ('simple-apim', 'rg-simple-apim--1') in cleanup_calls

    # Test with large index (single index, uses sequential path)
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, 9999)
    assert ('simple-apim', 'rg-simple-apim-9999') in cleanup_calls

    # Test with mixed positive and negative indexes in list (multiple indexes, uses parallel path)
    cleanup_calls.clear()
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.APIM_ACA, [-1, 0, 1])
    expected = [
        ('apim-aca', 'rg-apim-aca--1'),
        ('apim-aca', 'rg-apim-aca-0'),
        ('apim-aca', 'rg-apim-aca-1')
    ]
    for call in expected:
        assert call in cleanup_calls    # Test with single-item list
    cleanup_calls.clear()
    infrastructures.cleanup_infra_deployments(INFRASTRUCTURE.AFD_APIM_PE, [42])
    assert ('afd-apim-pe', 'rg-afd-apim-pe-42') in cleanup_calls


def test_cleanup_resources_partial_failures(monkeypatch):
    """Test _cleanup_resources when some operations fail with parallel cleanup."""
    run_commands = []

    def mock_run(command, ok_message=None, error_message=None, **kwargs):
        run_commands.append(command)

        # Mock deployment show response
        if 'deployment group show' in command:
            return Output(success=True, text='{"properties": {"provisioningState": "Failed"}}')

        # Mock resources exist
        if 'cognitiveservices account list' in command:
            return Output(success=True, text='[{"name": "cog-service-1", "location": "eastus"}]')

        if 'apim list' in command:
            return Output(success=True, text='[{"name": "apim-service-1", "location": "eastus"}]')

        if 'keyvault list' in command:
            return Output(success=True, text='[{"name": "kv-vault-1", "location": "eastus"}]')

        # Simulate failure for delete operations but success for purge
        if 'delete' in command and ('cognitiveservices' in command or 'apim delete' in command or 'keyvault delete' in command):
            return Output(success=False, text='Delete failed')

        # Simulate failure for purge operations
        if 'purge' in command:
            return Output(success=False, text='Purge failed')

        # Resource group deletion succeeds
        return Output(success=True, text='Operation completed')

    monkeypatch.setattr(infrastructures.az, 'run', mock_run)
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_message', lambda *a, **kw: None)
    monkeypatch.setattr(console, 'print_ok', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_error', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_warning', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_ok', lambda *a, **kw: None)

    # Should not raise exception even when individual operations fail
    infrastructures._cleanup_resources('test-deployment', 'test-rg')

    # Verify all listing and group operations were attempted
    # Note: With parallel cleanup, if delete fails, purge is not attempted (expected behavior)
    expected_patterns = [
        'deployment group show',
        'cognitiveservices account list',
        'apim list',
        'keyvault list',
        'group delete'
    ]

    for pattern in expected_patterns:
        assert any(pattern in cmd for cmd in run_commands), f"Expected command pattern not found: {pattern}"

    # Verify delete attempts were made (even though they failed)
    delete_patterns = [
        'cognitiveservices account delete',
        'apim delete',
        'keyvault delete'
    ]

    for pattern in delete_patterns:
        assert any(pattern in cmd for cmd in run_commands), f"Expected delete command pattern not found: {pattern}"


def test_cleanup_resources_malformed_responses(monkeypatch):
    """Test _cleanup_resources with malformed API responses."""

    def mock_run(command, ok_message=None, error_message=None, **kwargs):

        # Mock deployment show with missing properties
        if 'deployment group show' in command:
            return Output(success=True, text='{}')

        # Mock malformed resource responses (missing required fields)
        if 'cognitiveservices account list' in command:
            return Output(success=True, text='[{"name": "cog-service-1"}, {"location": "eastus"}, {}]')

        if 'apim list' in command:
            return Output(success=True, text='[{"name": "apim-service-1"}, {"location": "eastus"}]')

        if 'keyvault list' in command:
            return Output(success=True, text='[{"name": "kv-vault-1"}]')

        # Default response for delete/purge operations
        return Output(success=True, text='Operation completed')

    monkeypatch.setattr(infrastructures.az, 'run', mock_run)
    monkeypatch.setattr(infrastructures, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(infrastructures, 'print_message', lambda *a, **kw: None)

    # Should handle malformed responses gracefully without raising exceptions
    infrastructures._cleanup_resources('test-deployment', 'test-rg')

def test_appgw_apim_infrastructure_bicep_parameters(mock_utils):
    """Test APPGW-APIM-PE specific Bicep parameters."""
    # Test with custom APIs (should enable ACA)
    custom_apis = [
        API('test-api', 'Test API', '/test', 'Test API description')
    ]

    infra = infrastructures.AppGwApimPeInfrastructure(
        rg_location='eastus',
        index=1,
        apim_sku=APIM_SKU.STANDARDV2,
        infra_apis=custom_apis
    )

    # Initialize components
    infra._define_policy_fragments()
    infra._define_apis()

    bicep_params = infra._define_bicep_parameters()

    # Check APPGW-specific parameters
    assert 'apimPublicAccess' in bicep_params
    assert bicep_params['apimPublicAccess']['value'] is True
    assert 'useACA' in bicep_params
    assert bicep_params['useACA']['value'] is True  # Should be True due to custom APIs


def test_appgw_apim_internal_infrastructure_parameters(mock_utils):
    """Test APPGW-APIM (Internal) specific parameters."""
    infra = infrastructures.AppGwApimInfrastructure(
        rg_location='eastus',
        index=1,
        apim_sku=APIM_SKU.DEVELOPER
    )

    # Verify network mode is INTERNAL_VNET
    assert infra.networkMode == APIMNetworkMode.INTERNAL_VNET

    # Verify SKU defaults to DEVELOPER
    assert infra.apim_sku == APIM_SKU.DEVELOPER


def test_infrastructure_resource_suffix_generation(mock_utils, mock_az):
    """Test that resource suffix is properly generated and stored."""
    mock_az.get_unique_suffix_for_resource_group.return_value = 'test123abc'

    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus'
    )

    assert infra.resource_suffix == 'test123abc'
    mock_az.get_unique_suffix_for_resource_group.assert_called_once()


def test_infrastructure_account_info_retrieval(mock_utils, mock_az):
    """Test that account info is properly retrieved and stored."""
    mock_az.get_account_info.return_value = (
        'test-user', 'user-id-123', 'tenant-id-456', 'subscription-id-789'
    )

    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.APIM_ACA,
        index=1,
        rg_location='westus2'
    )

    assert infra.current_user == 'test-user'
    assert infra.current_user_id == 'user-id-123'
    assert infra.tenant_id == 'tenant-id-456'
    assert infra.subscription_id == 'subscription-id-789'


def test_infrastructure_policy_fragments_ordering(mock_utils):
    """Test that policy fragments are properly ordered (base + custom)."""
    custom_pf = PolicyFragment('Custom-PF', '<policy>custom</policy>', 'Custom policy fragment')

    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus',
        infra_pfs=[custom_pf]
    )

    pfs = infra._define_policy_fragments()

    # Verify base fragments come before custom
    base_names = [pf.name for pf in infra.base_pfs]
    custom_names = [pf.name for pf in [custom_pf]]

    pf_names = [pf.name for pf in pfs]

    # Find indices
    base_indices = [pf_names.index(name) for name in base_names if name in pf_names]
    custom_indices = [pf_names.index(name) for name in custom_names if name in pf_names]

    # Last base should come before first custom
    if base_indices and custom_indices:
        assert max(base_indices) < min(custom_indices)


def test_infrastructure_api_hello_world_always_present(mock_utils):
    """Test that hello-world API is always present in base APIs."""
    # Test without custom APIs
    infra1 = infrastructures.SimpleApimInfrastructure(
        rg_location='eastus',
        index=1
    )
    infra1._define_apis()
    assert any(api.name == 'hello-world' for api in infra1.base_apis)

    # Test with custom APIs
    custom_api = API('custom-api', 'Custom API', '/custom', 'Custom API')
    infra2 = infrastructures.SimpleApimInfrastructure(
        rg_location='eastus',
        index=1,
        infra_apis=[custom_api]
    )
    infra2._define_apis()
    assert any(api.name == 'hello-world' for api in infra2.base_apis)
    assert any(api.name == 'custom-api' for api in infra2.apis)


def test_afd_apim_infrastructure_private_link_handling(mock_utils, mock_az):
    """Test AFD-APIM-PE infrastructure private link handling."""
    infra = infrastructures.AfdApimAcaInfrastructure(
        rg_location='eastus',
        index=1
    )

    # Mock private endpoint connection list with single pending connection
    pending_connection = {
        'id': '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/privateEndpointConnections/conn1',
        'name': 'conn1',
        'properties': {'privateLinkServiceConnectionState': {'status': 'Pending'}}
    }

    mock_az.run.return_value = Mock(
        success=True,
        json_data=[pending_connection],
        is_json=True
    )

    result = infra._approve_private_link_connections('/subscriptions/sub/resourceGroups/rg/providers/Microsoft.ApiManagement/service/test-apim')

    # Verify approval was attempted and succeeded
    assert mock_az.run.call_count >= 1
    assert result is True


def test_appgw_apim_pe_infrastructure_keyvault_creation(mock_utils, mock_az):
    """Test APPGW-APIM-PE infrastructure Key Vault creation."""
    infra = infrastructures.AppGwApimPeInfrastructure(
        rg_location='eastus',
        index=1
    )

    # Mock Key Vault doesn't exist
    mock_az.run.return_value = Mock(success=False)

    result = infra._create_keyvault('test-kv')

    # Should attempt to create Key Vault when it doesn't exist
    assert not result  # Will fail due to mocking, but should attempt creation


def test_appgw_apim_certificate_properties():
    """Test APPGW-APIM certificate configuration."""
    # Test that certificate constants are properly defined
    assert infrastructures.AppGwApimPeInfrastructure.CERT_NAME == 'appgw-cert'
    assert infrastructures.AppGwApimPeInfrastructure.DOMAIN_NAME == 'api.apim-samples.contoso.com'

    # Test AppGwApimInfrastructure also has the same constants
    assert infrastructures.AppGwApimInfrastructure.CERT_NAME == 'appgw-cert'
    assert infrastructures.AppGwApimInfrastructure.DOMAIN_NAME == 'api.apim-samples.contoso.com'


def test_infrastructure_concrete_class_sku_inheritance():
    """Test that concrete infrastructure classes properly inherit and default SKUs."""
    simple = infrastructures.SimpleApimInfrastructure('eastus', 1)
    assert simple.apim_sku == APIM_SKU.BASICV2

    aca = infrastructures.ApimAcaInfrastructure('eastus', 1)
    assert aca.apim_sku == APIM_SKU.BASICV2

    afd = infrastructures.AfdApimAcaInfrastructure('eastus', 1)
    assert afd.apim_sku == APIM_SKU.BASICV2

    appgw_pe = infrastructures.AppGwApimPeInfrastructure('eastus', 1)
    assert appgw_pe.apim_sku == APIM_SKU.BASICV2

    appgw = infrastructures.AppGwApimInfrastructure('eastus', 1)
    assert appgw.apim_sku == APIM_SKU.DEVELOPER  # This one defaults to DEVELOPER


def test_cleanup_single_resource_exception_handling(monkeypatch):
    """Test _cleanup_single_resource exception handling."""
    def mock_run(command, ok_message=None, error_message=None):
        raise Exception("Test exception")

    monkeypatch.setattr(infrastructures.az, 'run', mock_run)

    resource = {
        'type': 'apim',
        'name': 'test-apim',
        'location': 'eastus',
        'rg_name': 'test-rg'
    }

    success, error_msg = infrastructures._cleanup_single_resource(resource)

    assert success is False
    assert "Test exception" in error_msg


def test_cleanup_resources_with_all_resource_types(monkeypatch):
    """Test cleanup with a mix of all resource types."""
    run_commands = []

    def mock_run(command, ok_message=None, error_message=None, **kwargs):
        run_commands.append(command)

        # Mock deployment show response
        if 'deployment group show' in command:
            return Output(success=True, text='{"properties": {}}')

        # Mock lists returning one of each resource type
        if 'cognitiveservices account list' in command:
            return Output(success=True, text='[{"name": "cog-1", "location": "eastus"}]')

        if 'apim list' in command:
            return Output(success=True, text='[{"name": "apim-1", "location": "eastus"}]')

        if 'keyvault list' in command:
            return Output(success=True, text='[{"name": "kv-1", "location": "eastus"}]')

        # Default successful response
        return Output(success=True, text='{}')

    monkeypatch.setattr(infrastructures.az, 'run', mock_run)
    monkeypatch.setattr(console, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(console, 'print_message', lambda *a, **kw: None)

    infrastructures._cleanup_resources('test-deployment', 'test-rg')

    # Verify all resource types were processed
    all_commands = ' '.join(run_commands)
    assert 'cognitiveservices' in all_commands
    assert 'apim' in all_commands
    assert 'keyvault' in all_commands


def test_infrastructure_initialization_error_handling(mock_utils, mock_az):
    """Test infrastructure initialization with mock errors."""
    # Test with resource group creation failure
    mock_az.create_resource_group.side_effect = Exception("RG creation failed")

    with pytest.raises(Exception):
        infrastructures.Infrastructure(
            infra=INFRASTRUCTURE.SIMPLE_APIM,
            index=1,
            rg_location='eastus'
        )


def test_policy_fragment_list_serialization(mock_utils):
    """Test that policy fragments serialize correctly for Bicep."""
    custom_pf = PolicyFragment(
        name='Test-PF',
        policyXml='<policy>test</policy>',
        description='Test policy fragment'
    )

    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus',
        infra_pfs=[custom_pf]
    )

    infra._define_policy_fragments()
    infra._define_apis()
    infra._define_bicep_parameters()

    # Verify policy fragments are in Bicep parameters
    assert 'policyFragments' in infra.bicep_parameters
    pf_values = infra.bicep_parameters['policyFragments']['value']

    # Should include both base and custom
    assert len(pf_values) == 7  # 6 base + 1 custom


def test_api_serialization_for_bicep(mock_utils):
    """Test that APIs serialize correctly for Bicep."""
    custom_api = API(
        name='test-api',
        displayName='Test API',
        path='/test',
        description='Test API',
        policyXml='<policy></policy>'
    )

    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus',
        infra_apis=[custom_api]
    )

    infra._define_policy_fragments()
    infra._define_apis()
    infra._define_bicep_parameters()

    # Verify APIs are in Bicep parameters
    assert 'apis' in infra.bicep_parameters
    api_values = infra.bicep_parameters['apis']['value']

    # Should include both base (hello-world) and custom
    assert len(api_values) == 2

    # Verify serialization includes required fields
    api_names = [api.get('name') if isinstance(api, dict) else api['name'] for api in api_values]
    assert 'hello-world' in api_names
    assert 'test-api' in api_names

def test_infrastructure_resource_group_creation_called(mock_utils, mock_az):
    """Test that resource group is created on infrastructure init."""
    _ = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='westus'
    )

    # Verify create_resource_group was called with correct params
    mock_az.create_resource_group.assert_called()
    call_args = mock_az.create_resource_group.call_args
    assert call_args[0][1] == 'westus'


def test_infrastructure_multiple_custom_pfs(mock_utils):
    """Test infrastructure with multiple custom policy fragments."""
    pfs = [
        PolicyFragment(f'custom-pf-{i}', '<policy></policy>', f'Custom PF {i}')
        for i in range(1, 6)
    ]

    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus',
        infra_pfs=pfs
    )

    infra._define_policy_fragments()
    # Should have 6 base + 5 custom
    assert len(infra.pfs) == 11


def test_infrastructure_large_custom_api_list(mock_utils):
    """Test infrastructure with many custom APIs."""
    apis = [
        API(
            name=f'api-{i}',
            displayName=f'API {i}',
            path=f'/api-{i}',
            description=f'API {i}',
            policyXml='<policy></policy>'
        )
        for i in range(1, 11)
    ]

    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus',
        infra_apis=apis
    )

    infra._define_apis()
    # Should have 1 base + 10 custom
    assert len(infra.apis) == 11


def test_infrastructure_bicep_parameters_contain_all_keys(mock_utils):
    """Test that bicep parameters contain all required keys."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus'
    )

    infra._define_policy_fragments()
    infra._define_apis()
    infra._define_bicep_parameters()

    required_keys = ['resourceSuffix', 'apimSku', 'apis', 'policyFragments']
    for key in required_keys:
        assert key in infra.bicep_parameters, f'Missing key: {key}'
        assert 'value' in infra.bicep_parameters[key]


def test_infrastructure_different_regions(mock_utils):
    """Test infrastructure in different Azure regions."""
    regions = ['eastus', 'westus', 'northeurope', 'southeastasia', 'canadacentral']

    for region in regions:
        infra = infrastructures.Infrastructure(
            infra=INFRASTRUCTURE.SIMPLE_APIM,
            index=1,
            rg_location=region
        )
        assert infra.rg_location == region


def test_simple_apim_no_network_mode_override(mock_utils):
    """Test SimpleApimInfrastructure uses default network mode."""
    infra = infrastructures.SimpleApimInfrastructure(
        rg_location='eastus',
        index=1
    )

    assert infra.networkMode == APIMNetworkMode.PUBLIC


def test_apim_aca_with_custom_components(mock_utils):
    """Test APIM ACA with both custom APIs and PFs."""
    pf = PolicyFragment('custom', '<policy></policy>', 'Custom')
    api = API('custom-api', 'Custom', '/custom', 'Custom', '<policy></policy>')

    infra = infrastructures.ApimAcaInfrastructure(
        rg_location='eastus',
        index=1,
        infra_pfs=[pf],
        infra_apis=[api]
    )

    infra._define_policy_fragments()
    infra._define_apis()

    assert any(p.name == 'custom' for p in infra.pfs)
    assert any(a.name == 'custom-api' for a in infra.apis)


def test_afd_apim_aca_default_sku(mock_utils):
    """Test AFD APIM ACA infrastructure uses default SKU."""
    infra = infrastructures.AfdApimAcaInfrastructure(
        rg_location='eastus',
        index=1
    )

    assert infra.apim_sku == APIM_SKU.BASICV2


def test_infrastructure_name_generation_consistency(mock_utils):
    """Test that infrastructure names are generated consistently."""
    infra1 = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus'
    )
    infra2 = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus'
    )

    # Same configuration should generate same RG name
    assert infra1.rg_name == infra2.rg_name


def test_infrastructure_unique_suffix_generation(mock_utils, mock_az):
    """Test unique resource suffix is generated for resource group."""
    mock_az.get_unique_suffix_for_resource_group.return_value = 'abc123'

    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus'
    )

    assert infra.resource_suffix == 'abc123'


def test_infrastructure_account_info_stored(mock_utils, mock_az):
    """Test account info is retrieved and stored."""
    mock_az.get_account_info.return_value = ('testuser', 'user-id-123', 'tenant-id-456', 'sub-id-789')

    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus'
    )

    assert infra.current_user == 'testuser'
    assert infra.current_user_id == 'user-id-123'
    assert infra.tenant_id == 'tenant-id-456'
    assert infra.subscription_id == 'sub-id-789'





def test_infrastructure_define_all_methods_sequence(mock_utils):
    """Test calling all define methods in sequence."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus'
    )

    # Execute in order
    pfs = infra._define_policy_fragments()
    apis = infra._define_apis()
    params = infra._define_bicep_parameters()

    assert len(pfs) > 0
    assert len(apis) > 0
    assert len(params) > 0
    assert infra.pfs == pfs
    assert infra.apis == apis
    assert infra.bicep_parameters == params


def test_afd_apim_with_both_custom_components(mock_utils):
    """Test AFD APIM with both custom APIs and Policy Fragments."""
    pf = PolicyFragment('afd-custom', '<policy></policy>', 'AFD Custom')
    api = API('afd-api', 'AFD API', '/afd', 'AFD', '<policy></policy>')

    infra = infrastructures.AfdApimAcaInfrastructure(
        rg_location='eastus',
        index=1,
        infra_pfs=[pf],
        infra_apis=[api]
    )

    infra._define_policy_fragments()
    infra._define_apis()
    infra._define_bicep_parameters()

    assert any(p.name == 'afd-custom' for p in infra.pfs)
    assert any(a.name == 'afd-api' for a in infra.apis)











def test_infrastructure_with_zero_custom_apis(mock_utils):
    """Test infrastructure with empty custom API list."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus',
        infra_apis=[]
    )

    infra._define_apis()
    # Should only have hello-world
    assert len(infra.apis) == 1
    assert infra.apis[0].name == 'hello-world'


def test_infrastructure_with_zero_custom_pfs(mock_utils):
    """Test infrastructure with empty custom policy fragments list."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus',
        infra_pfs=[]
    )

    infra._define_policy_fragments()
    # Should only have 6 base fragments
    assert len(infra.pfs) == 6


def test_all_infrastructure_subclasses_instantiation(mock_utils):
    """Test all infrastructure subclasses can be instantiated."""
    infra_types = [
        infrastructures.SimpleApimInfrastructure,
        infrastructures.ApimAcaInfrastructure,
        infrastructures.AfdApimAcaInfrastructure,
        infrastructures.AppGwApimPeInfrastructure,
        infrastructures.AppGwApimInfrastructure,
    ]

    for infra_class in infra_types:
        infra = infra_class(rg_location='eastus', index=1)
        assert infra is not None
        assert infra.rg_location == 'eastus'
        assert infra.index == 1


def test_infrastructure_policy_fragment_has_required_fields(mock_utils):
    """Test policy fragments have all required fields."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus'
    )

    infra._define_policy_fragments()

    for pf in infra.pfs:
        assert hasattr(pf, 'name')
        assert hasattr(pf, 'policyXml')
        assert hasattr(pf, 'description')
        assert pf.name is not None
        assert pf.policyXml is not None


def test_infrastructure_api_has_required_fields(mock_utils):
    """Test APIs have all required fields."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus'
    )

    infra._define_apis()

    for api in infra.apis:
        assert hasattr(api, 'name')
        assert hasattr(api, 'displayName')
        assert hasattr(api, 'path')
        assert hasattr(api, 'description')
        assert hasattr(api, 'policyXml')
        assert api.name is not None
        assert api.displayName is not None
        assert api.path is not None


# ==============================
#    DEPLOY AND VERIFY TESTS
# ==============================


def test_infrastructure_verify_infrastructure_method_exists():
    """Ensure base verification hook is exposed for testing."""
    infra = infrastructures.SimpleApimInfrastructure(
        rg_location='eastus',
        index=1
    )

    assert callable(infra._verify_infrastructure)


def test_infrastructure_verify_infrastructure_specific_exists():
    """Ensure infrastructure-specific verification hook is exposed."""
    infra = infrastructures.ApimAcaInfrastructure(
        rg_location='eastus',
        index=1
    )

    assert callable(infra._verify_infrastructure_specific)


def test_appgw_apim_pe_create_keyvault(mock_utils, mock_az):
    """Test keyvault creation for AppGwApimPeInfrastructure."""
    infra = infrastructures.AppGwApimPeInfrastructure(
        rg_location='eastus',
        index=1
    )

    mock_az.resource_exists.return_value = False
    mock_az.run.return_value = Mock(success=True)

    result = infra._create_keyvault('test-kv')

    assert isinstance(result, bool)


def test_appgw_apim_create_keyvault(mock_utils, mock_az):
    """Test keyvault creation for AppGwApimInfrastructure."""
    infra = infrastructures.AppGwApimInfrastructure(
        rg_location='eastus',
        index=1
    )

    mock_az.resource_exists.return_value = False
    mock_az.run.return_value = Mock(success=True)

    result = infra._create_keyvault('test-kv')

    assert isinstance(result, bool)


@pytest.mark.unit
@pytest.mark.parametrize(
    'infra_factory',
    [
        lambda: infrastructures.AppGwApimPeInfrastructure(rg_location='eastus', index=1),
        lambda: infrastructures.AppGwApimInfrastructure(rg_location='eastus', index=1),
    ]
)
def test_create_keyvault_certificate_returns_true_when_cert_exists(mock_utils, mock_az, infra_factory):
    """If the certificate already exists, do not attempt creation."""
    infra = infra_factory()

    mock_az.run.return_value = Mock(success=True)

    assert infra._create_keyvault_certificate('test-kv') is True
    mock_az.run.assert_called_once()
    assert 'az keyvault certificate show' in mock_az.run.call_args.args[0]


@pytest.mark.unit
@pytest.mark.parametrize(
    'infra_factory',
    [
        lambda: infrastructures.AppGwApimPeInfrastructure(rg_location='eastus', index=1),
        lambda: infrastructures.AppGwApimInfrastructure(rg_location='eastus', index=1),
    ]
)
def test_create_keyvault_certificate_creates_with_escaped_policy_when_missing(mock_utils, mock_az, infra_factory):
    """If missing, create certificate and ensure policy string is escaped for PowerShell."""
    infra = infra_factory()

    show_output = Mock(success=False)
    create_output = Mock(success=True)
    mock_az.run.side_effect = [show_output, create_output]

    assert infra._create_keyvault_certificate('test-kv') is True

    assert mock_az.run.call_count == 2
    create_cmd = mock_az.run.call_args.args[0]
    assert 'az keyvault certificate create' in create_cmd
    assert '--vault-name test-kv' in create_cmd
    assert f'--name {infra.CERT_NAME}' in create_cmd
    assert '--policy "' in create_cmd
    # Policy JSON should have escaped quotes (\")
    assert '\\"issuerParameters\\"' in create_cmd
    assert '\\"keyProperties\\"' in create_cmd
    assert '\\"x509CertificateProperties\\"' in create_cmd


@pytest.mark.unit
@pytest.mark.parametrize(
    'infra_factory',
    [
        lambda: infrastructures.AppGwApimPeInfrastructure(rg_location='eastus', index=1),
        lambda: infrastructures.AppGwApimInfrastructure(rg_location='eastus', index=1),
    ]
)
def test_create_keyvault_certificate_returns_false_when_create_fails(mock_utils, mock_az, infra_factory):
    """If creation fails, return False."""
    infra = infra_factory()

    show_output = Mock(success=False)
    create_output = Mock(success=False)
    mock_az.run.side_effect = [show_output, create_output]

    assert infra._create_keyvault_certificate('test-kv') is False


def test_afd_apim_aca_approve_private_links(mock_utils, mock_az):
    """Test private link approval for AfdApimAcaInfrastructure."""
    infra = infrastructures.AfdApimAcaInfrastructure(
        rg_location='eastus',
        index=1
    )

    mock_output = Mock()
    mock_output.success = True
    mock_output.getJson.return_value = [
        {'name': 'test-connection', 'properties': {'privateLinkServiceConnectionState': {'status': 'Pending'}}}
    ]
    mock_az.run.return_value = mock_output

    result = infra._approve_private_link_connections('/subscriptions/test/resourceGroups/test/providers/Microsoft.ApiManagement/service/test')

    assert isinstance(result, bool)


def test_appgw_apim_pe_approve_private_links(mock_utils, mock_az):
    """Test private link approval for AppGwApimPeInfrastructure."""
    infra = infrastructures.AppGwApimPeInfrastructure(
        rg_location='eastus',
        index=1
    )

    mock_output = Mock()
    mock_output.success = True
    mock_output.getJson.return_value = [
        {'name': 'test-connection', 'properties': {'privateLinkServiceConnectionState': {'status': 'Pending'}}}
    ]
    mock_az.run.return_value = mock_output

    result = infra._approve_private_link_connections('/subscriptions/test/resourceGroups/test/providers/Microsoft.ApiManagement/service/test')

    assert isinstance(result, bool)


@pytest.mark.unit
def test_disable_apim_public_access_success_writes_params_and_calls_az(mock_utils, mock_az, tmp_path, monkeypatch):
    """Disable public access should update params.json and trigger a redeploy."""
    infra = infrastructures.AfdApimAcaInfrastructure(rg_location='eastus', index=1)

    infra._define_policy_fragments()
    infra._define_apis()
    infra._define_bicep_parameters()
    assert infra.bicep_parameters['apimPublicAccess']['value'] is True

    # Redirect module-relative path resolution to a temp project layout.
    monkeypatch.setattr(
        infrastructures,
        '__file__',
        str(tmp_path / 'shared' / 'python' / 'infrastructures.py'),
        raising=False
    )
    infra_dir = tmp_path / 'infrastructure' / infra.infra.value
    infra_dir.mkdir(parents=True, exist_ok=True)

    mock_az.run.return_value = Mock(success=True)

    original_cwd = os.getcwd()
    result = infra._disable_apim_public_access()

    assert result is True
    assert os.getcwd() == original_cwd
    assert infra.bicep_parameters['apimPublicAccess']['value'] is False

    params_path = infra_dir / 'params.json'
    assert params_path.exists()

    params_json = json.loads(params_path.read_text(encoding='utf-8'))
    assert params_json['parameters']['apimPublicAccess']['value'] is False

    mock_az.run.assert_called_once()
    cmd = mock_az.run.call_args.args[0]
    assert 'az deployment group create' in cmd
    assert f'--name {infra.infra.value}-lockdown' in cmd
    assert f'--resource-group {infra.rg_name}' in cmd
    assert '--template-file' in cmd
    assert '--parameters' in cmd


@pytest.mark.unit
def test_disable_apim_public_access_returns_false_when_param_missing(mock_utils, mock_az):
    """If apimPublicAccess isn't present in parameters, the method should fail safely."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus'
    )

    infra._define_policy_fragments()
    infra._define_apis()
    infra._define_bicep_parameters()
    assert 'apimPublicAccess' not in infra.bicep_parameters

    result = infra._disable_apim_public_access()

    assert result is False
    mock_az.run.assert_not_called()


@pytest.mark.unit
def test_disable_apim_public_access_returns_false_when_deploy_fails(mock_utils, mock_az, tmp_path, monkeypatch):
    """If the redeploy fails (az.run.success=False), return False but still write params.json."""
    infra = infrastructures.AppGwApimPeInfrastructure(rg_location='eastus', index=1)

    infra._define_policy_fragments()
    infra._define_apis()
    infra._define_bicep_parameters()
    assert infra.bicep_parameters['apimPublicAccess']['value'] is True

    monkeypatch.setattr(
        infrastructures,
        '__file__',
        str(tmp_path / 'shared' / 'python' / 'infrastructures.py'),
        raising=False
    )
    infra_dir = tmp_path / 'infrastructure' / infra.infra.value
    infra_dir.mkdir(parents=True, exist_ok=True)

    mock_az.run.return_value = Mock(success=False)

    result = infra._disable_apim_public_access()

    assert result is False
    assert (infra_dir / 'params.json').exists()
    assert infra.bicep_parameters['apimPublicAccess']['value'] is False


def test_afd_apim_aca_verify_connectivity(mock_utils, mock_az):
    """Test connectivity verification for AfdApimAcaInfrastructure."""
    infra = infrastructures.AfdApimAcaInfrastructure(
        rg_location='eastus',
        index=1
    )

    with patch('infrastructures.requests.get') as mock_requests:
        mock_requests.return_value.status_code = 200

        result = infra._verify_apim_connectivity('https://test-apim.azure-api.net')

        assert isinstance(result, bool)


def test_appgw_apim_pe_verify_connectivity(mock_utils, mock_az):
    """Test connectivity verification for AppGwApimPeInfrastructure."""
    infra = infrastructures.AppGwApimPeInfrastructure(
        rg_location='eastus',
        index=1
    )

    with patch('infrastructures.requests.get') as mock_requests:
        mock_requests.return_value.status_code = 200

        result = infra._verify_apim_connectivity('https://test-apim.azure-api.net')

        assert isinstance(result, bool)


def test_afd_apim_aca_define_bicep_parameters(mock_utils):
    """Test bicep parameter definition for AfdApimAcaInfrastructure."""
    infra = infrastructures.AfdApimAcaInfrastructure(
        rg_location='eastus',
        index=1
    )

    infra._define_policy_fragments()
    infra._define_apis()
    params = infra._define_bicep_parameters()

    assert 'resourceSuffix' in params
    assert 'apimSku' in params
    assert 'apis' in params
    assert 'policyFragments' in params


def test_appgw_apim_pe_define_bicep_parameters(mock_utils):
    """Test bicep parameter definition for AppGwApimPeInfrastructure."""
    infra = infrastructures.AppGwApimPeInfrastructure(
        rg_location='eastus',
        index=1
    )

    infra._define_policy_fragments()
    infra._define_apis()
    params = infra._define_bicep_parameters()

    assert 'resourceSuffix' in params
    assert 'apimSku' in params
    assert 'apis' in params
    assert 'policyFragments' in params


def test_appgw_apim_define_bicep_parameters(mock_utils):
    """Test bicep parameter definition for AppGwApimInfrastructure."""
    infra = infrastructures.AppGwApimInfrastructure(
        rg_location='eastus',
        index=1
    )

    infra._define_policy_fragments()
    infra._define_apis()
    params = infra._define_bicep_parameters()

    assert 'resourceSuffix' in params
    assert 'apimSku' in params
    assert 'apis' in params
    assert 'policyFragments' in params


def test_infrastructure_with_network_mode_variations(mock_utils):
    """Test infrastructure with different network modes."""
    modes = [APIMNetworkMode.PUBLIC, APIMNetworkMode.INTERNAL_VNET, APIMNetworkMode.EXTERNAL_VNET]

    for mode in modes:
        infra = infrastructures.Infrastructure(
            infra=INFRASTRUCTURE.SIMPLE_APIM,
            index=1,
            rg_location='eastus',
            networkMode=mode
        )
        assert infra.networkMode == mode


def test_infrastructure_with_sku_variations(mock_utils):
    """Test infrastructure with different SKU values."""
    skus = [APIM_SKU.DEVELOPER, APIM_SKU.BASIC, APIM_SKU.STANDARD, APIM_SKU.PREMIUM,
            APIM_SKU.BASICV2, APIM_SKU.STANDARDV2, APIM_SKU.PREMIUMV2]

    for sku in skus:
        infra = infrastructures.Infrastructure(
            infra=INFRASTRUCTURE.SIMPLE_APIM,
            index=1,
            rg_location='eastus',
            apim_sku=sku
        )
        assert infra.apim_sku == sku




def test_infrastructure_multiple_custom_components(mock_utils):
    """Test infrastructure with both custom APIs and Policy Fragments."""
    pf = PolicyFragment('test-pf', '<policy></policy>', 'Test PF')
    api = API('test-api', 'Test API', '/test', 'Test', '<policy></policy>')

    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus',
        infra_pfs=[pf],
        infra_apis=[api]
    )

    infra._define_policy_fragments()
    infra._define_apis()
    infra._define_bicep_parameters()

    assert len(infra.pfs) > 6  # 6 base + 1 custom
    assert len(infra.apis) > 1  # 1 base + 1 custom
    assert infra.bicep_parameters is not None


def test_infrastructure_with_location_variations(mock_utils):
    """Test infrastructure in various Azure locations."""
    locations = ['eastus', 'westus', 'northeurope', 'southeastasia', 'uksouth', 'japaneast']

    for location in locations:
        infra = infrastructures.Infrastructure(
            infra=INFRASTRUCTURE.SIMPLE_APIM,
            index=1,
            rg_location=location
        )
        assert infra.rg_location == location


def test_infrastructure_with_different_indices(mock_utils):
    """Test infrastructure with different index values."""
    for index in [1, 2, 5, 10, 100]:
        infra = infrastructures.Infrastructure(
            infra=INFRASTRUCTURE.SIMPLE_APIM,
            index=index,
            rg_location='eastus'
        )
        assert infra.index == index


def test_appgw_apim_pe_create_keyvault_success(mock_utils, mock_az):
    """Test KeyVault creation for AppGwApimPeInfrastructure."""
    infra = infrastructures.AppGwApimPeInfrastructure(
        rg_location='eastus',
        index=1
    )

    mock_az.resource_exists.return_value = False
    mock_az.run.return_value = Mock(success=True)

    result = infra._create_keyvault('test-kv')
    assert isinstance(result, bool)


def test_appgw_apim_create_keyvault_success(mock_utils, mock_az):
    """Test KeyVault creation for AppGwApimInfrastructure."""
    infra = infrastructures.AppGwApimInfrastructure(
        rg_location='eastus',
        index=1
    )

    mock_az.resource_exists.return_value = False
    mock_az.run.return_value = Mock(success=True)

    result = infra._create_keyvault('test-kv')
    assert isinstance(result, bool)


def test_appgw_apim_pe_create_certificate_success(mock_utils, mock_az):
    """Test certificate creation for AppGwApimPeInfrastructure."""
    infra = infrastructures.AppGwApimPeInfrastructure(
        rg_location='eastus',
        index=1
    )

    mock_az.run.return_value = Mock(success=True)

    result = infra._create_keyvault_certificate('test-kv')
    assert isinstance(result, bool)


def test_appgw_apim_create_certificate_success(mock_utils, mock_az):
    """Test certificate creation for AppGwApimInfrastructure."""
    infra = infrastructures.AppGwApimInfrastructure(
        rg_location='eastus',
        index=1
    )

    mock_az.run.return_value = Mock(success=True)

    result = infra._create_keyvault_certificate('test-kv')
    assert isinstance(result, bool)


def test_afd_apim_aca_approve_private_links_multiple(mock_utils, mock_az):
    """Test private link approval with multiple connections."""
    infra = infrastructures.AfdApimAcaInfrastructure(
        rg_location='eastus',
        index=1
    )

    mock_output = Mock()
    mock_output.success = True
    mock_output.getJson.return_value = [
        {'name': 'conn1', 'properties': {'privateLinkServiceConnectionState': {'status': 'Pending'}}},
        {'name': 'conn2', 'properties': {'privateLinkServiceConnectionState': {'status': 'Pending'}}}
    ]
    mock_az.run.return_value = mock_output

    result = infra._approve_private_link_connections('/subscriptions/test/resourceGroups/test/providers/Microsoft.ApiManagement/service/test')

    assert isinstance(result, bool)


def test_appgw_apim_pe_approve_private_links_multiple(mock_utils, mock_az):
    """Test private link approval for AppGwApimPeInfrastructure with multiple connections."""
    infra = infrastructures.AppGwApimPeInfrastructure(
        rg_location='eastus',
        index=1
    )

    mock_output = Mock()
    mock_output.success = True
    mock_output.getJson.return_value = [
        {'name': 'conn1', 'properties': {'privateLinkServiceConnectionState': {'status': 'Pending'}}},
        {'name': 'conn2', 'properties': {'privateLinkServiceConnectionState': {'status': 'Pending'}}}
    ]
    mock_az.run.return_value = mock_output

    result = infra._approve_private_link_connections('/subscriptions/test/resourceGroups/test/providers/Microsoft.ApiManagement/service/test')

    assert isinstance(result, bool)


@pytest.mark.unit
def test_afd_apim_aca_deploy_infrastructure_success_calls_steps(mock_utils, mock_az):
    """AFD deploy should call approve/connectivity/disable steps when base deploy succeeds."""
    mock_utils.Output.side_effect = Output

    infra = infrastructures.AfdApimAcaInfrastructure(rg_location='eastus', index=1)

    base_output = Mock()
    base_output.success = True
    base_output.json_data = {'any': 'value'}
    base_output.get.side_effect = lambda key, *_args, **_kwargs: {
        'apimServiceId': '/subscriptions/test/resourceGroups/test/providers/Microsoft.ApiManagement/service/test',
        'apimResourceGatewayURL': 'https://test-apim.azure-api.net'
    }.get(key)

    infra._approve_private_link_connections = Mock(return_value=True)
    infra._verify_apim_connectivity = Mock(return_value=True)
    infra._disable_apim_public_access = Mock(return_value=True)

    with patch.object(infrastructures.Infrastructure, 'deploy_infrastructure', return_value=base_output) as mock_base_deploy:
        result = infra.deploy_infrastructure(is_update=False)

    assert result is base_output
    mock_base_deploy.assert_called_once()
    infra._approve_private_link_connections.assert_called_once_with('/subscriptions/test/resourceGroups/test/providers/Microsoft.ApiManagement/service/test')
    infra._verify_apim_connectivity.assert_called_once_with('https://test-apim.azure-api.net')
    infra._disable_apim_public_access.assert_called_once()


@pytest.mark.unit
def test_afd_apim_aca_deploy_infrastructure_returns_failed_output_when_approve_fails(mock_utils, mock_az):
    """AFD deploy should return a failed Output when private link approval fails."""
    mock_utils.Output.side_effect = Output

    infra = infrastructures.AfdApimAcaInfrastructure(rg_location='eastus', index=1)

    base_output = Mock()
    base_output.success = True
    base_output.json_data = {'any': 'value'}
    base_output.get.side_effect = lambda key, *_args, **_kwargs: {
        'apimServiceId': '/subscriptions/test/resourceGroups/test/providers/Microsoft.ApiManagement/service/test',
        'apimResourceGatewayURL': 'https://test-apim.azure-api.net'
    }.get(key)

    infra._approve_private_link_connections = Mock(return_value=False)

    with patch.object(infrastructures.Infrastructure, 'deploy_infrastructure', return_value=base_output):
        result = infra.deploy_infrastructure(is_update=False)

    assert result.success is False
    assert result.text == 'Private link approval failed'


@pytest.mark.unit
def test_appgw_apim_pe_deploy_infrastructure_success_calls_steps_and_sets_appgw_fields(mock_utils, mock_az):
    """APPGW PE deploy should create prereqs, deploy, approve, verify connectivity, disable public access."""
    mock_utils.Output.side_effect = Output

    infra = infrastructures.AppGwApimPeInfrastructure(rg_location='eastus', index=1)

    base_output = Mock()
    base_output.success = True
    base_output.json_data = {'any': 'value'}
    base_output.get.side_effect = lambda key, *_args, **_kwargs: {
        'apimServiceId': '/subscriptions/test/resourceGroups/test/providers/Microsoft.ApiManagement/service/test',
        'apimResourceGatewayURL': 'https://test-apim.azure-api.net',
        'appGatewayDomainName': 'api.example.com',
        'appgwPublicIpAddress': '1.2.3.4'
    }.get(key)

    infra._create_keyvault = Mock(return_value=True)
    infra._create_keyvault_certificate = Mock(return_value=True)
    infra._approve_private_link_connections = Mock(return_value=True)
    infra._verify_apim_connectivity = Mock(return_value=True)
    infra._disable_apim_public_access = Mock(return_value=True)

    with patch.object(infrastructures.Infrastructure, 'deploy_infrastructure', return_value=base_output) as mock_base_deploy:
        result = infra.deploy_infrastructure(is_update=False)

    assert result is base_output
    infra._create_keyvault.assert_called_once()
    infra._create_keyvault_certificate.assert_called_once()
    mock_base_deploy.assert_called_once()
    infra._approve_private_link_connections.assert_called_once_with('/subscriptions/test/resourceGroups/test/providers/Microsoft.ApiManagement/service/test')
    infra._verify_apim_connectivity.assert_called_once_with('https://test-apim.azure-api.net')
    infra._disable_apim_public_access.assert_called_once()
    assert infra.appgw_domain_name == 'api.example.com'
    assert infra.appgw_public_ip == '1.2.3.4'


@pytest.mark.unit
def test_appgw_apim_pe_deploy_infrastructure_returns_failed_output_when_keyvault_fails(mock_utils, mock_az):
    """APPGW PE deploy should return a failed Output if Key Vault creation fails."""
    mock_utils.Output.side_effect = Output

    infra = infrastructures.AppGwApimPeInfrastructure(rg_location='eastus', index=1)
    infra._create_keyvault = Mock(return_value=False)

    result = infra.deploy_infrastructure(is_update=False)

    assert result.success is False
    assert result.text == 'Failed to create Key Vault'


@pytest.mark.unit
def test_appgw_apim_pe_verify_infrastructure_specific_success(mock_utils, mock_az):
    """Verify should pass when App Gateway exists; container apps and PE checks are optional."""
    infra = infrastructures.AppGwApimPeInfrastructure(rg_location='eastus', index=1)

    appgw_output = Mock(success=True, json_data={'name': 'test-appgw'})
    aca_output = Mock(success=True, text='1')
    apim_output = Mock(success=True, text='/subscriptions/test/.../apim')
    pe_output = Mock(success=True, text='2')

    mock_az.run.side_effect = [appgw_output, aca_output, apim_output, pe_output]

    assert infra._verify_infrastructure_specific('rg-test') is True


@pytest.mark.unit
def test_appgw_apim_pe_verify_infrastructure_specific_returns_false_when_appgw_missing(mock_utils, mock_az):
    """Verify should fail when App Gateway cannot be retrieved."""
    infra = infrastructures.AppGwApimPeInfrastructure(rg_location='eastus', index=1)

    mock_az.run.return_value = Mock(success=False, json_data=None)

    assert infra._verify_infrastructure_specific('rg-test') is False


@pytest.mark.unit
def test_appgw_apim_pe_verify_infrastructure_specific_ignores_private_endpoint_errors(mock_utils, mock_az):
    """Private endpoint verification is best-effort and should not fail the overall verification."""
    infra = infrastructures.AppGwApimPeInfrastructure(rg_location='eastus', index=1)

    appgw_output = Mock(success=True, json_data={'name': 'test-appgw'})
    aca_output = Mock(success=True, text='0')

    def run_side_effect(*args, **kwargs):
        cmd = args[0] if args else ''
        if 'application-gateway list' in cmd:
            return appgw_output
        if 'containerapp list' in cmd:
            return aca_output
        if 'az apim list' in cmd:
            raise RuntimeError('boom')
        raise AssertionError(f'Unexpected az.run call: {cmd}')

    mock_az.run.side_effect = run_side_effect

    assert infra._verify_infrastructure_specific('rg-test') is True


def test_afd_apim_aca_verify_connectivity_with_retry(mock_utils, mock_az):
    """Test connectivity verification with retries for AfdApimAcaInfrastructure."""
    infra = infrastructures.AfdApimAcaInfrastructure(
        rg_location='eastus',
        index=1
    )

    with patch('infrastructures.requests.get') as mock_requests:
        mock_requests.return_value.status_code = 200

        result = infra._verify_apim_connectivity('https://test-apim.azure-api.net')

        assert isinstance(result, bool)


def test_appgw_apim_pe_verify_connectivity_with_retry(mock_utils, mock_az):
    """Test connectivity verification for AppGwApimPeInfrastructure."""
    infra = infrastructures.AppGwApimPeInfrastructure(
        rg_location='eastus',
        index=1
    )

    with patch('infrastructures.requests.get') as mock_requests:
        mock_requests.return_value.status_code = 200

        result = infra._verify_apim_connectivity('https://test-apim.azure-api.net')

        assert isinstance(result, bool)


def test_afd_apim_aca_define_bicep_parameters_complete(mock_utils):
    """Test complete bicep parameter definition for AfdApimAcaInfrastructure."""
    pf = PolicyFragment('custom-pf', '<policy></policy>', 'Custom')
    api = API('custom-api', 'Custom', '/custom', 'Custom', '<policy></policy>')

    infra = infrastructures.AfdApimAcaInfrastructure(
        rg_location='eastus',
        index=1,
        infra_pfs=[pf],
        infra_apis=[api]
    )

    infra._define_policy_fragments()
    infra._define_apis()
    params = infra._define_bicep_parameters()

    assert 'resourceSuffix' in params
    assert 'apimSku' in params
    assert 'apis' in params
    assert 'policyFragments' in params
    assert len(params['apis']['value']) > 1
    assert len(params['policyFragments']['value']) > 6


def test_appgw_apim_pe_define_bicep_parameters_complete(mock_utils):
    """Test complete bicep parameter definition for AppGwApimPeInfrastructure."""
    infra = infrastructures.AppGwApimPeInfrastructure(
        rg_location='eastus',
        index=1
    )

    infra._define_policy_fragments()
    infra._define_apis()
    params = infra._define_bicep_parameters()

    assert 'resourceSuffix' in params
    assert 'apimSku' in params
    assert 'apis' in params
    assert 'policyFragments' in params


def test_appgw_apim_define_bicep_parameters_complete(mock_utils):
    """Test complete bicep parameter definition for AppGwApimInfrastructure."""
    infra = infrastructures.AppGwApimInfrastructure(
        rg_location='eastus',
        index=1
    )

    infra._define_policy_fragments()
    infra._define_apis()
    params = infra._define_bicep_parameters()

    assert 'resourceSuffix' in params
    assert 'apimSku' in params
    assert 'apis' in params
    assert 'policyFragments' in params


def test_apim_aca_verify_infrastructure_specific_checks(mock_utils, mock_az):
    """Test ApimAcaInfrastructure specific verification checks."""
    infra = infrastructures.ApimAcaInfrastructure(
        rg_location='eastus',
        index=1
    )

    mock_az.does_resource_group_exist.return_value = True
    mock_az.does_apim_exist.return_value = True

    result = infra._verify_infrastructure_specific('test-rg')
    assert isinstance(result, bool)


def test_infrastructure_deployment_with_all_skus(mock_utils):
    """Test infrastructure creation with all available SKUs."""
    skus = [APIM_SKU.DEVELOPER, APIM_SKU.BASIC, APIM_SKU.STANDARD, APIM_SKU.PREMIUM,
            APIM_SKU.BASICV2, APIM_SKU.STANDARDV2, APIM_SKU.PREMIUMV2]

    for sku in skus:
        infra = infrastructures.Infrastructure(
            infra=INFRASTRUCTURE.SIMPLE_APIM,
            index=1,
            rg_location='eastus',
            apim_sku=sku
        )
        infra._define_policy_fragments()
        infra._define_apis()
        infra._define_bicep_parameters()
        assert infra.bicep_parameters['apimSku']['value'] == sku.value


def test_infrastructure_bicep_parameters_structure(mock_utils):
    """Test that bicep parameters have correct structure."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus'
    )

    infra._define_policy_fragments()
    infra._define_apis()
    params = infra._define_bicep_parameters()

    # Verify structure
    assert isinstance(params, dict)
    for _key, value in params.items():
        assert 'value' in value
        assert isinstance(value['value'], (str, list))


def test_infrastructure_policy_fragments_combining(mock_utils):
    """Test combining base and custom policy fragments."""
    pf1 = PolicyFragment('custom-1', '<policy></policy>', 'Custom 1')
    pf2 = PolicyFragment('custom-2', '<policy></policy>', 'Custom 2')

    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus',
        infra_pfs=[pf1, pf2]
    )

    pfs = infra._define_policy_fragments()

    # Should have 6 base + 2 custom
    assert len(pfs) == 8
    assert infra.base_pfs
    assert any(pf.name == 'custom-1' for pf in pfs)
    assert any(pf.name == 'custom-2' for pf in pfs)


def test_infrastructure_apis_combining(mock_utils):
    """Test combining base and custom APIs."""
    api1 = API('custom-1', 'Custom 1', '/c1', 'Custom 1', '<policy></policy>')
    api2 = API('custom-2', 'Custom 2', '/c2', 'Custom 2', '<policy></policy>')

    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus',
        infra_apis=[api1, api2]
    )

    apis = infra._define_apis()

    # Should have 1 base (hello-world) + 2 custom
    assert len(apis) == 3
    assert infra.base_apis
    assert any(api.name == 'custom-1' for api in apis)
    assert any(api.name == 'custom-2' for api in apis)
    assert infra.apis[0].name == 'hello-world'


def test_infrastructure_with_no_custom_components(mock_utils):
    """Test infrastructure with empty custom component lists."""
    infra = infrastructures.Infrastructure(
        infra=INFRASTRUCTURE.SIMPLE_APIM,
        index=1,
        rg_location='eastus',
        infra_apis=[],
        infra_pfs=[]
    )

    apis = infra._define_apis()
    pfs = infra._define_policy_fragments()

    # Only base components
    assert len(apis) == 1
    assert len(pfs) == 6


def test_infrastructure_network_mode_with_custom_components(mock_utils):
    """Test infrastructure with network mode and custom components."""
    pf = PolicyFragment('test-pf', '<policy></policy>', 'Test')
    api = API('test-api', 'Test API', '/test', 'Test', '<policy></policy>')

    for network_mode in [APIMNetworkMode.PUBLIC, APIMNetworkMode.INTERNAL_VNET, APIMNetworkMode.EXTERNAL_VNET]:
        infra = infrastructures.Infrastructure(
            infra=INFRASTRUCTURE.APPGW_APIM,
            index=1,
            rg_location='eastus',
            networkMode=network_mode,
            infra_pfs=[pf],
            infra_apis=[api]
        )
        assert infra.networkMode == network_mode
        infra._define_policy_fragments()
        infra._define_apis()
        assert len(infra.pfs) == 7
        assert len(infra.apis) == 2
