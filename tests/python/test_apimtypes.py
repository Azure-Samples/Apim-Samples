"""
Unit tests for apimtypes.py.
"""
import pytest
from shared.python import apimtypes

# ------------------------------
#    CONSTANTS
# ------------------------------

EXAMPLE_NAME = "test-api"
EXAMPLE_DISPLAY_NAME = "Test API"
EXAMPLE_PATH = "/test"
EXAMPLE_DESCRIPTION = "A test API."
EXAMPLE_POLICY_XML = "<policies />"

# ------------------------------
#    PUBLIC METHODS
# ------------------------------

def test_api_creation():
    """
    Test creation of API object and its attributes.
    """
    api = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )

    assert api.name == EXAMPLE_NAME
    assert api.displayName == EXAMPLE_DISPLAY_NAME
    assert api.path == EXAMPLE_PATH
    assert api.description == EXAMPLE_DESCRIPTION
    assert api.policyXml == EXAMPLE_POLICY_XML
    assert api.operations == []

def test_api_repr():
    """
    Test __repr__ method of API.
    """
    api = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    result = repr(api)
    assert "API" in result
    assert EXAMPLE_NAME in result
    assert EXAMPLE_DISPLAY_NAME in result

def test_api_equality():
    """
    Test equality comparison for API objects.
    """
    api1 = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    api2 = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    assert api1 == api2

def test_api_inequality():
    """
    Test inequality for API objects with different attributes.
    """
    api1 = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    api2 = apimtypes.API(
        name = "other-api",
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    assert api1 != api2

def test_api_missing_fields():
    """
    Test that missing required fields raise TypeError.
    """
    with pytest.raises(TypeError):
        apimtypes.API(
            displayName = EXAMPLE_DISPLAY_NAME,
            path = EXAMPLE_PATH,
            description = EXAMPLE_DESCRIPTION,
            policyXml = EXAMPLE_POLICY_XML
        )

    with pytest.raises(TypeError):
        apimtypes.API(
            name = EXAMPLE_NAME,
            path = EXAMPLE_PATH,
            description = EXAMPLE_DESCRIPTION,
            policyXml = EXAMPLE_POLICY_XML
        )

    with pytest.raises(TypeError):
        apimtypes.API(
            name = EXAMPLE_NAME,
            displayName = EXAMPLE_DISPLAY_NAME,
            description = EXAMPLE_DESCRIPTION,
            policyXml = EXAMPLE_POLICY_XML
        )

    with pytest.raises(TypeError):
        apimtypes.API(
            name = EXAMPLE_NAME,
            displayName = EXAMPLE_DISPLAY_NAME,
            path = EXAMPLE_PATH,
            policyXml = EXAMPLE_POLICY_XML
        )

    with pytest.raises(TypeError):
        apimtypes.API(
            name = EXAMPLE_NAME,
            displayName = EXAMPLE_DISPLAY_NAME,
            path = EXAMPLE_PATH,
            description = EXAMPLE_DESCRIPTION
        )