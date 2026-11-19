"""Configuration and sanitized live-probe mechanics for Azure OpenAI v1 Routing.

Autoreload: reload_conditional
Recompute configuration and recreate probe results after changing their schemas.
"""

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, TypedDict
from urllib.parse import urlsplit

# APIM Samples imports
from ai_models import ApprovedModel
from aoai_models import to_deployment_config
from apimrequests import ApimRequests


class ModelConfiguration(TypedDict):
    """The same deployment identity is installed on every account."""

    name: str
    version: str
    capacity: int
    deploymentName: str


@dataclass(frozen = True)
class ProbeResult:
    """Evidence of generated text from either pathway, without retaining its content."""

    status: int
    error_code: str | None
    error_message: str | None
    completion: bool
    pool: str
    request_id: str


def build_models(sample_name: str, models: Sequence[ApprovedModel], sku: str, capacity: int) -> list[ModelConfiguration]:
    """Validate PAYG configuration and keep model selectors equal to deployment names."""
    if not isinstance(sample_name, str) or not re.fullmatch(r'aoai-v1-routing-[a-z0-9-]{1,16}', sample_name):
        raise ValueError('Use aoai-v1-routing- plus 1-16 lowercase letters, digits or hyphens.')
    if sku not in ('Standard', 'GlobalStandard'):
        raise ValueError('Only Standard and GlobalStandard PAYG deployments are permitted.')
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
        raise ValueError('Capacity must be a positive integer.')
    if not models or any(not isinstance(model, ApprovedModel) or model.value.provider != 'openai' for model in models):
        raise ValueError('Select at least one approved OpenAI model.')
    names = [model.model_name for model in models]
    if len(set(names)) != len(names) or any(not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,47}', name) for name in names):
        raise ValueError('Deployment names must be distinct bounded lowercase aliases.')
    if any(len(f'{sample_name}-{name}-global-standard') > 80 for name in names):
        raise ValueError('The namespace and model name exceed the backend resource name budget.')

    return [{**to_deployment_config(model, capacity), 'deploymentName': model.model_name} for model in models]


def subscription_key(apis: Sequence[dict[str, Any]], api_name: str) -> str:
    """Select a shared API-module subscription without printing its key."""
    matches = [api for api in apis if api.get('name') == api_name]
    if len(matches) != 1 or not isinstance(matches[0].get('subscriptionPrimaryKey'), str) or not matches[0]['subscriptionPrimaryKey'].strip():
        raise ValueError('Expected exactly one API output with a subscription key.')

    return matches[0]['subscriptionPrimaryKey']


def probe(
    client_factory: Callable[[], ApimRequests],
    path: str,
    payload: dict[str, Any] | str,
    *,
    headers: dict[str, str] | None = None,
) -> ProbeResult:
    """Send exactly one request; close the shared client even on transport/parse errors.

    No readiness retries or delays hide upstream failures. The caller declares and
    asserts expected status, error identity and selected pool in the notebook.
    Responses success requires completed assistant output; Chat Completions uses choices.
    """
    if not isinstance(path, str) or not path.startswith('/') or not isinstance(payload, (dict, str)):
        raise ValueError('A rooted API path and JSON object or non-object JSON string are required.')
    with client_factory() as client:
        rows = client.multiPost(path, 1, data = payload, headers = headers, printResponse = False)
        if len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValueError('Expected exactly one APIM response.')
        row = rows[0]
        status = row.get('status_code')
        if isinstance(status, bool) or not isinstance(status, int) or not 100 <= status <= 599:
            raise ValueError('Invalid response status.')
        if not isinstance(row.get('response'), str):
            raise ValueError('Expected a serialized response body.')
        body = json.loads(row['response'])
        response_headers = row.get('headers')
        if not isinstance(body, dict) or not isinstance(response_headers, dict):
            raise ValueError('Expected a JSON object and response headers.')
        normalized = {str(key).lower(): value for key, value in response_headers.items()}
        request_id = normalized.get('x-routing-request-id', '')
        pool = normalized.get('x-routing-pool', '')
        if not isinstance(request_id, str) or not re.fullmatch(r'[0-9a-fA-F-]{36}', request_id):
            raise ValueError('Missing or malformed request correlation ID.')
        if not isinstance(pool, str) or (pool and not re.fullmatch(r'[a-z0-9.-]{1,100}', pool)):
            raise ValueError('Malformed pool evidence.')
        if status >= 400:
            error = body.get('error')
            if not isinstance(error, dict):
                raise ValueError('Expected a sanitized error object, not just a failure status.')
            code, message = error.get('code'), error.get('message')
            safe_codes = {
                'ModelNotAvailable', 'model_not_available', 'InvalidRequest', 'SubscriptionNotAllowed',
                'DeploymentNotFound', 'model_not_found', 'InvalidRequestError', 'BadRequest', 'RateLimitReached',
                'UpstreamError', 'UpstreamUnavailable', 'UpstreamTimeout', 'GatewayError',
            }
            safe_messages = {
                'The specified model is not available for use',
                'The request payload is invalid.',
                'The subscription is not permitted for this scenario.',
                'The upstream service rejected the request.',
                'The upstream service is unavailable.',
                'The upstream request timed out.',
                'The gateway could not complete the request.',
            }
            if not isinstance(code, str) or not isinstance(message, str) or code not in safe_codes or message not in safe_messages:
                raise ValueError('Response error is not the sample sanitized error contract.')

            return ProbeResult(status, code, message, False, pool, request_id)
        if urlsplit(path).path.endswith('/responses'):
            operation = 'Responses'
            output = body.get('output')
            completion = (
                body.get('object') == 'response' and body.get('status') == 'completed'
                and body.get('error') is None and isinstance(output, list)
                and any(
                    isinstance(item, dict) and item.get('type') == 'message'
                    and item.get('role') == 'assistant' and item.get('status') == 'completed'
                    and isinstance(item.get('content'), list)
                    and any(
                        isinstance(content, dict) and content.get('type') == 'output_text'
                        and isinstance(content.get('text'), str) and bool(content['text'].strip())
                        for content in item['content']
                    )
                    for item in output
                )
            )
        else:
            operation = 'Chat Completions'
            choices = body.get('choices')
            completion = (
                isinstance(choices, list) and bool(choices) and isinstance(choices[0], dict)
                and isinstance(choices[0].get('message'), dict)
                and isinstance(choices[0]['message'].get('content'), str)
                and bool(choices[0]['message']['content'].strip())
            )
        if status != 200 or not completion:
            raise ValueError(f'Expected a real non-streaming {operation} result.')

        return ProbeResult(status, None, None, True, pool, request_id)
