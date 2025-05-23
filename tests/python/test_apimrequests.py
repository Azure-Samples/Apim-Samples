import pytest
import requests
from unittest.mock import patch, MagicMock
from shared.python.apimrequests import ApimRequests
from shared.python.apimtypes import HTTP_VERB, SUBSCRIPTION_KEY_PARAMETER_NAME

# Sample values for tests
default_url = "https://example.com/apim/"
default_key = "test-key"
default_path = "/test"
default_headers = {"Custom-Header": "Value"}
default_data = {"foo": "bar"}

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
    assert apim.headers["Accept"] == "application/json"


@pytest.mark.unit
def test_init_no_key():
    """Test that headers are set correctly when no subscription key is provided."""
    apim = ApimRequests(default_url)
    assert apim.url == default_url
    assert apim.apimSubscriptionKey is None
    assert "Ocp-Apim-Subscription-Key" not in apim.headers
    assert apim.headers["Accept"] == "application/json"

@pytest.mark.http
@patch("shared.python.apimrequests.requests.request")
@patch("shared.python.apimrequests.utils.print_message")
@patch("shared.python.apimrequests.utils.print_info")
@patch("shared.python.apimrequests.utils.print_error")
def test_single_get_success(mock_print_error, mock_print_info, mock_print_message, mock_request, apim):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {"result": "ok"}
    mock_response.text = '{"result": "ok"}'
    mock_response.raise_for_status.return_value = None
    mock_request.return_value = mock_response

    with patch.object(apim, "_print_response") as mock_print_response:
        result = apim.singleGet(default_path, printResponse=True)
        assert result == '{\n    "result": "ok"\n}'
        mock_print_response.assert_called_once_with(mock_response)
        mock_print_error.assert_not_called()

@pytest.mark.http
@patch("shared.python.apimrequests.requests.request")
@patch("shared.python.apimrequests.utils.print_message")
@patch("shared.python.apimrequests.utils.print_info")
@patch("shared.python.apimrequests.utils.print_error")
def test_single_get_error(mock_print_error, mock_print_info, mock_print_message, mock_request, apim):
    mock_request.side_effect = requests.exceptions.RequestException("fail")
    result = apim.singleGet(default_path, printResponse=True)
    assert result is None
    mock_print_error.assert_called_once()

@pytest.mark.http
@patch("shared.python.apimrequests.requests.request")
@patch("shared.python.apimrequests.utils.print_message")
@patch("shared.python.apimrequests.utils.print_info")
@patch("shared.python.apimrequests.utils.print_error")
def test_single_post_success(mock_print_error, mock_print_info, mock_print_message, mock_request, apim):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {"created": True}
    mock_response.text = '{"created": true}'
    mock_response.raise_for_status.return_value = None
    mock_request.return_value = mock_response

    with patch.object(apim, "_print_response") as mock_print_response:
        result = apim.singlePost(default_path, data=default_data, printResponse=True)
        assert result == '{\n    "created": true\n}'
        mock_print_response.assert_called_once_with(mock_response)
        mock_print_error.assert_not_called()

@pytest.mark.http
@patch("shared.python.apimrequests.requests.Session")
@patch("shared.python.apimrequests.utils.print_message")
@patch("shared.python.apimrequests.utils.print_info")
def test_multi_get_success(mock_print_info, mock_print_message, mock_session, apim):
    mock_sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {"result": "ok"}
    mock_response.text = '{"result": "ok"}'
    mock_response.raise_for_status.return_value = None
    mock_sess.request.return_value = mock_response
    mock_session.return_value = mock_sess

    with patch.object(apim, "_print_response_code") as mock_print_code:
        result = apim.multiGet(default_path, runs=2, printResponse=True)
        assert len(result) == 2
        for run in result:
            assert run["status_code"] == 200
            assert run["response"] == '{\n    "result": "ok"\n}'
        assert mock_sess.request.call_count == 2
        mock_print_code.assert_called()

@pytest.mark.http
@patch("shared.python.apimrequests.requests.Session")
@patch("shared.python.apimrequests.utils.print_message")
@patch("shared.python.apimrequests.utils.print_info")
def test_multi_get_error(mock_print_info, mock_print_message, mock_session, apim):
    mock_sess = MagicMock()
    mock_sess.request.side_effect = requests.exceptions.RequestException("fail")
    mock_session.return_value = mock_sess
    with patch.object(apim, "_print_response_code"):
        # Should raise inside the loop and propagate the exception, ensuring the session is closed
        with pytest.raises(requests.exceptions.RequestException):
            apim.multiGet(default_path, runs=1, printResponse=True)
