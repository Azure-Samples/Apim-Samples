"""
Unit tests for apimtypes.py.
"""

from pathlib import Path
import json
import pytest

# APIM Samples imports
from apimtypes import API, APIMNetworkMode, APIM_SKU, APIOperation, BACKEND_XML_POLICY_PATH, DEFAULT_XML_POLICY_PATH, GET_APIOperation, \
    GET_APIOperation2, get_project_root, HELLO_WORLD_XML_POLICY_PATH, HTTP_VERB, INFRASTRUCTURE, NamedValue, Output, PolicyFragment, \
    POST_APIOperation, Product, REQUEST_HEADERS_XML_POLICY_PATH, Role, SUBSCRIPTION_KEY_PARAMETER_NAME, SLEEP_TIME_BETWEEN_REQUESTS_MS


# ------------------------------
#    CONSTANTS
# ------------------------------

EXAMPLE_NAME = 'test-api'
EXAMPLE_DISPLAY_NAME = 'Test API'
EXAMPLE_PATH = '/test'
EXAMPLE_DESCRIPTION = 'A test API.'
EXAMPLE_POLICY_XML = '<policies />'
EXAMPLE_PRODUCT_NAMES = ['product1', 'product2']


# ------------------------------
#    TEST METHODS
# ------------------------------

@pytest.mark.unit
def test_api_creation():
    """Test creation of API object and its attributes."""
    api = API(
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
    tags = ['tag1', 'tag2']
    api = API(
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
    product_names = ['product1', 'product2']
    api = API(
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
    tags = ['foo', 'bar']
    api = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        tags = tags
    )
    d = api.to_dict()
    assert 'tags' in d
    assert d['tags'] == tags

@pytest.mark.unit
def test_api_to_dict_omits_tags_when_empty():
    """Test that to_dict omits tags when not set or empty."""
    api = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    d = api.to_dict()
    assert 'tags' not in d or d['tags'] == []

@pytest.mark.unit
def test_api_to_dict_includes_product_names():
    """Test that to_dict includes productNames when present."""
    product_names = ['product1', 'product2']
    api = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        productNames = product_names
    )
    d = api.to_dict()
    assert 'productNames' in d
    assert d['productNames'] == product_names

@pytest.mark.unit
def test_api_to_dict_omits_product_names_when_empty():
    """Test that to_dict omits productNames when not set or empty."""
    api = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    d = api.to_dict()
    assert 'productNames' not in d or d['productNames'] == []

@pytest.mark.unit
def test_api_with_both_tags_and_product_names():
    """Test creation of API object with both tags and product names."""
    tags = ['tag1', 'tag2']
    product_names = ['product1', 'product2']
    api = API(
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
    assert d['tags'] == tags
    assert d['productNames'] == product_names

@pytest.mark.unit
def test_api_repr():
    """Test __repr__ method of API."""
    api = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    result = repr(api)
    assert 'API' in result
    assert EXAMPLE_NAME in result
    assert EXAMPLE_DISPLAY_NAME in result

@pytest.mark.unit
def test_api_equality():
    """Test equality comparison for API objects.
    """
    api1 = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        tags = ['a', 'b']
    )
    api2 = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        tags = ['a', 'b']
    )
    assert api1 == api2

    # Different tags should not be equal
    api3 = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        tags = ['x']
    )
    assert api1 != api3

    # Different product names should not be equal
    api4 = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        tags = ['a', 'b'],
        productNames = ['different-product']
    )
    assert api1 != api4

def test_api_inequality():
    """
    Test inequality for API objects with different attributes.
    """
    api1 = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    api2 = API(
        name = 'other-api',
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
        API(
            displayName = EXAMPLE_DISPLAY_NAME,
            path = EXAMPLE_PATH,
            description = EXAMPLE_DESCRIPTION,
            policyXml = EXAMPLE_POLICY_XML
        )

    with pytest.raises(TypeError):
        API(
            name = EXAMPLE_NAME,
            path = EXAMPLE_PATH,
            description = EXAMPLE_DESCRIPTION,
            policyXml = EXAMPLE_POLICY_XML
        )

    with pytest.raises(TypeError):
        API(
            name = EXAMPLE_NAME,
            displayName = EXAMPLE_DISPLAY_NAME,
            description = EXAMPLE_DESCRIPTION,
            policyXml = EXAMPLE_POLICY_XML
        )

    with pytest.raises(TypeError):
        API(
            name = EXAMPLE_NAME,
            displayName = EXAMPLE_DISPLAY_NAME,
            path = EXAMPLE_PATH,
            policyXml = EXAMPLE_POLICY_XML
        )


# ------------------------------
#    ENUMS
# ------------------------------

def test_apimnetworkmode_enum():
    assert APIMNetworkMode.PUBLIC == 'Public'
    assert APIMNetworkMode.EXTERNAL_VNET == 'External'
    assert APIMNetworkMode.INTERNAL_VNET == 'Internal'
    assert APIMNetworkMode.NONE == 'None'
    with pytest.raises(ValueError):
        APIMNetworkMode('invalid')

def test_apim_sku_enum():
    assert APIM_SKU.DEVELOPER == 'Developer'
    assert APIM_SKU.BASIC == 'Basic'
    assert APIM_SKU.STANDARD == 'Standard'
    assert APIM_SKU.PREMIUM == 'Premium'
    assert APIM_SKU.BASICV2 == 'Basicv2'
    assert APIM_SKU.STANDARDV2 == 'Standardv2'
    assert APIM_SKU.PREMIUMV2 == 'Premiumv2'
    with pytest.raises(ValueError):
        APIM_SKU('invalid')

def test_http_verb_enum():
    assert HTTP_VERB.GET == 'GET'
    assert HTTP_VERB.POST == 'POST'
    assert HTTP_VERB.PUT == 'PUT'
    assert HTTP_VERB.DELETE == 'DELETE'
    assert HTTP_VERB.PATCH == 'PATCH'
    assert HTTP_VERB.OPTIONS == 'OPTIONS'
    assert HTTP_VERB.HEAD == 'HEAD'
    with pytest.raises(ValueError):
        HTTP_VERB('FOO')

def test_infrastructure_enum():
    assert INFRASTRUCTURE.SIMPLE_APIM == 'simple-apim'
    assert INFRASTRUCTURE.APIM_ACA == 'apim-aca'
    assert INFRASTRUCTURE.AFD_APIM_PE == 'afd-apim-pe'
    with pytest.raises(ValueError):
        INFRASTRUCTURE('bad')


# ------------------------------
#    OPERATION CLASSES
# ------------------------------

def test_apioperation_to_dict():
    op = APIOperation(
        name='op1',
        displayName='Operation 1',
        urlTemplate='/foo',
        method=HTTP_VERB.GET,
        description='desc',
        policyXml='<xml/>'
    )
    d = op.to_dict()
    assert d['name'] == 'op1'
    assert d['displayName'] == 'Operation 1'
    assert d['urlTemplate'] == '/foo'
    assert d['method'] == HTTP_VERB.GET
    assert d['description'] == 'desc'
    assert d['policyXml'] == '<xml/>'

def test_get_apioperation():
    op = GET_APIOperation(description='desc', policyXml='<xml/>')
    assert op.name == 'GET'
    assert op.method == HTTP_VERB.GET
    assert op.urlTemplate == '/'
    assert op.description == 'desc'
    assert op.policyXml == '<xml/>'
    d = op.to_dict()
    assert d['method'] == HTTP_VERB.GET

def test_post_apioperation():
    op = POST_APIOperation(description='desc', policyXml='<xml/>')
    assert op.name == 'POST'
    assert op.method == HTTP_VERB.POST
    assert op.urlTemplate == '/'
    assert op.description == 'desc'
    assert op.policyXml == '<xml/>'
    d = op.to_dict()
    assert d['method'] == HTTP_VERB.POST

def test_apioperation_invalid_method():
    # Negative: method must be a valid HTTP_VERB
    with pytest.raises(ValueError):
        APIOperation(
            name='bad',
            displayName='Bad',
            urlTemplate='/bad',
            method='INVALID',
            description='desc',
            policyXml='<xml/>'
        )

# ------------------------------
#    PRODUCT TESTS
# ------------------------------

@pytest.mark.unit
def test_product_creation():
    """Test creation of Product object and its attributes."""
    product = Product(
        name = 'hr',
        displayName = 'Human Resources',
        description = 'HR product description'
    )

    assert product.name == 'hr'
    assert product.displayName == 'Human Resources'
    assert product.description == 'HR product description'
    assert product.state == 'published'  # default value
    assert product.subscriptionRequired is True  # default value
    assert product.policyXml is not None  # should have default policy


@pytest.mark.unit
def test_product_creation_with_custom_values():
    """Test creation of Product object with custom values."""
    custom_policy = '<policies><inbound><base /></inbound></policies>'
    product = Product(
        name = 'test-product',
        displayName = 'Test Product',
        description = 'Test description',
        state = 'notPublished',
        subscriptionRequired = False,
        policyXml = custom_policy
    )

    assert product.name == 'test-product'
    assert product.displayName == 'Test Product'
    assert product.description == 'Test description'
    assert product.state == 'notPublished'
    assert product.subscriptionRequired is False
    assert product.policyXml == custom_policy


@pytest.mark.unit
def test_product_creation_with_approval_required():
    """Test creation of Product object with approvalRequired set to True."""
    product = Product(
        name = 'premium-hr',
        displayName = 'Premium Human Resources',
        description = 'Premium HR product requiring approval',
        subscriptionRequired = True,
        approvalRequired = True
    )

    assert product.name == 'premium-hr'
    assert product.displayName == 'Premium Human Resources'
    assert product.description == 'Premium HR product requiring approval'
    assert product.state == 'published'  # default value
    assert product.subscriptionRequired is True
    assert product.approvalRequired is True
    assert product.policyXml is not None  # should have default policy


@pytest.mark.unit
def test_product_to_dict():
    """Test that to_dict includes all required fields."""
    custom_policy = '<policies><inbound><base /></inbound></policies>'
    product = Product(
        name = 'hr',
        displayName = 'Human Resources',
        description = 'HR product',
        state = 'published',
        subscriptionRequired = True,
        policyXml = custom_policy
    )
    d = product.to_dict()

    assert d['name'] == 'hr'
    assert d['displayName'] == 'Human Resources'
    assert d['description'] == 'HR product'
    assert d['state'] == 'published'
    assert d['subscriptionRequired'] is True
    assert d['policyXml'] == custom_policy


@pytest.mark.unit
def test_product_to_dict_includes_approval_required():
    """Test that to_dict includes approvalRequired field."""
    product = Product(
        name = 'premium-hr',
        displayName = 'Premium Human Resources',
        description = 'Premium HR product',
        subscriptionRequired = True,
        approvalRequired = True
    )
    d = product.to_dict()

    assert d['name'] == 'premium-hr'
    assert d['displayName'] == 'Premium Human Resources'
    assert d['description'] == 'Premium HR product'
    assert d['state'] == 'published'
    assert d['subscriptionRequired'] is True
    assert d['approvalRequired'] is True
    assert 'policyXml' in d


@pytest.mark.unit
def test_product_approval_required_default_false():
    """Test that approvalRequired defaults to False when not specified."""
    product = Product(
        name = 'basic-hr',
        displayName = 'Basic Human Resources',
        description = 'Basic HR product'
    )

    assert product.approvalRequired is False
    d = product.to_dict()
    assert d['approvalRequired'] is False


@pytest.mark.unit
def test_product_equality():
    """Test equality comparison for Product objects."""
    product1 = Product(
        name = 'hr',
        displayName = 'Human Resources',
        description = 'HR product'
    )
    product2 = Product(
        name = 'hr',
        displayName = 'Human Resources',
        description = 'HR product'
    )
    assert product1 == product2

    # Different names should not be equal
    product3 = Product(
        name = 'finance',
        displayName = 'Human Resources',
        description = 'HR product'
    )
    assert product1 != product3


@pytest.mark.unit
def test_product_repr():
    """Test __repr__ method of Product."""
    product = Product(
        name = 'hr',
        displayName = 'Human Resources',
        description = 'HR product'
    )
    result = repr(product)
    assert 'Product' in result
    assert 'hr' in result
    assert 'Human Resources' in result

@pytest.mark.unit
def test_api_subscription_required_default():
    """Test that API object has subscriptionRequired defaulting to True."""
    api = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    assert api.subscriptionRequired is True

@pytest.mark.unit
def test_api_subscription_required_explicit_false():
    """Test creation of API object with explicit subscriptionRequired=False."""
    api = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        subscriptionRequired = False
    )
    assert api.subscriptionRequired is False

@pytest.mark.unit
def test_api_subscription_required_explicit_true():
    """Test creation of API object with explicit subscriptionRequired=True."""
    api = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        subscriptionRequired = True
    )
    assert api.subscriptionRequired is True

@pytest.mark.unit
def test_api_to_dict_includes_subscription_required_when_true():
    """Test that to_dict includes subscriptionRequired when True."""
    api = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        subscriptionRequired = True
    )
    d = api.to_dict()
    assert 'subscriptionRequired' in d
    assert d['subscriptionRequired'] is True

@pytest.mark.unit
def test_api_to_dict_includes_subscription_required_when_false():
    """Test that to_dict includes subscriptionRequired when explicitly False."""
    api = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        subscriptionRequired = False
    )
    d = api.to_dict()
    assert 'subscriptionRequired' in d
    assert d['subscriptionRequired'] is False

@pytest.mark.unit
def test_api_equality_with_subscription_required():
    """Test equality comparison for API objects with different subscriptionRequired values."""
    api1 = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        subscriptionRequired = True
    )
    api2 = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        subscriptionRequired = True
    )
    api3 = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        subscriptionRequired = False
    )

    # Same subscriptionRequired values should be equal
    assert api1 == api2

    # Different subscriptionRequired values should not be equal
    assert api1 != api3

@pytest.mark.unit
def test_api_with_all_properties():
    """Test creation of API object with all properties including subscriptionRequired."""
    tags = ['tag1', 'tag2']
    product_names = ['product1', 'product2']
    api = API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        tags = tags,
        productNames = product_names,
        subscriptionRequired = True
    )

    assert api.name == EXAMPLE_NAME
    assert api.displayName == EXAMPLE_DISPLAY_NAME
    assert api.path == EXAMPLE_PATH
    assert api.description == EXAMPLE_DESCRIPTION
    assert api.policyXml == EXAMPLE_POLICY_XML
    assert api.operations == []
    assert api.tags == tags
    assert api.productNames == product_names
    assert api.subscriptionRequired is True

    d = api.to_dict()
    assert d['name'] == EXAMPLE_NAME
    assert d['displayName'] == EXAMPLE_DISPLAY_NAME
    assert d['path'] == EXAMPLE_PATH
    assert d['description'] == EXAMPLE_DESCRIPTION
    assert d['policyXml'] == EXAMPLE_POLICY_XML
    assert d['tags'] == tags
    assert d['productNames'] == product_names
    assert d['subscriptionRequired'] is True


# ------------------------------
#    MISSING COVERAGE TESTS FOR APIMTYPES
# ------------------------------

def test_named_value_creation():
    """Test NamedValue creation and methods."""
    nv = NamedValue(
        name='test-nv',
        value='test-value',
        isSecret=True
    )
    assert nv.name == 'test-nv'
    assert nv.value == 'test-value'
    assert nv.isSecret is True

    # Test to_dict method
    d = nv.to_dict()
    assert d['name'] == 'test-nv'
    assert d['isSecret'] is True

def test_named_value_defaults():
    """Test NamedValue default values."""
    nv = NamedValue(name='test', value='value')
    assert nv.isSecret is False  # default value

def test_policy_fragment_creation():
    """Test PolicyFragment creation and methods."""
    pf = PolicyFragment(
        name='test-fragment',
        description='Test fragment',
        policyXml='<policy/>'
    )
    assert pf.name == 'test-fragment'
    assert pf.description == 'Test fragment'
    assert pf.policyXml == '<policy/>'

    # Test to_dict method
    d = pf.to_dict()
    assert d['name'] == 'test-fragment'
    assert d['policyXml'] == '<policy/>'

def test_policy_fragment_defaults():
    """Test PolicyFragment default values."""
    pf = PolicyFragment(name='test', policyXml='<policy/>')
    assert not pf.description  # default value

def test_product_defaults():
    """Test Product default values."""
    product = Product(name='test', displayName='Test', description='Test description')
    assert product.state == 'published'  # default value
    assert product.subscriptionRequired is True  # default value

def test_get_apioperation2():
    """Test GET_APIOperation2 class."""
    op = GET_APIOperation2(
        name='test-op',
        displayName='Test Operation',
        urlTemplate='/test',
        description='test',
        policyXml='<xml/>'
    )
    assert op.name == 'test-op'
    assert op.displayName == 'Test Operation'
    assert op.urlTemplate == '/test'
    assert op.method == HTTP_VERB.GET
    assert op.description == 'test'
    assert op.policyXml == '<xml/>'

def test_api_operation_equality():
    """Test APIOperation equality comparison."""
    op1 = APIOperation(
        name='test',
        displayName='Test',
        urlTemplate='/test',
        method=HTTP_VERB.GET,
        description='Test op',
        policyXml='<xml/>'
    )
    op2 = APIOperation(
        name='test',
        displayName='Test',
        urlTemplate='/test',
        method=HTTP_VERB.GET,
        description='Test op',
        policyXml='<xml/>'
    )
    op3 = APIOperation(
        name='different',
        displayName='Test',
        urlTemplate='/test',
        method=HTTP_VERB.GET,
        description='Test op',
        policyXml='<xml/>'
    )

    assert op1 == op2
    assert op1 != op3

def test_api_operation_repr():
    """Test APIOperation __repr__ method."""
    op = APIOperation(
        name='test',
        displayName='Test',
        urlTemplate='/test',
        method=HTTP_VERB.GET,
        description='Test op',
        policyXml='<xml/>'
    )
    result = repr(op)
    assert 'APIOperation' in result
    assert 'test' in result

def test_named_value_repr():
    """Test NamedValue __repr__ method."""
    nv = NamedValue(name='test-nv', value='value')
    result = repr(nv)
    assert 'NamedValue' in result
    assert 'test-nv' in result

def test_policy_fragment_repr():
    """Test PolicyFragment __repr__ method."""
    pf = PolicyFragment(name='test-fragment', policyXml='<policy/>')
    result = repr(pf)
    assert 'PolicyFragment' in result
    assert 'test-fragment' in result


# ------------------------------
#    ADDITIONAL COVERAGE TESTS
# ------------------------------

def testget_project_root_functionality():
    """Test get_project_root function comprehensively."""

    # This function should return the project root
    root = get_project_root()
    assert isinstance(root, Path)
    assert root.exists()

def test_output_class_basic():
    """Test Output class initialization and properties."""
    # Test successful output with JSON
    output = Output(True, '{"key": "value"}')
    assert output.success is True
    assert output.text == '{"key": "value"}'
    assert output.json_data == {"key": "value"}
    assert output.is_json is True

def test_output_class_non_json():
    """Test Output class with non-JSON text."""
    output = Output(True, 'some plain text')
    assert output.success is True
    assert output.text == 'some plain text'
    assert output.json_data is None
    assert output.is_json is False

def test_output_get_with_properties_structure():
    """Test Output.get() with deployment output structure."""
    json_text = json.dumps({
        'properties': {
            'outputs': {
                'apimName': {'value': 'my-apim'}
            }
        }
    })
    output = Output(True, json_text)
    result = output.get('apimName', suppress_logging=True)
    assert result == 'my-apim'

def test_output_get_missing_key():
    """Test Output.get() with missing key."""
    json_text = json.dumps({
        'properties': {
            'outputs': {
                'apimName': {'value': 'my-apim'}
            }
        }
    })
    output = Output(True, json_text)
    result = output.get('nonExistent', suppress_logging=True)
    assert result is None

def test_output_get_non_dict_json():
    """Test Output.get() when json_data is not a dict."""
    output = Output(True, '[1, 2, 3]')
    result = output.get('key', suppress_logging=True)
    assert result is None

def test_output_get_missing_properties():
    """Test Output.get() when 'properties' key is missing."""
    json_text = json.dumps({
        'data': {
            'outputs': {
                'apimName': {'value': 'my-apim'}
            }
        }
    })
    output = Output(True, json_text)
    # Should look for key at root level
    result = output.get('apimName', suppress_logging=True)
    assert result is None

def test_output_getJson_with_nested_structure():
    """Test Output.getJson() returns parsed JSON from nested value."""
    nested_json = '{"nested": "data"}'
    json_text = json.dumps({
        'properties': {
            'outputs': {
                'config': {'value': nested_json}
            }
        }
    })
    output = Output(True, json_text)
    result = output.getJson('config', suppress_logging=True)
    assert result == {"nested": "data"}

def test_output_getJson_with_dict_value():
    """Test Output.getJson() with dict value."""
    json_text = json.dumps({
        'properties': {
            'outputs': {
                'config': {'value': {"nested": "dict"}}
            }
        }
    })
    output = Output(True, json_text)
    result = output.getJson('config', suppress_logging=True)
    assert result == {"nested": "dict"}

def test_output_getJson_with_missing_key():
    """Test Output.getJson() with missing key."""
    json_text = json.dumps({
        'properties': {
            'outputs': {
                'apimName': {'value': 'my-apim'}
            }
        }
    })
    output = Output(True, json_text)
    result = output.getJson('nonExistent', suppress_logging=True)
    assert result is None

def test_output_get_with_direct_key():
    """Test Output.get() when output key is at root level."""
    json_text = json.dumps({
        'apimName': {'value': 'my-apim'},
        'location': {'value': 'eastus'}
    })
    output = Output(True, json_text)
    result = output.get('apimName', suppress_logging=True)
    assert result == 'my-apim'

def test_output_get_with_label_and_secure():
    """Test Output.get() with label and secure masking."""
    json_text = json.dumps({
        'properties': {
            'outputs': {
                'secretKey': {'value': 'very-secret-key-12345'}
            }
        }
    })
    output = Output(True, json_text)
    # Should not raise even with label; we suppress logging in test
    result = output.get('secretKey', label='Secret', secure=True, suppress_logging=True)
    assert result == 'very-secret-key-12345'

def test_output_getJson_with_list_value():
    """Test Output.getJson() with array value."""
    json_text = json.dumps({
        'properties': {
            'outputs': {
                'items': {'value': [1, 2, 3, 4, 5]}
            }
        }
    })
    output = Output(True, json_text)
    result = output.getJson('items', suppress_logging=True)
    assert result == [1, 2, 3, 4, 5]

def test_output_getJson_with_string_json_value():
    """Test Output.getJson() when value is JSON-formatted string."""
    nested_json = '{"nested": "object"}'
    json_text = json.dumps({
        'properties': {
            'outputs': {
                'config': {'value': nested_json}
            }
        }
    })
    output = Output(True, json_text)
    result = output.getJson('config', suppress_logging=True)
    assert result == {"nested": "object"}

def test_output_get_empty_string_value():
    """Test Output.get() with empty string value."""
    json_text = json.dumps({
        'properties': {
            'outputs': {
                'empty': {'value': ''}
            }
        }
    })
    output = Output(True, json_text)
    result = output.get('empty', suppress_logging=True)
    assert not result

def test_output_getJson_empty_object():
    """Test Output.getJson() with empty JSON object."""
    json_text = json.dumps({
        'properties': {
            'outputs': {
                'emptyObj': {'value': {}}
            }
        }
    })
    output = Output(True, json_text)
    result = output.getJson('emptyObj', suppress_logging=True)
    assert result == {}

def test_output_parse_error_handling():
    """Test Output class handles JSON parse errors gracefully."""
    # JSON that doesn't parse but has structure
    output = Output(True, '{invalid json here}')
    # Should still initialize without crashing
    assert output.text == '{invalid json here}'
    assert output.success is True


def test_api_edge_cases():
    """Test API class with edge cases and full coverage."""
    # Test with all None/empty values
    api = API('', '', '', '', '', operations=None, tags=None, productNames=None)
    assert not api.name
    assert api.operations == []
    assert api.tags == []
    assert api.productNames == []

    # Test subscription required variations
    api_sub_true = API('test', 'Test', '/test', 'desc', 'policy', subscriptionRequired=True)
    assert api_sub_true.subscriptionRequired is True

    api_sub_false = API('test', 'Test', '/test', 'desc', 'policy', subscriptionRequired=False)
    assert api_sub_false.subscriptionRequired is False


def test_product_edge_cases():
    """Test Product class with edge cases."""
    # Test with minimal parameters
    product = Product('test', 'Test Product', 'Test Description')
    assert product.name == 'test'
    assert product.displayName == 'Test Product'
    assert product.description == 'Test Description'
    assert product.state == 'published'
    assert product.subscriptionRequired is True  # Default is True
    assert product.approvalRequired is False
    # Policy XML should contain some content, not be empty
    assert product.policyXml is not None and len(product.policyXml) > 0

    # Test with all parameters
    product_full = Product(
        'full', 'Full Product', 'Description', 'notPublished',
        True, True, '<policy/>'
    )
    assert product_full.state == 'notPublished'
    assert product_full.subscriptionRequired is True
    assert product_full.approvalRequired is True
    assert product_full.policyXml == '<policy/>'


def test_named_value_edge_cases():
    """Test NamedValue class edge cases."""
    # Test with minimal parameters
    nv = NamedValue('key', 'value')
    assert nv.name == 'key'
    assert nv.value == 'value'
    assert nv.isSecret is False  # Use correct attribute name

    # Test with secret
    nv_secret = NamedValue('secret-key', 'secret-value', True)
    assert nv_secret.isSecret is True  # Use correct attribute name


def test_policy_fragment_edge_cases():
    """Test PolicyFragment class edge cases."""
    # Test with minimal parameters
    pf = PolicyFragment('frag', '<fragment/>')
    assert pf.name == 'frag'
    assert pf.policyXml == '<fragment/>'  # Use correct attribute name
    assert not pf.description

    # Test with description
    pf_desc = PolicyFragment('frag', '<fragment/>', 'Test fragment')
    assert pf_desc.description == 'Test fragment'


def test_api_operation_comprehensive():
    """Test APIOperation class comprehensively."""
    # Test invalid HTTP method
    with pytest.raises(ValueError, match='Invalid HTTP_VERB'):
        APIOperation('test', 'Test', '/test', 'INVALID', 'Test description', '<policy/>')

    # Test all valid methods
    for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
        # Get HTTP_VERB enum value
        http_verb = HTTP_VERB(method)
        op = APIOperation(f'test-{method.lower()}', f'Test {method}', f'/test-{method.lower()}', http_verb, f'Test {method} description', '<policy/>')
        assert op.method == http_verb
        assert op.displayName == f'Test {method}'
        assert op.policyXml == '<policy/>'


def test_convenience_functions():
    """Test convenience functions for API operations."""
    get_op = GET_APIOperation('Get data', '<get-policy/>')
    assert get_op.method == HTTP_VERB.GET
    assert get_op.displayName == 'GET'  # displayName is set to 'GET', not the description
    assert get_op.description == 'Get data'  # description parameter goes to description field

    post_op = POST_APIOperation('Post data', '<post-policy/>')
    assert post_op.method == HTTP_VERB.POST
    assert post_op.displayName == 'POST'  # displayName is set to 'POST', not the description
    assert post_op.description == 'Post data'  # description parameter goes to description field


def test_enum_edge_cases():
    """Test enum edge cases and completeness."""
    # Test all enum values exist
    assert hasattr(INFRASTRUCTURE, 'SIMPLE_APIM')
    assert hasattr(INFRASTRUCTURE, 'AFD_APIM_PE')
    assert hasattr(INFRASTRUCTURE, 'APIM_ACA')

    assert hasattr(APIM_SKU, 'DEVELOPER')
    assert hasattr(APIM_SKU, 'BASIC')
    assert hasattr(APIM_SKU, 'STANDARD')
    assert hasattr(APIM_SKU, 'PREMIUM')

    assert hasattr(APIMNetworkMode, 'EXTERNAL_VNET')  # Correct enum name
    assert hasattr(APIMNetworkMode, 'INTERNAL_VNET')  # Correct enum name

    assert hasattr(HTTP_VERB, 'GET')
    assert hasattr(HTTP_VERB, 'POST')


def test_role_enum_comprehensive():
    """Test Role enum comprehensively."""
    # Test all role values (these are GUIDs, not string names)
    assert Role.HR_MEMBER == '316790bc-fbd3-4a14-8867-d1388ffbc195'
    assert Role.HR_ASSOCIATE == 'd3c1b0f2-4a5e-4c8b-9f6d-7c8e1f2a3b4c'
    assert Role.HR_ADMINISTRATOR == 'a1b2c3d4-e5f6-7g8h-9i0j-k1l2m3n4o5p6'


def test_to_dict_comprehensive():
    """Test to_dict methods comprehensively."""
    # Test API with all properties
    op = GET_APIOperation('Get', '<get/>')
    api = API(
        'test-api', 'Test API', '/test', 'Test desc', '<policy/>',
        operations=[op], tags=['tag1', 'tag2'], productNames=['prod1'],
        subscriptionRequired=True
    )

    api_dict = api.to_dict()
    assert api_dict['name'] == 'test-api'
    assert api_dict['displayName'] == 'Test API'
    assert api_dict['path'] == '/test'
    assert api_dict['description'] == 'Test desc'
    assert api_dict['policyXml'] == '<policy/>'
    assert len(api_dict['operations']) == 1
    assert api_dict['tags'] == ['tag1', 'tag2']
    assert api_dict['productNames'] == ['prod1']
    assert api_dict['subscriptionRequired'] is True

    # Test Product to_dict
    product = Product('prod', 'Product', 'Desc', 'published', True, True, '<prod-policy/>')
    prod_dict = product.to_dict()
    assert prod_dict['name'] == 'prod'
    assert prod_dict['displayName'] == 'Product'
    assert prod_dict['description'] == 'Desc'
    assert prod_dict['state'] == 'published'
    assert prod_dict['subscriptionRequired'] is True
    assert prod_dict['approvalRequired'] is True
    assert prod_dict['policyXml'] == '<prod-policy/>'

    # Test NamedValue to_dict
    nv = NamedValue('key', 'value', True)
    nv_dict = nv.to_dict()
    assert nv_dict['name'] == 'key'
    assert nv_dict['value'] == 'value'
    assert nv_dict['isSecret'] is True  # Use correct key name

    # Test PolicyFragment to_dict
    pf = PolicyFragment('frag', '<frag/>', 'Fragment desc')
    pf_dict = pf.to_dict()
    assert pf_dict['name'] == 'frag'
    assert pf_dict['policyXml'] == '<frag/>'  # Use correct key name
    assert pf_dict['description'] == 'Fragment desc'


def test_equality_and_repr_comprehensive():
    """Test equality and repr methods comprehensively."""
    api1 = API('test', 'Test', '/test', 'desc', 'policy')
    api2 = API('test', 'Test', '/test', 'desc', 'policy')
    api3 = API('different', 'Different', '/diff', 'desc', 'policy')

    assert api1 == api2
    assert api1 != api3
    assert api1 != 'not an api'

    # Test repr
    repr_str = repr(api1)
    assert 'API' in repr_str
    assert 'test' in repr_str

    # Test Product equality and repr
    prod1 = Product('prod', 'Product', 'Product description')
    prod2 = Product('prod', 'Product', 'Product description')
    prod3 = Product('other', 'Other', 'Other description')

    assert prod1 == prod2
    assert prod1 != prod3
    assert prod1 != 'not a product'

    repr_str = repr(prod1)
    assert 'Product' in repr_str
    assert 'prod' in repr_str

    # Test APIOperation equality and repr
    op1 = GET_APIOperation('Get', '<get/>')
    op2 = GET_APIOperation('Get', '<get/>')
    op3 = POST_APIOperation('Post', '<post/>')

    assert op1 == op2
    assert op1 != op3
    assert op1 != 'not an operation'

    repr_str = repr(op1)
    assert 'APIOperation' in repr_str
    assert 'GET' in repr_str


def test_constants_accessibility():
    """Test that all constants are accessible."""
    # Test policy file paths
    assert isinstance(DEFAULT_XML_POLICY_PATH, str)
    assert isinstance(HELLO_WORLD_XML_POLICY_PATH, str)
    assert isinstance(REQUEST_HEADERS_XML_POLICY_PATH, str)
    assert isinstance(BACKEND_XML_POLICY_PATH, str)

    # Test other constants
    assert isinstance(SUBSCRIPTION_KEY_PARAMETER_NAME, str)
    assert isinstance(SLEEP_TIME_BETWEEN_REQUESTS_MS, int)
