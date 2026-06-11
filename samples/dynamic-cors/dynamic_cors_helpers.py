"""Runtime helpers for the Dynamic CORS sample notebook."""

import json
import socket
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests as http_requests

# APIM Samples imports
import utils
from console import print_error, print_ok


class DynamicCorsTestRunner:
    """Own one cell's HTTP session and persist its Dynamic CORS test results."""

    def __init__(
        self,
        deployment,
        rg_name: str,
        apim_gateway_url: str,
        results_path: Path,
        result_groups: list[str],
    ) -> None:
        self.endpoint_url, request_headers, allow_insecure_tls = utils.get_endpoint(deployment, rg_name, apim_gateway_url)
        self.results_path = results_path
        self.result_groups = set(result_groups)
        self.results: list[dict[str, Any]] = []
        self.session = http_requests.Session()
        self.session.verify = not allow_insecure_tls
        if request_headers:
            self.session.headers.update(request_headers)

    def __enter__(self) -> 'DynamicCorsTestRunner':
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        try:
            self._persist_results()
        finally:
            self.session.close()

    def options_request(self, path: str, origin: str) -> tuple[int, dict[str, str], float]:
        """Send an OPTIONS preflight request and return status, headers, and duration."""
        response = self.session.options(
            f'{self.endpoint_url}/{path}',
            headers={'Origin': origin, 'Access-Control-Request-Method': 'GET'},
            timeout=30,
        )

        return response.status_code, dict(response.headers), self._elapsed_ms(response)

    def get(self, path: str, origin: str, label: str) -> tuple[dict[str, Any], float]:
        """Send a GET request and return its JSON body and duration."""
        response = self.session.get(f'{self.endpoint_url}/{path}', headers={'Origin': origin}, timeout=30)
        elapsed_ms = self._elapsed_ms(response)
        body = response.json() if response.ok else {}
        print(f'  {label}: {response.status_code} ({elapsed_ms} ms)')

        return body, elapsed_ms

    def post(self, path: str, *, headers: dict[str, str], data: str | None = None) -> tuple[http_requests.Response, float]:
        """Send an administrative POST request and return its response and duration."""
        response = self.session.post(f'{self.endpoint_url}/{path}', headers=headers, data=data, timeout=30)

        return response, self._elapsed_ms(response)

    def track(
        self,
        suite,
        option: str,
        label: str,
        actual: Any,
        expected: Any,
        duration_ms: float | None = None,
    ) -> bool:
        """Verify one expectation and record it for the consolidated summary."""
        passed = suite.verify(actual, expected, label)
        self.results.append(
            {
                'Option': option,
                'Test': label,
                'Expected': str(expected),
                'Actual': str(actual),
                'Duration (ms)': duration_ms,
                'Result': passed,
            }
        )

        return passed

    def run_option_tests(self, suite, option: str, products_path: str, analytics_path: str) -> None:
        """Execute the shared OPTIONS and GET test matrix for one CORS option."""
        prefix = option.upper().replace(' ', '')

        status, headers, elapsed_ms = self.options_request(products_path, 'https://shop.contoso.com')
        self.track(suite, option, f'{prefix} Products OPTIONS - allowed origin (shop)', status, 200, elapsed_ms)
        self.track(
            suite,
            option,
            f'{prefix} Products Access-Control-Allow-Origin (shop)',
            headers.get('Access-Control-Allow-Origin', ''),
            'https://shop.contoso.com',
        )

        status, headers, elapsed_ms = self.options_request(products_path, 'https://admin.contoso.com')
        self.track(suite, option, f'{prefix} Products OPTIONS - allowed origin (admin)', status, 200, elapsed_ms)
        self.track(
            suite,
            option,
            f'{prefix} Products Access-Control-Allow-Origin (admin)',
            headers.get('Access-Control-Allow-Origin', ''),
            'https://admin.contoso.com',
        )

        status, _, elapsed_ms = self.options_request(products_path, 'https://unauthorized.contoso.net')
        self.track(suite, option, f'{prefix} Products OPTIONS - unauthorized origin', status, 403, elapsed_ms)

        status, headers, elapsed_ms = self.options_request(analytics_path, 'https://dashboard.contoso.com')
        self.track(suite, option, f'{prefix} Analytics OPTIONS - allowed origin', status, 200, elapsed_ms)
        self.track(
            suite,
            option,
            f'{prefix} Analytics Access-Control-Allow-Origin',
            headers.get('Access-Control-Allow-Origin', ''),
            'https://dashboard.contoso.com',
        )

        status, _, elapsed_ms = self.options_request(analytics_path, 'https://shop.contoso.com')
        self.track(suite, option, f'{prefix} Analytics OPTIONS - unauthorized origin (shop)', status, 403, elapsed_ms)

        body, elapsed_ms = self.get(products_path, 'https://shop.contoso.com', f'{prefix} Products GET (shop)')
        self.track(suite, option, f'{prefix} Products GET corsAllowed (shop)', body.get('corsAllowed'), True, elapsed_ms)
        self.track(
            suite,
            option,
            f'{prefix} Products GET allowedOrigin (shop)',
            body.get('allowedOrigin'),
            'https://shop.contoso.com',
        )

        body, elapsed_ms = self.get(products_path, 'https://unauthorized.contoso.net', f'{prefix} Products GET (unauthorized)')
        self.track(suite, option, f'{prefix} Products GET corsAllowed (unauthorized)', body.get('corsAllowed'), False, elapsed_ms)

        body, elapsed_ms = self.get(analytics_path, 'https://dashboard.contoso.com', f'{prefix} Analytics GET (dashboard)')
        self.track(suite, option, f'{prefix} Analytics GET corsAllowed', body.get('corsAllowed'), True, elapsed_ms)

        body, elapsed_ms = self.get(analytics_path, 'https://shop.contoso.com', f'{prefix} Analytics GET (unauthorized)')
        self.track(suite, option, f'{prefix} Analytics GET corsAllowed (unauthorized)', body.get('corsAllowed'), False, elapsed_ms)

    def _persist_results(self) -> None:
        existing = load_test_results(self.results_path)
        retained = [result for result in existing if result.get('Option') not in self.result_groups]
        self.results_path.write_text(json.dumps([*retained, *self.results], indent=2), encoding='utf-8')

    @staticmethod
    def _elapsed_ms(response: http_requests.Response) -> float:
        return round(response.elapsed.total_seconds() * 1000, 1)


def load_test_results(results_path: Path) -> list[dict[str, Any]]:
    """Load persisted Dynamic CORS results, returning an empty list when absent."""
    if not results_path.exists():
        return []

    loaded = json.loads(results_path.read_text(encoding='utf-8'))
    if not isinstance(loaded, list) or not all(isinstance(result, dict) for result in loaded):
        raise ValueError(f'Invalid Dynamic CORS result data in {results_path}')

    return loaded


def wait_for_gateway_dns(apim_gateway_url: str, max_wait: int = 120, poll_interval: int = 10) -> None:
    """Wait until the APIM gateway hostname resolves or raise SystemExit."""
    gateway_host = urlparse(apim_gateway_url).hostname
    if not gateway_host:
        raise ValueError(f'APIM gateway URL has no hostname: {apim_gateway_url}')

    for elapsed in range(0, max_wait + 1, poll_interval):
        try:
            socket.getaddrinfo(gateway_host, 443)
            message = f'Gateway DNS resolved after {elapsed}s' if elapsed else f'Gateway DNS resolved: {gateway_host}'
            print_ok(message)
            return
        except socket.gaierror:
            if elapsed < max_wait:
                print(f'Waiting for APIM gateway DNS to propagate ({gateway_host}) ... {elapsed}s / {max_wait}s')
                time.sleep(poll_interval)

    print_error(f'Gateway DNS did not resolve within {max_wait}s.')
    print_error('If APIM was just provisioned, wait a few more minutes and re-run this cell.')
    raise SystemExit(1)
