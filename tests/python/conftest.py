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

# APIM Samples imports (must come after the sys path inserts)
from test_helpers import (
    MockApimRequestsPatches,
    MockInfrastructuresPatches,
    create_mock_http_response,
    create_mock_output,
    create_sample_apis,
    create_sample_policy_fragments,
    get_sample_infrastructure_params,
)

# ------------------------------
#    TEST ISOLATION
# ------------------------------


# Neutralize developer-shell environment variables that change interactive
# infrastructure-selection behavior. Without this, a developer who has set
# APIM_SAMPLES_INFRA_CREATION_BEHAVIOR=create-new-always (or
# APIM_TEST_QUERY_RG_LOCATION=True) will see tests in test_utils.py hang
# inside the real Azure CLI because the alternate code paths are not
# mocked by every test. Tests that need a specific value should set it
# themselves via monkeypatch.setenv.
#
# Note: a module-level pop is not sufficient because test_logging_config
# tests call ``logging_config.configure_logging`` which in turn invokes
# ``load_dotenv`` and reintroduces values from the developer's local .env
# file. The autouse fixture below ensures every test starts with these
# variables removed regardless of any earlier dotenv loads.
_LEAKED_ENV_VARS = ('APIM_SAMPLES_INFRA_CREATION_BEHAVIOR', 'APIM_TEST_QUERY_RG_LOCATION')

for _leaked_env_var in _LEAKED_ENV_VARS:
    os.environ.pop(_leaked_env_var, None)


@pytest.fixture(autouse=True)
def _neutralize_leaked_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip developer env vars (possibly re-injected via .env) before each test."""

    for _var in _LEAKED_ENV_VARS:
        monkeypatch.delenv(_var, raising=False)


@pytest.fixture(autouse=True)
def _skip_az_run_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the multi-second back-off between ``azure_resources.run`` retries.

    ``azure_resources.run`` sleeps several seconds between retry attempts to absorb
    transient DNS/network failures during real Azure calls. Unit tests never rely on
    that wall-clock delay, so patching it suite-wide keeps the test run fast even when
    many tests exercise the failure path (which retries by default).
    """

    import azure_resources as az  # local import: conftest path setup must run first

    monkeypatch.setattr(az.time, 'sleep', lambda _seconds: None)


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
        'test_subscription_key': 'test-subscription-key-123',
        'test_resource_group': 'rg-test-apim-01',
        'test_location': 'eastus2',
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
    return create_mock_http_response(status_code=200, json_data={'result': 'ok'})


@pytest.fixture
def mock_http_response_error():
    """Pre-configured error HTTP response."""
    return create_mock_http_response(status_code=500, text='Internal Server Error')


@pytest.fixture
def apimrequests_patches():
    """Provide common apimrequests patches for HTTP tests."""
    with MockApimRequestsPatches() as patches:
        yield patches
