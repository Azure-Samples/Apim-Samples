"""Sample-owned validation, output selection and bounded smoke-test mechanics."""

import json
import math
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

import matplotlib.pyplot as plt

# APIM Samples imports
import charts
from apimrequests import ApimRequests
from apimtypes import AzureOpenAIModel
from console import Column, TableLogger, print_info, print_warning
from htmlreport import HtmlReport


class ModelConfiguration(TypedDict):
    """One model deployment and its dedicated singleton backend pool."""

    name: str
    version: str
    capacity: int
    deploymentName: str
    backendName: str
    poolName: str


@dataclass(frozen = True)
class SmokeResult:
    """Normalized smoke evidence without keys, prompts or completion content."""

    status_code: int
    attempts: int
    has_completion: bool
    backend_pool: str | None = None
    model: str | None = None
    response_time: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen = True)
class ProbeEvidence:
    """Label one completed probe without retaining its request or response body."""

    stage: str
    model_name: str
    result: SmokeResult
    expected_status: int = 200


def validate_configuration(sample_name: str, model_sku: str, capacity: int) -> None:
    """Reject unsafe names and non-PAYG SKUs before starting a deployment."""
    if not isinstance(sample_name, str) or not re.fullmatch(r'aoai-v1-migration-[a-z0-9-]{1,22}', sample_name):
        raise ValueError('sample_name must start with aoai-v1-migration- and contain lowercase letters, digits or hyphens (max 40).')
    if model_sku not in ('Standard', 'GlobalStandard'):
        raise ValueError('Only PAYG Standard and GlobalStandard are supported.')
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
        raise ValueError('Model capacity must be a positive integer.')


def subscription_key(apis: list[dict[str, Any]], api_name: str) -> str:
    """Select exactly one API subscription key; never log the value."""
    matches = [api for api in apis if api.get('name') == api_name]
    if len(matches) != 1:
        raise ValueError(f'Expected exactly one deployment output for {api_name}.')
    key = matches[0].get('subscriptionPrimaryKey')
    if not isinstance(key, str) or not key.strip():
        raise ValueError(f'Missing subscription key for {api_name}.')

    return key


def build_models(sample_name: str, models: Sequence[AzureOpenAIModel], capacity: int) -> list[ModelConfiguration]:
    """Build two distinct model/pool records with deterministic resource names."""
    validate_configuration(sample_name, 'GlobalStandard', capacity)
    if len(models) != 2 or any(not isinstance(model, AzureOpenAIModel) for model in models) or len(set(models)) != 2:
        raise ValueError('Select exactly two different AzureOpenAIModel entries.')
    result: list[ModelConfiguration] = []
    for model in models:
        model_name = model.value.replace('.', '-')
        if not re.fullmatch(r'[a-z0-9-]+', model_name):
            raise ValueError('Model names must produce safe lowercase deployment identifiers.')
        deployment_name = f'{sample_name}-{model_name}'
        result.append({
            'name': model.value, 'version': model.version, 'capacity': capacity,
            'deploymentName': deployment_name, 'backendName': f'{deployment_name}-backend', 'poolName': f'{deployment_name}-pool',
        })
    if len({item['deploymentName'] for item in result}) != 2:
        raise ValueError('Model deployment names must be distinct after normalization.')

    return result


def test(
    client_factory: Callable[[], ApimRequests],
    path: str,
    payload: dict[str, Any],
    *,
    expected_status: int = 200,
    expected_pool: str | None = None,
    expected_model: str | None = None,
    warmup: bool = False,
    retry_delays: Sequence[float] = (10, 20, 30, 60, 60),
    sleep: Callable[[float], None] = time.sleep,
) -> SmokeResult:
    """Own the client lifetime and retry only bounded readiness/quota failures.

    Each attempt is a separate non-streaming lab request, not an APIM retry policy.
    Content is inspected but never returned or persisted. Transport/parser failures
    close the session and propagate; rerun after resolving the reported problem.
    Optional warm-up validates one successful request, then discards its evidence.
    The measured request reuses the client with a fresh bounded readiness budget.
    """
    if not path.startswith('/') or not isinstance(payload, dict) or payload.get('stream') is True:
        raise ValueError('Smoke tests require an absolute API path and a non-streaming JSON object.')
    if any(delay < 0 for delay in retry_delays):
        raise ValueError('Retry delays must be non-negative.')
    if warmup and expected_status != 200:
        raise ValueError('Warm-up requires a successful completion probe.')

    attempt = 0
    with client_factory() as client:
        while True:
            rows = client.multiPost(path, 1, data = payload, printResponse = False)
            if len(rows) != 1 or not isinstance(rows[0], dict) or not isinstance(rows[0].get('status_code'), int):
                raise ValueError('Malformed APIM smoke-test result.')
            status = rows[0]['status_code']
            if status == expected_status:
                body = json.loads(rows[0]['response'])
                if not isinstance(body, dict):
                    raise ValueError('Expected an OpenAI JSON response object.')
                if expected_status == 200:
                    choices = body.get('choices')
                    completion = (
                        isinstance(choices, list) and bool(choices)
                        and isinstance(choices[0], dict) and isinstance(choices[0].get('message'), dict)
                        and isinstance(choices[0]['message'].get('content'), str)
                        and bool(choices[0]['message']['content'].strip())
                    )
                    if not completion:
                        raise ValueError('Successful response did not contain a chat completion.')
                else:
                    completion = False
                    gateway_status = body.get('statusCode')
                    gateway_message = body.get('message')
                    gateway_error = (
                        isinstance(gateway_status, int) and not isinstance(gateway_status, bool)
                        and gateway_status == status and 400 <= gateway_status <= 599
                        and isinstance(gateway_message, str) and bool(gateway_message.strip())
                    )
                    if not isinstance(body.get('error'), dict) and not gateway_error:
                        raise ValueError(
                            'Expected an OpenAI-style error object or an APIM gateway error '
                            'with matching statusCode and a non-empty message.'
                        )

                headers = rows[0].get('headers', {})
                if not isinstance(headers, dict) or any(not isinstance(name, str) for name in headers):
                    raise ValueError('Malformed APIM response headers.')
                pool = next((value for name, value in headers.items() if name.lower() == 'x-migration-backend-pool'), None)
                if pool is not None and not isinstance(pool, str):
                    raise ValueError('Malformed backend pool response header.')
                response_model = body.get('model')
                if response_model is not None and not isinstance(response_model, str):
                    raise ValueError('Malformed response model identifier.')
                if expected_pool is not None and pool != expected_pool:
                    raise ValueError(f'Expected backend pool {expected_pool}, received {pool}.')
                if expected_model is not None and response_model != expected_model:
                    raise ValueError(f'Expected response model {expected_model}, received {response_model}.')

                response_time = rows[0].get('response_time')
                if response_time is not None and (
                    isinstance(response_time, bool) or not isinstance(response_time, (int, float))
                    or not math.isfinite(response_time) or response_time < 0
                ):
                    raise ValueError('Malformed APIM response time.')
                usage = body.get('usage')
                token_counts: list[int | None] = []
                if usage is not None and not isinstance(usage, dict):
                    raise ValueError('Malformed OpenAI token usage.')
                for name in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                    count = usage.get(name) if usage is not None else None
                    if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < 0):
                        raise ValueError(f'Malformed OpenAI {name}.')
                    token_counts.append(count)

                if warmup:
                    print_info('Warm-up validated and excluded from evidence; sending the measured request.')
                    warmup = False
                    attempt = 0
                    continue

                return SmokeResult(status, attempt + 1, completion, pool, response_model, response_time, *token_counts)

            if status not in (401, 403, 404, 429, 500, 502, 503, 504) or attempt == len(retry_delays):
                phase = 'Warm-up' if warmup else 'Smoke test'
                raise RuntimeError(f'{phase} failed with HTTP {status} after {attempt + 1} attempt(s); see RUNBOOK.md.')
            sleep(retry_delays[attempt])
            attempt += 1


def generate_report(probes: Sequence[ProbeEvidence], output_path: Path) -> Path:
    """Print measured evidence, show shared latency charts, and save a local report."""
    if not probes:
        raise ValueError('Run the migration probes before generating a report.')
    if any(probe.result.status_code != probe.expected_status or probe.result.has_completion != (probe.expected_status == 200) for probe in probes):
        raise ValueError('Report evidence must match each probe outcome; rerun the failed probe.')

    description = (
        f'{len(probes)} contract probes, not a throughput or performance benchmark. HTTP 500 for the unknown model is an expected rejection, '
        'not a failed migration. Timings and token counts describe the final response of each probe; earlier readiness attempts and waits '
        'are excluded. Legacy Before also excludes one validated warm-up request per model. '
        'Missing measurements remain empty. No keys, prompts or completion content are retained.'
    )
    report = HtmlReport('Azure OpenAI v1 Migration', 'Legacy baseline, v1 coexistence, and unchanged legacy regression')
    report.add_info_callout('How to read this evidence', description)
    headers = ['Stage', 'Model', 'HTTP', 'Attempts', 'Response Time (ms)', 'Prompt Tokens', 'Completion Tokens', 'Total Tokens', 'Outcome']
    rows = []
    for probe in probes:
        result = probe.result
        rows.append([
            probe.stage, probe.model_name, result.status_code, f'{result.attempts:,}',
            '' if result.response_time is None else f'{result.response_time * 1000:,.1f}',
            *['' if count is None else f'{count:,}' for count in (result.prompt_tokens, result.completion_tokens, result.total_tokens)],
            'Completion' if result.has_completion else 'Expected rejection',
        ])
    table = TableLogger()
    table.header(*(Column(name, align = '>' if 2 <= index <= 7 else '<') for index, name in enumerate(headers)))
    table.populate(rows)
    table.print()
    report.add_table('Contract Probe Evidence', headers, rows, 'Final-response measurements, with the intentional negative probe labeled explicitly.')
    report.add_table(
        'Verified Model Routing', ['Stage', 'Model', 'Backend Pool', 'Response Model'],
        [[probe.stage, probe.model_name, probe.result.backend_pool or '', probe.result.model or ''] for probe in probes if probe.result.has_completion],
        'Both contracts use the same singleton pool for each model. Exact pool and snapshot assertions remain in the notebook.',
    )

    model_names = list(dict.fromkeys(probe.model_name for probe in probes if probe.result.has_completion))
    for model_name in model_names:
        model_probes = [probe for probe in probes if probe.model_name == model_name and probe.result.has_completion]
        if any(probe.result.response_time is None for probe in model_probes):
            message = f'Latency chart unavailable for {model_name}: rerun its probes to capture response times.'
            print_warning(message)
            report.add_info_callout('Missing response times', message)
            continue
        chart_rows = [
            {
                'run': probe.stage, 'status_code': probe.result.status_code,
                'response_time': probe.result.response_time, 'response': json.dumps({'index': 1}),
            }
            for probe in model_probes
        ]
        title = f'{model_name}: Legacy Before / v1 / Legacy After'
        figure = charts.BarChart(
            title, 'Contract Probe', 'Response Time (ms)', chart_rows,
            fig_text = 'Final successful request only; warm-up and readiness waits are excluded. Three probes do not establish a latency trend.\n'
                       'The expected HTTP 500 rejection is shown in the evidence table, not in this successful-contract comparison.',
            backend_labels = {1: f'{model_name} singleton pool'},
        ).render()
        try:
            figure.set_size_inches(12, 6)
            figure.subplots_adjust(right = 0.72, bottom = 0.22)
            report.add_figure(title, figure, 'Compare contract stages for the same model, not different models or capacity tiers.')
            plt.show()
        finally:
            plt.close(figure)

    return report.write(output_path)
