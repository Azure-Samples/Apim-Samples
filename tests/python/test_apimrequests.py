from unittest.mock import patch, MagicMock
import requests
import pytest

# APIM Samples imports
from apimrequests import ApimRequests
from apimtypes import SUBSCRIPTION_KEY_PARAMETER_NAME, HTTP_VERB, SLEEP_TIME_BETWEEN_REQUESTS_MS
from test_helpers import create_mock_http_response, create_mock_session_with_response

# Sample values for tests
DEFAULT_URL = 'https://example.com/apim/'
DEFAULT_KEY = 'test-KEY'
DEFAULT_PATH = '/test'
DEFAULT_HEADERS = {'Custom-Header': 'Value'}
DEFAULT_DATA = {'foo': 'bar'}

@pytest.fixture
def apim():
    return ApimRequests(DEFAULT_URL, DEFAULT_KEY)


@pytest.mark.unit
def test_init_sets_headers():
    """Test that headers are set correctly when subscription KEY is provided."""
    apim = ApimRequests(DEFAULT_URL, DEFAULT_KEY)
    assert apim._url == DEFAULT_URL
    assert apim.subscriptionKey == DEFAULT_KEY
    assert apim.headers[SUBSCRIPTION_KEY_PARAMETER_NAME] == DEFAULT_KEY


@pytest.mark.unit
def test_init_no_key():
    """Test that headers are set correctly when no subscription KEY is provided."""
    apim = ApimRequests(DEFAULT_URL)
    assert apim._url == DEFAULT_URL
    assert apim.subscriptionKey is None
    assert 'Ocp-Apim-Subscription-Key' not in apim.headers
    assert apim.headers['Accept'] == 'application/json'

@pytest.mark.http
def test_single_get_success(apim, apimrequests_patches, mock_http_response_200):
    apimrequests_patches.request.return_value = mock_http_response_200

    with patch.object(apim, '_print_response') as mock_print_response:
        result = apim.singleGet(DEFAULT_PATH, printResponse=True)

    assert result == '{\n    "result": "ok"\n}'
    mock_print_response.assert_called_once_with(mock_http_response_200)
    apimrequests_patches.print_error.assert_not_called()

@pytest.mark.http
def test_single_get_error(apim, apimrequests_patches):
    apimrequests_patches.request.side_effect = requests.exceptions.RequestException('fail')
    result = apim.singleGet(DEFAULT_PATH, printResponse=True)
    assert result is None
    apimrequests_patches.print_error.assert_called_once()

@pytest.mark.http
def test_single_post_success(apim, apimrequests_patches):
    response = create_mock_http_response(
        status_code=201,
        json_data={'created': True}
    )
    apimrequests_patches.request.return_value = response

    with patch.object(apim, '_print_response') as mock_print_response:
        result = apim.singlePost(DEFAULT_PATH, data=DEFAULT_DATA, printResponse=True)

    assert result == '{\n    "created": true\n}'
    mock_print_response.assert_called_once_with(response)
    apimrequests_patches.print_error.assert_not_called()

@pytest.mark.http
def test_multi_get_success(apim, apimrequests_patches, mock_http_response_200):
    with patch('apimrequests.requests.Session') as session_cls:
        session = create_mock_session_with_response(mock_http_response_200)
        session_cls.return_value = session

        with patch.object(apim, '_print_response_code') as mock_print_code:
            result = apim.multiGet(DEFAULT_PATH, runs=2, printResponse=True)

    assert len(result) == 2
    for run in result:
        assert run['status_code'] == 200
        assert run['response'] == '{\n    "result": "ok"\n}'
    assert session.request.call_count == 2
    mock_print_code.assert_called()

@pytest.mark.http
def test_multi_get_error(apim, apimrequests_patches):
    with patch('apimrequests.requests.Session') as session_cls:
        session = MagicMock()
        session.request.side_effect = requests.exceptions.RequestException('fail')
        session_cls.return_value = session

        with patch.object(apim, '_print_response_code'):
            with pytest.raises(requests.exceptions.RequestException):
                apim.multiGet(DEFAULT_PATH, runs=1, printResponse=True)


# Sample values for tests
URL = 'https://example.com/apim/'
KEY = 'test-KEY'
PATH = '/test'

def make_apim():
    return ApimRequests(URL, KEY)

@pytest.mark.http
def test_single_post_error():
    apim = make_apim()
    with patch('apimrequests.requests.request') as mock_request, \
         patch('apimrequests.print_error') as mock_print_error:
        mock_request.side_effect = requests.RequestException('fail')
        result = apim.singlePost(PATH, data={'foo': 'bar'}, printResponse=True)
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
            result = apim.multiGet(PATH, runs=1, printResponse=True)
            assert result[0]['response'] == 'not json'

@pytest.mark.http
def test_request_header_merging():
    apim = make_apim()
    with patch('apimrequests.requests.request') as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.json.return_value = {'ok': True}
        mock_response.text = '{"ok": true}'
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        # Custom header should override default
        custom_headers = {'Accept': 'application/xml', 'X-Test': '1'}
        with patch.object(apim, '_print_response'):
            apim.singleGet(PATH, headers=custom_headers, printResponse=True)
            called_headers = mock_request.call_args[1]['headers']
            assert called_headers['Accept'] == 'application/xml'
            assert called_headers['X-Test'] == '1'

@pytest.mark.http
def test_init_missing_url():
    # Negative: missing URL should raise TypeError
    with pytest.raises(TypeError):
        ApimRequests()  # pylint: disable=no-value-for-parameter

@pytest.mark.http
def test_print_response_code_edge():
    apim = make_apim()
    class DummyResponse:
        status_code = 302
        reason = 'Found'
    with patch('apimrequests.print_val') as mock_print_val:
        apim._print_response_code(DummyResponse())
        mock_print_val.assert_called_with('Response status', '302')

# ------------------------------
#    HEADERS PROPERTY
# ------------------------------

def test_headers_property_allows_external_modification():
    apim = ApimRequests(DEFAULT_URL, DEFAULT_KEY)
    apim.headers['X-Test'] = 'value'
    assert apim.headers['X-Test'] == 'value'

def test_headers_property_is_dict_reference():
    apim = ApimRequests(DEFAULT_URL, DEFAULT_KEY)
    h = apim.headers
    h['X-Ref'] = 'ref'
    assert apim.headers['X-Ref'] == 'ref'


def test_subscription_key_setter_updates_and_clears_header():
    apim = ApimRequests(DEFAULT_URL, DEFAULT_KEY)

    apim.subscriptionKey = 'new-key'
    assert apim.headers[SUBSCRIPTION_KEY_PARAMETER_NAME] == 'new-key'

    apim.subscriptionKey = None
    assert SUBSCRIPTION_KEY_PARAMETER_NAME not in apim.headers

# ------------------------------
#    ADDITIONAL COVERAGE TESTS FOR APIMREQUESTS
# ------------------------------

@pytest.mark.unit
def test_request_with_custom_headers(apim, apimrequests_patches):
    """Test request with custom headers merged with default headers."""
    apimrequests_patches.request.return_value = create_mock_http_response(
        status_code=200,
        json_data={'result': 'ok'}
    )

    custom_headers = {'Custom': 'value'}
    apim.singleGet(DEFAULT_PATH, headers=custom_headers)

    # Verify custom headers were merged with default headers
    call_kwargs = apimrequests_patches.request.call_args[1]
    assert 'Custom' in call_kwargs['headers']
    assert SUBSCRIPTION_KEY_PARAMETER_NAME in call_kwargs['headers']

@pytest.mark.unit
def test_request_timeout_error(apim, apimrequests_patches):
    """Test request with timeout error."""
    apimrequests_patches.request.side_effect = requests.exceptions.Timeout()

    result = apim.singleGet(DEFAULT_PATH)

    assert result is None

@pytest.mark.unit
def test_request_connection_error(apim, apimrequests_patches):
    """Test request with connection error."""
    apimrequests_patches.request.side_effect = requests.exceptions.ConnectionError()

    result = apim.singleGet(DEFAULT_PATH)

    assert result is None

@pytest.mark.unit
def test_request_http_error(apim, apimrequests_patches):
    """Test request with HTTP error response."""
    response = create_mock_http_response(
        status_code=404,
        headers={'Content-Type': 'text/plain'},
        text='Resource not found'
    )
    apimrequests_patches.request.return_value = response

    result = apim.singleGet(DEFAULT_PATH)

    # The method returns the response body even for error status codes
    assert result == 'Resource not found'

@pytest.mark.unit
def test_request_non_json_response(apim, apimrequests_patches):
    """Test request with non-JSON response."""
    response = create_mock_http_response(
        status_code=200,
        headers={'Content-Type': 'text/plain'},
        text='Plain text response'
    )
    response.json.side_effect = ValueError('Not JSON')
    apimrequests_patches.request.return_value = response

    result = apim.singleGet(DEFAULT_PATH)

    # Should return text response when JSON parsing fails
    assert result == 'Plain text response'

@pytest.mark.unit
def test_request_with_data(apim, apimrequests_patches):
    """Test POST request with data."""
    apimrequests_patches.request.return_value = create_mock_http_response(
        status_code=201,
        json_data={'created': True}
    )

    data = {'name': 'test', 'value': 'data'}
    result = apim.singlePost(DEFAULT_PATH, data=data)

    # Verify data was passed correctly
    call_kwargs = apimrequests_patches.request.call_args[1]
    assert call_kwargs['json'] == data
    # The method returns JSON-formatted string for application/json content
    assert result == '{\n    "created": true\n}'

@pytest.mark.unit
def test_apim_requests_without_subscription_key():
    """Test ApimRequests initialization without subscription KEY."""
    apim = ApimRequests(DEFAULT_URL)

    assert apim._url == DEFAULT_URL
    assert apim.subscriptionKey is None
    assert SUBSCRIPTION_KEY_PARAMETER_NAME not in apim.headers
    assert apim.headers['Accept'] == 'application/json'


@pytest.mark.unit
def test_headers_setter(apim):
    """Test the headers setter property."""
    new_headers = {'Authorization': 'Bearer token', 'Custom': 'value'}
    apim.headers = new_headers
    assert apim.headers == new_headers


@pytest.mark.unit
def test_request_with_message(apim, apimrequests_patches):
    """Test _request method with message parameter."""
    apimrequests_patches.request.return_value = create_mock_http_response(
        status_code=200,
        json_data={'result': 'ok'}
    )

    with patch.object(apim, '_print_response'):
        apim._request(HTTP_VERB.GET, '/test', msg='Test message')

    apimrequests_patches.print_message.assert_called_once_with('Test message', blank_above=True)


@pytest.mark.unit
def test_request_path_without_leading_slash(apim, apimrequests_patches):
    """Test _request method with PATH without leading slash."""
    apimrequests_patches.request.return_value = create_mock_http_response(
        status_code=200,
        json_data={'result': 'ok'}
    )

    with patch.object(apim, '_print_response'):
        apim._request(HTTP_VERB.GET, 'test')

    # Should call with the corrected URL
    expected_url = DEFAULT_URL + '/test'
    apimrequests_patches.request.assert_called_once()
    args, _kwargs = apimrequests_patches.request.call_args
    assert args[1] == expected_url

@pytest.mark.unit
def test_multi_request_with_message(apim, apimrequests_patches):
    """Test _multiRequest supports optional message output."""
    response = create_mock_http_response(json_data={'result': 'ok'})
    with patch('apimrequests.requests.Session') as mock_session_cls:
        mock_session = create_mock_session_with_response(response)
        mock_session_cls.return_value = mock_session

        with patch.object(apim, '_print_response_code'):
            result = apim._multiRequest(HTTP_VERB.GET, '/test', 1, msg='Multi-request message')

    apimrequests_patches.print_message.assert_called_once_with('Multi-request message', blank_above=True)
    assert len(result) == 1


@pytest.mark.unit
def test_multi_request_path_without_leading_slash(apim, apimrequests_patches):
    """Test _multiRequest method with PATH without leading slash."""
    response = create_mock_http_response(json_data={'result': 'ok'})
    with patch('apimrequests.requests.Session') as mock_session_cls:
        mock_session = create_mock_session_with_response(response)
        mock_session_cls.return_value = mock_session

        with patch.object(apim, '_print_response_code'):
            apim._multiRequest(HTTP_VERB.GET, 'test', 1)

    # Should call with the corrected URL
    expected_url = DEFAULT_URL + '/test'
    mock_session.request.assert_called_once()
    args, _kwargs = mock_session.request.call_args
    assert args[1] == expected_url


@pytest.mark.unit
def test_multi_request_non_json_response(apim):
    """Test _multiRequest method with non-JSON response."""
    response = create_mock_http_response(
        status_code=200,
        headers={'Content-Type': 'text/plain'},
        text='Plain text response'
    )

    with patch('apimrequests.requests.Session') as mock_session_cls:
        mock_session = create_mock_session_with_response(response)
        mock_session_cls.return_value = mock_session

        with patch.object(apim, '_print_response_code'):
            result = apim._multiRequest(HTTP_VERB.GET, '/test', 1)

    assert len(result) == 1
    assert result[0]['response'] == 'Plain text response'


@pytest.mark.unit
def test_multi_request_sleep_zero(apim):
    """Test _multiRequest respects sleepMs=0 without sleeping."""
    response = create_mock_http_response(json_data={'ok': True})

    with patch('apimrequests.requests.Session') as mock_session_cls, \
         patch('apimrequests.time.sleep') as mock_sleep:
        mock_session = create_mock_session_with_response(response)
        mock_session_cls.return_value = mock_session

        with patch.object(apim, '_print_response_code'):
            result = apim._multiRequest(HTTP_VERB.GET, '/sleep', 1, sleepMs=0)

    assert result[0]['status_code'] == 200
    mock_sleep.assert_not_called()


@pytest.mark.unit
def test_multi_request_default_sleep_interval(apim):
    """Test _multiRequest uses default sleep interval when sleepMs is None."""

    response = create_mock_http_response(json_data={'ok': True})

    with patch('apimrequests.requests.Session') as mock_session_cls, \
         patch('apimrequests.time.sleep') as mock_sleep:
        mock_session = create_mock_session_with_response(response)
        mock_session_cls.return_value = mock_session

        with patch.object(apim, '_print_response_code'):
            apim._multiRequest(HTTP_VERB.GET, '/sleep-default', runs=2, sleepMs=None)

    mock_sleep.assert_called_once_with(SLEEP_TIME_BETWEEN_REQUESTS_MS / 1000)


@pytest.mark.unit
def test_multi_request_sleep_positive(apim):
    """Test _multiRequest sleeps when sleepMs is positive."""
    response = create_mock_http_response(json_data={'ok': True})

    with patch('apimrequests.requests.Session') as mock_session_cls, \
         patch('apimrequests.time.sleep') as mock_sleep:
        mock_session = create_mock_session_with_response(response)
        mock_session_cls.return_value = mock_session

        with patch.object(apim, '_print_response_code'):
            result = apim._multiRequest(HTTP_VERB.GET, '/sleep', 2, sleepMs=150)

    # Verify sleep was called between the two requests (only once, not after last run)
    mock_sleep.assert_called_once_with(0.15)
    # Verify we got 2 results
    assert len(result) == 2


@pytest.mark.unit
def test_multi_request_sleep_positive_multiple_runs(apim):
    """Test _multiRequest with sleepMs > 0 and multiple runs verifies sleep behavior."""
    response = create_mock_http_response(json_data={'ok': True})

    with patch('apimrequests.requests.Session') as mock_session_cls, \
         patch('apimrequests.time.sleep') as mock_sleep:
        mock_session = create_mock_session_with_response(response)
        mock_session_cls.return_value = mock_session

        with patch.object(apim, '_print_response_code'):
            result = apim._multiRequest(HTTP_VERB.GET, '/test', runs=3, sleepMs=250)

    # With 3 runs, sleep should be called 2 times (between runs, not after the last)
    assert mock_sleep.call_count == 2
    # Each call should be with the correct sleep duration
    mock_sleep.assert_called_with(0.25)
    assert len(result) == 3
    # Verify responses are in order
    for i, run in enumerate(result):
        assert run['run'] == i + 1


@pytest.mark.unit
def test_print_response_non_200_status(apim, apimrequests_patches):
    """Test _print_response method with non-200 status code."""
    mock_response = create_mock_http_response(
        status_code=404,
        headers={'Content-Type': 'application/json'},
        text='{"error": "not found"}'
    )
    mock_response.reason = 'Not Found'

    with patch.object(apim, '_print_response_code'):
        apim._print_response(mock_response)

    # Should print response body directly for non-200 status
    apimrequests_patches.print_val.assert_any_call('Response body', '{"error": "not found"}', True)


@pytest.mark.unit
def test_print_response_200_invalid_json(apim, apimrequests_patches):
    """Test _print_response handles invalid JSON body for 200 responses."""
    mock_response = create_mock_http_response(
        status_code=200,
        headers={'Content-Type': 'application/json'},
        text='not valid json'
    )
    mock_response.reason = 'OK'

    with patch.object(apim, '_print_response_code'):
        apim._print_response(mock_response)

    apimrequests_patches.print_val.assert_any_call('Response body', 'not valid json', True)


@pytest.mark.unit
def test_print_response_200_valid_json(apim, apimrequests_patches):
    """Test _print_response prints formatted JSON when parse succeeds."""
    mock_response = create_mock_http_response(
        status_code=200,
        json_data={'alpha': 1}
    )
    mock_response.reason = 'OK'

    with patch.object(apim, '_print_response_code'):
        apim._print_response(mock_response)

    apimrequests_patches.print_val.assert_any_call('Response body', '{\n    "alpha": 1\n}', True)


@pytest.mark.unit
def test_print_response_code_success_and_error(apim, apimrequests_patches):
    """Test _print_response_code color formatting for success and error codes."""
    class DummyResponse:
        status_code = 200
        reason = 'OK'

    apim._print_response_code(DummyResponse())

    class ErrorResponse:
        status_code = 500
        reason = 'Server Error'

    apim._print_response_code(ErrorResponse())

    messages = [record.args[1] for record in apimrequests_patches.print_val.call_args_list]

    assert any('200 - OK' in msg for msg in messages)
    assert any('500 - Server Error' in msg for msg in messages)


@pytest.mark.unit
def test_poll_async_operation_success(apim, apimrequests_patches):
    """Test _poll_async_operation method with successful completion."""
    mock_response = create_mock_http_response(status_code=200)
    with patch('apimrequests.requests.get', return_value=mock_response):
        with patch('apimrequests.time.sleep'):
            result = apim._poll_async_operation('http://example.com/operation/123')

    assert result == mock_response
    apimrequests_patches.print_ok.assert_called_once_with('Async operation completed successfully!')


@pytest.mark.unit
def test_poll_async_operation_in_progress_then_success(apim, apimrequests_patches):
    """Test _poll_async_operation method with in-progress then success."""
    # First call returns 202 (in progress), second call returns 200 (complete)
    responses = [
        MagicMock(status_code=202),
        MagicMock(status_code=200)
    ]
    with patch('apimrequests.requests.get', side_effect=responses) as mock_get, \
         patch('apimrequests.time.sleep') as mock_sleep:
        result = apim._poll_async_operation('http://example.com/operation/123', poll_interval=1)

    assert result == responses[1]  # Should return the final success response
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(1)


@pytest.mark.unit
def test_poll_async_operation_unexpected_status(apim, apimrequests_patches):
    """Test _poll_async_operation method with unexpected status code."""
    mock_response = MagicMock(status_code=500)
    with patch('apimrequests.requests.get', return_value=mock_response):
        result = apim._poll_async_operation('http://example.com/operation/123')

    assert result == mock_response  # Should return the error response
    apimrequests_patches.print_error.assert_called_with('Unexpected status code during polling: 500')


@pytest.mark.unit
def test_poll_async_operation_request_exception(apim, apimrequests_patches):
    """Test _poll_async_operation method with request exception."""
    with patch('apimrequests.requests.get', side_effect=requests.exceptions.RequestException('Connection error')):
        result = apim._poll_async_operation('http://example.com/operation/123')

    assert result is None
    apimrequests_patches.print_error.assert_called_with('Error polling operation: Connection error')


@pytest.mark.unit
def test_poll_async_operation_timeout(apim, apimrequests_patches):
    """Test _poll_async_operation method with timeout."""
    # Mock time to simulate timeout.
    # Note: patching `time.time` affects the shared `time` module, which is also
    # used by the stdlib logging module. Make this mock tolerant of extra calls.
    times = [0, 30, 61]  # start, first check, timeout check

    def time_side_effect():
        if len(times) > 1:
            return times.pop(0)
        return times[0]

    mock_response = MagicMock(status_code=202)

    with patch('apimrequests.requests.get', return_value=mock_response), \
         patch('apimrequests.time.sleep'), \
         patch('apimrequests.time.time', side_effect=time_side_effect):
        result = apim._poll_async_operation('http://example.com/operation/123', timeout=60)

    assert result is None
    apimrequests_patches.print_error.assert_called_with('Async operation timeout reached after 60 seconds')


@pytest.mark.unit
def test_single_post_async_success_with_location(apim, apimrequests_patches):
    """Test singlePostAsync method with successful async operation."""
    # Mock initial 202 response with Location header
    initial_response = MagicMock()
    initial_response.status_code = 202
    initial_response.headers = {'Location': 'http://example.com/operation/123'}

    # Mock final 200 response
    final_response = create_mock_http_response(
        status_code=200,
        json_data={'result': 'completed'}
    )

    apimrequests_patches.request.return_value = initial_response

    with patch.object(apim, '_poll_async_operation', return_value=final_response) as mock_poll:
        with patch.object(apim, '_print_response') as mock_print_response:
            result = apim.singlePostAsync('/test', data={'test': 'data'}, msg='Async test')

    apimrequests_patches.print_message.assert_called_once_with('Async test', blank_above=True)
    mock_poll.assert_called_once()
    mock_print_response.assert_called_once_with(final_response)
    assert result == '{\n    "result": "completed"\n}'


@pytest.mark.unit
def test_single_post_async_no_location_header(apim, apimrequests_patches):
    """Test singlePostAsync method with 202 response but no Location header."""
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.headers = {}  # No Location header
    apimrequests_patches.request.return_value = mock_response

    with patch.object(apim, '_print_response') as mock_print_response:
        result = apim.singlePostAsync('/test')

    apimrequests_patches.print_error.assert_called_once_with('No Location header found in 202 response')
    mock_print_response.assert_called_once_with(mock_response)
    assert result is None


@pytest.mark.unit
def test_single_post_async_non_async_response(apim, apimrequests_patches):
    """Test singlePostAsync method with non-async (immediate) response."""
    mock_response = create_mock_http_response(
        status_code=200,
        json_data={'result': 'immediate'}
    )
    apimrequests_patches.request.return_value = mock_response

    with patch.object(apim, '_print_response') as mock_print_response:
        result = apim.singlePostAsync('/test')

    mock_print_response.assert_called_once_with(mock_response)
    assert result == '{\n    "result": "immediate"\n}'


@pytest.mark.unit
def test_single_post_async_request_exception(apim, apimrequests_patches):
    """Test singlePostAsync method with request exception."""
    apimrequests_patches.request.side_effect = requests.exceptions.RequestException('Connection error')

    result = apim.singlePostAsync('/test')

    assert result is None
    apimrequests_patches.print_error.assert_called_once_with('Error making request: Connection error')


@pytest.mark.unit
def test_single_post_async_failed_polling(apim, apimrequests_patches):
    """Test singlePostAsync method with failed async operation polling."""
    initial_response = MagicMock()
    initial_response.status_code = 202
    initial_response.headers = {'Location': 'http://example.com/operation/123'}
    apimrequests_patches.request.return_value = initial_response

    with patch.object(apim, '_poll_async_operation', return_value=None) as mock_poll:
        result = apim.singlePostAsync('/test')

    mock_poll.assert_called_once()
    apimrequests_patches.print_error.assert_called_once_with('Async operation failed or timed out')
    assert result is None


@pytest.mark.unit
def test_single_post_async_path_without_leading_slash(apim, apimrequests_patches):
    """Test singlePostAsync method with PATH without leading slash."""
    mock_response = create_mock_http_response(
        status_code=200,
        json_data={'result': 'ok'}
    )
    apimrequests_patches.request.return_value = mock_response

    with patch.object(apim, '_print_response'):
        apim.singlePostAsync('test')

    # Should call with the corrected URL
    expected_url = DEFAULT_URL + '/test'
    apimrequests_patches.request.assert_called_once()
    args, _kwargs = apimrequests_patches.request.call_args
    assert args[1] == expected_url


@pytest.mark.unit
def test_single_post_async_non_json_response(apim, apimrequests_patches):
    """Test singlePostAsync method with non-JSON response."""
    mock_response = create_mock_http_response(
        status_code=200,
        headers={'Content-Type': 'text/plain'},
        text='Plain text result'
    )
    apimrequests_patches.request.return_value = mock_response

    with patch.object(apim, '_print_response'):
        result = apim.singlePostAsync('/test')

    assert result == 'Plain text result'


@pytest.mark.unit
def test_print_response_code_2xx_non_200(apim, apimrequests_patches):
    """Test _print_response_code with 2xx status codes other than 200."""
    class DummyResponse:
        status_code = 201
        reason = 'Created'

    apim._print_response_code(DummyResponse())

    # Verify print_val was called with colored output for success
    apimrequests_patches.print_val.assert_called_once()
    call_args = apimrequests_patches.print_val.call_args[0]
    assert 'Response status' in call_args[0]
    assert '201 - Created' in call_args[1]


@pytest.mark.unit
def test_print_response_code_3xx(apim, apimrequests_patches):
    """Test _print_response_code with 3xx redirect status codes."""
    class DummyResponse:
        status_code = 301
        reason = 'Moved Permanently'

    apim._print_response_code(DummyResponse())

    call_args = apimrequests_patches.print_val.call_args[0]
    assert '301' in call_args[1]


@pytest.mark.unit
def test_multi_request_session_exception_on_close(apim):
    """Test _multiRequest handles exception and ensures session is closed."""
    with patch('apimrequests.requests.Session') as mock_session_cls:
        mock_session = MagicMock()
        mock_response = create_mock_http_response(json_data={'ok': True})
        mock_session.request.return_value = mock_response
        mock_session_cls.return_value = mock_session

        with patch.object(apim, '_print_response_code'):
            result = apim._multiRequest(HTTP_VERB.GET, '/test', 1)

    # Verify session was closed even after successful operation
    mock_session.close.assert_called_once()
    assert len(result) == 1


@pytest.mark.unit
def test_single_post_async_with_message(apim, apimrequests_patches):
    """Test singlePostAsync with message parameter."""
    mock_response = create_mock_http_response(
        status_code=200,
        json_data={'result': 'ok'}
    )
    apimrequests_patches.request.return_value = mock_response

    with patch.object(apim, '_print_response'):
        apim.singlePostAsync('/test', msg='Test async message')

    apimrequests_patches.print_message.assert_called_once_with('Test async message', blank_above=True)


@pytest.mark.unit
def test_single_post_async_with_headers(apim, apimrequests_patches):
    """Test singlePostAsync with custom headers."""
    mock_response = create_mock_http_response(
        status_code=200,
        json_data={'result': 'ok'}
    )
    apimrequests_patches.request.return_value = mock_response

    custom_headers = {'X-Custom': 'header-value'}
    with patch.object(apim, '_print_response'):
        apim.singlePostAsync('/test', headers=custom_headers)

    # Verify headers were merged
    call_kwargs = apimrequests_patches.request.call_args[1]
    assert 'X-Custom' in call_kwargs['headers']


@pytest.mark.unit
def test_single_post_async_non_json_final_response(apim, apimrequests_patches):
    """Test singlePostAsync with non-JSON response from polling."""
    initial_response = MagicMock()
    initial_response.status_code = 202
    initial_response.headers = {'Location': 'http://example.com/operation/123'}
    apimrequests_patches.request.return_value = initial_response

    final_response = create_mock_http_response(
        status_code=200,
        headers={'Content-Type': 'text/plain'},
        text='Plain text final result'
    )

    with patch.object(apim, '_poll_async_operation', return_value=final_response):
        with patch.object(apim, '_print_response') as mock_print_response:
            result = apim.singlePostAsync('/test')

    assert result == 'Plain text final result'
    mock_print_response.assert_called_once_with(final_response)


@pytest.mark.unit
def test_poll_async_operation_with_custom_headers(apim, apimrequests_patches):
    """Test _poll_async_operation with custom headers."""
    mock_response = create_mock_http_response(status_code=200)
    custom_headers = {'X-Custom': 'value'}

    with patch('apimrequests.requests.get', return_value=mock_response) as mock_get:
        result = apim._poll_async_operation('http://example.com/op', headers=custom_headers)

    assert result == mock_response
    # Verify custom headers were passed
    call_kwargs = mock_get.call_args[1]
    assert call_kwargs['headers'] == custom_headers


@pytest.mark.unit
def test_request_no_message(apim, apimrequests_patches):
    """Test _request method when no message is provided."""
    apimrequests_patches.request.return_value = create_mock_http_response(
        status_code=200,
        json_data={'result': 'ok'}
    )

    with patch.object(apim, '_print_response'):
        apim._request(HTTP_VERB.GET, '/test')

    # Verify print_message was not called when msg is None
    apimrequests_patches.print_message.assert_not_called()


@pytest.mark.unit
def test_multi_request_no_message(apim, apimrequests_patches):
    """Test _multiRequest method when no message is provided."""
    response = create_mock_http_response(json_data={'result': 'ok'})
    with patch('apimrequests.requests.Session') as mock_session_cls:
        mock_session = create_mock_session_with_response(response)
        mock_session_cls.return_value = mock_session

        with patch.object(apim, '_print_response_code'):
            apim._multiRequest(HTTP_VERB.GET, '/test', 1)

    # Verify print_message was not called when msg is None
    apimrequests_patches.print_message.assert_not_called()


@pytest.mark.unit
def test_single_post_async_no_print_response(apim, apimrequests_patches):
    """Test singlePostAsync with printResponse=False."""
    mock_response = create_mock_http_response(
        status_code=200,
        json_data={'result': 'ok'}
    )
    apimrequests_patches.request.return_value = mock_response

    with patch.object(apim, '_print_response') as mock_print_response:
        result = apim.singlePostAsync('/test', printResponse=False)

    # When printResponse is False, _print_response should not be called
    mock_print_response.assert_not_called()
    assert result == '{\n    "result": "ok"\n}'


@pytest.mark.unit
def test_single_post_async_202_with_location_no_print_response(apim, apimrequests_patches):
    """Test singlePostAsync with 202 response, location header, and printResponse=False."""
    initial_response = MagicMock()
    initial_response.status_code = 202
    initial_response.headers = {'Location': 'http://example.com/operation/123'}
    apimrequests_patches.request.return_value = initial_response

    final_response = create_mock_http_response(
        status_code=200,
        json_data={'result': 'completed'}
    )

    with patch.object(apim, '_poll_async_operation', return_value=final_response) as mock_poll:
        with patch.object(apim, '_print_response') as mock_print_response:
            result = apim.singlePostAsync('/test', data={'test': 'data'}, printResponse=False)

    mock_poll.assert_called_once()
    # When printResponse is False, _print_response should not be called for final response
    mock_print_response.assert_not_called()
    assert result == '{\n    "result": "completed"\n}'


@pytest.mark.unit
def test_single_post_async_202_no_location_no_print_response(apim, apimrequests_patches):
    """Test singlePostAsync with 202 response, no location header, and printResponse=False."""
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.headers = {}  # No Location header
    apimrequests_patches.request.return_value = mock_response

    with patch.object(apim, '_print_response') as mock_print_response:
        result = apim.singlePostAsync('/test', printResponse=False)

    apimrequests_patches.print_error.assert_called_once_with('No Location header found in 202 response')
    # When printResponse is False, _print_response should not be called for initial 202 response
    mock_print_response.assert_not_called()
    assert result is None


@pytest.mark.unit
def test_single_get_no_print_response(apim, apimrequests_patches):
    """Test singleGet with printResponse=False."""
    apimrequests_patches.request.return_value = create_mock_http_response(
        status_code=200,
        json_data={'result': 'ok'}
    )

    with patch.object(apim, '_print_response') as mock_print_response:
        result = apim.singleGet('/test', printResponse=False)

    mock_print_response.assert_not_called()
    assert '{\n    "result": "ok"\n}' in result


@pytest.mark.unit
def test_multi_get_no_print_response(apim):
    """Test multiGet with printResponse=False."""
    response = create_mock_http_response(json_data={'result': 'ok'})
    with patch('apimrequests.requests.Session') as mock_session_cls:
        mock_session = create_mock_session_with_response(response)
        mock_session_cls.return_value = mock_session

        with patch.object(apim, '_print_response_code'):
            result = apim.multiGet('/test', runs=1, printResponse=False)

    assert len(result) == 1
    assert result[0]['response'] == '{\n    "result": "ok"\n}'


@pytest.mark.unit
def test_single_post_async_no_custom_headers(apim, apimrequests_patches):
    """Test singlePostAsync without custom headers (None)."""
    mock_response = create_mock_http_response(
        status_code=200,
        json_data={'result': 'ok'}
    )
    apimrequests_patches.request.return_value = mock_response

    with patch.object(apim, '_print_response'):
        result = apim.singlePostAsync('/test', headers=None)

    assert result == '{\n    "result": "ok"\n}'
    # Verify request was called with merged headers
    call_kwargs = apimrequests_patches.request.call_args[1]
    assert 'headers' in call_kwargs
