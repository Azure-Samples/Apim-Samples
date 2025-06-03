"""
Unit tests for apimtypes.py.
"""

import pytest
import apimtypes


# ------------------------------
#    CONSTANTS
# ------------------------------

EXAMPLE_NAME = "test-api"
EXAMPLE_DISPLAY_NAME = "Test API"
EXAMPLE_PATH = "/test"
EXAMPLE_DESCRIPTION = "A test API."
EXAMPLE_POLICY_XML = "<policies />"
EXAMPLE_PRODUCT_NAMES = ["product1", "product2"]


# ------------------------------
#    TEST METHODS
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
    assert api.tags == []
    assert api.productNames == []

@pytest.mark.unit
def test_api_creation_with_tags():
    """Test creation of API object with tags."""
    tags = ["tag1", "tag2"]
    api = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        tags = tags
    )
    assert api.tags == tags

@pytest.mark.unit
def test_api_creation_with_product_names():
    """Test creation of API object with product names."""
    product_names = ["product1", "product2"]
    api = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        productNames = product_names
    )
    assert api.productNames == product_names

@pytest.mark.unit
def test_api_to_dict_includes_tags():
    """Test that to_dict includes tags when present."""
    tags = ["foo", "bar"]
    api = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        tags = tags
    )
    d = api.to_dict()
    assert "tags" in d
    assert d["tags"] == tags

@pytest.mark.unit
def test_api_to_dict_omits_tags_when_empty():
    """Test that to_dict omits tags when not set or empty."""
    api = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    d = api.to_dict()
    assert "tags" not in d or d["tags"] == []

@pytest.mark.unit
def test_api_to_dict_includes_product_names():
    """Test that to_dict includes productNames when present."""
    product_names = ["product1", "product2"]
    api = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        productNames = product_names
    )
    d = api.to_dict()
    assert "productNames" in d
    assert d["productNames"] == product_names

@pytest.mark.unit
def test_api_to_dict_omits_product_names_when_empty():
    """Test that to_dict omits productNames when not set or empty."""
    api = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    d = api.to_dict()
    assert "productNames" not in d or d["productNames"] == []

@pytest.mark.unit
def test_api_with_both_tags_and_product_names():
    """Test creation of API object with both tags and product names."""
    tags = ["tag1", "tag2"]
    product_names = ["product1", "product2"]
    api = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        tags = tags,
        productNames = product_names
    )
    assert api.tags == tags
    assert api.productNames == product_names
    
    d = api.to_dict()
    assert d["tags"] == tags
    assert d["productNames"] == product_names

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
        operations = None,
        tags = ["a", "b"]
    )
    api2 = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        tags = ["a", "b"]
    )
    assert api1 == api2

    # Different tags should not be equal
    api3 = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        tags = ["x"]
    )
    assert api1 != api3

    # Different product names should not be equal
    api4 = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        tags = ["a", "b"],
        productNames = ["different-product"]
    )
    assert api1 != api4

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

# ------------------------------
#    PRODUCT TESTS
# ------------------------------

@pytest.mark.unit
def test_product_creation():
    """Test creation of Product object and its attributes."""
    product = apimtypes.Product(
        name = "hr",
        displayName = "Human Resources",
        description = "HR product description"
    )

    assert product.name == "hr"
    assert product.displayName == "Human Resources"
    assert product.description == "HR product description"
    assert product.state == "published"  # default value
    assert product.subscriptionRequired == True  # default value
    assert product.policyXml is not None  # should have default policy


@pytest.mark.unit
def test_product_creation_with_custom_values():
    """Test creation of Product object with custom values."""
    custom_policy = "<policies><inbound><base /></inbound></policies>"
    product = apimtypes.Product(
        name = "test-product",
        displayName = "Test Product",
        description = "Test description",
        state = "notPublished",
        subscriptionRequired = False,
        policyXml = custom_policy
    )

    assert product.name == "test-product"
    assert product.displayName == "Test Product"
    assert product.description == "Test description"
    assert product.state == "notPublished"
    assert product.subscriptionRequired == False
    assert product.policyXml == custom_policy


@pytest.mark.unit
def test_product_creation_with_approval_required():
    """Test creation of Product object with approvalRequired set to True."""
    product = apimtypes.Product(
        name = "premium-hr",
        displayName = "Premium Human Resources",
        description = "Premium HR product requiring approval",
        subscriptionRequired = True,
        approvalRequired = True
    )

    assert product.name == "premium-hr"
    assert product.displayName == "Premium Human Resources"
    assert product.description == "Premium HR product requiring approval"
    assert product.state == "published"  # default value
    assert product.subscriptionRequired == True
    assert product.approvalRequired == True
    assert product.policyXml is not None  # should have default policy


@pytest.mark.unit
def test_product_to_dict():
    """Test that to_dict includes all required fields."""
    custom_policy = "<policies><inbound><base /></inbound></policies>"
    product = apimtypes.Product(
        name = "hr",
        displayName = "Human Resources",
        description = "HR product",
        state = "published",
        subscriptionRequired = True,
        policyXml = custom_policy
    )
    d = product.to_dict()
    
    assert d["name"] == "hr"
    assert d["displayName"] == "Human Resources"
    assert d["description"] == "HR product"
    assert d["state"] == "published"
    assert d["subscriptionRequired"] == True
    assert d["policyXml"] == custom_policy


@pytest.mark.unit
def test_product_to_dict_includes_approval_required():
    """Test that to_dict includes approvalRequired field."""
    product = apimtypes.Product(
        name = "premium-hr",
        displayName = "Premium Human Resources",
        description = "Premium HR product",
        subscriptionRequired = True,
        approvalRequired = True
    )
    d = product.to_dict()
    
    assert d["name"] == "premium-hr"
    assert d["displayName"] == "Premium Human Resources"
    assert d["description"] == "Premium HR product"
    assert d["state"] == "published"
    assert d["subscriptionRequired"] == True
    assert d["approvalRequired"] == True
    assert "policyXml" in d


@pytest.mark.unit
def test_product_approval_required_default_false():
    """Test that approvalRequired defaults to False when not specified."""
    product = apimtypes.Product(
        name = "basic-hr",
        displayName = "Basic Human Resources",
        description = "Basic HR product"
    )
    
    assert product.approvalRequired == False
    d = product.to_dict()
    assert d["approvalRequired"] == False


@pytest.mark.unit
def test_product_equality():
    """Test equality comparison for Product objects."""
    product1 = apimtypes.Product(
        name = "hr",
        displayName = "Human Resources",
        description = "HR product"
    )
    product2 = apimtypes.Product(
        name = "hr",
        displayName = "Human Resources",
        description = "HR product"
    )
    assert product1 == product2

    # Different names should not be equal
    product3 = apimtypes.Product(
        name = "finance",
        displayName = "Human Resources",
        description = "HR product"
    )
    assert product1 != product3


@pytest.mark.unit
def test_product_repr():
    """Test __repr__ method of Product."""
    product = apimtypes.Product(
        name = "hr",
        displayName = "Human Resources",
        description = "HR product"
    )
    result = repr(product)
    assert "Product" in result
    assert "hr" in result
    assert "Human Resources" in result
