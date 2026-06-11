"""Runtime helpers for the inference-failover sample notebook."""

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests as http_requests

# APIM Samples imports
from apimtypes import SUBSCRIPTION_KEY_PARAMETER_NAME
from console import print_info, print_message


@dataclass(frozen=True)
class InferenceScenario:
    """Describe one inference traffic scenario."""

    label: str
    route: str
    subscription_key: str
    payload: dict[str, Any]
    runs: int
    backend_url_index: Mapping[str, int]
    sleep_ms: int = 0


@dataclass(frozen=True)
class ContractProbeResults:
    """Contain deterministic gateway contract responses."""

    success: http_requests.Response
    malformed: http_requests.Response
    missing_key: http_requests.Response
    unknown_operation: http_requests.Response


@dataclass(frozen=True)
class InferenceScenarioSummary:
    """Contain normalized outcome counts for one scenario."""

    successes: int
    client_errors: int
    server_errors: int
    status_code_counts: dict[int, int]
    served_backend_urls: list[str]
    retry_counts: dict[int, int]


class InferenceTrafficRunner:
    """Run inference traffic while owning one reusable HTTP session."""

    def __init__(
        self,
        endpoint_url: str,
        request_headers: Mapping[str, str] | None,
        allow_insecure_tls: bool,
        *,
        session_factory: Callable[[], http_requests.Session] = http_requests.Session,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.endpoint_url = endpoint_url.rstrip('/')
        self.request_headers = dict(request_headers or {})
        self.allow_insecure_tls = allow_insecure_tls
        self._session_factory = session_factory
        self._sleep = sleep
        self._clock = clock
        self._session: http_requests.Session | None = None

    def __enter__(self) -> 'InferenceTrafficRunner':
        self._get_session()

        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP session owned by the runner."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def pause(self, seconds: float) -> None:
        """Pause between scenarios through the injectable sleep boundary."""
        if seconds < 0:
            raise ValueError('Pause duration must not be negative.')
        if seconds > 0:
            self._sleep(seconds)

    def run_contract_probes(
        self,
        route: str,
        unknown_operation_route: str,
        subscription_key: str,
        payload: dict[str, Any],
    ) -> ContractProbeResults:
        """Run the deterministic success, client, authentication, and routing probes."""
        session = self._get_session()
        probe_headers = {SUBSCRIPTION_KEY_PARAMETER_NAME: subscription_key}

        return ContractProbeResults(
            success=session.post(route, headers=probe_headers, json=payload, timeout=120),
            malformed=session.post(route, headers=probe_headers, data='{"messages":', timeout=120),
            missing_key=session.post(route, json=payload, timeout=120),
            unknown_operation=session.post(unknown_operation_route, headers=probe_headers, json=payload, timeout=120),
        )

    def run_scenario(self, scenario: InferenceScenario) -> list[dict[str, Any]]:
        """Run one inference scenario and return chart-compatible response records."""
        if scenario.runs < 1:
            raise ValueError('Scenario runs must be at least 1.')
        if scenario.sleep_ms < 0:
            raise ValueError('Scenario sleep must not be negative.')

        session = self._get_session()
        url = f'{self.endpoint_url}/{scenario.route.lstrip("/")}'
        print_message(scenario.label, blank_above=True)
        print_info(f'POST {url}')
        results: list[dict[str, Any]] = []

        for run_index in range(1, scenario.runs + 1):
            started_at = self._clock()
            response = session.post(
                url,
                headers={SUBSCRIPTION_KEY_PARAMETER_NAME: scenario.subscription_key},
                json=scenario.payload,
                timeout=120,
            )
            response_time = self._clock() - started_at
            backend_url = response.headers.get('X-Backend-URL', 'unknown')
            backend_retry = parse_backend_retry(response)
            validate_status(response)
            print_info(
                f'Run {run_index}/{scenario.runs}: {response.status_code} via {backend_url}; X-Backend-Retry={backend_retry} ({response_time:.2f}s)'
            )
            if 400 <= response.status_code < 600:
                print_info(f'Captured error response body: {response.text}')

            response_body = response.text
            if response.status_code == 200:
                response_body = json.dumps(
                    {
                        'index': get_backend_index(backend_url, scenario.backend_url_index),
                        'backendUrl': backend_url,
                        'backendRetry': backend_retry,
                    }
                )

            results.append(
                {
                    'run': run_index,
                    'response': response_body,
                    'model_response': response.text,
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'headers': dict(response.headers),
                    'backend_url': backend_url,
                    'backend_retry': backend_retry,
                }
            )

            if scenario.sleep_ms and run_index < scenario.runs:
                self._sleep(scenario.sleep_ms / 1000)

        return results

    def _get_session(self) -> http_requests.Session:
        if self._session is None:
            self._session = self._session_factory()
            self._session.verify = not self.allow_insecure_tls
            self._session.headers.update(self.request_headers)
            self._session.headers.update({'Content-Type': 'application/json'})

        return self._session


def get_backend_index(backend_url: str, backend_url_index: Mapping[str, int]) -> int:
    """Return the chart index for a backend URL, or 99 when no marker matches."""
    return next((backend_index for marker, backend_index in backend_url_index.items() if marker in backend_url), 99)


def parse_backend_retry(response: http_requests.Response) -> int:
    """Parse and validate the required caller-visible retry count."""
    retry_header = response.headers.get('X-Backend-Retry')
    if retry_header is None:
        raise ValueError('Required X-Backend-Retry response header is missing.')

    try:
        backend_retry = int(retry_header)
    except ValueError as error:
        raise ValueError(f'Invalid X-Backend-Retry response header: {retry_header}') from error

    if backend_retry < 0:
        raise ValueError(f'Invalid negative X-Backend-Retry response header: {backend_retry}')

    return backend_retry


def validate_status(response: http_requests.Response) -> None:
    """Reject responses outside the outcomes captured by the sample."""
    if response.status_code == 200 or 400 <= response.status_code < 600:
        return

    raise ValueError(f'Unexpected HTTP {response.status_code} response from the inference route: {response.text}')


def summarize_scenario(results: list[dict[str, Any]]) -> InferenceScenarioSummary:
    """Summarize status, retry, and successful backend outcomes."""
    status_code_counts: dict[int, int] = {}
    retry_counts: dict[int, int] = {}
    for result in results:
        status_code = result['status_code']
        backend_retry = result['backend_retry']
        status_code_counts[status_code] = status_code_counts.get(status_code, 0) + 1
        retry_counts[backend_retry] = retry_counts.get(backend_retry, 0) + 1

    return InferenceScenarioSummary(
        successes=sum(1 for result in results if result['status_code'] == 200),
        client_errors=sum(1 for result in results if 400 <= result['status_code'] < 500),
        server_errors=sum(1 for result in results if 500 <= result['status_code'] < 600),
        status_code_counts=dict(sorted(status_code_counts.items())),
        served_backend_urls=sorted(
            {result['backend_url'] for result in results if result['status_code'] == 200 and result['backend_url'] != 'unknown'}
        ),
        retry_counts=dict(sorted(retry_counts.items())),
    )


def format_request_count(count: int) -> str:
    """Return a request count with the grammatically correct noun."""
    noun = 'request' if count == 1 else 'requests'

    return f'{count} {noun}'


def format_backend_url_counts(api_results: list[dict[str, Any]]) -> str:
    """Return a compact distribution summary from captured backend URLs."""
    backend_url_counts: dict[str, int] = {}
    for result in api_results:
        backend_url = result['backend_url']
        backend_url_counts[backend_url] = backend_url_counts.get(backend_url, 0) + 1

    return '\n'.join(f'- {backend_url}: {format_request_count(count)}' for backend_url, count in sorted(backend_url_counts.items()))


def with_backend_identifier(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a telemetry frame copy with a compact backend identifier."""
    result = frame.copy()
    if 'Backend URL' not in result.columns:
        return result
    if 'Backend' not in result.columns:
        backend_identifiers = result['Backend URL'].str.extract(r'/deployments/([a-z])-', expand=False).fillna('')
        result.insert(1, 'Backend', backend_identifiers)
    else:
        result['Backend'] = result['Backend'].replace('?', '')

    return result


def format_gateway_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    """Return gateway distribution values formatted for display."""
    result = frame.copy()
    average_backend_ms = pd.to_numeric(result['AverageBackendMs'].astype(str).str.replace(',', '', regex=False), errors='coerce')
    success_rate = pd.to_numeric(result['SuccessRate'].astype(str).str.rstrip('%'), errors='coerce')
    result['AverageBackendMs'] = average_backend_ms.map(lambda value: '' if pd.isna(value) else f'{value:,.1f}')
    result['SuccessRate'] = success_rate.map(lambda value: '' if pd.isna(value) else f'{value:.2f}%')
    if 'Backend URL' in result.columns:
        backend_names = result['Backend URL'].str.extract(r'/deployments/([a-z]-[^/]+)', expand=False).fillna('')
        result['Backend'] = backend_names.str.replace('-', ') ', n=1, regex=False)
        result = result.drop(columns=['Backend URL'])

    return result
