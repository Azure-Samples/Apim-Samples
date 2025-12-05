"""
Module for making requests to Azure API Management endpoints with consistent logging and output formatting.
"""

import json
import time
import requests
import urllib3
import utils
from typing import Any
from apimtypes import HTTP_VERB, SUBSCRIPTION_KEY_PARAMETER_NAME, SLEEP_TIME_BETWEEN_REQUESTS_MS

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ------------------------------
#    CLASSES
# ------------------------------

class ApimRequests:
    """
    Methods for making requests to the Azure API Management service.
    Provides single and multiple request helpers with consistent logging.
    """


    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, url: str, apimSubscriptionKey: str | None = None, headers: dict[str, str] | None = None) -> None:
        """
        Initialize the ApimRequests object.

        Args:
            url: The base URL for the APIM endpoint.
            apimSubscriptionKey: Optional subscription key for APIM.
        """

        self._url = url
        self._headers: dict[str, str] = headers
        self.subscriptionKey = apimSubscriptionKey

        self._headers['Accept'] = 'application/json'

    # ------------------------------
    #    PROPERTIES
    # ------------------------------

    # apimSubscriptionKey
    @property
    def subscriptionKey(self) -> str | None:
        """
        Gets the APIM subscription key, if defined.

        Returns:
            str | None: The APIM subscrption key, if defined; otherwise None.
        """
        return self._subscriptionKey

    @subscriptionKey.setter
    def subscriptionKey(self, value: str | None) -> None:
        """
        Sets the APIM subscription key for the request to use.

        Args:
            value: The APIM subscription key to use or None to not use any key for the request
        """

        self._subscriptionKey = value

        if self._subscriptionKey:
            self._headers[SUBSCRIPTION_KEY_PARAMETER_NAME] = self._subscriptionKey

    # headers
    @property
    def headers(self) -> dict[str, str]:
        """
        Get the HTTP headers used for requests.

        Returns:
            dict[str, str]: The headers dictionary.
        """
        return self._headers

    @headers.setter
    def headers(self, value: dict[str, str]) -> None:
        """
        Set the HTTP headers used for requests.

        Args:
            value: The new headers dictionary.
        """
        self._headers = value

    # ------------------------------
    #    PRIVATE METHODS
    # ------------------------------

    def _request(self, method: HTTP_VERB, path: str, headers: list[any] = None, data: any = None, msg: str | None = None, printResponse: bool = True) -> str | None:
        """
        Make a request to the Azure API Management service.

        Args:
            method: The HTTP method to use (e.g., 'GET', 'POST').
            path: The path to append to the base URL for the request.
            headers: Additional headers to include in the request.
            data: Data to include in the request body.
            printResponse: Whether to print the returned output.

        Returns:
            str | None: The JSON response as a string, or None on error.
        """

        try:
            if msg:
                utils.print_message(msg, blank_above = True)

            # Ensure path has a leading slash
            if not path.startswith('/'):
                path = '/' + path

            url = self._url + path
            utils.print_info(f'{method.value} {url}')

            merged_headers = self.headers.copy()

            if headers:
                merged_headers.update(headers)

            response = requests.request(method.value, url, headers = merged_headers, json = data, verify = False)

            content_type = response.headers.get('Content-Type')

            responseBody = None

            if content_type and 'application/json' in content_type:
                responseBody = json.dumps(response.json(), indent = 4)
            else:
                responseBody = response.text

            if printResponse:
                self._print_response(response)

            return responseBody

        except requests.exceptions.RequestException as e:
            utils.print_error(f'Error making request: {e}')
            return None

    def _multiRequest(self, method: HTTP_VERB, path: str, runs: int, headers: list[any] = None, data: any = None, msg: str | None = None, printResponse: bool = True, sleepMs: int | None = None) -> list[dict[str, Any]]:
        """
        Make multiple requests to the Azure API Management service.

        Args:
            method: The HTTP method to use (e.g., 'GET', 'POST').
            path: The path to append to the base URL for the request.
            runs: The number of times to run the request.
            headers: Additional headers to include in the request.
            data: Data to include in the request body.
            printResponse: Whether to print the returned output.
            sleepMs: Optional sleep time between requests in milliseconds (0 to not sleep).

        Returns:
            List of response dicts for each run.
        """

        api_runs = []

        session = requests.Session()
        session.headers.update(self.headers.copy())

        try:
            if msg:
                utils.print_message(msg, blank_above = True)

            # Ensure path has a leading slash
            if not path.startswith('/'):
                path = '/' + path

            url = self._url + path
            utils.print_info(f'{method.value} {url}')

            for i in range(runs):
                utils.print_info(f'▶️ Run {i + 1}/{runs}:')

                start_time = time.time()
                response = session.request(method.value, url, json = data, verify = False)
                response_time = time.time() - start_time
                utils.print_info(f'⌚ {response_time:.2f} seconds')

                self._print_response_code(response)

                content_type = response.headers.get('Content-Type')

                if content_type and 'application/json' in content_type:
                    resp_data = json.dumps(response.json(), indent = 4)
                else:
                    resp_data = response.text

                api_runs.append({
                    'run': i + 1,
                    'response': resp_data,
                    'status_code': response.status_code,
                    'response_time': response_time
                })

                if sleepMs is not None:
                    if sleepMs > 0:
                        time.sleep(sleepMs / 1000)
                else:
                    time.sleep(SLEEP_TIME_BETWEEN_REQUESTS_MS / 1000)   # default sleep time
        finally:
            session.close()

        return api_runs

    def _print_response(self, response) -> None:
        """
        Print the response headers and body with appropriate formatting.
        """

        self._print_response_code(response)
        utils.print_val('Response headers', response.headers, True)

        if response.status_code == 200:
            try:
                data = json.loads(response.text)
                utils.print_val('Response body', json.dumps(data, indent = 4), True)
            except Exception:
                utils.print_val('Response body', response.text, True)
        else:
            utils.print_val('Response body', response.text, True)

    def _print_response_code(self, response) -> None:
        """
        Print the response status code with color formatting.
        """

        if 200 <= response.status_code < 300:
            status_code_str = f'{utils.BOLD_G}{response.status_code} - {response.reason}{utils.RESET}'
        elif response.status_code >= 400:
            status_code_str = f'{utils.BOLD_R}{response.status_code} - {response.reason}{utils.RESET}'
        else:
            status_code_str = str(response.status_code)

        utils.print_val('Response status', status_code_str)

    def _poll_async_operation(self, location_url: str, headers: dict = None, timeout: int = 60, poll_interval: int = 2) -> requests.Response | None:
        """
        Poll an async operation until completion.

        Args:
            location_url: The URL from the Location header
            headers: Headers to include in polling requests
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            The final response when operation completes or None on error
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(location_url, headers=headers or {}, verify = False)

                utils.print_info(f'Polling operation - Status: {response.status_code}')

                if response.status_code == 200:
                    utils.print_ok('Async operation completed successfully!')
                    return response
                elif response.status_code == 202:
                    utils.print_info(f'Operation still in progress, waiting {poll_interval} seconds...')
                    time.sleep(poll_interval)
                else:
                    utils.print_error(f'Unexpected status code during polling: {response.status_code}')
                    return response

            except requests.exceptions.RequestException as e:
                utils.print_error(f'Error polling operation: {e}')
                return None

        utils.print_error(f'Async operation timeout reached after {timeout} seconds')
        return None

    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def singleGet(self, path: str, headers = None, msg: str | None = None, printResponse: bool = True) -> Any:
        """
        Make a GET request to the Azure API Management service.

        Args:
            path: The path to append to the base URL for the request.
            headers: Additional headers to include in the request.
            printResponse: Whether to print the returned output.

        Returns:
            str | None: The JSON response as a string, or None on error.
        """

        return self._request(method = HTTP_VERB.GET, path = path, headers = headers, msg = msg, printResponse = printResponse)

    def singlePost(self, path: str, *, headers = None, data = None, msg: str | None = None, printResponse: bool = True) -> Any:
        """
        Make a POST request to the Azure API Management service.

        Args:
            path: The path to append to the base URL for the request.
            headers: Additional headers to include in the request.
            data: Data to include in the request body.
            printResponse: Whether to print the returned output.

        Returns:
            str | None: The JSON response as a string, or None on error.
        """

        return self._request(method = HTTP_VERB.POST, path = path, headers = headers, data = data, msg = msg, printResponse = printResponse)

    def multiGet(self, path: str, runs: int, headers = None, data = None, msg: str | None = None, printResponse: bool = True, sleepMs: int | None = None) -> list[dict[str, Any]]:
        """
        Make multiple GET requests to the Azure API Management service.

        Args:
            path: The path to append to the base URL for the request.
            runs: The number of times to run the GET request.
            headers: Additional headers to include in the request.
            data: Data to include in the request body.
            printResponse: Whether to print the returned output.
            sleepMs: Optional sleep time between requests in milliseconds (0 to not sleep).

        Returns:
            List of response dicts for each run.
        """

        return self._multiRequest(method = HTTP_VERB.GET, path = path, runs = runs, headers = headers, data = data, msg = msg, printResponse = printResponse, sleepMs = sleepMs)

    def singlePostAsync(self, path: str, *, headers = None, data = None, msg: str | None = None, printResponse = True, timeout = 60, poll_interval = 2) -> Any:
        """
        Make an async POST request to the Azure API Management service and poll until completion.

        Args:
            path: The path to append to the base URL for the request.
            headers: Additional headers to include in the request.
            data: Data to include in the request body.
            msg: Optional message to display.
            printResponse: Whether to print the returned output.
            timeout: Maximum time to wait for completion in seconds.
            poll_interval: Time between polls in seconds.

        Returns:
            str | None: The JSON response as a string, or None on error.
        """

        try:
            if msg:
                utils.print_message(msg, blank_above = True)

            # Ensure path has a leading slash
            if not path.startswith('/'):
                path = '/' + path

            url = self._url + path
            utils.print_info(f'POST {url}')

            merged_headers = self.headers.copy()

            if headers:
                merged_headers.update(headers)

            # Make the initial async request
            response = requests.request(HTTP_VERB.POST.value, url, headers = merged_headers, json = data, verify = False)

            utils.print_info(f'Initial response status: {response.status_code}')

            if response.status_code == 202:  # Accepted - async operation started
                location_header = response.headers.get('Location')
                if location_header:
                    utils.print_info(f'Found Location header: {location_header}')

                    # Poll the location URL until completion
                    final_response = self._poll_async_operation(
                        location_header,
                        headers=merged_headers,
                        timeout=timeout,
                        poll_interval=poll_interval
                    )

                    if final_response and final_response.status_code == 200:
                        if printResponse:
                            self._print_response(final_response)

                        content_type = final_response.headers.get('Content-Type')
                        responseBody = None

                        if content_type and 'application/json' in content_type:
                            responseBody = json.dumps(final_response.json(), indent = 4)
                        else:
                            responseBody = final_response.text

                        return responseBody
                    else:
                        utils.print_error('Async operation failed or timed out')
                        return None
                else:
                    utils.print_error('No Location header found in 202 response')
                    if printResponse:
                        self._print_response(response)
                    return None
            else:
                # Non-async response, handle normally
                if printResponse:
                    self._print_response(response)

                content_type = response.headers.get('Content-Type')
                responseBody = None

                if content_type and 'application/json' in content_type:
                    responseBody = json.dumps(response.json(), indent = 4)
                else:
                    responseBody = response.text

                return responseBody

        except requests.exceptions.RequestException as e:
            utils.print_error(f'Error making request: {e}')
            return None
