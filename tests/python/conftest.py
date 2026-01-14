"""
Shared test configuration and fixtures for pytest.
"""
import os
import sys
from typing import Any

import pytest

# Add the shared/python directory to the Python path for all tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared/python')))

# Add the tests/python directory to import test_helpers
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# APIM Samples imports (must come after the sys path inserts, so we disable the offending pylint rule C0413 (wrong-import-position) below)
from test_helpers import ( # pylint: disable=wrong-import-position
    create_mock_http_response,
    create_mock_output,
    create_sample_apis,
    create_sample_policy_fragments,
    get_sample_infrastructure_params,
    MockApimRequestsPatches,
    MockInfrastructuresPatches
)


# ------------------------------
#    SHARED FIXTURES
# ------------------------------

@pytest.fixture(scope='session')
def shared_python_path() -> str:
    """Provide the path to the shared Python modules."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared/python'))

@pytest.fixture(scope='session')
def test_data_path() -> str:
    """Provide the path to test data files."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))

@pytest.fixture
def sample_test_data() -> dict[str, Any]:
    """Provide sample test data for use across tests."""
    return {
        'test_url': 'https://test-apim.azure-api.net',
        'test_subscription_key': 'test-subscription-key-12345',
        'test_resource_group': 'rg-test-apim-01',
        'test_location': 'eastus2'
    }


# ------------------------------
#    MOCK FIXTURES
# ------------------------------

@pytest.fixture(autouse=True)
def infrastructures_patches():
    """Automatically patch infrastructures dependencies for tests."""
    with MockInfrastructuresPatches() as patches:
        yield patches


@pytest.fixture
def mock_utils(infrastructures_patches):
    """Return the patched utils module for infrastructures tests."""
    return infrastructures_patches.utils


@pytest.fixture
def mock_az(infrastructures_patches):
    """Return the patched azure_resources module for infrastructures tests."""
    return infrastructures_patches.az


@pytest.fixture
def mock_az_success():
    """Pre-configured successful Azure CLI output."""
    return create_mock_output(success=True, json_data={'result': 'success'})


@pytest.fixture
def mock_az_failure():
    """Pre-configured failed Azure CLI output."""
    return create_mock_output(success=False, text='Error message')


@pytest.fixture
def sample_policy_fragments():
    """Provide sample policy fragments for testing."""
    return create_sample_policy_fragments(count=2)


@pytest.fixture
def sample_apis():
    """Provide sample APIs for testing."""
    return create_sample_apis(count=2)


@pytest.fixture
def sample_infrastructure_params() -> dict[str, Any]:
    """Provide common infrastructure parameters."""
    return get_sample_infrastructure_params()


@pytest.fixture
def mock_http_response_200():
    """Pre-configured successful HTTP response."""
    return create_mock_http_response(
        status_code=200,
        json_data={'result': 'ok'}
    )


@pytest.fixture
def mock_http_response_error():
    """Pre-configured error HTTP response."""
    return create_mock_http_response(
        status_code=500,
        text='Internal Server Error'
    )


@pytest.fixture
def apimrequests_patches():
    """Provide common apimrequests patches for HTTP tests."""
    with MockApimRequestsPatches() as patches:
        yield patches
