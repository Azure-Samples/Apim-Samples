"""Sample-owned validation, output selection and bounded smoke-test mechanics."""

import json
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, TypedDict

# APIM Samples imports
from apimrequests import ApimRequests
from apimtypes import AzureOpenAIModel


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
    retry_delays: Sequence[float] = (10, 20, 30, 60, 60),
    sleep: Callable[[float], None] = time.sleep,
) -> SmokeResult:
    """Own the client lifetime and retry only bounded readiness/quota failures.

    Each attempt is a separate non-streaming lab request, not an APIM retry policy.
    Content is inspected but never returned or persisted. Transport/parser failures
    close the session and propagate; rerun after resolving the reported problem.
    """
    if not path.startswith('/') or not isinstance(payload, dict) or payload.get('stream') is True:
        raise ValueError('Smoke tests require an absolute API path and a non-streaming JSON object.')
    if any(delay < 0 for delay in retry_delays):
        raise ValueError('Retry delays must be non-negative.')

    with client_factory() as client:
        for attempt in range(len(retry_delays) + 1):
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

                return SmokeResult(status, attempt + 1, completion, pool, response_model)

            if status not in (401, 403, 404, 429, 500, 502, 503, 504) or attempt == len(retry_delays):
                raise RuntimeError(f'Smoke test failed with HTTP {status} after {attempt + 1} attempt(s); see RUNBOOK.md.')
            sleep(retry_delays[attempt])

    raise RuntimeError('No smoke-test attempt executed.')
