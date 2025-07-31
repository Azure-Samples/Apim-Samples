import pytest
import requests
from unittest.mock import patch, MagicMock
from apimrequests import ApimRequests
from apimtypes import SUBSCRIPTION_KEY_PARAMETER_NAME

# Sample values for tests
default_url = 'https://example.com/apim/'
default_key = 'test-key'
default_path = '/test'
default_headers = {'Custom-Header': 'Value'}
default_data = {'foo': 'bar'}

@pytest.fixture
def apim():
    return ApimRequests(default_url, default_key)


@pytest.mark.unit
def test_init_sets_headers():
    """Test that headers are set correctly when subscription key is provided."""
    apim = ApimRequests(default_url, default_key)
    assert apim.url == default_url
    assert apim.apimSubscriptionKey == default_key
    assert apim.headers[SUBSCRIPTION_KEY_PARAMETER_NAME] == default_key


@pytest.mark.unit
def test_init_no_key():
    """Test that headers are set correctly when no subscription key is provided."""
    apim = ApimRequests(default_url)
    assert apim.url == default_url
    assert apim.apimSubscriptionKey is None
    assert 'Ocp-Apim-Subscription-Key' not in apim.headers
    assert apim.headers['Accept'] == 'application/json'

@pytest.mark.http
@patch('apimrequests.requests.request')
@patch('apimrequests.utils.print_message')
@patch('apimrequests.utils.print_info')
@patch('apimrequests.utils.print_error')
def test_single_get_success(mock_print_error, mock_print_info, mock_print_message, mock_request, apim):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {'Content-Type': 'application/json'}
    mock_response.json.return_value = {'result': 'ok'}
    mock_response.text = '{'result': 'ok'}'
    mock_response.raise_for_status.return_value = None
    mock_request.return_value = mock_response

    with patch.object(apim, '_print_response') as mock_print_response:
        result = apim.singleGet(default_path, printResponse=True)
        assert result == '{\n    'result': 'ok'\n}'
        mock_print_response.assert_called_once_with(mock_response)
        mock_print_error.assert_not_called()

@pytest.mark.http
@patch('apimrequests.requests.request')
@patch('apimrequests.utils.print_message')
@patch('apimrequests.utils.print_info')
@patch('apimrequests.utils.print_error')
def test_single_get_error(mock_print_error, mock_print_info, mock_print_message, mock_request, apim):
    mock_request.side_effect = requests.exceptions.RequestException('fail')
    result = apim.singleGet(default_path, printResponse=True)
    assert result is None
    mock_print_error.assert_called_once()

@pytest.mark.http
@patch('apimrequests.requests.request')
@patch('apimrequests.utils.print_message')
@patch('apimrequests.utils.print_info')
@patch('apimrequests.utils.print_error')
def test_single_post_success(mock_print_error, mock_print_info, mock_print_message, mock_request, apim):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.headers = {'Content-Type': 'application/json'}
    mock_response.json.return_value = {'created': True}
    mock_response.text = '{'created': true}'
    mock_response.raise_for_status.return_value = None
    mock_request.return_value = mock_response

    with patch.object(apim, '_print_response') as mock_print_response:
        result = apim.singlePost(default_path, data=default_data, printResponse=True)
        assert result == '{\n    'created': true\n}'
        mock_print_response.assert_called_once_with(mock_response)
        mock_print_error.assert_not_called()

@pytest.mark.http
@patch('apimrequests.requests.Session')
@patch('apimrequests.utils.print_message')
@patch('apimrequests.utils.print_info')
def test_multi_get_success(mock_print_info, mock_print_message, mock_session, apim):
    mock_sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {'Content-Type': 'application/json'}
    mock_response.json.return_value = {'result': 'ok'}
    mock_response.text = '{'result': 'ok'}'
    mock_response.raise_for_status.return_value = None
    mock_sess.request.return_value = mock_response
    mock_session.return_value = mock_sess

    with patch.object(apim, '_print_response_code') as mock_print_code:
        result = apim.multiGet(default_path, runs=2, printResponse=True)
        assert len(result) == 2
        for run in result:
            assert run['status_code'] == 200
            assert run['response'] == '{\n    'result': 'ok'\n}'
        assert mock_sess.request.call_count == 2
        mock_print_code.assert_called()

@pytest.mark.http
@patch('apimrequests.requests.Session')
@patch('apimrequests.utils.print_message')
@patch('apimrequests.utils.print_info')
def test_multi_get_error(mock_print_info, mock_print_message, mock_session, apim):
    mock_sess = MagicMock()
    mock_sess.request.side_effect = requests.exceptions.RequestException('fail')
    mock_session.return_value = mock_sess
    with patch.object(apim, '_print_response_code'):
        # Should raise inside the loop and propagate the exception, ensuring the session is closed
        with pytest.raises(requests.exceptions.RequestException):
            apim.multiGet(default_path, runs=1, printResponse=True)


# Sample values for tests
url = 'https://example.com/apim/'
key = 'test-key'
path = '/test'

def make_apim():
    return ApimRequests(url, key)

@pytest.mark.http
def test_single_post_error():
    apim = make_apim()
    with patch('apimrequests.requests.request') as mock_request, \
         patch('apimrequests.utils.print_error') as mock_print_error:
        import requests
        mock_request.side_effect = requests.RequestException('fail')
        result = apim.singlePost(path, data={'foo': 'bar'}, printResponse=True)
        assert result is None
        mock_print_error.assert_called()

@pytest.mark.http
def test_multi_get_non_json():
    apim = make_apim()
    with patch('apimrequests.requests.Session') as mock_session:
        mock_sess = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'text/plain'}
        mock_response.text = 'not json'
        mock_response.raise_for_status.return_value = None
        mock_sess.request.return_value = mock_response
        mock_session.return_value = mock_sess
        with patch.object(apim, '_print_response_code'):
            result = apim.multiGet(path, runs=1, printResponse=True)
            assert result[0]['response'] == 'not json'

@pytest.mark.http
def test_request_header_merging():
    apim = make_apim()
    with patch('apimrequests.requests.request') as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.json.return_value = {'ok': True}
        mock_response.text = '{'ok': true}'
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        # Custom header should override default
        custom_headers = {'Accept': 'application/xml', 'X-Test': '1'}
        with patch.object(apim, '_print_response'):
            apim.singleGet(path, headers=custom_headers, printResponse=True)
            called_headers = mock_request.call_args[1]['headers']
            assert called_headers['Accept'] == 'application/xml'
            assert called_headers['X-Test'] == '1'

@pytest.mark.http
def test_init_missing_url():
    # Negative: missing URL should raise TypeError
    with pytest.raises(TypeError):
        ApimRequests()

@pytest.mark.http
def test_print_response_code_edge():
    apim = make_apim()
    class DummyResponse:
        status_code = 302
        reason = 'Found'
    with patch('apimrequests.utils.print_val') as mock_print_val:
        apim._print_response_code(DummyResponse())
        mock_print_val.assert_called_with('Response status', '302')

# ------------------------------
#    HEADERS PROPERTY
# ------------------------------

def test_headers_property_allows_external_modification():
    apim = ApimRequests(default_url, default_key)
    apim.headers['X-Test'] = 'value'
    assert apim.headers['X-Test'] == 'value'

def test_headers_property_is_dict_reference():
    apim = ApimRequests(default_url, default_key)
    h = apim.headers
    h['X-Ref'] = 'ref'
    assert apim.headers['X-Ref'] == 'ref'

# ------------------------------
#    ADDITIONAL COVERAGE TESTS FOR APIMREQUESTS
# ------------------------------

@pytest.mark.unit
@patch('apimrequests.requests.request')
def test_request_with_custom_headers(mock_request, apim):
    """Test request with custom headers merged with default headers."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'result': 'ok'}
    mock_response.raise_for_status.return_value = None
    mock_request.return_value = mock_response
    
    custom_headers = {'Custom': 'value'}
    result = apim.singleGet(default_path, headers=custom_headers)
    
    # Verify custom headers were merged with default headers
    call_kwargs = mock_request.call_args[1]
    assert 'Custom' in call_kwargs['headers']
    assert SUBSCRIPTION_KEY_PARAMETER_NAME in call_kwargs['headers']

@pytest.mark.unit
@patch('apimrequests.requests.request')
def test_request_timeout_error(mock_request, apim):
    """Test request with timeout error."""
    mock_request.side_effect = requests.exceptions.Timeout()
    
    result = apim.singleGet(default_path)
    
    assert result is None

@pytest.mark.unit
@patch('apimrequests.requests.request')
def test_request_connection_error(mock_request, apim):
    """Test request with connection error."""
    mock_request.side_effect = requests.exceptions.ConnectionError()
    
    result = apim.singleGet(default_path)
    
    assert result is None

@pytest.mark.unit
@patch('apimrequests.requests.request')
def test_request_http_error(mock_request, apim):
    """Test request with HTTP error response."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.reason = 'Not Found'
    mock_response.headers = {'Content-Type': 'text/plain'}
    mock_response.text = 'Resource not found'
    mock_request.return_value = mock_response

    result = apim.singleGet(default_path)

    # The method returns the response body even for error status codes
    assert result == 'Resource not found'

@pytest.mark.unit
@patch('apimrequests.requests.request')
def test_request_non_json_response(mock_request, apim):
    """Test request with non-JSON response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {'Content-Type': 'text/plain'}
    mock_response.json.side_effect = ValueError('Not JSON')
    mock_response.text = 'Plain text response'
    mock_request.return_value = mock_response

    result = apim.singleGet(default_path)

    # Should return text response when JSON parsing fails
    assert result == 'Plain text response'

@pytest.mark.unit
@patch('apimrequests.requests.request')
def test_request_with_data(mock_request, apim):
    """Test POST request with data."""
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.headers = {'Content-Type': 'application/json'}
    mock_response.json.return_value = {'created': True}
    mock_response.text = '{'created': true}'
    mock_request.return_value = mock_response

    data = {'name': 'test', 'value': 'data'}
    result = apim.singlePost(default_path, data=data)

    # Verify data was passed correctly
    call_kwargs = mock_request.call_args[1]
    assert call_kwargs['json'] == data
    # The method returns JSON-formatted string for application/json content
    assert result == '{\n    'created': true\n}'

@pytest.mark.unit
def test_apim_requests_without_subscription_key():
    """Test ApimRequests initialization without subscription key."""
    apim = ApimRequests(default_url)
    
    assert apim.url == default_url
    assert apim.apimSubscriptionKey is None
    assert SUBSCRIPTION_KEY_PARAMETER_NAME not in apim.headers
    assert apim.headers['Accept'] == 'application/json'