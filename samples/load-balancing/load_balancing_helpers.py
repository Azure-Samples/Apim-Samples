"""Runtime helpers for the load-balancing sample notebook.

Autoreload: reload_conditional
Method edits reload. Recreate traffic runners and result objects after state/schema changes; close existing sessions normally.
"""

import json
import time
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any, TypedDict
from uuid import NAMESPACE_URL, uuid5

import requests as http_requests

# APIM Samples imports
from apimrequests import ApimRequests
from apimtypes import HttpStatusCode
from console import print_info, print_message, print_val
from mockapi_dashboard import MockApiDashboardClient


class MockApiSuccessResponse(TypedDict):
    """Describe the MockAPI static successful response contract."""

    statusCode: int
    headers: dict[str, list[str]]
    contentType: str
    body: str


class MockApiRateLimit(TypedDict):
    """Describe an independent rolling-window permit budget."""

    requestLimit: int
    windowSeconds: int
    successResponse: MockApiSuccessResponse


class MockApiResponse(MockApiSuccessResponse):
    """Describe the exhausted response and its successful permit budget."""

    rateLimit: MockApiRateLimit


class MockApiEndpoint(TypedDict):
    """Describe the MockAPI endpoint schema."""

    id: str
    name: str
    enabled: bool
    methods: list[str]
    path: str
    response: MockApiResponse


def throttled_endpoint(index: int, *, request_limit: int = 5, window_seconds: int = 3) -> MockApiEndpoint:
    """Build a deterministic sample-owned endpoint without unsupported response templates."""
    if type(index) is not int or index not in (0, 1, 2):
        raise ValueError('The backend index must be 0, 1, or 2.')
    if type(request_limit) is not int or request_limit < 1 or type(window_seconds) is not int or not 1 <= window_seconds <= 86400:
        raise ValueError('Use a positive request limit and a window from 1 through 86400 seconds.')
    path = f'/load-balancing/backend-{index}'
    return {
        'id': str(uuid5(NAMESPACE_URL, f'apim-samples:{path}')),
        'name': f'Load Balancing backend {index}',
        'enabled': True,
        'methods': ['GET'],
        'path': path,
        'response': {
            'statusCode': 429,
            'headers': {'Retry-After': [str(window_seconds)]},
            'contentType': 'application/json',
            'body': json.dumps({'index': index, 'error': 'Backend capacity exhausted'}),
            'rateLimit': {
                'requestLimit': request_limit,
                'windowSeconds': window_seconds,
                'successResponse': {
                    'statusCode': 200,
                    'headers': {},
                    'contentType': 'application/json',
                    'body': json.dumps({'index': index}),
                },
            },
        },
    }


class LoadBalancingBackendSetup:
    """Compose two infrastructure dashboards and three independent sample permit budgets."""

    def __init__(
        self,
        dashboard_urls: list[str],
        dashboard_password: str,
        *,
        session_factory: Callable[[], http_requests.Session] = http_requests.Session,
    ) -> None:
        if len(dashboard_urls) != 2 or len(set(dashboard_urls)) != 2:
            raise ValueError('Two distinct infrastructure MockAPI dashboard URLs are required.')
        self._clients = [
            MockApiDashboardClient(url, dashboard_password, session_factory = session_factory)
            for url in dashboard_urls
        ]
        if len({client.dashboard_url for client in self._clients}) != 2:
            raise ValueError('Two distinct infrastructure MockAPI dashboard URLs are required.')

    def configure(self, *, request_limit: int = 5, window_seconds: int = 3) -> None:
        """Upsert three isolated budgets across the existing two apps, with autosave to Blob."""
        endpoints = [throttled_endpoint(index, request_limit=request_limit, window_seconds=window_seconds) for index in range(3)]
        with ExitStack() as stack:
            clients = [stack.enter_context(client) for client in self._clients]
            for index, endpoint in enumerate(endpoints):
                clients[index % 2].ensure_endpoint(endpoint)


@dataclass(frozen=True)
class LoadBalancingScenario:
    """Describe one structured load-balancing traffic scenario."""

    label: str
    api_index: int
    path: str
    runs: int
    sleep_ms: int | None = None


@dataclass(frozen=True)
class RetryTrackingResult:
    """Contain adaptive Retry-After traffic results and observed waits."""

    api_results: list[dict[str, Any]]
    retry_after_samples: list[int]
    waits: list[tuple[int, int]]

    @property
    def pre_wait_values(self) -> list[int]:
        """Return parseable Retry-After values observed through the first wait."""
        if not self.waits:
            return []

        first_wait_run = self.waits[0][0]
        return [
            int(result['headers']['Retry-After'])
            for result in self.api_results
            if result['run'] <= first_wait_run and str(result['headers'].get('Retry-After', '')).isdigit()
        ]

    @property
    def recovered_after_first_wait(self) -> bool:
        """Require success on the first request immediately after the first adaptive wait."""
        if not self.waits:
            return False

        first_wait_run = self.waits[0][0]
        return any(result['run'] == first_wait_run + 1 and result['status_code'] == HttpStatusCode.OK for result in self.api_results)

    @property
    def chart_separators(self) -> list[tuple[float, str]]:
        """Return chart separators positioned after requests that triggered waits."""
        return [(run_index - 0.5, f'Waited {seconds}s after 429') for run_index, seconds in self.waits]


class LoadBalancingTrafficRunner:
    """Run load-balancing traffic while owning reusable HTTP client lifecycles."""

    def __init__(
        self,
        requests: ApimRequests,
        endpoint_url: str,
        allow_insecure_tls: bool,
        *,
        session_factory: Callable[[], http_requests.Session] = http_requests.Session,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.requests = requests
        self.endpoint_url = endpoint_url.rstrip('/')
        self.allow_insecure_tls = allow_insecure_tls
        self._session_factory = session_factory
        self._sleep = sleep
        self._clock = clock
        self._session: http_requests.Session | None = None

    def __enter__(self) -> 'LoadBalancingTrafficRunner':
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        """Close all HTTP clients owned by the runner."""
        if self._session is not None:
            self._session.close()
            self._session = None
        self.requests.close()

    def run_structured(
        self,
        scenarios: list[LoadBalancingScenario],
        subscription_keys: list[str],
        *,
        pause_seconds: float = 2,
        initial_pause_seconds: float = 0,
    ) -> list[list[dict[str, Any]]]:
        """Execute structured scenarios with one reusable APIM request client."""
        results_by_scenario = []
        if initial_pause_seconds > 0:
            self._sleep(initial_pause_seconds)

        for scenario_index, scenario in enumerate(scenarios):
            if scenario_index and pause_seconds > 0:
                self._sleep(pause_seconds)

            self.requests.subscriptionKey = subscription_keys[scenario.api_index]
            print_message(f'Starting API calls for {scenario.label}', blank_above=True)
            results = self.requests.multiGet(
                    scenario.path,
                    runs=scenario.runs,
                    msg=f'Calling {scenario.label}',
                    sleepMs=scenario.sleep_ms,
                )
            self._add_observed_counts(results)
            results_by_scenario.append(results)

        return results_by_scenario

    def run_retry_tracking(self, path: str, runs: int, subscription_key: str, *, pause_seconds: float = 0) -> RetryTrackingResult:
        """Run adaptive traffic that waits for each parseable 429 Retry-After value."""
        if runs < 1:
            raise ValueError('Retry-tracking runs must be at least 1.')
        if pause_seconds > 0:
            self._sleep(pause_seconds)

        self.requests.subscriptionKey = subscription_key
        session = self._get_session()
        session.headers.clear()
        session.headers.update(self.requests.headers)

        api_results: list[dict[str, Any]] = []
        retry_after_samples: list[int] = []
        waits: list[tuple[int, int]] = []
        url = f'{self.endpoint_url}/{path.lstrip("/")}'

        for run_index in range(1, runs + 1):
            print_info(f'Run {run_index}/{runs}:')
            started_at = self._clock()
            response = session.get(url, timeout=30)
            response_time = self._clock() - started_at
            self._print_response(response)

            api_results.append(
                {
                    'run': run_index,
                    'response': self._serialize_response(response),
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'headers': dict(response.headers),
                }
            )

            retry_after = response.headers.get('Retry-After')
            if response.status_code == HttpStatusCode.TOO_MANY_REQUESTS and retry_after and retry_after.isdigit():
                wait_seconds = int(retry_after)
                retry_after_samples.append(wait_seconds)
                print_message(f'429 at run {run_index}; sleeping {wait_seconds}s', blank_above=True)
                self._sleep(wait_seconds)
                waits.append((run_index, wait_seconds))

        self._add_observed_counts(api_results)
        return RetryTrackingResult(api_results, retry_after_samples, waits)

    @staticmethod
    def _add_observed_counts(results: list[dict[str, Any]]) -> None:
        """Annotate successful responses with per-scenario observed counts, not server counters."""
        counts: dict[int, int] = {}
        for result in results:
            if not isinstance(result, dict) or result.get('status_code') != HttpStatusCode.OK:
                continue
            try:
                body = json.loads(result['response'])
            except (TypeError, ValueError):
                continue
            if not isinstance(body, dict) or type(body.get('index')) is not int or body['index'] not in (0, 1, 2):
                continue
            index = body['index']
            counts[index] = counts.get(index, 0) + 1
            body['count'] = counts[index]
            result['response'] = json.dumps(body, indent=4)

    def _get_session(self) -> http_requests.Session:
        if self._session is None:
            self._session = self._session_factory()
            self._session.verify = not self.allow_insecure_tls

        return self._session

    @staticmethod
    def _serialize_response(response: http_requests.Response) -> str:
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' not in content_type:
            return response.text

        try:
            return json.dumps(response.json(), indent=4)
        except ValueError:
            return response.text

    @staticmethod
    def _print_response(response: http_requests.Response) -> None:
        print_val('Response status', response.status_code)
        print_val('Response headers', response.headers, True)
        print_val('Response body', response.text, True)
