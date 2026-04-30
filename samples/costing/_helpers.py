"""
Costing-sample-private helpers.

These functions are intentionally scoped to the costing sample because they
encode costing-specific contracts (the local `bu-request-counts.local.json`
schema, the fake-JWT shape used by the emit-metric policy, the retry profile
appropriate for the traffic-generation cells). They are NOT part of the
shared helpers in `shared/python/` to avoid leaking sample-specific concerns
into other samples.

Imported by `samples/costing/create.ipynb` after the sample folder is added
to `sys.path` in cell A1 (Initialize).
"""

import base64
import json
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests as http_requests
import utils
from apimtypes import API, HTTP_VERB, APIOperation, GET_APIOperation2, PolicyFragment
from azure_resources import get_apim_subscription_key, run
from console import Column, TableLogger, print_error, print_info, print_ok, print_plain, print_val, print_warning
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def make_fake_jwt(appid: str) -> str:
    """Create a minimal unsigned JWT carrying an `appid` claim.

    The emit-metric policy reads the `appid` (or `azp`) claim from the
    bearer token to extract caller identity. Signing is irrelevant for the
    sample because the policy does not validate the token.

    Args:
        appid: The Entra ID application ID to embed in the JWT payload.

    Returns:
        A three-segment JWT string (header.payload.signature) with an
        empty signature segment.
    """
    header = base64.urlsafe_b64encode(json.dumps({'alg': 'none', 'typ': 'JWT'}).encode()).rstrip(b'=').decode()
    payload = base64.urlsafe_b64encode(json.dumps({'appid': appid}).encode()).rstrip(b'=').decode()

    return f'{header}.{payload}.'


def build_session(
    request_headers: dict | None,
    allow_insecure_tls: bool,
    *,
    extra_headers: dict | None = None,
    with_retries: bool = False,
) -> http_requests.Session:
    """Create a `requests.Session` with TLS verification and headers preconfigured.

    Args:
        request_headers: Headers returned by `utils.get_endpoint(...)` (may be None).
        allow_insecure_tls: True when the endpoint uses a self-signed certificate
            (e.g. Application Gateway infrastructures). Disables TLS verification.
        extra_headers: Optional additional headers to set on the session
            (e.g. `Content-Type`, `api-key`, `Authorization`).
        with_retries: When True, mounts an HTTPAdapter that retries on 502/503/504
            and on transient connection / read errors. Useful for the heavy
            BU traffic loop in cell C1 where a single TLS blip should not abort
            the whole run.

    Returns:
        A configured `requests.Session`. Caller is responsible for closing it.
    """
    session = http_requests.Session()
    session.verify = not allow_insecure_tls
    if request_headers:
        session.headers.update(request_headers)
    if extra_headers:
        session.headers.update(extra_headers)

    if with_retries:
        retry_strategy = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
            allowed_methods=['GET', 'POST'],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount('https://', adapter)
        session.mount('http://', adapter)

    return session


def purge_traffic_source(local_data_path: Path, source_name: str) -> bool:
    """Remove a single named entry from `bu-request-counts.local.json` if present.

    Each traffic-generation cell calls this *before* checking whether it should
    actually run. That keeps the persisted JSON honest when the corresponding
    `run_*` toggle is flipped off between runs — otherwise the file would
    still show last run's request counts and mislead the workbook cross-check.

    Args:
        local_data_path: Path to the local JSON file (typically returned by
            `utils.determine_policy_path('bu-request-counts.local.json', ...)`).
        source_name: The `name` field of the traffic-source entry to remove
            (e.g. `'subscription-based-costing'`, `'ai-gateway-aoai'`).

    Returns:
        True if an entry was removed (and the file was rewritten),
        False if the file is missing or contained no matching entry.
    """
    if not local_data_path.exists():
        return False

    existing = json.loads(local_data_path.read_text(encoding='utf-8'))
    sources = existing.get('trafficSources', [])
    filtered = [s for s in sources if s.get('name') != source_name]

    if len(filtered) == len(sources):
        return False

    existing['trafficSources'] = filtered
    existing['generatedUtc'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    local_data_path.write_text(json.dumps(existing, indent=2), encoding='utf-8')

    return True


def persist_traffic_source(
    local_data_path: Path,
    *,
    sample_folder: str,
    rg_name: str,
    apim_name: str,
    source_entry: dict[str, Any],
) -> None:
    """Append-or-replace a single traffic-source entry in the local JSON file.

    Replacement is keyed by `source_entry['name']` so each cell can call this
    idempotently on re-runs. The top-level `generatedUtc` is always refreshed.

    Args:
        local_data_path: Path to `bu-request-counts.local.json`.
        sample_folder: Sample folder name, persisted as `sampleFolder`.
        rg_name: Resource group name, persisted as `resourceGroup`.
        apim_name: APIM service name, persisted as `apimService`.
        source_entry: The traffic-source dict to insert. Must contain a
            `name` key; existing entries with the same name are replaced.
    """
    existing = json.loads(local_data_path.read_text(encoding='utf-8')) if local_data_path.exists() else {}
    sources = [s for s in existing.get('trafficSources', []) if s.get('name') != source_entry['name']]
    sources.append(source_entry)

    persisted = {
        'sampleFolder': sample_folder,
        'resourceGroup': rg_name,
        'apimService': apim_name,
        'generatedUtc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'trafficSources': sources,
    }
    local_data_path.write_text(json.dumps(persisted, indent=2), encoding='utf-8')


def send_requests(
    session: http_requests.Session,
    method: str,
    url: str,
    count: int,
    *,
    headers: dict | None = None,
    timeout: float = 30,
) -> int:
    """Send `count` requests on `session`; returns the number that received an HTTP response.

    Each call is wrapped in a try/except so a single transport error does not abort
    the loop. Used by the traffic-generation cells (7/8/11) to keep their
    delivered-vs-planned tracking consistent: the returned value mirrors what
    backend logs (ApiManagementGatewayLogs) will show, while the caller's `count`
    argument represents the intended (planned) traffic.

    Args:
        session: A `requests.Session` (typically built via `build_session`).
        method: HTTP verb, e.g. `'GET'` or `'POST'`.
        url: Target URL.
        count: Number of requests to send.
        headers: Optional per-request headers (merged with session headers by
            `requests`). Use this for the per-call `api-key` or `Authorization`
            header that varies between iterations of the outer loop.
        timeout: Per-request timeout in seconds.

    Returns:
        The number of requests that received an HTTP response from APIM
        (any status code). Requests that failed with a transport error
        (timeout, TLS reset, DNS, etc.) are excluded.
    """
    delivered = 0
    for _ in range(count):
        try:
            session.request(method, url, headers=headers, timeout=timeout)
            delivered += 1
        except http_requests.RequestException:
            # Intentionally ignore transport-level failures so one failed call
            # does not abort the batch; only requests that received an HTTP
            # response are counted as delivered.
            continue
    return delivered


def get_traffic_endpoint(
    deployment,
    rg_name: str,
    apim_gateway_url: str,
    apim_name: str,
    *,
    api_id: str,
) -> tuple[str, dict, bool, str]:
    """Resolve the gateway endpoint and APIM subscription key for a traffic cell.

    Wraps the `utils.get_endpoint(...)` + `get_apim_subscription_key(...)` pair
    that every C/D traffic cell repeats. Raises `RuntimeError` if the APIM
    subscription key cannot be retrieved so callers can fail fast.

    Args:
        deployment: The infrastructure type (passed straight to `utils.get_endpoint`).
        rg_name: Resource group name.
        apim_gateway_url: Gateway URL from deployment outputs.
        apim_name: APIM service name.
        api_id: The APIM-side API identifier (e.g. `f'api-{api_prefix}aoai-gateway'`)
            used to look up the per-API subscription key.

    Returns:
        `(endpoint_url, request_headers, allow_insecure_tls, subscription_key)`.
    """
    endpoint_url, request_headers, allow_insecure_tls = utils.get_endpoint(deployment, rg_name, apim_gateway_url)
    subscription_key = get_apim_subscription_key(apim_name, rg_name, sid=api_id)

    if not subscription_key:
        raise RuntimeError(f'Could not retrieve subscription key for "{api_id}"')

    return endpoint_url, request_headers, allow_insecure_tls, subscription_key


def acquire_entraid_token(
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> tuple[str, dict] | None:
    """Acquire an Entra ID access token via the client-credentials flow.

    Used by cell C3 (real-JWT validation). Returns `None` and prints an error
    if the token endpoint responds with a non-200 status.

    Args:
        tenant_id: Entra ID tenant ID.
        client_id: App registration's application (client) ID.
        client_secret: App registration's client secret.

    Returns:
        `(access_token, claims)` on success, where `claims` is the decoded
        JWT payload as a dict. Returns `None` if token acquisition failed.
    """
    token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
    response = http_requests.post(
        token_url,
        data={
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': f'api://{client_id}/.default',
        },
        timeout=30,
    )

    if response.status_code != 200:
        print_error(f'Token acquisition failed ({response.status_code}): {response.text[:300]}')
        return None

    access_token = response.json().get('access_token', '')
    payload_part = access_token.split('.')[1]
    payload_part += '=' * (4 - len(payload_part) % 4)  # pad base64
    claims = json.loads(base64.urlsafe_b64decode(payload_part))

    return access_token, claims


def send_aoai_traffic(
    session: http_requests.Session,
    chat_url: str,
    caller_headers: dict,
    count: int,
    *,
    chat_body: dict,
    stream_body: dict,
) -> tuple[int, int, int, int, bool]:
    """Send `count` AOAI requests alternating non-streaming / streaming.

    Encapsulates the inner request loop used by cell D1's per-(BU, model) loop:
    even iterations send non-streaming chat completions, odd iterations send
    streaming requests with `stream_options.include_usage = true` so APIM
    captures token counts in `ApiManagementGatewayLlmLog`. On the first timeout
    the function bails out for the rest of `count` to avoid stacking
    cold-start delays into multi-minute hangs.

    Args:
        session: Pre-configured `requests.Session` (built via `build_session`).
        chat_url: Full chat-completions URL for the target deployment.
        caller_headers: Per-call headers (api-key for the BU + Authorization JWT).
        count: Total number of requests to send for this (BU, model) cell.
        chat_body: JSON body for non-streaming requests.
        stream_body: JSON body for streaming requests (must include `stream: True`
            and `stream_options.include_usage: True`).

    Returns:
        `(non_streaming_delivered, streaming_delivered, planned_ns, planned_s, bailed)`.
        `*_delivered` counts only requests that returned an HTTP response.
        `bailed` is True if a timeout caused the loop to exit early.
    """
    non_streaming_count = 0
    streaming_count = 0
    planned_non_streaming = 0
    planned_streaming = 0
    bailed = False

    for j in range(count):
        if bailed:
            break

        use_streaming = j % 2 == 1
        if use_streaming:
            planned_streaming += 1
        else:
            planned_non_streaming += 1

        body = stream_body if use_streaming else chat_body

        try:
            r = session.post(
                chat_url,
                json=body,
                headers=caller_headers,
                timeout=45 if use_streaming else 30,
                stream=use_streaming,
            )
            if use_streaming and r.status_code == 200:
                # Drain SSE stream so APIM logs the final chunk (with usage).
                for _ in r.iter_lines(decode_unicode=True):
                    pass
        except http_requests.Timeout:
            print_warning(f'  Timeout on request {j + 1}/{count}; skipping remaining requests')
            bailed = True
            continue
        except http_requests.RequestException:
            continue

        # 4xx/5xx still count: they appear in ApiManagementGatewayLogs.
        if use_streaming:
            streaming_count += 1
        else:
            non_streaming_count += 1

    return non_streaming_count, streaming_count, planned_non_streaming, planned_streaming, bailed


def print_portal_links(items: list[tuple[str, str | None]]) -> None:
    """Print a prominent "NEXT STEP" box with the workbook URL, then numbered links.

    The first item is assumed to be the workbook (the primary action).
    All items are printed as a numbered reference list for easy cross-checking.

    Each item is a `(label, url)` tuple. When `url` is None or empty, the
    entry is rendered as `(not deployed)` so the numbering still reflects the
    intended priority order.

    Args:
        items: Ordered list of `(label, url_or_none)` tuples. First item should be workbook.
    """

    print('')
    print('================================================================================')
    print_info('NEXT STEP: OPEN THE AZURE MONITOR WORKBOOK')
    print('================================================================================')
    print_info('1) Copy the URL below')
    print_info('2) Paste it into your browser address bar')
    print_info('3) Press Enter')
    print('')

    # Extract and highlight workbook URL from the first item
    if items:
        workbook_label, workbook_url = items[0]
        if workbook_url:
            print_val('WORKBOOK URL', workbook_url)
        else:
            print_warning(f'{workbook_label} is not available')
    else:
        print_warning('No portal links provided')

    print('')
    print_info('Additional portal links for reference:')
    print('')

    n = 0
    for label, url in items:
        n += 1
        print_info(f'{n}. {label}')
        if url:
            print_plain(f'       {url}')
        else:
            print_plain('   (not deployed)')
        print_plain()


# ---------------------------------------------------------------------------
# API + policy-fragment assembly (called from cell A1 / Initialize)
# ---------------------------------------------------------------------------


def build_costing_apis(
    api_prefix: str,
    sample_folder: str,
    tags: list[str],
    *,
    enable_entraid_tracking: bool,
    enable_token_tracking: bool,
    enable_foundry: bool,
    force_stream_include_usage: bool,
) -> tuple[list[API], list[PolicyFragment], dict[str, str]]:
    """Build the costing sample's APIs and policy fragments based on feature toggles.

    The costing sample optionally exposes up to four APIs:
      * `cost-tracking-api` (always)        — basic per-BU subscription tracking
      * `appid-tracking-api` (Entra ID)     — `emit-metric` extracts caller `appid`
      * `token-tracking-api` (mock AOAI)    — caller-attributed token tracking
      * `aoai-gateway` (real AOAI Foundry)  — real chat completions w/ token logs

    Args:
        api_prefix: Sample-wide prefix for API names (e.g. `'costing-'`).
        sample_folder: Sample folder name (e.g. `'costing'`) used for policy lookup.
        tags: Base tag list applied to the always-on cost-tracking API.
        enable_entraid_tracking: Adds the Entra ID `appid-tracking-api`.
        enable_token_tracking: Adds the token-tracking API and (with `enable_foundry`)
            the AOAI gateway API. Required for any token-level tracking.
        enable_foundry: When True (and `enable_token_tracking`), adds the real
            AOAI gateway backend.
        force_stream_include_usage: When True, leaves the policy block that
            forces `stream_options.include_usage = true` intact. When False,
            the block is stripped so streaming responses are not modified.

    Returns:
        A 3-tuple `(apis, pfs, paths)` where `paths` maps logical names to the
        URL path segment for each API: `api_path`, `entraid_api_path`,
        `token_api_path`, `aoai_api_path`. Disabled APIs return an empty string.
    """
    paths = {
        'api_path': 'cost-demo',
        'entraid_api_path': '',
        'token_api_path': '',
        'aoai_api_path': '',
    }

    cost_demo_get = GET_APIOperation2('get-status', 'Get Status', '/get', 'Get Status')
    apis: list[API] = [
        API(
            f'{api_prefix}cost-tracking-api',
            'Cost Tracking Demo API',
            paths['api_path'],
            'API for demonstrating cost tracking and allocation',
            operations=[cost_demo_get],
            tags=tags,
            subscriptionRequired=True,
            serviceUrl='https://httpbin.org',
        )
    ]

    # Shared policy fragment: caller-identity extraction
    pf_caller_id_xml = Path(utils.determine_policy_path('pf-extract-caller-id.xml', sample_folder)).read_text(encoding='utf-8')
    pfs: list[PolicyFragment] = [
        PolicyFragment(
            'Extract-CallerId',
            pf_caller_id_xml,
            'Extracts caller identity from JWT appid/azp claim into callerId variable.',
        )
    ]

    if enable_entraid_tracking:
        emit_metric_policy_xml = Path(utils.determine_policy_path('emit_metric_caller_id.xml', sample_folder)).read_text(encoding='utf-8')
        paths['entraid_api_path'] = 'appid-cost-demo'
        apis.append(
            API(
                f'{api_prefix}appid-tracking-api',
                'Cost Tracking by App ID',
                paths['entraid_api_path'],
                'API for demonstrating cost tracking by Entra ID application',
                policyXml=emit_metric_policy_xml,
                operations=[GET_APIOperation2('get-status', 'Get Status', '/get', 'Get Status')],
                tags=['costing', 'emit-metric', 'entra-appid'],
                subscriptionRequired=True,
                serviceUrl='https://httpbin.org',
            )
        )

    token_metric_policy_xml: str | None = None
    if enable_token_tracking:
        if force_stream_include_usage:
            pf_stream_usage_path = Path(utils.get_project_root()) / 'shared' / 'apim-policies' / 'fragments' / 'pf-ensure-stream-include-usage.xml'
            pfs.append(
                PolicyFragment(
                    'Ensure-Stream-Include-Usage',
                    pf_stream_usage_path.read_text(encoding='utf-8'),
                    'Ensures streaming chat requests include stream_options.include_usage = true.',
                )
            )

        token_metric_policy_xml = Path(utils.determine_policy_path('emit_metric_caller_tokens.xml', sample_folder)).read_text(encoding='utf-8')
        if not force_stream_include_usage:
            # Remove the streaming-usage enforcement fragment when not forcing stream_options.include_usage
            token_metric_policy_xml = re.sub(
                (
                    r'\s*<!-- Ensure streaming AI requests include stream_options\.include_usage = true '
                    r'\(reusable fragment\) -->\s*<include-fragment '
                    r'fragment-id="Ensure-Stream-Include-Usage" />\s*'
                ),
                '',
                token_metric_policy_xml,
            )

        mock_ai_policy_xml = Path(utils.determine_policy_path('mock-ai-response.xml', sample_folder)).read_text(encoding='utf-8')

        paths['token_api_path'] = 'token-cost-demo'
        apis.append(
            API(
                f'{api_prefix}token-tracking-api',
                'AI Gateway Token Tracking',
                paths['token_api_path'],
                'API for demonstrating per-caller token/PTU tracking (AI Gateway pattern)',
                policyXml=token_metric_policy_xml,
                operations=[GET_APIOperation2('get-status', 'Get Status', '/get', 'Get Status', policyXml=mock_ai_policy_xml)],
                tags=['costing', 'emit-metric', 'ai-gateway', 'token-tracking'],
                subscriptionRequired=True,
                serviceUrl='https://httpbin.org',
            )
        )

    if enable_foundry and enable_token_tracking and token_metric_policy_xml is not None:
        aoai_operation_policy_xml = Path(utils.determine_policy_path('aoai-gateway-operation.xml', sample_folder)).read_text(encoding='utf-8')

        paths['aoai_api_path'] = 'aoai-gateway'
        aoai_chat_post = APIOperation(
            'chat-completion',
            'Chat Completion',
            '/deployments/{deploymentId}/chat/completions',
            HTTP_VERB.POST,
            'Azure OpenAI chat completion (streaming and non-streaming)',
            policyXml=aoai_operation_policy_xml,
            templateParameters=[{'name': 'deploymentId', 'type': 'string', 'required': True}],
        )
        apis.append(
            API(
                f'{api_prefix}aoai-gateway',
                'AOAI Gateway (Cost Tracking)',
                paths['aoai_api_path'],
                'Azure OpenAI gateway for demonstrating real token tracking with Foundry',
                policyXml=token_metric_policy_xml,
                operations=[aoai_chat_post],
                tags=['costing', 'emit-metric', 'ai-gateway', 'aoai', 'foundry'],
                subscriptionRequired=True,
                serviceUrl='https://placeholder.openai.azure.com/openai',
                enableLlmLogging=True,
            )
        )

    return apis, pfs, paths


# ---------------------------------------------------------------------------
# Cost Management export (called from cell B1)
# ---------------------------------------------------------------------------


def configure_cost_export(
    *,
    subscription_id: str,
    rg_name: str,
    storage_account_name: str,
    cost_export_name: str,
    cost_export_frequency: str = 'Daily',
) -> bool:
    """Create a system-assigned-MI cost export and grant it Storage Blob Data Contributor.

    Recreates the export if one with the same name already exists. Verifies that
    `Microsoft.CostManagementExports` is registered before attempting any writes.

    Returns True on success, False otherwise.
    """
    print_info('Configuring automated Cost Management export (managed identity)...')

    storage_account_id = (
        f'/subscriptions/{subscription_id}/resourceGroups/{rg_name}/providers/Microsoft.Storage/storageAccounts/{storage_account_name}'
    )
    export_scope = f'/subscriptions/{subscription_id}'
    api_version = '2025-03-01'

    rp_check = run('az provider show --namespace Microsoft.CostManagementExports --query registrationState -o tsv')
    if not rp_check.success or rp_check.text.strip() != 'Registered':
        print_error('The Microsoft.CostManagementExports resource provider is not registered.')
        print_info('Run the setup script to register all required providers: setup/local_setup.py')
        return False

    existing_export = run(
        f'az rest --method GET '
        f'--url "{export_scope}/providers/Microsoft.CostManagement/exports/{cost_export_name}'
        f'?api-version={api_version}" -o json',
        retries=0,
    )
    if existing_export.success:
        print_warning(f'Cost export "{cost_export_name}" already exists - recreating...')
        run(f'az rest --method DELETE --url "{export_scope}/providers/Microsoft.CostManagement/exports/{cost_export_name}?api-version={api_version}"')

    recurrence = {'Daily': 'Daily', 'Weekly': 'Weekly', 'Monthly': 'Monthly'}.get(cost_export_frequency, 'Daily')
    start_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y-%m-%dT00:00:00Z')
    end_date = (datetime.now(timezone.utc) + timedelta(days=365)).strftime('%Y-%m-%dT00:00:00Z')

    export_body = {
        'identity': {'type': 'systemAssigned'},
        'location': 'global',
        'properties': {
            'definition': {
                'type': 'ActualCost',
                'timeframe': 'MonthToDate',
                'dataSet': {'granularity': 'Daily'},
            },
            'deliveryInfo': {
                'destination': {
                    'type': 'AzureBlob',
                    'container': 'cost-exports',
                    'rootFolderPath': 'apim-costing',
                    'resourceId': storage_account_id,
                }
            },
            'schedule': {
                'status': 'Active',
                'recurrence': recurrence,
                'recurrencePeriod': {'from': start_date, 'to': end_date},
            },
            'format': 'Csv',
        },
    }

    print_info('Creating cost export with managed identity...')
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as body_file:
        json.dump(export_body, body_file)
        body_file_path = body_file.name

    try:
        export_result = run(
            f'az rest --method PUT '
            f'--url "{export_scope}/providers/Microsoft.CostManagement/exports/{cost_export_name}'
            f'?api-version={api_version}" '
            f'--body @{body_file_path} -o json'
        )
    finally:
        Path(body_file_path).unlink(missing_ok=True)

    if not (export_result and export_result.success):
        print_error('Failed to create cost export')
        print_warning('Continuing without cost export - you can configure it manually later')
        return False

    print_ok(f'Cost export created: {cost_export_name}')
    print_val('Export frequency', recurrence)
    print_val('Authentication', 'System-assigned managed identity')

    principal_id = json.loads(export_result.text).get('identity', {}).get('principalId')
    if principal_id:
        print_info('Assigning Storage Blob Data Contributor role to export identity...')
        role_assignment = run(
            f'az role assignment create '
            f'--assignee-object-id {principal_id} '
            f'--assignee-principal-type ServicePrincipal '
            f'--role "Storage Blob Data Contributor" '
            f'--scope {storage_account_id}'
        )
        if role_assignment.success:
            print_ok('Storage Blob Data Contributor role assigned to export identity')
        else:
            print_warning('Could not assign role - you may need to do this manually')
    else:
        print_warning('Could not retrieve export identity principal ID')

    print_info('Cost data will be exported automatically starting tomorrow')
    return True


# ---------------------------------------------------------------------------
# Per-BU budget alerts (called from cell B3)
# ---------------------------------------------------------------------------


def create_bu_budget_alerts(
    *,
    subscription_id: str,
    rg_name: str,
    rg_location: str,
    log_analytics_name: str,
    alert_email: str,
    alert_threshold: int,
    bu_names: list[str],
    sample_folder: str,
    index: int,
) -> None:
    """Create an Action Group + per-BU scheduled-query alerts in Log Analytics.

    Each alert runs the `budget-alert-threshold.kql` template every 5 minutes
    over a 1-hour rolling window and emails the configured address when a
    business unit exceeds `alert_threshold` requests in that window.
    """
    if not alert_email:
        print_warning('No alert_email configured - skipping budget alert setup')
        print_info('Set alert_email above to enable budget alerts per business unit')
        return

    print_info('Setting up budget alerts per business unit subscription...')

    workspace_result = run(
        f'az monitor log-analytics workspace show --resource-group {rg_name} --workspace-name {log_analytics_name} --query id -o tsv'
    )
    workspace_id = workspace_result.text.strip()

    action_group_name = f'ag-apim-cost-alerts-{index}'
    print_info(f'Creating action group: {action_group_name}...')
    ag_result = run(
        f'az monitor action-group create '
        f'--resource-group {rg_name} '
        f'--name {action_group_name} '
        f'--short-name apimcost '
        f'--action email cost-alert-email {alert_email} '
        f'-o json'
    )
    if not ag_result.success:
        print_error(f'Failed to create action group: {ag_result.text}')
        return
    action_group_id = ag_result.json_data.get('id', '')
    print_ok(f'Action group created: {action_group_name}')

    kql_template = Path(utils.determine_policy_path('budget-alert-threshold.kql', sample_folder)).read_text(encoding='utf-8')

    print_info(f'Creating alerts for {len(bu_names)} business units (threshold: {alert_threshold} requests/hour)...')

    for bu_name in bu_names:
        alert_name = f'apim-budget-{bu_name}-{index}'
        kusto_query = f"let buName = '{bu_name}';\nlet threshold = {alert_threshold};\n{kql_template}"
        alert_body = {
            'location': rg_location,
            'properties': {
                'displayName': f'APIM Budget Alert: {bu_name}',
                'description': f'Fires when {bu_name} exceeds {alert_threshold} API requests per hour',
                'severity': 2,
                'enabled': True,
                'evaluationFrequency': 'PT5M',
                'windowSize': 'PT1H',
                'scopes': [workspace_id],
                'criteria': {
                    'allOf': [
                        {
                            'query': kusto_query,
                            'timeAggregation': 'Count',
                            'operator': 'GreaterThan',
                            'threshold': 0,
                            'failingPeriods': {
                                'numberOfEvaluationPeriods': 1,
                                'minFailingPeriodsToAlert': 1,
                            },
                        }
                    ]
                },
                'actions': {'actionGroups': [action_group_id]},
            },
        }
        alert_id = f'/subscriptions/{subscription_id}/resourceGroups/{rg_name}/providers/Microsoft.Insights/scheduledQueryRules/{alert_name}'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(alert_body, f)
            alert_body_path = f.name
        try:
            result = run(
                f'az rest --method PUT --uri https://management.azure.com{alert_id}?api-version=2023-03-15-preview --body @{alert_body_path}'
            )
        finally:
            Path(alert_body_path).unlink(missing_ok=True)

        if result.success:
            print_ok(f'  Alert created: {alert_name}')
        else:
            print_error(f'  Failed to create alert for {bu_name}: {result.text[:200]}')

    print()
    print_ok('Budget alerts configured!')
    print_val('Action Group', action_group_name)
    print_val('Alert Email', alert_email)
    print_val('Threshold', f'{alert_threshold} requests per hour per BU')
    print_val('Evaluation', 'Every 5 minutes, 1-hour rolling window')


# ---------------------------------------------------------------------------
# AOAI traffic summary tables + persist (called from cell D1)
# ---------------------------------------------------------------------------


def print_aoai_traffic_summary(
    model_request_counts: dict[str, dict[str, int]],
    bu_model_counts: dict[tuple[str, str], dict[str, int]],
) -> tuple[int, int, int]:
    """Print per-model and per-BU×per-model AOAI request tables.

    Returns:
        `(grand_non_streaming, grand_streaming, total)` — used by the caller
        for the trailing summary line and persistence step.
    """
    print()
    print_info('Requests per model')
    summary_table = TableLogger()
    summary_table.header(
        Column('Model'),
        Column('Non-streaming', align='>'),
        Column('Streaming', align='>'),
        Column('Total', align='>'),
    )
    summary_rows = []
    grand_ns = grand_s = 0
    for m, counts in model_request_counts.items():
        total = counts['non_streaming'] + counts['streaming']
        summary_rows.append([m, counts['non_streaming'], counts['streaming'], total])
        grand_ns += counts['non_streaming']
        grand_s += counts['streaming']
    summary_table.populate(summary_rows)
    summary_table.total('GRAND TOTAL', grand_ns, grand_s, grand_ns + grand_s)
    summary_table.print()

    print()
    print_info('Requests by business unit and model')
    bu_model_table = TableLogger()
    bu_model_table.header(
        Column('Business Unit'),
        Column('Model'),
        Column('Non-streaming', align='>'),
        Column('Streaming', align='>'),
        Column('Total', align='>'),
    )
    bu_rows = []
    bu_grand_ns = bu_grand_s = 0
    for bu, m in sorted(bu_model_counts.keys()):
        counts = bu_model_counts[(bu, m)]
        total = counts['non_streaming'] + counts['streaming']
        bu_rows.append([bu, m, counts['non_streaming'], counts['streaming'], total])
        bu_grand_ns += counts['non_streaming']
        bu_grand_s += counts['streaming']
    bu_model_table.populate(bu_rows)
    bu_model_table.total('GRAND TOTAL', '', bu_grand_ns, bu_grand_s, bu_grand_ns + bu_grand_s)
    bu_model_table.print()

    return grand_ns, grand_s, grand_ns + grand_s


def persist_aoai_traffic(
    local_data_path: Path,
    *,
    sample_folder: str,
    rg_name: str,
    apim_name: str,
    aoai_api_path: str,
    subscriptions: dict[str, dict[str, Any]],
    bu_model_counts: dict[tuple[str, str], dict[str, int]],
    bu_model_planned: dict[tuple[str, str], dict[str, int]],
) -> int:
    """Roll up per-(BU,model) AOAI counts into a single trafficSources entry.

    Returns the total planned request count across all BU/model pairs (used
    by the caller for a trailing print line). The total delivered count is
    derived inside the function and stored as `totalRequests` in the JSON.
    """
    ai_bu_rollup: dict[str, dict] = {}
    total_delivered = 0
    for (bu, m), counts in bu_model_counts.items():
        bu_info_local = subscriptions.get(bu, {})
        planned = bu_model_planned.get((bu, m), {'non_streaming': 0, 'streaming': 0})
        entry = ai_bu_rollup.setdefault(
            bu,
            {
                'name': bu,
                'display_name': bu_info_local.get('display_name', ''),
                'weight': float(bu_info_local.get('request_weight', 1.0)),
                'planned': 0,
                'requests': 0,
                'isAi': True,
                'byModel': [],
            },
        )
        model_total = counts['non_streaming'] + counts['streaming']
        planned_total = planned['non_streaming'] + planned['streaming']
        entry['planned'] += planned_total
        entry['requests'] += model_total
        total_delivered += model_total
        entry['byModel'].append(
            {
                'model': m,
                'plannedNonStreaming': planned['non_streaming'],
                'plannedStreaming': planned['streaming'],
                'nonStreaming': counts['non_streaming'],
                'streaming': counts['streaming'],
                'total': model_total,
            }
        )

    total_planned = sum(p['non_streaming'] + p['streaming'] for p in bu_model_planned.values())
    persist_traffic_source(
        local_data_path,
        sample_folder=sample_folder,
        rg_name=rg_name,
        apim_name=apim_name,
        source_entry={
            'name': 'ai-gateway-aoai',
            'apiName': aoai_api_path,
            'isAi': True,
            'plannedRequests': total_planned,
            'totalRequests': total_delivered,
            'businessUnits': list(ai_bu_rollup.values()),
        },
    )
    return total_planned


# ---------------------------------------------------------------------------
# Workbook cross-reference (called from cell E3)
# ---------------------------------------------------------------------------


def print_workbook_cross_reference(local_data_path: Path) -> None:
    """Read `bu-request-counts.local.json` and print workbook cross-reference tables.

    Prints the four headline tiles (Total / Non-AI / AI / AI-BU), per-source
    breakdown, per-BU rollup across all BU-attributed sources, and per-caller
    breakdown for AI sources that don't carry bu-* attribution.

    Silently does nothing useful if the file is missing — emits a warning so
    the user knows to run the traffic cells first.
    """
    if not local_data_path.exists():
        print_warning(f'No ground-truth file found at: {local_data_path}')
        print_info('Run the traffic cells (C1, D1 or D2) first to generate the file.')
        return

    data = json.loads(local_data_path.read_text(encoding='utf-8'))
    sources = data.get('trafficSources', [])

    total_planned = sum(s.get('plannedRequests', 0) for s in sources)
    total_delivered = sum(s.get('totalRequests', 0) for s in sources)

    ai_sources = [s for s in sources if s.get('isAi')]
    ai_planned = sum(s.get('plannedRequests', 0) for s in ai_sources)
    ai_delivered = sum(s.get('totalRequests', 0) for s in ai_sources)

    ai_bu_sources = [s for s in ai_sources if 'businessUnits' in s]
    ai_bu_planned = sum(s.get('plannedRequests', 0) for s in ai_bu_sources)
    ai_bu_delivered = sum(s.get('totalRequests', 0) for s in ai_bu_sources)

    non_ai_sources = [s for s in sources if not s.get('isAi')]
    non_ai_planned = sum(s.get('plannedRequests', 0) for s in non_ai_sources)
    non_ai_delivered = sum(s.get('totalRequests', 0) for s in non_ai_sources)

    print_info('Workbook-tile cross-reference (from bu-request-counts.local.json)')
    print_val('Generated UTC', data.get('generatedUtc', ''))
    print_val('Resource group', data.get('resourceGroup', ''))
    print_val('APIM service', data.get('apimService', ''))
    print()

    tile_table = TableLogger()
    tile_table.header(
        Column('Tile (workbook equivalent)'),
        Column('Planned', align='>'),
        Column('Delivered', align='>'),
    )
    tile_table.populate(
        [
            ['Total APIM Requests (all subs, all APIs)', total_planned, total_delivered],
            ['  - Non-AI Requests (bu-*)', non_ai_planned, non_ai_delivered],
            ['  - AI APIM Requests (all subs)', ai_planned, ai_delivered],
            ['     of which: AI Requests Received (bu-*)', ai_bu_planned, ai_bu_delivered],
        ]
    )
    tile_table.print()
    print()

    print_info('Traffic sources')
    src_table = TableLogger()
    src_table.header(
        Column('Source'),
        Column('API path'),
        Column('AI'),
        Column('Attribution'),
        Column('Planned', align='>'),
        Column('Delivered', align='>'),
    )
    src_rows = []
    for s in sources:
        if 'businessUnits' in s:
            attribution = 'business units'
        elif 'callers' in s:
            attribution = 'callers'
        else:
            attribution = '-'
        src_rows.append(
            [
                s.get('name', ''),
                s.get('apiName', ''),
                'yes' if s.get('isAi') else 'no',
                attribution,
                s.get('plannedRequests', 0),
                s.get('totalRequests', 0),
            ]
        )
    src_table.populate(src_rows)
    src_table.total('TOTAL', '', '', '', total_planned, total_delivered)
    src_table.print()
    print()

    bu_rollup: dict[str, dict] = {}
    for s in sources:
        for bu in s.get('businessUnits', []):
            entry = bu_rollup.setdefault(
                bu['name'],
                {
                    'display': bu.get('display_name', ''),
                    'planned': 0,
                    'delivered': 0,
                    'ai_planned': 0,
                    'ai_delivered': 0,
                },
            )
            entry['planned'] += bu.get('planned', 0)
            entry['delivered'] += bu.get('requests', 0)
            if s.get('isAi'):
                entry['ai_planned'] += bu.get('planned', 0)
                entry['ai_delivered'] += bu.get('requests', 0)

    if bu_rollup:
        print_info('Requests by business unit (sums across all BU-attributed sources)')
        bu_table = TableLogger()
        bu_table.header(
            Column('Business Unit'),
            Column('Display Name'),
            Column('Planned', align='>'),
            Column('Delivered', align='>'),
            Column('AI Planned', align='>'),
            Column('AI Delivered', align='>'),
        )
        gp = gd = gap = gad = 0
        bu_rows = []
        for bu_name in sorted(bu_rollup):
            r = bu_rollup[bu_name]
            bu_rows.append([bu_name, r['display'], r['planned'], r['delivered'], r['ai_planned'], r['ai_delivered']])
            gp += r['planned']
            gd += r['delivered']
            gap += r['ai_planned']
            gad += r['ai_delivered']
        bu_table.populate(bu_rows)
        bu_table.total('TOTAL', '', gp, gd, gap, gad)
        bu_table.print()
        print()

    caller_sources = [s for s in sources if 'callers' in s]
    for s in caller_sources:
        print_info(f'Caller breakdown - {s.get("name", "")} (api: {s.get("apiName", "")})')
        ct = TableLogger()
        ct.header(
            Column('App ID'),
            Column('Caller Name'),
            Column('Planned', align='>'),
            Column('Delivered', align='>'),
        )
        cp = cd = 0
        cr = []
        for c in s.get('callers', []):
            cr.append([c.get('appid', ''), c.get('name', ''), c.get('planned', 0), c.get('requests', 0)])
            cp += c.get('planned', 0)
            cd += c.get('requests', 0)
        ct.populate(cr)
        ct.total('TOTAL', '', cp, cd)
        ct.print()
        print()

    print_ok('Cross-reference tables ready - compare against the Azure Monitor workbook tiles once log ingestion completes.')
    print_info(f'File: {local_data_path}')
