"""Runtime helpers for the load-balancing sample notebook."""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests as http_requests

# APIM Samples imports
from apimrequests import ApimRequests
from apimtypes import HttpStatusCode
from console import print_info, print_message, print_val


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
        """Return whether a successful request followed the first adaptive wait."""
        if not self.waits:
            return False

        first_wait_run = self.waits[0][0]
        return any(result['run'] > first_wait_run and result['status_code'] == HttpStatusCode.OK for result in self.api_results)

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
    ) -> list[list[dict[str, Any]]]:
        """Execute structured scenarios with one reusable APIM request client."""
        results_by_scenario = []

        for scenario_index, scenario in enumerate(scenarios):
            if scenario_index and pause_seconds > 0:
                self._sleep(pause_seconds)

            self.requests.subscriptionKey = subscription_keys[scenario.api_index]
            print_message(f'Starting API calls for {scenario.label}', blank_above=True)
            results_by_scenario.append(
                self.requests.multiGet(
                    scenario.path,
                    runs=scenario.runs,
                    msg=f'Calling {scenario.label}',
                    sleepMs=scenario.sleep_ms,
                )
            )

        return results_by_scenario

    def run_retry_tracking(self, path: str, runs: int, subscription_key: str) -> RetryTrackingResult:
        """Run adaptive traffic that waits for each parseable 429 Retry-After value."""
        if runs < 1:
            raise ValueError('Retry-tracking runs must be at least 1.')

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

        return RetryTrackingResult(api_results, retry_after_samples, waits)

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
