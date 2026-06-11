"""Runtime helpers for the inference-failover sample notebook."""

import json
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests as http_requests

# APIM Samples imports
from apimtypes import SUBSCRIPTION_KEY_PARAMETER_NAME
from console import print_info, print_message
from htmlreport import HtmlList, HtmlSuccess, HtmlText, HtmlWarning


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


def get_priority_and_weight(backend_index: int, backend_labels: Mapping[int, str]) -> tuple[int, int]:
    """Return the routing priority and weight encoded in a backend legend label."""
    route_label = backend_labels[backend_index].split(':', maxsplit=1)[0]
    priority_label, weight_label = route_label.split(' / ', maxsplit=1)

    return int(priority_label.removeprefix('Priority ')), int(weight_label.removeprefix('Weight '))


def build_scenario_report_row(
    test_id: str,
    title: str,
    api_results: list[dict[str, Any]],
    backend_url_index: Mapping[str, int],
    backend_labels: Mapping[int, str],
) -> list[object]:
    """Return one compact HTML report row with routing statistics and interpretation."""
    total_requests = len(api_results)
    if not total_requests:
        return ['', test_id, title, 0, 0, 0, 'None', 'No requests', 'No scenario requests were captured.']

    status_counts = Counter(result['status_code'] for result in api_results)
    retry_counts = Counter(result['backend_retry'] for result in api_results)
    backend_indexes = [get_backend_index(result['backend_url'], backend_url_index) for result in api_results]
    priority_weight_counts = Counter(get_priority_and_weight(index, backend_labels) for index in backend_indexes if index in backend_labels)
    priority_counts: Counter = Counter()
    weights_by_priority: dict[int, list[str]] = {}
    for (priority, weight), count in sorted(priority_weight_counts.items()):
        priority_counts[priority] += count
        weights_by_priority.setdefault(priority, []).append(f'W{weight}: {count} ({count / total_requests:.1%})')
    routed_requests = sum(priority_counts.values())
    unresolved_requests = total_requests - routed_requests
    routed_beyond_primary = sum(count for priority, count in priority_counts.items() if priority > 1)
    non_200_responses = total_requests - status_counts.get(200, 0)
    caller_succeeded = not non_200_responses
    retried_requests = sum(count for retry_count, count in retry_counts.items() if retry_count > 0)
    backend_retries_absorbed = sum(retry_count * count for retry_count, count in retry_counts.items())
    caller_visible_failures = non_200_responses
    observed_backend_failures = backend_retries_absorbed + caller_visible_failures
    terminal_503_responses = status_counts.get(503, 0)
    priority_mix = '\n'.join(f'P{priority}: {", ".join(weight_mix)}' for priority, weight_mix in sorted(weights_by_priority.items()))
    retry_mix = (
        '\n'.join(f'{retry_count}: {count} ({count / total_requests:.1%})' for retry_count, count in sorted(retry_counts.items()) if retry_count > 0)
        or 'None'
    )
    if unresolved_requests:
        unresolved_mix = f'No resolved backend: {unresolved_requests} ({unresolved_requests / total_requests:.1%})'
        priority_mix = f'{priority_mix}\n{unresolved_mix}' if priority_mix else unresolved_mix

    observations = []
    if non_200_responses:
        observations.append(f'{non_200_responses}/{total_requests} ({non_200_responses / total_requests:.1%}) caller-visible non-200 responses')
    else:
        observations.append('All requests returned HTTP 200')
    if backend_retries_absorbed:
        observations.append(f'{retried_requests}/{total_requests} returned after a retry')
    else:
        observations.append('all responses returned without a backend retry')
    if routed_beyond_primary:
        observations.append(f'{routed_beyond_primary}/{total_requests} ({routed_beyond_primary / total_requests:.1%}) routed beyond P1')
    else:
        observations.append('no failover beyond P1 observed')
    if priority_counts:
        observations.append(f'Deepest routed tier: P{max(priority_counts)}')
    if unresolved_requests:
        observations.append(f'{unresolved_requests} calls returned no resolved backend, consistent with exhausted or rejected routing')
    observations.append(f'APIM absorbed {backend_retries_absorbed} backend failures and sent {caller_visible_failures} failures to callers')
    if observed_backend_failures:
        shielded_percentage = backend_retries_absorbed / observed_backend_failures * 100
        observations.append(f'APIM prevented {shielded_percentage:.1f}% of observed failed backend attempts from reaching callers')
    else:
        observations.append('APIM shielding percentage is not applicable because no backend failures occurred')
    if terminal_503_responses:
        observations.append(f'{terminal_503_responses} caller-visible HTTP 503 responses followed eligible-capacity exhaustion in the low-TPM pool')
    elif caller_visible_failures:
        observations.append('caller-visible failures remained because the model-safe pool exhausted its configured fallback chain')

    priority_tokens = tuple(f'P{priority}' for priority in sorted(priority_counts))
    observation_items = tuple(item.strip() for item in '; '.join(observations).split(';'))

    return [
        (HtmlSuccess('All requests returned HTTP 200') if caller_succeeded else HtmlWarning('Some requests returned non-200 responses')),
        test_id,
        title,
        total_requests,
        status_counts.get(200, 0),
        non_200_responses,
        HtmlText(retry_mix, preserve_line_breaks=True),
        HtmlText(priority_mix, bold_tokens=priority_tokens, preserve_line_breaks=True),
        HtmlList(observation_items),
    ]
