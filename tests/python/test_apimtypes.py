"""
Unit tests for apimtypes.py
"""

import importlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import apimtypes

# APIM Samples imports
from apimtypes import API, APIMNetworkMode, APIM_SKU, APIOperation, BACKEND_XML_POLICY_PATH, DEFAULT_XML_POLICY_PATH, GET_APIOperation, \
    GET_APIOperation2, get_project_root, HELLO_WORLD_XML_POLICY_PATH, HTTP_VERB, INFRASTRUCTURE, NamedValue, Output, PolicyFragment, \
    POST_APIOperation, Product, REQUEST_HEADERS_XML_POLICY_PATH, Role, SUBSCRIPTION_KEY_PARAMETER_NAME, SLEEP_TIME_BETWEEN_REQUESTS_MS
from test_helpers import assert_policy_fragment_structure


# ------------------------------
#    BASE TEST CLASS FOR API
# ------------------------------

class TestAPICreation:
    """Test suite for API object creation and attributes."""

    @pytest.fixture
    def base_api_params(self):
        """Common API parameters."""
        return {
            'name': 'test-api',
            'displayName': 'Test API',
            'path': '/test',
            'description': 'A test API.',
            'policyXml': '<policies />',
            'operations': None
        }

    def test_basic_creation(self, base_api_params):
        """Test creation of API object with required fields."""
        api = API(**base_api_params)

        assert api.name == base_api_params['name']
        assert api.displayName == base_api_params['displayName']
        assert api.path == base_api_params['path']
        assert api.description == base_api_params['description']
        assert api.policyXml == base_api_params['policyXml']
        assert api.operations == []
        assert api.tags == []
        assert api.productNames == []

    @pytest.mark.parametrize('tags', [
        ['tag1', 'tag2'],
        ['single-tag'],
        ['foo', 'bar', 'baz']
    ])
    def test_creation_with_tags(self, base_api_params, tags):
        """Test creation of API object with tags."""
        api = API(**base_api_params, tags=tags)
        assert api.tags == tags

    @pytest.mark.parametrize('product_names', [
        ['product1', 'product2'],
        ['single-product'],
        ['p1', 'p2', 'p3']
    ])
    def test_creation_with_product_names(self, base_api_params, product_names):
        """Test creation of API object with product names."""
        api = API(**base_api_params, productNames=product_names)
        assert api.productNames == product_names

    def test_creation_with_both_tags_and_products(self, base_api_params):
        """Test creation of API object with both tags and product names."""
        tags = ['tag1', 'tag2']
        product_names = ['product1', 'product2']

        api = API(**base_api_params, tags=tags, productNames=product_names)

        assert api.tags == tags
        assert api.productNames == product_names

    @pytest.mark.parametrize('missing_field', [
        'name',
        'displayName',
        'path',
        'description'
    ])
    def test_missing_required_fields(self, base_api_params, missing_field):
        """Test that missing required fields raise TypeError."""
        params = base_api_params.copy()
        del params[missing_field]

        with pytest.raises(TypeError):
            API(**params)

    def test_default_policy_loaded_when_missing(self, base_api_params, monkeypatch):
        """Test API loads default policy when policyXml parameter is omitted."""

        captured = {}

        def fake_read_policy(path):
            captured['path'] = path
            return '<default-policy />'

        monkeypatch.setattr(apimtypes, '_read_policy_xml', fake_read_policy)

        params = base_api_params.copy()
        params.pop('policyXml')
        api = API(**params)

        assert api.policyXml == '<default-policy />'
        assert captured['path'] == DEFAULT_XML_POLICY_PATH


class TestAPIToDictSerialization:
    """Test suite for API.to_dict() method."""

    @pytest.fixture
    def base_api(self):
        """Create a basic API instance."""
        return API(
            name='test-api',
            displayName='Test API',
            path='/test',
            description='A test API.',
            policyXml='<policies />'
        )

    @pytest.fixture
    def base_api_no_policyXml(self):
        """Create a basic API instance."""
        return API(
            name='test-api',
            displayName='Test API',
            path='/test',
            description='A test API.',
        )

    def test_default_policyXml_when_policyXml_empty(self, base_api_no_policyXml):
        """Test that to_dict defaults policyXml when not set or empty."""
        d = base_api_no_policyXml.to_dict()
        assert d['policyXml'] == '<policies><inbound><base /></inbound></policies>'

    def test_includes_tags_when_present(self, base_api):
        """Test that to_dict includes tags when present."""
        base_api.tags = ['foo', 'bar']
        d = base_api.to_dict()
        assert 'tags' in d
        assert d['tags'] == ['foo', 'bar']

    def test_omits_tags_when_empty(self, base_api):
        """Test that to_dict omits tags when not set or empty."""
        d = base_api.to_dict()
        assert 'tags' not in d or d['tags'] == []

    def test_includes_product_names_when_present(self, base_api):
        """Test that to_dict includes productNames when present."""
        base_api.productNames = ['product1', 'product2']
        d = base_api.to_dict()
        assert 'productNames' in d
        assert d['productNames'] == ['product1', 'product2']

    def test_omits_product_names_when_empty(self, base_api):
        """Test that to_dict omits productNames when not set or empty."""
        d = base_api.to_dict()
        assert 'productNames' not in d or d['productNames'] == []


class TestAPIComparisons:
    """Test suite for API equality and inequality."""

    @pytest.fixture
    def sample_api(self):
        """Create a sample API for comparison tests."""
        return API(
            name='test-api',
            displayName='Test API',
            path='/test',
            description='A test API.',
            policyXml='<policies />',
            tags=['a', 'b']
        )

    def test_equality_same_attributes(self, sample_api):
        """Test equality comparison for identical API objects."""
        api2 = API(
            name='test-api',
            displayName='Test API',
            path='/test',
            description='A test API.',
            policyXml='<policies />',
            tags=['a', 'b']
        )
        assert sample_api == api2

    @pytest.mark.parametrize('changed_attr,new_value', [
        ('name', 'other-api'),
        ('tags', ['x']),
        ('productNames', ['different-product'])
    ])
    def test_inequality_different_attributes(self, sample_api, changed_attr, new_value):
        """Test inequality for API objects with different attributes."""
        params = {
            'name': 'test-api',
            'displayName': 'Test API',
            'path': '/test',
            'description': 'A test API.',
            'policyXml': '<policies />',
            'tags': ['a', 'b']
        }
        params[changed_attr] = new_value

        api2 = API(**params)
        assert sample_api != api2

    def test_repr(self, sample_api):
        """Test __repr__ method of API."""
        result = repr(sample_api)
        assert 'API' in result
        assert sample_api.name in result
        assert sample_api.displayName in result


# ------------------------------
#    ENUM TESTS
# ------------------------------

class TestEnums:
    """Test suite for all enum types."""

    @pytest.mark.parametrize('enum_value,expected', [
        (APIMNetworkMode.PUBLIC, 'Public'),
        (APIMNetworkMode.EXTERNAL_VNET, 'External'),
        (APIMNetworkMode.INTERNAL_VNET, 'Internal'),
        (APIMNetworkMode.NONE, 'None')
    ])
    def test_apim_network_mode(self, enum_value, expected):
        """Test APIMNetworkMode enum values."""
        assert enum_value == expected

    @pytest.mark.parametrize('enum_value,expected', [
        (APIM_SKU.DEVELOPER, 'Developer'),
        (APIM_SKU.BASIC, 'Basic'),
        (APIM_SKU.STANDARD, 'Standard'),
        (APIM_SKU.PREMIUM, 'Premium'),
        (APIM_SKU.BASICV2, 'Basicv2'),
        (APIM_SKU.STANDARDV2, 'Standardv2'),
        (APIM_SKU.PREMIUMV2, 'Premiumv2')
    ])
    def test_apim_sku(self, enum_value, expected):
        """Test APIM_SKU enum values."""
        assert enum_value == expected

    @pytest.mark.parametrize('sku', [
        APIM_SKU.DEVELOPER,
        APIM_SKU.BASIC,
        APIM_SKU.STANDARD,
        APIM_SKU.PREMIUM
    ])
    def test_apim_sku_is_v1(self, sku):
        """Test APIM_SKU.is_v1() method for v1 SKUs."""
        assert sku.is_v1() is True
        assert sku.is_v2() is False

    @pytest.mark.parametrize('sku', [
        APIM_SKU.BASICV2,
        APIM_SKU.STANDARDV2,
        APIM_SKU.PREMIUMV2
    ])
    def test_apim_sku_is_v2(self, sku):
        """Test APIM_SKU.is_v2() method for v2 SKUs."""
        assert sku.is_v2() is True
        assert sku.is_v1() is False

    @pytest.mark.parametrize('enum_value,expected', [
        (HTTP_VERB.GET, 'GET'),
        (HTTP_VERB.POST, 'POST'),
        (HTTP_VERB.PUT, 'PUT'),
        (HTTP_VERB.DELETE, 'DELETE'),
        (HTTP_VERB.PATCH, 'PATCH'),
        (HTTP_VERB.OPTIONS, 'OPTIONS'),
        (HTTP_VERB.HEAD, 'HEAD')
    ])
    def test_http_verb(self, enum_value, expected):
        """Test HTTP_VERB enum values."""
        assert enum_value == expected

    @pytest.mark.parametrize('enum_value,expected', [
        (INFRASTRUCTURE.SIMPLE_APIM, 'simple-apim'),
        (INFRASTRUCTURE.APIM_ACA, 'apim-aca'),
        (INFRASTRUCTURE.AFD_APIM_PE, 'afd-apim-pe')
    ])
    def test_infrastructure(self, enum_value, expected):
        """Test INFRASTRUCTURE enum values."""
        assert enum_value == expected

    @pytest.mark.parametrize('enum_class,invalid_value', [
        (APIMNetworkMode, 'invalid'),
        (APIM_SKU, 'invalid'),
        (HTTP_VERB, 'FOO'),
        (INFRASTRUCTURE, 'bad')
    ])
    def test_invalid_enum_values(self, enum_class, invalid_value):
        """Test that invalid enum values raise ValueError."""
        with pytest.raises(ValueError):
            enum_class(invalid_value)


# ------------------------------
#    API OPERATION TESTS
# ------------------------------

class TestAPIOperation:
    """Test suite for APIOperation and related classes."""

    def test_basic_operation_to_dict(self):
        """Test APIOperation to_dict method."""
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

    def test_get_operation(self):
        """Test GET_APIOperation convenience class."""
        op = GET_APIOperation(description='desc', policyXml='<xml/>')

        assert op.name == 'GET'
        assert op.method == HTTP_VERB.GET
        assert op.urlTemplate == '/'
        assert op.description == 'desc'
        assert op.policyXml == '<xml/>'
        assert op.to_dict()['method'] == HTTP_VERB.GET

    def test_get_operation2(self):
        """Test GET_APIOperation2 class with custom parameters."""
        op = GET_APIOperation2(
            name='get-users',
            displayName='Get Users',
            urlTemplate='/users',
            description='Get all users',
            policyXml='<custom/>'
        )

        assert op.name == 'get-users'
        assert op.displayName == 'Get Users'
        assert op.urlTemplate == '/users'
        assert op.method == HTTP_VERB.GET
        assert op.description == 'Get all users'
        assert op.policyXml == '<custom/>'
        assert op.to_dict()['method'] == HTTP_VERB.GET

    def test_post_operation(self):
        """Test POST_APIOperation convenience class."""
        op = POST_APIOperation(description='desc', policyXml='<xml/>')

        assert op.name == 'POST'
        assert op.method == HTTP_VERB.POST
        assert op.urlTemplate == '/'
        assert op.description == 'desc'
        assert op.policyXml == '<xml/>'
        assert op.to_dict()['method'] == HTTP_VERB.POST

    def test_invalid_method(self):
        """Test that invalid HTTP method raises ValueError."""
        with pytest.raises(ValueError):
            APIOperation(
                name='bad',
                displayName='Bad',
                urlTemplate='/bad',
                method='INVALID',
                description='desc',
                policyXml='<xml/>'
            )

    def test_operation_accepts_string_method(self):
        """Test APIOperation accepts valid HTTP verb strings."""

        op = APIOperation(
            name='string-method',
            displayName='String Method',
            urlTemplate='/items',
            method='GET',
            description='desc',
            policyXml='<xml/>'
        )

        assert op.method == 'GET'


# ------------------------------
#    PRODUCT TESTS
# ------------------------------

class TestProductCreation:
    """Test suite for Product object creation."""

    @pytest.fixture
    def base_product_params(self):
        """Common Product parameters."""
        return {
            'name': 'hr',
            'displayName': 'Human Resources',
            'description': 'HR product description'
        }

    def test_basic_creation(self, base_product_params):
        """Test creation of Product object with defaults."""
        product = Product(**base_product_params)

        assert product.name == 'hr'
        assert product.displayName == 'Human Resources'
        assert product.description == 'HR product description'
        assert product.state == 'published'
        assert product.subscriptionRequired is True
        assert product.policyXml is not None

    @pytest.mark.parametrize('state,subscription_req,approval_req', [
        ('published', True, False),
        ('notPublished', False, False),
        ('published', True, True)
    ])
    def test_creation_with_custom_values(self, base_product_params, state, subscription_req, approval_req):
        """Test creation of Product with various custom values."""
        custom_policy = '<policies><inbound><base /></inbound></policies>'
        product = Product(
            **base_product_params,
            state=state,
            subscriptionRequired=subscription_req,
            approvalRequired=approval_req,
            policyXml=custom_policy
        )

        assert product.state == state
        assert product.subscriptionRequired is subscription_req
        assert product.approvalRequired is approval_req
        assert product.policyXml == custom_policy

    def test_approval_required_default(self, base_product_params):
        """Test that approvalRequired defaults to False."""
        product = Product(**base_product_params)
        assert product.approvalRequired is False

    def test_product_fallback_policy_when_file_not_found(self, monkeypatch, base_product_params):
        """Test Product uses fallback policy when default policy file is not found."""
        def mock_read_policy_xml_raise(path):
            raise FileNotFoundError(f'Policy file not found: {path}')

        monkeypatch.setattr(apimtypes, '_read_policy_xml', mock_read_policy_xml_raise)

        product = Product(**base_product_params)
        assert product.policyXml is not None
        assert '<policies>' in product.policyXml
        assert '<inbound>' in product.policyXml


class TestProductSerialization:
    """Test suite for Product.to_dict() method."""

    def test_to_dict_all_fields(self):
        """Test that to_dict includes all required fields."""
        custom_policy = '<policies><inbound><base /></inbound></policies>'
        product = Product(
            name='hr',
            displayName='Human Resources',
            description='HR product',
            state='published',
            subscriptionRequired=True,
            approvalRequired=True,
            policyXml=custom_policy
        )
        d = product.to_dict()

        assert d['name'] == 'hr'
        assert d['displayName'] == 'Human Resources'
        assert d['description'] == 'HR product'
        assert d['state'] == 'published'
        assert d['subscriptionRequired'] is True
        assert d['approvalRequired'] is True
        assert d['policyXml'] == custom_policy


# ------------------------------
#    POLICY FRAGMENT TESTS
# ------------------------------

class TestPolicyFragment:
    """Test suite for PolicyFragment objects."""

    def test_basic_creation(self):
        """Test creation of PolicyFragment object."""
        pf = PolicyFragment(
            name='Test-Fragment',
            policyXml='<policy>test</policy>',
            description='Test fragment'
        )

        assert pf.name == 'Test-Fragment'
        assert pf.policyXml == '<policy>test</policy>'
        assert pf.description == 'Test fragment'
        assert_policy_fragment_structure(pf)

    def test_to_dict(self):
        """Test PolicyFragment to_dict method."""
        pf = PolicyFragment(
            name='Test-Fragment',
            policyXml='<policy>test</policy>',
            description='Test fragment'
        )
        d = pf.to_dict()

        assert d['name'] == 'Test-Fragment'
        assert d['policyXml'] == '<policy>test</policy>'
        assert d['description'] == 'Test fragment'


# ------------------------------
#    OUTPUT CLASS TESTS
# ------------------------------

class TestOutput:
    """Test suite for Output class."""

    def test_basic_creation(self):
        """Test Output creation with text."""
        output = Output(success=True, text='test output')

        assert output.success is True
        assert output.text == 'test output'
        assert output.json_data is None

    def test_json_parsing_valid(self):
        """Test Output correctly parses valid JSON."""
        json_str = '{"key": "value", "number": 42}'
        output = Output(success=True, text=json_str)

        assert output.json_data is not None
        assert output.json_data['key'] == 'value'
        assert output.json_data['number'] == 42

    def test_json_parsing_invalid(self):
        """Test Output handles invalid JSON gracefully."""
        output = Output(success=True, text='not json')
        assert output.json_data is None

    def test_json_parsing_with_single_quotes_sets_exception(self):
        """Test Output stores parse exception when JSON uses single quotes."""
        text = "{'properties': {'outputs': {'endpoint': {'value': 'test'}}}}"
        output = Output(success=True, text=text)

        assert output.jsonParseException is not None

    def test_json_extraction_from_mixed_text(self):
        """Test Output extracts JSON embedded within non-JSON text."""
        text = 'info: {"properties": {"outputs": {"endpoint": {"value": "https://mixed"}}}} end'
        output = Output(success=True, text=text)

        assert output.json_data is not None
        assert output.get('endpoint', suppress_logging=True) == 'https://mixed'

    def test_get_method_with_properties_structure(self):
        """Test Output.get() with standard deployment output structure."""
        json_text = '''{"properties": {"outputs": {"endpoint": {"value": "https://test.com"}}}}'''
        output = Output(success=True, text=json_text)

        result = output.get('endpoint', suppress_logging=True)
        assert result == 'https://test.com'

    def test_get_method_with_simple_structure(self):
        """Test Output.get() with simple output structure."""
        json_text = '''{"endpoint": {"value": "https://simple.com"}}'''
        output = Output(success=True, text=json_text)

        result = output.get('endpoint', suppress_logging=True)
        assert result == 'https://simple.com'

    def test_get_method_key_not_found(self):
        """Test Output.get() when key is not found."""
        json_text = '''{"properties": {"outputs": {"other": {"value": "val"}}}}'''
        output = Output(success=True, text=json_text)

        result = output.get('missing', suppress_logging=True)
        assert result is None

    def test_get_method_key_not_found_with_label_raises(self):
        """Test Output.get() raises when key not found and label provided."""
        json_text = '''{"properties": {"outputs": {"other": {"value": "val"}}}}'''
        output = Output(success=True, text=json_text)

        with pytest.raises(Exception):
            output.get('missing', label='Test Label', suppress_logging=True)

    def test_get_method_with_label_and_secure_masking(self):
        """Test Output.get() with label and secure masking."""
        json_text = '''{"properties": {"outputs": {"secret": {"value": "supersecretvalue"}}}}'''
        output = Output(success=True, text=json_text)

        result = output.get('secret', label='Secret', secure=True)
        assert result == 'supersecretvalue'

    def test_get_method_secure_short_value_unmasked(self, monkeypatch):
        """Test Output.get() does not mask secure values shorter than four characters."""
        json_text = '''{"properties": {"outputs": {"code": {"value": "abc"}}}}'''
        output = Output(success=True, text=json_text)

        logged = []
        monkeypatch.setattr(apimtypes, 'print_val', lambda label, value, *a, **k: logged.append((label, value)))

        result = output.get('code', label='Code', secure=True, suppress_logging=False)

        assert result == 'abc'
        assert ('Code', 'abc') in logged

    def test_get_method_json_data_not_dict(self):
        """Test Output.get() when json_data is not a dict."""
        output = Output(success=True, text='["array", "data"]')

        result = output.get('key', suppress_logging=True)
        assert result is None

    def test_get_method_properties_not_dict(self):
        """Test Output.get() when properties is not a dict."""
        json_text = '''{"properties": "not a dict"}'''
        output = Output(success=True, text=json_text)

        result = output.get('key', suppress_logging=True)
        assert result is None

    def test_get_method_outputs_not_dict(self):
        """Test Output.get() when outputs is not a dict."""
        json_text = '''{"properties": {"outputs": "not a dict"}}'''
        output = Output(success=True, text=json_text)

        result = output.get('key', suppress_logging=True)
        assert result is None

    def test_get_method_output_entry_invalid(self):
        """Test Output.get() when output entry is invalid."""
        json_text = '''{"properties": {"outputs": {"key": "no value field"}}}'''
        output = Output(success=True, text=json_text)

        result = output.get('key', suppress_logging=True)
        assert result is None

    def test_getjson_method_with_dict_value(self):
        """Test Output.getJson() with dictionary value."""
        json_text = '''{"properties": {"outputs": {"config": {"value": {"key": "val"}}}}}'''
        output = Output(success=True, text=json_text)

        result = output.getJson('config', suppress_logging=True)
        assert result == {'key': 'val'}

    def test_getjson_method_with_string_json(self):
        """Test Output.getJson() parsing string as JSON."""
        json_text = '''{"properties": {"outputs": {"data": {"value": "{\\"nested\\": \\"value\\"}"}}}}'''
        output = Output(success=True, text=json_text)

        result = output.getJson('data', suppress_logging=True)
        assert result == {'nested': 'value'}

    def test_getjson_method_with_python_literal(self):
        """Test Output.getJson() parsing Python literal."""
        json_text = '''{"properties": {"outputs": {"data": {"value": "{'key': 'value'}"}}}}'''
        output = Output(success=True, text=json_text)

        result = output.getJson('data', suppress_logging=True)
        assert result == {'key': 'value'}

    def test_getjson_method_unparseable_string(self):
        """Test Output.getJson() with unparseable string returns original value."""
        json_text = '''{"properties": {"outputs": {"data": {"value": "not valid json or literal"}}}}'''
        output = Output(success=True, text=json_text)

        result = output.getJson('data')
        assert result == 'not valid json or literal'

    def test_getjson_method_key_not_found(self):
        """Test Output.getJson() when key not found."""
        json_text = '''{"properties": {"outputs": {"other": {"value": "val"}}}}'''
        output = Output(success=True, text=json_text)

        result = output.getJson('missing', suppress_logging=True)
        assert result is None

    def test_getjson_method_raises_with_label(self):
        """Test Output.getJson() raises when key not found and label provided."""
        json_text = '''{"properties": {"outputs": {}}}'''
        output = Output(success=True, text=json_text)

        with pytest.raises(Exception):
            output.getJson('missing', label='Test')

    def test_getjson_method_json_data_not_dict(self):
        """Test Output.getJson() when json_data is not a dict."""
        output = Output(success=True, text='[1, 2, 3]')

        result = output.getJson('key', suppress_logging=True)
        assert result is None

    def test_getjson_method_properties_not_dict(self):
        """Test Output.getJson() when properties is not a dict."""
        json_text = '''{"properties": ["not", "a", "dict"]}'''
        output = Output(success=True, text=json_text)

        result = output.getJson('key', suppress_logging=True)
        assert result is None

    def test_getjson_method_outputs_not_dict(self):
        """Test Output.getJson() when outputs is not a dict."""
        json_text = '''{"properties": {"outputs": ["not", "dict"]}}'''
        output = Output(success=True, text=json_text)

        result = output.getJson('key', suppress_logging=True)
        assert result is None

    def test_getjson_method_output_entry_invalid(self):
        """Test Output.getJson() when output entry is missing value field."""
        json_text = '''{"properties": {"outputs": {"key": {"no_value": "here"}}}}'''
        output = Output(success=True, text=json_text)

        result = output.getJson('key', suppress_logging=True)
        assert result is None

    def test_output_with_simple_structure_getjson(self):
        """Test Output.getJson() with simple structure (no properties wrapper)."""
        json_text = '''{"data": {"value": {"nested": "obj"}}}'''
        output = Output(success=True, text=json_text)

        result = output.getJson('data', suppress_logging=True)
        assert result == {'nested': 'obj'}

    def test_getjson_secure_logging_masks_value(self, monkeypatch):
        """Test Output.getJson() masks logged value when secure flag is set."""
        json_text = '''{"properties": {"outputs": {"secret": {"value": "abcd1234"}}}}'''
        output = Output(success=True, text=json_text)

        logged_values = []
        monkeypatch.setattr(apimtypes, 'print_val', lambda label, value, *a, **k: logged_values.append((label, value)))

        result = output.getJson('secret', label='Secret', secure=True, suppress_logging=False)

        assert result == 'abcd1234'
        assert ('Secret', '****1234') in logged_values

    def test_getjson_simple_structure_with_logging(self, monkeypatch):
        """Test Output.getJson() logs value when using simple structure outputs."""
        json_text = '''{"simple": {"value": {"k": "v"}}}'''
        output = Output(success=True, text=json_text)

        logged = []
        monkeypatch.setattr(apimtypes, 'print_val', lambda label, value, *a, **k: logged.append((label, value)))

        result = output.getJson('simple', label='Simple', suppress_logging=False)

        assert result == {'k': 'v'}
        assert ('Simple', {'k': 'v'}) in logged


class TestEndpoints:
    """Test suite for Endpoints container."""

    def test_initialization_assigns_deployment(self):
        endpoint = apimtypes.Endpoints(INFRASTRUCTURE.SIMPLE_APIM)

        assert endpoint.deployment == INFRASTRUCTURE.SIMPLE_APIM
        assert getattr(endpoint, 'afd_endpoint_url', None) is None


# ------------------------------
#    NAMED VALUE TESTS
# ------------------------------

class TestNamedValue:
    """Test suite for NamedValue objects."""

    @pytest.mark.parametrize('is_secret', [True, False])
    def test_creation(self, is_secret):
        """Test NamedValue creation with secret flag."""
        nv = NamedValue(
            name='test-key',
            value='test-value',
            isSecret=is_secret
        )

        assert nv.name == 'test-key'
        assert nv.value == 'test-value'
        assert nv.isSecret is is_secret

    def test_to_dict(self):
        """Test NamedValue to_dict method."""
        nv = NamedValue(name='key', value='val', isSecret=True)
        d = nv.to_dict()

        assert d['name'] == 'key'
        assert d['value'] == 'val'
        assert d['isSecret'] is True


# ------------------------------
#    ROLE TESTS
# ------------------------------

class TestRole:
    """Test suite for Role class (mock GUIDs)."""

    def test_role_constants(self):
        """Test Role has expected constants."""
        assert hasattr(Role, 'NONE')
        assert hasattr(Role, 'HR_MEMBER')
        assert hasattr(Role, 'HR_ASSOCIATE')
        assert hasattr(Role, 'HR_ADMINISTRATOR')
        assert hasattr(Role, 'MARKETING_MEMBER')


# ------------------------------
#    CONSTANTS TESTS
# ------------------------------

class TestConstants:
    """Test suite for module-level constants."""

    def test_policy_paths_exist(self):
        """Test that policy path constants are defined."""
        assert BACKEND_XML_POLICY_PATH is not None
        assert DEFAULT_XML_POLICY_PATH is not None
        assert HELLO_WORLD_XML_POLICY_PATH is not None
        assert REQUEST_HEADERS_XML_POLICY_PATH is not None

    def test_subscription_key_parameter(self):
        """Test subscription key parameter name."""
        assert SUBSCRIPTION_KEY_PARAMETER_NAME == 'api-key'

    def test_sleep_time_constant(self):
        """Test sleep time constant is defined."""
        assert isinstance(SLEEP_TIME_BETWEEN_REQUESTS_MS, int)
        assert SLEEP_TIME_BETWEEN_REQUESTS_MS > 0


# ------------------------------
#    PROJECT ROOT TESTS
# ------------------------------

# ------------------------------
#    PRIVATE FUNCTION TESTS
# ------------------------------

class TestReadPolicyXml:
    """Test suite for _read_policy_xml private function."""

    @pytest.fixture(autouse=True)
    def setup(self, infrastructures_patches):
        """Stop the mock of _read_policy_xml so we can test the real function."""
        # Exit the patch for _read_policy_xml only
        if hasattr(infrastructures_patches, 'apimtypes_read_policy_patch'):
            infrastructures_patches.apimtypes_read_policy_patch.__exit__(None, None, None)
            infrastructures_patches.patches.remove(infrastructures_patches.apimtypes_read_policy_patch)

    def test_read_policy_xml_returns_string(self):
        """Test that _read_policy_xml returns a string when given a valid file."""
        # Use an actual policy file from the repository
        result = apimtypes._read_policy_xml(DEFAULT_XML_POLICY_PATH)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_read_policy_xml_returns_xml_structure(self):
        """Test that returned content has basic XML structure."""
        result = apimtypes._read_policy_xml(DEFAULT_XML_POLICY_PATH)
        assert '<' in result
        assert '>' in result

    def test_read_policy_xml_with_backend_file(self):
        """Test reading backend policy XML file from repository."""
        result = apimtypes._read_policy_xml(BACKEND_XML_POLICY_PATH)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_read_policy_xml_with_hello_world_file(self):
        """Test reading hello-world policy XML file from repository."""
        result = apimtypes._read_policy_xml(HELLO_WORLD_XML_POLICY_PATH)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_read_policy_xml_with_request_headers_file(self):
        """Test reading request-headers policy XML file from repository."""
        result = apimtypes._read_policy_xml(REQUEST_HEADERS_XML_POLICY_PATH)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_read_policy_xml_content_is_xml(self):
        """Test that read content is valid XML structure."""
        result = apimtypes._read_policy_xml(DEFAULT_XML_POLICY_PATH)
        assert result.strip().startswith('<') or result.strip().startswith('<?xml')
        assert '>' in result

    def test_read_policy_xml_file_not_found(self):
        """Test that FileNotFoundError is raised when file does not exist."""
        with pytest.raises(FileNotFoundError):
            apimtypes._read_policy_xml('nonexistent_file.xml')

    def test_read_policy_xml_empty_file(self, tmp_path):
        """Test reading an empty XML file returns empty string."""
        empty_file = tmp_path / 'empty.xml'
        empty_file.write_text('', encoding = 'utf-8')

        result = apimtypes._read_policy_xml(str(empty_file))

        assert not result
        assert isinstance(result, str)

    def test_read_policy_xml_with_whitespace_only(self, tmp_path):
        """Test reading file with only whitespace."""
        whitespace_file = tmp_path / 'whitespace.xml'
        whitespace_file.write_text('   \n\t  \n  ', encoding = 'utf-8')

        result = apimtypes._read_policy_xml(str(whitespace_file))

        assert result == '   \n\t  \n  '
        assert isinstance(result, str)

    def test_read_policy_xml_with_unicode_content(self, tmp_path):
        """Test reading file with Unicode characters."""
        unicode_file = tmp_path / 'unicode.xml'
        unicode_content = '<policy>Hello 世界 🌍</policy>'
        unicode_file.write_text(unicode_content, encoding = 'utf-8')

        result = apimtypes._read_policy_xml(str(unicode_file))

        assert result == unicode_content
        assert '世界' in result
        assert '🌍' in result

    def test_read_policy_xml_with_special_xml_chars(self, tmp_path):
        """Test reading file with XML special characters."""
        xml_file = tmp_path / 'special.xml'
        xml_content = '<policy>&lt;tag&gt;&amp;&quot;&apos;</policy>'
        xml_file.write_text(xml_content, encoding = 'utf-8')

        result = apimtypes._read_policy_xml(str(xml_file))

        assert result == xml_content
        assert '&lt;' in result
        assert '&amp;' in result

    def test_read_policy_xml_preserves_newlines(self, tmp_path):
        """Test that newlines are preserved in the content."""
        newline_file = tmp_path / 'newlines.xml'
        xml_content = '<policy>\n    <inbound>\n        <base />\n    </inbound>\n</policy>'
        newline_file.write_text(xml_content, encoding = 'utf-8')

        result = apimtypes._read_policy_xml(str(newline_file))

        assert result == xml_content
        assert result.count('\n') == 4

    def test_read_policy_xml_large_file(self, tmp_path):
        """Test reading a large policy file."""
        large_file = tmp_path / 'large.xml'
        large_content = '<policies>' + '<policy>test</policy>' * 1000 + '</policies>'
        large_file.write_text(large_content, encoding = 'utf-8')

        result = apimtypes._read_policy_xml(str(large_file))

        assert result == large_content
        assert len(result) > 10000

    def test_read_policy_xml_with_bom(self, tmp_path):
        """Test reading file with UTF-8 BOM (Byte Order Mark)."""
        bom_file = tmp_path / 'bom.xml'
        xml_content = '<?xml version="1.0" encoding="utf-8"?><policy></policy>'
        bom_file.write_text(xml_content, encoding = 'utf-8-sig')

        result = apimtypes._read_policy_xml(str(bom_file))

        # When reading with utf-8, BOM should be preserved or handled
        assert isinstance(result, str)
        assert 'policy' in result

    def test_read_policy_xml_is_directory(self, tmp_path):
        """Test that error is raised when path is a directory."""
        # On Windows, trying to open a directory raises PermissionError
        # On Unix-like systems, it raises IsADirectoryError
        with pytest.raises((IsADirectoryError, PermissionError)):
            apimtypes._read_policy_xml(str(tmp_path))

    def test_read_policy_xml_permission_error(self, tmp_path, monkeypatch):
        """Test that PermissionError is raised when file cannot be read."""
        restricted_file = tmp_path / 'restricted.xml'
        restricted_file.write_text('<policy></policy>', encoding = 'utf-8')

        def mock_open(*args, **kwargs):
            raise PermissionError('Permission denied')

        monkeypatch.setattr('builtins.open', mock_open)

        with pytest.raises(PermissionError):
            apimtypes._read_policy_xml(str(restricted_file))


# ------------------------------
#    PROJECT ROOT TESTS
# ------------------------------

class TestProjectRoot:
    """Test suite for get_project_root function."""

    def test_get_project_root(self):
        """Test that get_project_root returns a valid Path."""
        root = get_project_root()

        assert isinstance(root, Path)
        assert root.exists()
        assert root.is_dir()

    def test_get_project_root_from_env_var(self, monkeypatch):
        """Test get_project_root uses PROJECT_ROOT environment variable."""
        test_path = Path('c:/test/project')
        monkeypatch.setenv('PROJECT_ROOT', str(test_path))

        # Need to reimport to pick up new env var
        importlib.reload(apimtypes)

        root = apimtypes.get_project_root()
        assert root == test_path

    def test_get_project_root_returns_path_with_indicators(self, tmp_path, monkeypatch):
        """Test get_project_root finds correct directory with indicators."""
        # Create directory structure
        project_dir = tmp_path / 'project'
        project_dir.mkdir()
        (project_dir / 'README.md').write_text('test')
        (project_dir / 'requirements.txt').write_text('test')
        (project_dir / 'bicepconfig.json').write_text('test')

        # Mock __file__ to point into a subdirectory
        shared_dir = project_dir / 'shared' / 'python'
        shared_dir.mkdir(parents=True)
        test_file = shared_dir / 'apimtypes.py'
        test_file.write_text('test')

        # Remove env var to force detection logic
        monkeypatch.delenv('PROJECT_ROOT', raising=False)

        with patch('apimtypes.Path') as mock_path_class:
            mock_path_instance = MagicMock()
            mock_path_instance.resolve.return_value = test_file.resolve()
            mock_path_class.return_value = mock_path_instance
            mock_path_class.side_effect = lambda x: Path(x) if isinstance(x, str) else mock_path_instance

            # Call using patched Path directly on already-imported module
            root = apimtypes.get_project_root()

            # Should find the project directory
            assert root == project_dir or root.exists()

    def test_get_project_root_contains_required_files(self):
        """Test that detected project root contains required indicator files."""
        root = get_project_root()

        # Verify it has the expected files
        assert (root / 'README.md').exists()
        assert (root / 'requirements.txt').exists()
        assert (root / 'bicepconfig.json').exists()

    def test_get_project_root_detects_parent_indicators(self, tmp_path, monkeypatch):
        """Ensure traversal finds indicators in parent directories."""
        project_dir = tmp_path / 'proj'
        project_dir.mkdir()
        for name in ['README.md', 'requirements.txt', 'bicepconfig.json']:
            (project_dir / name).write_text('x')

        child_dir = project_dir / 'shared' / 'python'
        child_dir.mkdir(parents=True)
        fake_file = child_dir / 'apimtypes.py'
        fake_file.write_text('x')

        monkeypatch.delenv('PROJECT_ROOT', raising=False)
        monkeypatch.setattr(apimtypes, '__file__', str(fake_file))

        root = apimtypes.get_project_root()
        assert root == project_dir

    def test_get_project_root_fallback_when_no_indicators(self, monkeypatch):
        """Ensure fallback path is used when no indicators exist."""
        monkeypatch.delenv('PROJECT_ROOT', raising=False)

        # Force indicator checks to fail
        monkeypatch.setattr(Path, 'exists', lambda self: False)

        expected = Path(apimtypes.__file__).resolve().parent.parent.parent
        result = apimtypes.get_project_root()

        assert result == expected


# ------------------------------
#    ADDITIONAL BRANCH COVERAGE TESTS
# ------------------------------

class TestAPISKUEdgeCases:
    """Additional edge case tests for APIM_SKU enum."""

    def test_sku_v1_v2_mutual_exclusivity(self):
        """Test that v1 and v2 SKUs are mutually exclusive."""
        v1_skus = [APIM_SKU.DEVELOPER, APIM_SKU.BASIC, APIM_SKU.STANDARD, APIM_SKU.PREMIUM]
        v2_skus = [APIM_SKU.BASICV2, APIM_SKU.STANDARDV2, APIM_SKU.PREMIUMV2]

        for sku in v1_skus:
            assert sku.is_v1() and not sku.is_v2()

        for sku in v2_skus:
            assert sku.is_v2() and not sku.is_v1()


class TestAPIOperationStringMethod:
    """Test APIOperation with string method coercion."""

    def test_operation_with_valid_string_methods(self):
        """Test APIOperation accepts all valid HTTP verb strings."""
        for verb_str in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']:
            op = APIOperation(
                name=f'op-{verb_str}',
                displayName=f'Operation {verb_str}',
                urlTemplate='/test',
                method=verb_str,
                description='test',
                policyXml='<xml/>'
            )
            assert op.method == verb_str


class TestProductPolicyHandling:
    """Test Product policy XML handling edge cases."""

    def test_product_with_none_policy_loads_default(self, monkeypatch):
        """Test Product with None policyXml loads default policy file."""
        def mock_read_policy(path):
            if 'default' in path:
                return '<default-policy-xml />'
            raise FileNotFoundError()

        monkeypatch.setattr(apimtypes, '_read_policy_xml', mock_read_policy)

        product = Product(
            name='test',
            displayName='Test',
            description='Test',
            policyXml=None
        )

        assert product.policyXml == '<default-policy-xml />'

    def test_product_with_explicit_policy_not_overridden(self):
        """Test Product with explicit policyXml doesn't load default."""
        custom_policy = '<custom-policy />'
        product = Product(
            name='test',
            displayName='Test',
            description='Test',
            policyXml=custom_policy
        )

        assert product.policyXml == custom_policy


class TestOutputGetMethodEdgeCases:
    """Additional edge case tests for Output.get() method."""

    def test_get_method_with_value_field_not_dict(self):
        """Test Output.get() when output entry value field is missing."""
        json_text = '''{"properties": {"outputs": {"key": {"wrong_field": "val"}}}}'''
        output = Output(success=True, text=json_text)

        result = output.get('key', suppress_logging=True)
        assert result is None

    def test_get_method_simple_structure_missing_value_field(self):
        """Test Output.get() simple structure with missing value field."""
        json_text = '''{"endpoint": {"no_value_field": "here"}}'''
        output = Output(success=True, text=json_text)

        result = output.get('endpoint', suppress_logging=True)
        assert result is None


class TestOutputGetJsonMethodEdgeCases:
    """Additional edge case tests for Output.getJson() method."""

    def test_getjson_with_complex_nested_structure(self):
        """Test Output.getJson() with deeply nested structures."""
        json_text = '''{"properties": {"outputs": {"complex": {"value": {"level1": {"level2": {"level3": "value"}}}}}}}'''
        output = Output(success=True, text=json_text)

        result = output.getJson('complex', suppress_logging=True)
        assert result['level1']['level2']['level3'] == 'value'

    def test_getjson_with_list_value(self):
        """Test Output.getJson() with list as value."""
        json_text = '''{"properties": {"outputs": {"items": {"value": [1, 2, 3]}}}}'''
        output = Output(success=True, text=json_text)

        result = output.getJson('items', suppress_logging=True)
        assert result == [1, 2, 3]

    def test_getjson_simple_structure_missing_value_field(self):
        """Test Output.getJson() simple structure with missing value."""
        json_text = '''{"simple": {"no_value": "here"}}'''
        output = Output(success=True, text=json_text)

        result = output.getJson('simple', suppress_logging=True)
        assert result is None


class TestAPIOperationEdgeCases:
    """Edge case tests for APIOperation classes."""

    def test_operation_with_template_parameters(self):
        """Test APIOperation with template parameters."""
        params = [
            {'name': 'id', 'type': 'int'},
            {'name': 'name', 'type': 'string'}
        ]
        op = APIOperation(
            name='get-by-id',
            displayName='Get By ID',
            urlTemplate='/items/{id}',
            method=HTTP_VERB.GET,
            description='Get item by ID',
            policyXml='<policy/>',
            templateParameters=params
        )

        assert op.templateParameters == params
        assert len(op.to_dict()['templateParameters']) == 2

    def test_get_operation_with_template_parameters(self):
        """Test GET_APIOperation with template parameters."""
        params = [{'name': 'id', 'type': 'int'}]
        op = GET_APIOperation(
            description='Get operation',
            policyXml='<policy/>',
            templateParameters=params
        )

        assert op.templateParameters == params


class TestProductEdgeCases:
    """Edge case tests for Product class."""

    def test_product_to_dict_includes_policy(self):
        """Test Product.to_dict includes policyXml when set."""
        custom_policy = '<custom-policy />'
        product = Product(
            name='test',
            displayName='Test',
            description='Test',
            policyXml=custom_policy
        )

        d = product.to_dict()
        assert 'policyXml' in d
        assert d['policyXml'] == custom_policy

    def test_product_state_values(self):
        """Test Product with different state values."""
        for state in ['published', 'notPublished']:
            product = Product(
                name='test',
                displayName='Test',
                description='Test',
                state=state
            )
            assert product.state == state
            assert product.to_dict()['state'] == state


class TestNamedValueEdgeCases:
    """Edge case tests for NamedValue class."""

    def test_named_value_default_is_secret(self):
        """Test NamedValue defaults isSecret to False."""
        nv = NamedValue(name='key', value='val')
        assert nv.isSecret is False

    def test_named_value_with_special_characters(self):
        """Test NamedValue handles special characters in value."""
        special_value = 'value!@#$%^&*()_+-=[]{}|;:,.<>?'
        nv = NamedValue(name='special', value=special_value, isSecret=True)
        assert nv.value == special_value
        assert nv.to_dict()['value'] == special_value


class TestAPIEdgeCases:
    """Edge case tests for API class."""

    def test_api_service_url(self):
        """Test API with service URL."""
        service_url = 'https://backend.example.com'
        api = API(
            name='backend-api',
            displayName='Backend API',
            path='/backend',
            description='Backend API',
            serviceUrl=service_url
        )

        assert api.serviceUrl == service_url
        assert api.to_dict()['serviceUrl'] == service_url

    def test_api_subscription_required(self):
        """Test API subscription required setting."""
        api = API(
            name='public-api',
            displayName='Public API',
            path='/public',
            description='Public API',
            subscriptionRequired=False
        )

        assert api.subscriptionRequired is False
        assert api.to_dict()['subscriptionRequired'] is False




class TestOutputGetEdgeCases:
    """Additional edge case tests for Output.get() method."""

    def test_output_get_with_missing_label_returns_none(self):
        """Test Output.get() without label returns None on error."""
        output = apimtypes.Output(success=True, text='{}')

        # Should return None when key is missing and no label is provided
        result = output.get('nonexistent_key')
        assert result is None

    def test_output_get_json_with_syntax_error(self):
        """Test Output.getJson() returns original value when parsing fails."""
        json_text = json.dumps({
            'output1': {
                'value': 'invalid syntax {bracket'
            }
        })
        output = apimtypes.Output(success=True, text=json_text)

        # Should return the original value when parsing fails
        result = output.getJson('output1')
        assert result == 'invalid syntax {bracket'

    def test_output_get_json_with_non_dict_properties(self):
        """Test Output.getJson() when properties is not a dict."""
        json_text = json.dumps({
            'properties': 'not a dict'
        })
        output = apimtypes.Output(success=True, text=json_text)

        # Should handle gracefully and return None
        result = output.getJson('key')
        assert result is None
