"""
Module for making requests to Azure API Management endpoints with consistent logging and output formatting.
"""

import json
import time
from typing import Any

import requests
import utils
from apimtypes import (HTTP_VERB, SLEEP_TIME_BETWEEN_REQUESTS_MS,
                       SUBSCRIPTION_KEY_PARAMETER_NAME)

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

    def __init__(self, url: str, apim_subscription_key: str | None = None, timeout: int = 30) -> None:
        """
        Initialize the ApimRequests object.

        Args:
            url: The base URL for the APIM endpoint.
            apimSubscriptionKey: Optional subscription key for APIM.
        """

        self.url = url
        # prefer snake_case internally
        self.apim_subscription_key = apim_subscription_key
        # keep legacy camelCase attribute for backwards compatibility
        self.apimSubscriptionKey = apim_subscription_key  # pylint: disable=invalid-name
        # Default timeout (seconds) for network calls to prevent hanging requests
        self._timeout = timeout
        self._headers: dict[str, str] = {}

        if self.apimSubscriptionKey:
            self._headers[SUBSCRIPTION_KEY_PARAMETER_NAME] = self.apimSubscriptionKey

        self._headers["Accept"] = "application/json"

    # ------------------------------
    #    PROPERTIES
    # ------------------------------

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

    def _request(
        self,
        method: HTTP_VERB,
        path: str,
        headers: list[any] = None,
        data: any = None,
        msg: str | None = None,
        print_response: bool = True,
    ) -> str | None:
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
                utils.print_message(msg, blank_above=True)

            # Ensure path has a leading slash
            if not path.startswith("/"):
                path = "/" + path

            url = self.url + path
            utils.print_info(f"{method.value} {url}")

            merged_headers = self.headers.copy()

            if headers:
                merged_headers.update(headers)

            response = requests.request(
                method.value, url, headers=merged_headers, json=data, timeout=self._timeout
            )

            content_type = response.headers.get("Content-Type")

            response_body = None

            if content_type and "application/json" in content_type:
                response_body = json.dumps(response.json(), indent=4)
            else:
                response_body = response.text

            if print_response:
                self._print_response(response)

            return response_body

        except requests.exceptions.RequestException as e:
            utils.print_error(f"Error making request: {e}")
            return None

    def _multi_request(
        self,
        method: HTTP_VERB,
        path: str,
        runs: int,
        data: any = None,
        msg: str | None = None,
        sleep_ms: int | None = None,
    ) -> list[dict[str, Any]]:
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
                utils.print_message(msg, blank_above=True)

            # Ensure path has a leading slash
            if not path.startswith("/"):
                path = "/" + path

            url = self.url + path
            utils.print_info(f"{method.value} {url}")

            for i in range(runs):
                utils.print_info(f"▶️ Run {i + 1}/{runs}:")

                start_time = time.time()
                response = session.request(method.value, url, json=data, timeout=self._timeout)
                response_time = time.time() - start_time
                utils.print_info(f"⌚ {response_time:.2f} seconds")

                self._print_response_code(response)

                content_type = response.headers.get("Content-Type")

                if content_type and "application/json" in content_type:
                    resp_data = json.dumps(response.json(), indent=4)
                else:
                    resp_data = response.text

                api_runs.append(
                    {
                        "run": i + 1,
                        "response": resp_data,
                        "status_code": response.status_code,
                        "response_time": response_time,
                    }
                )

                if sleep_ms is not None:
                    if sleep_ms > 0:
                        time.sleep(sleep_ms / 1000)
                else:
                    time.sleep(
                        SLEEP_TIME_BETWEEN_REQUESTS_MS / 1000
                    )  # default sleep time
        finally:
            session.close()

        return api_runs

    # Backwards-compatible camelCase wrapper for legacy callers/tests
    def _multiRequest(  # pylint: disable=invalid-name
        self,
        method: HTTP_VERB,
        path: str,
        runs: int,
        data: any = None,
        msg: str | None = None,
        sleepMs: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Backwards-compatible camelCase wrapper for `_multi_request`.

        This exists to support legacy callers and tests that use the older
        camelCase method name. It forwards all arguments to the
        snake_case implementation.

        Returns:
            A list of response metadata dictionaries produced by `_multi_request`.
        """

        return self._multi_request(
            method=method,
            path=path,
            runs=runs,
            data=data,
            msg=msg,
            sleep_ms=sleepMs,
        )

    def _print_response(self, response) -> None:
        """
        Print the response headers and body with appropriate formatting.
        """

        self._print_response_code(response)
        utils.print_val("Response headers", response.headers, True)

        if response.status_code == 200:
            try:
                data = json.loads(response.text)
                utils.print_val("Response body", json.dumps(data, indent=4), True)
            except Exception:
                utils.print_val("Response body", response.text, True)
        else:
            utils.print_val("Response body", response.text, True)

    def _print_response_code(self, response) -> None:
        """
        Print the response status code with color formatting.
        """

        if 200 <= response.status_code < 300:
            status_code_str = (
                f"{utils.BOLD_G}{response.status_code} - {response.reason}{utils.RESET}"
            )
        elif response.status_code >= 400:
            status_code_str = (
                f"{utils.BOLD_R}{response.status_code} - {response.reason}{utils.RESET}"
            )
        else:
            status_code_str = str(response.status_code)

        utils.print_val("Response status", status_code_str)

    def _poll_async_operation(
        self,
        location_url: str,
        headers: dict = None,
        timeout: int = 60,
        poll_interval: int = 2,
    ) -> requests.Response | None:
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
                response = requests.get(location_url, headers=headers or {}, timeout=self._timeout)

                utils.print_info(f"Polling operation - Status: {response.status_code}")

                if response.status_code == 200:
                    utils.print_ok("Async operation completed successfully!")
                    return response
                elif response.status_code == 202:
                    utils.print_info(
                        f"Operation still in progress, waiting {poll_interval} seconds..."
                    )
                    time.sleep(poll_interval)
                else:
                    utils.print_error(
                        f"Unexpected status code during polling: {response.status_code}"
                    )
                    return response

            except requests.exceptions.RequestException as e:
                utils.print_error(f"Error polling operation: {e}")
                return None

        utils.print_error(f"Async operation timeout reached after {timeout} seconds")
        return None

    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    # New snake_case public API (preferred)
    def single_get(
        self,
        path: str,
        headers=None,
        msg: str | None = None,
        print_response: bool = True,
    ) -> Any:
        """
        Perform a single GET request to the APIM endpoint.

        Args:
            path: Path to append to the base APIM URL.
            headers: Optional additional HTTP headers.
            msg: Optional message to print before the request.
            print_response: When True, prints formatted response output.

        Returns:
            The response body as a string (JSON pretty-printed when applicable)
            or None on error.
        """

        return self._request(
            method=HTTP_VERB.GET,
            path=path,
            headers=headers,
            msg=msg,
            print_response=print_response,
        )

    def single_post(
        self,
        path: str,
        *,
        headers=None,
        data=None,
        msg: str | None = None,
        print_response: bool = True,
    ) -> Any:
        """
        Perform a single POST request to the APIM endpoint.

        Args:
            path: Path to append to the base APIM URL.
            headers: Optional additional HTTP headers.
            data: Optional JSON-serializable body to send.
            msg: Optional message to print before the request.
            print_response: When True, prints formatted response output.

        Returns:
            The response body as a string (JSON pretty-printed when applicable)
            or None on error.
        """

        return self._request(
            method=HTTP_VERB.POST,
            path=path,
            headers=headers,
            data=data,
            msg=msg,
            print_response=print_response,
        )

    def multi_get(
        self,
        path: str,
        runs: int,
        data=None,
        msg: str | None = None,
        sleep_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform multiple GET requests to the APIM endpoint.

        Runs the same GET request `runs` times and returns a list of
        response metadata dictionaries that include run index, response body,
        HTTP status, and response time.

        Args:
            path: Path to append to the base APIM URL.
            runs: Number of times to execute the request.
            data: Optional JSON-serializable body to send.
            msg: Optional message to print before the requests.
            sleep_ms: Optional sleep time between runs in milliseconds.

        Returns:
            A list of dictionaries containing keys: 'run', 'response', 'status_code',
            and 'response_time'.
        """

        return self._multi_request(
            method=HTTP_VERB.GET,
            path=path,
            runs=runs,
            data=data,
            msg=msg,
            sleep_ms=sleep_ms,
        )

    def single_post_async(
        self,
        path: str,
        *,
        headers=None,
        data=None,
        msg: str | None = None,
        print_response=True,
        timeout=60,
        poll_interval=2,
    ) -> Any:
        """
        Perform an asynchronous POST request and poll until completion.

        This snake_case wrapper forwards to the legacy camelCase implementation
        (`singlePostAsync`) for compatibility while providing a descriptive
        docstring for newer callers.

        See `singlePostAsync` for behavior details and return values.
        """

        # reuse existing implementation (body below) by calling the camelCase method implementation
        return self.singlePostAsync(
            path,
            headers=headers,
            data=data,
            msg=msg,
            printResponse=print_response,
            timeout=timeout,
            poll_interval=poll_interval,
        )


    def singleGet(  # pylint: disable=invalid-name
        self,
        path: str,
        headers=None,
        msg: str | None = None,
        printResponse: bool = True,
    ) -> Any:
        """
        Make a GET request to the Azure API Management service.

        Args:
            path: The path to append to the base URL for the request.
            headers: Additional headers to include in the request.
            printResponse: Whether to print the returned output.

        Returns:
            str | None: The JSON response as a string, or None on error.
        """

        return self._request(
            method=HTTP_VERB.GET,
            path=path,
            headers=headers,
            msg=msg,
            print_response=printResponse,
        )

    def singlePost(  # pylint: disable=invalid-name
        self,
        path: str,
        *,
        headers=None,
        data=None,
        msg: str | None = None,
        printResponse: bool = True,
    ) -> Any:
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

        return self._request(
            method=HTTP_VERB.POST,
            path=path,
            headers=headers,
            data=data,
            msg=msg,
            print_response=printResponse,
        )

    def multiGet(  # pylint: disable=invalid-name
        self,
        path: str,
        runs: int,
        data=None,
        msg: str | None = None,
        sleepMs: int | None = None,
    ) -> list[dict[str, Any]]:
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

        return self._multi_request(
            method=HTTP_VERB.GET,
            path=path,
            runs=runs,
            data=data,
            msg=msg,
            sleep_ms=sleepMs,
        )

    def singlePostAsync(  # pylint: disable=invalid-name
        self,
        path: str,
        *,
        headers=None,
        data=None,
        msg: str | None = None,
        printResponse=True,
        timeout=60,
        poll_interval=2,
    ) -> Any:
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
                utils.print_message(msg, blank_above=True)

            # Ensure path has a leading slash
            if not path.startswith("/"):
                path = "/" + path

            url = self.url + path
            utils.print_info(f"POST {url}")

            merged_headers = self.headers.copy()

            if headers:
                merged_headers.update(headers)

            # Make the initial async request
            response = requests.request(
                HTTP_VERB.POST.value,
                url,
                headers=merged_headers,
                json=data,
                timeout=self._timeout,
            )

            utils.print_info(f"Initial response status: {response.status_code}")

            if response.status_code == 202:  # Accepted - async operation started
                location_header = response.headers.get("Location")
                if location_header:
                    utils.print_info(f"Found Location header: {location_header}")

                    # Poll the location URL until completion
                    final_response = self._poll_async_operation(
                        location_header,
                        headers=merged_headers,
                        timeout=timeout,
                        poll_interval=poll_interval,
                    )

                    if final_response and final_response.status_code == 200:
                        if printResponse:
                            self._print_response(final_response)

                        content_type = final_response.headers.get("Content-Type")
                        responseBody = None

                        if content_type and "application/json" in content_type:
                            responseBody = json.dumps(final_response.json(), indent=4)
                        else:
                            responseBody = final_response.text

                        return responseBody
                    else:
                        utils.print_error("Async operation failed or timed out")
                        return None
                else:
                    utils.print_error("No Location header found in 202 response")
                    if printResponse:
                        self._print_response(response)
                    return None
            else:
                # Non-async response, handle normally
                if printResponse:
                    self._print_response(response)

                content_type = response.headers.get("Content-Type")
                responseBody = None

                if content_type and "application/json" in content_type:
                    responseBody = json.dumps(response.json(), indent=4)
                else:
                    responseBody = response.text

                return responseBody

        except requests.exceptions.RequestException as e:
            utils.print_error(f"Error making request: {e}")
            return None
