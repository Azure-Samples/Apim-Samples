"""
Unit tests for apimtypes.py.
"""

from pathlib import Path
import pytest
import apimtypes



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
    tags = ['tag1', 'tag2']
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
    product_names = ['product1', 'product2']
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
    tags = ['foo', 'bar']
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
    assert 'tags' in d
    assert d['tags'] == tags

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
    assert 'tags' not in d or d['tags'] == []

@pytest.mark.unit
def test_api_to_dict_includes_product_names():
    """Test that to_dict includes productNames when present."""
    product_names = ['product1', 'product2']
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
    assert 'productNames' in d
    assert d['productNames'] == product_names

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
    assert 'productNames' not in d or d['productNames'] == []

@pytest.mark.unit
def test_api_with_both_tags_and_product_names():
    """Test creation of API object with both tags and product names."""
    tags = ['tag1', 'tag2']
    product_names = ['product1', 'product2']
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
    assert d['tags'] == tags
    assert d['productNames'] == product_names

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
    assert 'API' in result
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
        tags = ['a', 'b']
    )
    api2 = apimtypes.API(
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
    api3 = apimtypes.API(
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
    api4 = apimtypes.API(
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
    api1 = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    api2 = apimtypes.API(
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
    assert apimtypes.APIMNetworkMode.PUBLIC == 'Public'
    assert apimtypes.APIMNetworkMode.EXTERNAL_VNET == 'External'
    assert apimtypes.APIMNetworkMode.INTERNAL_VNET == 'Internal'
    assert apimtypes.APIMNetworkMode.NONE == 'None'
    with pytest.raises(ValueError):
        apimtypes.APIMNetworkMode('invalid')

def test_apim_sku_enum():
    assert apimtypes.APIM_SKU.DEVELOPER == 'Developer'
    assert apimtypes.APIM_SKU.BASIC == 'Basic'
    assert apimtypes.APIM_SKU.STANDARD == 'Standard'
    assert apimtypes.APIM_SKU.PREMIUM == 'Premium'
    assert apimtypes.APIM_SKU.BASICV2 == 'Basicv2'
    assert apimtypes.APIM_SKU.STANDARDV2 == 'Standardv2'
    assert apimtypes.APIM_SKU.PREMIUMV2 == 'Premiumv2'
    with pytest.raises(ValueError):
        apimtypes.APIM_SKU('invalid')

def test_http_verb_enum():
    assert apimtypes.HTTP_VERB.GET == 'GET'
    assert apimtypes.HTTP_VERB.POST == 'POST'
    assert apimtypes.HTTP_VERB.PUT == 'PUT'
    assert apimtypes.HTTP_VERB.DELETE == 'DELETE'
    assert apimtypes.HTTP_VERB.PATCH == 'PATCH'
    assert apimtypes.HTTP_VERB.OPTIONS == 'OPTIONS'
    assert apimtypes.HTTP_VERB.HEAD == 'HEAD'
    with pytest.raises(ValueError):
        apimtypes.HTTP_VERB('FOO')

def test_infrastructure_enum():
    assert apimtypes.INFRASTRUCTURE.SIMPLE_APIM == 'simple-apim'
    assert apimtypes.INFRASTRUCTURE.APIM_ACA == 'apim-aca'
    assert apimtypes.INFRASTRUCTURE.AFD_APIM_PE == 'afd-apim-pe'
    with pytest.raises(ValueError):
        apimtypes.INFRASTRUCTURE('bad')


# ------------------------------
#    OPERATION CLASSES
# ------------------------------

def test_apioperation_to_dict():
    op = apimtypes.APIOperation(
        name='op1',
        displayName='Operation 1',
        urlTemplate='/foo',
        method=apimtypes.HTTP_VERB.GET,
        description='desc',
        policyXml='<xml/>'
    )
    d = op.to_dict()
    assert d['name'] == 'op1'
    assert d['displayName'] == 'Operation 1'
    assert d['urlTemplate'] == '/foo'
    assert d['method'] == apimtypes.HTTP_VERB.GET
    assert d['description'] == 'desc'
    assert d['policyXml'] == '<xml/>'

def test_get_apioperation():
    op = apimtypes.GET_APIOperation(description='desc', policyXml='<xml/>')
    assert op.name == 'GET'
    assert op.method == apimtypes.HTTP_VERB.GET
    assert op.urlTemplate == '/'
    assert op.description == 'desc'
    assert op.policyXml == '<xml/>'
    d = op.to_dict()
    assert d['method'] == apimtypes.HTTP_VERB.GET

def test_post_apioperation():
    op = apimtypes.POST_APIOperation(description='desc', policyXml='<xml/>')
    assert op.name == 'POST'
    assert op.method == apimtypes.HTTP_VERB.POST
    assert op.urlTemplate == '/'
    assert op.description == 'desc'
    assert op.policyXml == '<xml/>'
    d = op.to_dict()
    assert d['method'] == apimtypes.HTTP_VERB.POST

def test_apioperation_invalid_method():
    # Negative: method must be a valid HTTP_VERB
    with pytest.raises(ValueError):
        apimtypes.APIOperation(
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
    product = apimtypes.Product(
        name = 'hr',
        displayName = 'Human Resources',
        description = 'HR product description'
    )

    assert product.name == 'hr'
    assert product.displayName == 'Human Resources'
    assert product.description == 'HR product description'
    assert product.state == 'published'  # default value
    assert product.subscriptionRequired == True  # default value
    assert product.policyXml is not None  # should have default policy


@pytest.mark.unit
def test_product_creation_with_custom_values():
    """Test creation of Product object with custom values."""
    custom_policy = '<policies><inbound><base /></inbound></policies>'
    product = apimtypes.Product(
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
    assert product.subscriptionRequired == False
    assert product.policyXml == custom_policy


@pytest.mark.unit
def test_product_creation_with_approval_required():
    """Test creation of Product object with approvalRequired set to True."""
    product = apimtypes.Product(
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
    assert product.subscriptionRequired == True
    assert product.approvalRequired == True
    assert product.policyXml is not None  # should have default policy


@pytest.mark.unit
def test_product_to_dict():
    """Test that to_dict includes all required fields."""
    custom_policy = '<policies><inbound><base /></inbound></policies>'
    product = apimtypes.Product(
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
    assert d['subscriptionRequired'] == True
    assert d['policyXml'] == custom_policy


@pytest.mark.unit
def test_product_to_dict_includes_approval_required():
    """Test that to_dict includes approvalRequired field."""
    product = apimtypes.Product(
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
    assert d['subscriptionRequired'] == True
    assert d['approvalRequired'] == True
    assert 'policyXml' in d


@pytest.mark.unit
def test_product_approval_required_default_false():
    """Test that approvalRequired defaults to False when not specified."""
    product = apimtypes.Product(
        name = 'basic-hr',
        displayName = 'Basic Human Resources',
        description = 'Basic HR product'
    )

    assert product.approvalRequired == False
    d = product.to_dict()
    assert d['approvalRequired'] == False


@pytest.mark.unit
def test_product_equality():
    """Test equality comparison for Product objects."""
    product1 = apimtypes.Product(
        name = 'hr',
        displayName = 'Human Resources',
        description = 'HR product'
    )
    product2 = apimtypes.Product(
        name = 'hr',
        displayName = 'Human Resources',
        description = 'HR product'
    )
    assert product1 == product2

    # Different names should not be equal
    product3 = apimtypes.Product(
        name = 'finance',
        displayName = 'Human Resources',
        description = 'HR product'
    )
    assert product1 != product3


@pytest.mark.unit
def test_product_repr():
    """Test __repr__ method of Product."""
    product = apimtypes.Product(
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
    api = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None
    )
    assert api.subscriptionRequired == True

@pytest.mark.unit
def test_api_subscription_required_explicit_false():
    """Test creation of API object with explicit subscriptionRequired=False."""
    api = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        subscriptionRequired = False
    )
    assert api.subscriptionRequired == False

@pytest.mark.unit
def test_api_subscription_required_explicit_true():
    """Test creation of API object with explicit subscriptionRequired=True."""
    api = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        subscriptionRequired = True
    )
    assert api.subscriptionRequired == True

@pytest.mark.unit
def test_api_to_dict_includes_subscription_required_when_true():
    """Test that to_dict includes subscriptionRequired when True."""
    api = apimtypes.API(
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
    assert d['subscriptionRequired'] == True

@pytest.mark.unit
def test_api_to_dict_includes_subscription_required_when_false():
    """Test that to_dict includes subscriptionRequired when explicitly False."""
    api = apimtypes.API(
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
    assert d['subscriptionRequired'] == False

@pytest.mark.unit
def test_api_equality_with_subscription_required():
    """Test equality comparison for API objects with different subscriptionRequired values."""
    api1 = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        subscriptionRequired = True
    )
    api2 = apimtypes.API(
        name = EXAMPLE_NAME,
        displayName = EXAMPLE_DISPLAY_NAME,
        path = EXAMPLE_PATH,
        description = EXAMPLE_DESCRIPTION,
        policyXml = EXAMPLE_POLICY_XML,
        operations = None,
        subscriptionRequired = True
    )
    api3 = apimtypes.API(
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
    api = apimtypes.API(
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
    assert api.subscriptionRequired == True

    d = api.to_dict()
    assert d['name'] == EXAMPLE_NAME
    assert d['displayName'] == EXAMPLE_DISPLAY_NAME
    assert d['path'] == EXAMPLE_PATH
    assert d['description'] == EXAMPLE_DESCRIPTION
    assert d['policyXml'] == EXAMPLE_POLICY_XML
    assert d['tags'] == tags
    assert d['productNames'] == product_names
    assert d['subscriptionRequired'] == True


# ------------------------------
#    MISSING COVERAGE TESTS FOR APIMTYPES
# ------------------------------

def test_named_value_creation():
    """Test NamedValue creation and methods."""
    nv = apimtypes.NamedValue(
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
    nv = apimtypes.NamedValue(name='test', value='value')
    assert nv.isSecret is False  # default value

def test_policy_fragment_creation():
    """Test PolicyFragment creation and methods."""
    pf = apimtypes.PolicyFragment(
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
    pf = apimtypes.PolicyFragment(name='test', policyXml='<policy/>')
    assert pf.description == ''  # default value

def test_product_defaults():
    """Test Product default values."""
    product = apimtypes.Product(name='test', displayName='Test', description='Test description')
    assert product.state == 'published'  # default value
    assert product.subscriptionRequired is True  # default value

def test_get_apioperation2():
    """Test GET_APIOperation2 class."""
    op = apimtypes.GET_APIOperation2(
        name='test-op',
        displayName='Test Operation',
        urlTemplate='/test',
        description='test',
        policyXml='<xml/>'
    )
    assert op.name == 'test-op'
    assert op.displayName == 'Test Operation'
    assert op.urlTemplate == '/test'
    assert op.method == apimtypes.HTTP_VERB.GET
    assert op.description == 'test'
    assert op.policyXml == '<xml/>'

def test_api_operation_equality():
    """Test APIOperation equality comparison."""
    op1 = apimtypes.APIOperation(
        name='test',
        displayName='Test',
        urlTemplate='/test',
        method=apimtypes.HTTP_VERB.GET,
        description='Test op',
        policyXml='<xml/>'
    )
    op2 = apimtypes.APIOperation(
        name='test',
        displayName='Test',
        urlTemplate='/test',
        method=apimtypes.HTTP_VERB.GET,
        description='Test op',
        policyXml='<xml/>'
    )
    op3 = apimtypes.APIOperation(
        name='different',
        displayName='Test',
        urlTemplate='/test',
        method=apimtypes.HTTP_VERB.GET,
        description='Test op',
        policyXml='<xml/>'
    )

    assert op1 == op2
    assert op1 != op3

def test_api_operation_repr():
    """Test APIOperation __repr__ method."""
    op = apimtypes.APIOperation(
        name='test',
        displayName='Test',
        urlTemplate='/test',
        method=apimtypes.HTTP_VERB.GET,
        description='Test op',
        policyXml='<xml/>'
    )
    result = repr(op)
    assert 'APIOperation' in result
    assert 'test' in result

def test_named_value_repr():
    """Test NamedValue __repr__ method."""
    nv = apimtypes.NamedValue(name='test-nv', value='value')
    result = repr(nv)
    assert 'NamedValue' in result
    assert 'test-nv' in result

def test_policy_fragment_repr():
    """Test PolicyFragment __repr__ method."""
    pf = apimtypes.PolicyFragment(name='test-fragment', policyXml='<policy/>')
    result = repr(pf)
    assert 'PolicyFragment' in result
    assert 'test-fragment' in result


# ------------------------------
#    ADDITIONAL COVERAGE TESTS
# ------------------------------

def test_get_project_root_functionality():
    """Test _get_project_root function comprehensively."""

    # This function should return the project root
    root = apimtypes._get_project_root()
    assert isinstance(root, Path)
    assert root.exists()


def test_api_edge_cases():
    """Test API class with edge cases and full coverage."""
    # Test with all None/empty values
    api = apimtypes.API('', '', '', '', '', operations=None, tags=None, productNames=None)
    assert api.name == ''
    assert api.operations == []
    assert api.tags == []
    assert api.productNames == []

    # Test subscription required variations
    api_sub_true = apimtypes.API('test', 'Test', '/test', 'desc', 'policy', subscriptionRequired=True)
    assert api_sub_true.subscriptionRequired is True

    api_sub_false = apimtypes.API('test', 'Test', '/test', 'desc', 'policy', subscriptionRequired=False)
    assert api_sub_false.subscriptionRequired is False


def test_product_edge_cases():
    """Test Product class with edge cases."""
    # Test with minimal parameters
    product = apimtypes.Product('test', 'Test Product', 'Test Description')
    assert product.name == 'test'
    assert product.displayName == 'Test Product'
    assert product.description == 'Test Description'
    assert product.state == 'published'
    assert product.subscriptionRequired is True  # Default is True
    assert product.approvalRequired is False
    # Policy XML should contain some content, not be empty
    assert product.policyXml is not None and len(product.policyXml) > 0

    # Test with all parameters
    product_full = apimtypes.Product(
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
    nv = apimtypes.NamedValue('key', 'value')
    assert nv.name == 'key'
    assert nv.value == 'value'
    assert nv.isSecret is False  # Use correct attribute name

    # Test with secret
    nv_secret = apimtypes.NamedValue('secret-key', 'secret-value', True)
    assert nv_secret.isSecret is True  # Use correct attribute name


def test_policy_fragment_edge_cases():
    """Test PolicyFragment class edge cases."""
    # Test with minimal parameters
    pf = apimtypes.PolicyFragment('frag', '<fragment/>')
    assert pf.name == 'frag'
    assert pf.policyXml == '<fragment/>'  # Use correct attribute name
    assert pf.description == ''

    # Test with description
    pf_desc = apimtypes.PolicyFragment('frag', '<fragment/>', 'Test fragment')
    assert pf_desc.description == 'Test fragment'


def test_api_operation_comprehensive():
    """Test APIOperation class comprehensively."""
    # Test invalid HTTP method
    with pytest.raises(ValueError, match='Invalid HTTP_VERB'):
        apimtypes.APIOperation('test', 'Test', '/test', 'INVALID', 'Test description', '<policy/>')

    # Test all valid methods
    for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
        # Get HTTP_VERB enum value
        http_verb = apimtypes.HTTP_VERB(method)
        op = apimtypes.APIOperation(f'test-{method.lower()}', f'Test {method}', f'/test-{method.lower()}', http_verb, f'Test {method} description', '<policy/>')
        assert op.method == http_verb
        assert op.displayName == f'Test {method}'
        assert op.policyXml == '<policy/>'


def test_convenience_functions():
    """Test convenience functions for API operations."""
    get_op = apimtypes.GET_APIOperation('Get data', '<get-policy/>')
    assert get_op.method == apimtypes.HTTP_VERB.GET
    assert get_op.displayName == 'GET'  # displayName is set to 'GET', not the description
    assert get_op.description == 'Get data'  # description parameter goes to description field

    post_op = apimtypes.POST_APIOperation('Post data', '<post-policy/>')
    assert post_op.method == apimtypes.HTTP_VERB.POST
    assert post_op.displayName == 'POST'  # displayName is set to 'POST', not the description
    assert post_op.description == 'Post data'  # description parameter goes to description field


def test_enum_edge_cases():
    """Test enum edge cases and completeness."""
    # Test all enum values exist
    assert hasattr(apimtypes.INFRASTRUCTURE, 'SIMPLE_APIM')
    assert hasattr(apimtypes.INFRASTRUCTURE, 'AFD_APIM_PE')
    assert hasattr(apimtypes.INFRASTRUCTURE, 'APIM_ACA')

    assert hasattr(apimtypes.APIM_SKU, 'DEVELOPER')
    assert hasattr(apimtypes.APIM_SKU, 'BASIC')
    assert hasattr(apimtypes.APIM_SKU, 'STANDARD')
    assert hasattr(apimtypes.APIM_SKU, 'PREMIUM')

    assert hasattr(apimtypes.APIMNetworkMode, 'EXTERNAL_VNET')  # Correct enum name
    assert hasattr(apimtypes.APIMNetworkMode, 'INTERNAL_VNET')  # Correct enum name

    assert hasattr(apimtypes.HTTP_VERB, 'GET')
    assert hasattr(apimtypes.HTTP_VERB, 'POST')


def test_role_enum_comprehensive():
    """Test Role enum comprehensively."""
    # Test all role values (these are GUIDs, not string names)
    assert apimtypes.Role.HR_MEMBER == '316790bc-fbd3-4a14-8867-d1388ffbc195'
    assert apimtypes.Role.HR_ASSOCIATE == 'd3c1b0f2-4a5e-4c8b-9f6d-7c8e1f2a3b4c'
    assert apimtypes.Role.HR_ADMINISTRATOR == 'a1b2c3d4-e5f6-7g8h-9i0j-k1l2m3n4o5p6'


def test_to_dict_comprehensive():
    """Test to_dict methods comprehensively."""
    # Test API with all properties
    op = apimtypes.GET_APIOperation('Get', '<get/>')
    api = apimtypes.API(
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
    product = apimtypes.Product('prod', 'Product', 'Desc', 'published', True, True, '<prod-policy/>')
    prod_dict = product.to_dict()
    assert prod_dict['name'] == 'prod'
    assert prod_dict['displayName'] == 'Product'
    assert prod_dict['description'] == 'Desc'
    assert prod_dict['state'] == 'published'
    assert prod_dict['subscriptionRequired'] is True
    assert prod_dict['approvalRequired'] is True
    assert prod_dict['policyXml'] == '<prod-policy/>'

    # Test NamedValue to_dict
    nv = apimtypes.NamedValue('key', 'value', True)
    nv_dict = nv.to_dict()
    assert nv_dict['name'] == 'key'
    assert nv_dict['value'] == 'value'
    assert nv_dict['isSecret'] is True  # Use correct key name

    # Test PolicyFragment to_dict
    pf = apimtypes.PolicyFragment('frag', '<frag/>', 'Fragment desc')
    pf_dict = pf.to_dict()
    assert pf_dict['name'] == 'frag'
    assert pf_dict['policyXml'] == '<frag/>'  # Use correct key name
    assert pf_dict['description'] == 'Fragment desc'


def test_equality_and_repr_comprehensive():
    """Test equality and repr methods comprehensively."""
    api1 = apimtypes.API('test', 'Test', '/test', 'desc', 'policy')
    api2 = apimtypes.API('test', 'Test', '/test', 'desc', 'policy')
    api3 = apimtypes.API('different', 'Different', '/diff', 'desc', 'policy')

    assert api1 == api2
    assert api1 != api3
    assert api1 != 'not an api'

    # Test repr
    repr_str = repr(api1)
    assert 'API' in repr_str
    assert 'test' in repr_str

    # Test Product equality and repr
    prod1 = apimtypes.Product('prod', 'Product', 'Product description')
    prod2 = apimtypes.Product('prod', 'Product', 'Product description')
    prod3 = apimtypes.Product('other', 'Other', 'Other description')

    assert prod1 == prod2
    assert prod1 != prod3
    assert prod1 != 'not a product'

    repr_str = repr(prod1)
    assert 'Product' in repr_str
    assert 'prod' in repr_str

    # Test APIOperation equality and repr
    op1 = apimtypes.GET_APIOperation('Get', '<get/>')
    op2 = apimtypes.GET_APIOperation('Get', '<get/>')
    op3 = apimtypes.POST_APIOperation('Post', '<post/>')

    assert op1 == op2
    assert op1 != op3
    assert op1 != 'not an operation'

    repr_str = repr(op1)
    assert 'APIOperation' in repr_str
    assert 'GET' in repr_str


def test_constants_accessibility():
    """Test that all constants are accessible."""
    # Test policy file paths
    assert isinstance(apimtypes.DEFAULT_XML_POLICY_PATH, str)
    assert isinstance(apimtypes.HELLO_WORLD_XML_POLICY_PATH, str)
    assert isinstance(apimtypes.REQUEST_HEADERS_XML_POLICY_PATH, str)
    assert isinstance(apimtypes.BACKEND_XML_POLICY_PATH, str)

    # Test other constants
    assert isinstance(apimtypes.SUBSCRIPTION_KEY_PARAMETER_NAME, str)
    assert isinstance(apimtypes.SLEEP_TIME_BETWEEN_REQUESTS_MS, int)
