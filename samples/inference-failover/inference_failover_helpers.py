"""Runtime helpers for the inference-failover sample notebook."""

import json
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir
from typing import Any

# APIM Samples imports
import charts
import matplotlib.pyplot as plt
import pandas as pd
import requests as http_requests
from apimtesting import ApimTesting
from apimtypes import SUBSCRIPTION_KEY_PARAMETER_NAME
from console import print_info, print_message, print_warning
from htmlreport import HtmlList, HtmlReport, HtmlSuccess, HtmlText, HtmlWarning


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
    retry_counts: dict[int | None, int]


@dataclass(frozen=True)
class InferenceReportContext:
    """Contain deployment metadata and Azure resources linked from the local report."""

    sample_folder: str
    apim_source_region: str
    deployment_name: str
    resource_group_name: str
    tenant_id: str
    subscription_id: str
    apim_name: str
    workbook_id: str
    log_analytics_id: str


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
        malformed_headers = {**probe_headers, 'Content-Type': 'application/json'}

        return ContractProbeResults(
            success=session.post(route, headers=probe_headers, json=payload, timeout=120),
            malformed=session.post(route, headers=malformed_headers, data='{"messages":', timeout=120),
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
            backend_retry = parse_backend_retry(response, required=response.status_code < 500)
            validate_status(response)
            backend_retry_label = backend_retry if backend_retry is not None else 'unknown'
            print_info(f'Run {run_index}/{scenario.runs}: {response.status_code} via {backend_url}; X-Backend-Retry={backend_retry_label} ({response_time:.2f}s)')
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


def parse_backend_retry(response: http_requests.Response, *, required: bool = True) -> int | None:
    """Parse a caller-visible retry count, optionally allowing missing metadata."""
    retry_header = response.headers.get('X-Backend-Retry')
    if retry_header is None:
        if required:
            raise ValueError('Required X-Backend-Retry response header is missing.')

        return None

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
    retry_counts: dict[int | None, int] = {}
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
        served_backend_urls=sorted({result['backend_url'] for result in results if result['status_code'] == 200 and result['backend_url'] != 'unknown'}),
        retry_counts=dict(sorted(retry_counts.items(), key=lambda item: (item[0] is None, item[0] if item[0] is not None else 0))),
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


def with_one_based_row_index(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a frame copy with a display-oriented one-based row index."""
    result = frame.copy()
    result.index = range(1, len(result) + 1)
    result.index.name = 'Row'

    return result


def format_gateway_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    """Return gateway distribution values formatted for display."""
    result = frame.copy()
    average_backend_ms = pd.to_numeric(result['AverageBackendMs'].astype(str).str.replace(',', '', regex=False), errors='coerce')
    success_rate = pd.to_numeric(result['SuccessRate'].astype(str).str.rstrip('%'), errors='coerce')
    result['AverageBackendMs'] = average_backend_ms.map(lambda value: '' if pd.isna(value) else f'{value:,.1f}')
    result['SuccessRate'] = success_rate.map(lambda value: '' if pd.isna(value) else f'{value:.2f}%')
    if 'Backend URL' in result.columns:
        backend_names = result['Backend URL'].str.extract(r'/deployments/([a-z]-[^/]+)', expand=False)
        result['Backend'] = backend_names.str.replace('-', ') ', n=1, regex=False)
        missing_backend = backend_names.isna()
        client_errors = pd.to_numeric(result.get('Client Errors', pd.Series(0, index=result.index)), errors='coerce').fillna(0)
        server_errors = pd.to_numeric(result.get('Server Errors', pd.Series(0, index=result.index)), errors='coerce').fillna(0)
        result.loc[missing_backend, 'Backend'] = 'Backend not recorded'
        result.loc[missing_backend & server_errors.gt(0), 'Backend'] = 'APIM failure (no final backend recorded)'
        result.loc[missing_backend & server_errors.eq(0) & client_errors.gt(0), 'Backend'] = 'Gateway rejection (no backend call)'
        result = result.drop(columns=['Backend URL'])
    return with_one_based_row_index(result)


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
    unknown_retry_count = retry_counts.get(None, 0)
    known_retry_counts = {retry_count: count for retry_count, count in retry_counts.items() if retry_count is not None}
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
    retried_requests = sum(count for retry_count, count in known_retry_counts.items() if retry_count > 0)
    backend_retries_absorbed = sum(retry_count * count for retry_count, count in known_retry_counts.items())
    caller_visible_failures = non_200_responses
    observed_backend_failures = backend_retries_absorbed + caller_visible_failures
    terminal_503_responses = status_counts.get(503, 0)
    priority_mix = '\n'.join(f'P{priority}: {", ".join(weight_mix)}' for priority, weight_mix in sorted(weights_by_priority.items()))
    retry_mix_lines = [f'{retry_count}: {count} ({count / total_requests:.1%})' for retry_count, count in sorted(known_retry_counts.items()) if retry_count > 0]
    if unknown_retry_count:
        retry_mix_lines.append(f'Unknown: {unknown_retry_count} ({unknown_retry_count / total_requests:.1%})')
    retry_mix = '\n'.join(retry_mix_lines) or 'None'
    if unresolved_requests:
        unresolved_mix = f'No resolved backend: {unresolved_requests} ({unresolved_requests / total_requests:.1%})'
        priority_mix = f'{priority_mix}\n{unresolved_mix}' if priority_mix else unresolved_mix

    observations = []
    if non_200_responses:
        observations.append(f'{non_200_responses}/{total_requests} ({non_200_responses / total_requests:.1%}) caller-visible non-200 responses')
    else:
        observations.append('All requests returned HTTP 200')
    if retried_requests:
        observations.append(f'{retried_requests}/{total_requests} returned after a retry')
    elif unknown_retry_count:
        observations.append('retry metadata was unavailable for one or more 5xx responses')
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
    if unknown_retry_count:
        observations.append(f'APIM reported {backend_retries_absorbed} confirmed backend retries; {unknown_retry_count} responses did not expose X-Backend-Retry')
    else:
        observations.append(f'APIM absorbed {backend_retries_absorbed} backend failures and sent {caller_visible_failures} failures to callers')
    if observed_backend_failures and not unknown_retry_count:
        shielded_percentage = backend_retries_absorbed / observed_backend_failures * 100
        observations.append(f'APIM prevented {shielded_percentage:.1f}% of observed failed backend attempts from reaching callers')
    elif not unknown_retry_count:
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


def generate_local_html_report(
    context: InferenceReportContext,
    tests: ApimTesting,
    scenario_results: Sequence[list[dict[str, Any]]],
    backend_url_indexes: Mapping[str, Mapping[str, int]],
    backend_labels: Mapping[str, Mapping[int, str]],
    distribution_frame: pd.DataFrame | None = None,
    token_frame: pd.DataFrame | None = None,
    output_path: Path | None = None,
) -> Path:
    """Generate the self-contained inference failover run report."""
    scenario_groups = _build_report_scenario_groups(scenario_results, backend_url_indexes, backend_labels)
    report = HtmlReport(
        'Inference Failover Run Report',
        f'APIM source region: {context.apim_source_region} | Deployment: {context.deployment_name} | Resource group: {context.resource_group_name}',
    )
    success_rate = (tests.tests_passed / tests.total_tests * 100) if tests.total_tests else 0
    report.add_metrics(
        'Scenario Test Summary',
        {
            'Result': 'Passed' if not tests.tests_failed and tests.total_tests else 'Needs review',
            'Tests': tests.total_tests,
            'Passed': tests.tests_passed,
            'Failed': tests.tests_failed,
            'Success rate': f'{success_rate:.1f}%',
        },
        highlight_success=False,
    )
    report.add_info_callout(
        'Lab Capacity Is Intentionally Low',
        'Each regional Azure OpenAI deployment is intentionally configured at 1,000 TPM so that concentrated requests trigger observable failover. '
        'This is a learning configuration, not production sizing guidance. With appropriately sized production capacity, '
        'caller-visible success rates should be substantially higher and, normally, close to perfect.',
    )
    if tests.errors:
        report.add_table('Assertion Failures', ['Failure'], [[error] for error in tests.errors])

    scenario_definitions = [scenario for _, scenarios in scenario_groups for scenario in scenarios]
    scenario_request_count = sum(len(results) for _, _, _, results, _, _ in scenario_definitions)
    if scenario_request_count and all(result['status_code'] == 200 for _, _, _, results, _, _ in scenario_definitions for result in results):
        report.add_success_callout(
            'All scenario requests returned HTTP 200',
            f'All {scenario_request_count} controlled inference requests completed successfully. APIM served the full run without a caller-visible error.',
        )

    for model_name, model_scenarios in scenario_groups:
        report.add_table(
            HtmlText(f'Scenario Outcomes: {model_name}', bold_tokens=(model_name,)),
            ['', 'Test #', 'Scenario', 'Requests', 'HTTP 200', 'Other', 'APIM retries', 'Priority / weight mix', 'What the data says'],
            [build_scenario_report_row(test_id, title, results, url_index, labels) for test_id, title, _, results, url_index, labels in model_scenarios],
            HtmlText(
                'The green checkmark indicates that every request returned HTTP 200 from the caller perspective, '
                'including successes after APIM retries. '
                'The amber warning triangle indicates that one or more requests returned a caller-visible non-200 response. '
                'APIM retries lists only non-zero X-Backend-Retry values absorbed by APIM after the initial backend attempt. '
                'Priority / weight mix aggregates concrete Azure OpenAI destinations into APIM routing tiers and weights. '
                'The interpretation highlights failures APIM absorbed, failover depth, and caller-visible outcomes.',
                bold_tokens=(
                    'The green checkmark indicates that every request returned HTTP 200',
                    'The amber warning triangle indicates that one or more requests returned a caller-visible non-200 response',
                ),
            ),
            column_widths=['4%', '5%', '10%', '6%', '6%', '5%', '11%', '17%', '36%'],
        )

    for test_id, title, description, results, _, labels in scenario_definitions:
        _add_scenario_figure(report, context.apim_source_region, f'{test_id}) {title}', description, results, labels)

    _add_distribution_telemetry(report, distribution_frame)
    _add_token_telemetry(report, token_frame)
    report.add_links('Azure Views', _build_azure_links(context))

    destination = output_path or Path(gettempdir()) / 'apim-samples-reports' / context.sample_folder / 'inference-failover-report.html'

    return report.write(destination)


def _build_report_scenario_groups(
    scenario_results: Sequence[list[dict[str, Any]]],
    backend_url_indexes: Mapping[str, Mapping[str, int]],
    backend_labels: Mapping[str, Mapping[int, str]],
) -> list[tuple[str, list[tuple[str, str, str, list[dict[str, Any]], Mapping[str, int], Mapping[int, str]]]]]:
    if len(scenario_results) != 6:
        raise ValueError('The inference report requires exactly six scenario result sets.')

    required_models = ('gpt-5.1', 'gpt-4.1-mini')
    missing_models = [model for model in required_models if model not in backend_url_indexes or model not in backend_labels]
    if missing_models:
        raise ValueError(f'Missing report backend metadata for: {", ".join(missing_models)}')

    return [
        (
            'gpt-5.1',
            [
                (
                    'A-1',
                    'Baseline Warm Path',
                    'Small control requests against the gpt-5.1 pool before deliberate pressure begins.',
                    scenario_results[0],
                    backend_url_indexes['gpt-5.1'],
                    backend_labels['gpt-5.1'],
                ),
                (
                    'A-2',
                    'Sustained Pressure',
                    'Larger requests without spacing exercise gpt-5.1 failover tiers.',
                    scenario_results[2],
                    backend_url_indexes['gpt-5.1'],
                    backend_labels['gpt-5.1'],
                ),
                (
                    'A-3',
                    'Paced Recovery',
                    'Spaced requests show recovery behavior after sustained pressure.',
                    scenario_results[4],
                    backend_url_indexes['gpt-5.1'],
                    backend_labels['gpt-5.1'],
                ),
                (
                    'A-4',
                    'Terminal Exhaustion',
                    'A hard burst probes deep fallback and terminal responses.',
                    scenario_results[5],
                    backend_url_indexes['gpt-5.1'],
                    backend_labels['gpt-5.1'],
                ),
            ],
        ),
        (
            'gpt-4.1-mini',
            [
                (
                    'B-1',
                    'Baseline Warm Path',
                    'Small control requests against the independent gpt-4.1-mini pool.',
                    scenario_results[1],
                    backend_url_indexes['gpt-4.1-mini'],
                    backend_labels['gpt-4.1-mini'],
                ),
                (
                    'B-2',
                    'Sustained Pressure',
                    'Unpaced load confirms that gpt-4.1-mini fallback remains model-safe.',
                    scenario_results[3],
                    backend_url_indexes['gpt-4.1-mini'],
                    backend_labels['gpt-4.1-mini'],
                ),
            ],
        ),
    ]


def _add_scenario_figure(
    report: HtmlReport,
    apim_source_region: str,
    title: str,
    description: str,
    results: list[dict[str, Any]],
    labels: Mapping[int, str],
) -> None:
    figure = charts.BarChart(
        api_results=results,
        title=f'{title} - APIM source: {apim_source_region}',
        x_label='Run #',
        y_label='Response Time (ms)',
        fig_text=description,
        backend_labels=dict(labels),
    ).render()
    try:
        report.add_figure(title, figure, description)
    finally:
        plt.close(figure)


def _add_distribution_telemetry(report: HtmlReport, distribution_frame: pd.DataFrame | None) -> None:
    if distribution_frame is None:
        print_warning('Gateway distribution telemetry is not available for the HTML report yet')
        return

    report_frame = with_backend_identifier(distribution_frame)
    report.add_table(
        'Gateway-Recorded Backend Distribution',
        report_frame.columns.tolist(),
        report_frame.values.tolist(),
        'Log Analytics rows summarize the destination selected for each gateway request.',
    )
    figure, axis = plt.subplots(figsize=(12, 5))
    try:
        report_frame.pivot(index='API', columns='Backend', values='Requests').fillna(0).plot(kind='bar', ax=axis)
        axis.set_title('Gateway-recorded request distribution by backend')
        axis.set_xlabel('API')
        axis.set_ylabel('Requests')
        figure.subplots_adjust(bottom=0.4)
        report.add_figure('Gateway-Recorded Request Distribution', figure)
    finally:
        plt.close(figure)


def _add_token_telemetry(report: HtmlReport, token_frame: pd.DataFrame | None) -> None:
    if token_frame is None:
        print_warning('Token telemetry is not available for the HTML report yet')
        return

    report.add_table(
        'LLM Token Volume',
        token_frame.columns.tolist(),
        token_frame.values.tolist(),
        'Token totals confirm that LLM diagnostics captured successful inference traffic.',
    )
    figure, axis = plt.subplots(figsize=(8, 4))
    try:
        token_frame.groupby('API')['TotalTokens'].sum().plot(kind='bar', ax=axis)
        axis.set_title('LLM token volume by inference API')
        axis.set_xlabel('Inference API')
        axis.set_ylabel('Total tokens')
        axis.tick_params(axis='x', rotation=0)
        figure.tight_layout()
        report.add_figure('LLM Token Volume By Inference API', figure)
    finally:
        plt.close(figure)


def _build_azure_links(context: InferenceReportContext) -> dict[str, str]:
    portal_base = f'https://portal.azure.com/#@{context.tenant_id}/resource'
    apim_id = f'/subscriptions/{context.subscription_id}/resourceGroups/{context.resource_group_name}/providers/Microsoft.ApiManagement/service/{context.apim_name}'

    return {
        'Workbook': f'{portal_base}{context.workbook_id}/workbook',
        'Log Analytics': f'{portal_base}{context.log_analytics_id}/logs',
        'API Management': f'{portal_base}{apim_id}/overview',
    }
