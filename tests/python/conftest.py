"""
Shared test configuration and fixtures for pytest.
"""
import os
import sys
from typing import Any

import pytest

# Add the shared/python directory to the Python path for all tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared/python')))


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
