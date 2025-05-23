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


@pytest.mark.unit
def test_api_creation():
    """Test creation of API object and its attributes."""
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


@pytest.mark.unit
def test_api_repr():
    """Test __repr__ method of API."""
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

@pytest.mark.unit
def test_api_equality():
    """Test equality comparison for API objects.
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




# ------------------------------
#    ENUMS
# ------------------------------

def test_apimnetworkmode_enum():
    assert apimtypes.APIMNetworkMode.PUBLIC == "Public"
    assert apimtypes.APIMNetworkMode.EXTERNAL_VNET == "External"
    assert apimtypes.APIMNetworkMode.INTERNAL_VNET == "Internal"
    assert apimtypes.APIMNetworkMode.NONE == "None"
    with pytest.raises(ValueError):
        apimtypes.APIMNetworkMode("invalid")

def test_apim_sku_enum():
    assert apimtypes.APIM_SKU.DEVELOPER == "Developer"
    assert apimtypes.APIM_SKU.BASIC == "Basic"
    assert apimtypes.APIM_SKU.STANDARD == "Standard"
    assert apimtypes.APIM_SKU.PREMIUM == "Premium"
    assert apimtypes.APIM_SKU.BASICV2 == "Basicv2"
    assert apimtypes.APIM_SKU.STANDARDV2 == "Standardv2"
    assert apimtypes.APIM_SKU.PREMIUMV2 == "Premiumv2"
    with pytest.raises(ValueError):
        apimtypes.APIM_SKU("invalid")

def test_http_verb_enum():
    assert apimtypes.HTTP_VERB.GET == "GET"
    assert apimtypes.HTTP_VERB.POST == "POST"
    assert apimtypes.HTTP_VERB.PUT == "PUT"
    assert apimtypes.HTTP_VERB.DELETE == "DELETE"
    assert apimtypes.HTTP_VERB.PATCH == "PATCH"
    assert apimtypes.HTTP_VERB.OPTIONS == "OPTIONS"
    assert apimtypes.HTTP_VERB.HEAD == "HEAD"
    with pytest.raises(ValueError):
        apimtypes.HTTP_VERB("FOO")

def test_infrastructure_enum():
    assert apimtypes.INFRASTRUCTURE.SIMPLE_APIM == "simple-apim"
    assert apimtypes.INFRASTRUCTURE.APIM_ACA == "apim-aca"
    assert apimtypes.INFRASTRUCTURE.AFD_APIM_PE == "afd-apim-pe"
    with pytest.raises(ValueError):
        apimtypes.INFRASTRUCTURE("bad")

# ------------------------------
#    OPERATION CLASSES
# ------------------------------

def test_apioperation_to_dict():
    op = apimtypes.APIOperation(
        name="op1",
        displayName="Operation 1",
        urlTemplate="/foo",
        method=apimtypes.HTTP_VERB.GET,
        description="desc",
        policyXml="<xml/>"
    )
    d = op.to_dict()
    assert d["name"] == "op1"
    assert d["displayName"] == "Operation 1"
    assert d["urlTemplate"] == "/foo"
    assert d["method"] == apimtypes.HTTP_VERB.GET
    assert d["description"] == "desc"
    assert d["policyXml"] == "<xml/>"

def test_get_apioperation():
    op = apimtypes.GET_APIOperation(description="desc", policyXml="<xml/>")
    assert op.name == "GET"
    assert op.method == apimtypes.HTTP_VERB.GET
    assert op.urlTemplate == "/"
    assert op.description == "desc"
    assert op.policyXml == "<xml/>"
    d = op.to_dict()
    assert d["method"] == apimtypes.HTTP_VERB.GET

def test_post_apioperation():
    op = apimtypes.POST_APIOperation(description="desc", policyXml="<xml/>")
    assert op.name == "POST"
    assert op.method == apimtypes.HTTP_VERB.POST
    assert op.urlTemplate == "/"
    assert op.description == "desc"
    assert op.policyXml == "<xml/>"
    d = op.to_dict()
    assert d["method"] == apimtypes.HTTP_VERB.POST

def test_apioperation_invalid_method():
    # Negative: method must be a valid HTTP_VERB
    with pytest.raises(ValueError):
        apimtypes.APIOperation(
            name="bad",
            displayName="Bad",
            urlTemplate="/bad",
            method="INVALID",
            description="desc",
            policyXml="<xml/>"
        )
