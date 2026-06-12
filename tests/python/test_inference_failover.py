"""Regression tests for the AOAI-only Inference Failover sample assets."""

import json
import re
from pathlib import Path
from xml.etree import ElementTree

SAMPLE_PATH = Path(__file__).resolve().parents[2] / 'samples' / 'inference-failover'
SIMPLE_APIM_BICEP_PATH = Path(__file__).resolve().parents[2] / 'infrastructure' / 'simple-apim' / 'main.bicep'
BICEP_PATH = SAMPLE_PATH / 'main.bicep'
DIAGNOSTICS_BICEP_PATH = Path(__file__).resolve().parents[2] / 'shared' / 'bicep' / 'modules' / 'apim' / 'v1' / 'diagnostics.bicep'
NOTEBOOK_PATH = SAMPLE_PATH / 'create.ipynb'
POLICY_PATH = SAMPLE_PATH / 'apim-policies' / 'inference-api-policy.xml'
README_PATH = SAMPLE_PATH / 'README.md'
WORKBOOK_PATH = SAMPLE_PATH / 'inference-failover.workbook.json'
WORKBOOK_UPDATE_PATH = SAMPLE_PATH / 'update-workbook.ps1'
QUERIES_PATH = SAMPLE_PATH / 'queries'
KQL_PATHS = [
    QUERIES_PATH / 'backend-distribution.kql',
    QUERIES_PATH / 'failure-analysis.kql',
    QUERIES_PATH / 'failover-outcomes.kql',
    QUERIES_PATH / 'llm-telemetry-coverage.kql',
    QUERIES_PATH / 'request-details.kql',
    QUERIES_PATH / 'token-throughput.kql',
    QUERIES_PATH / 'verify-llm-ingestion.kql',
]
EXPECTED_BACKENDS = {
    'gpt-5-1-PTU-eastus2',
    'gpt-5-1-PAYG-eastus2',
    'gpt-5-1-PTU-westus3',
    'gpt-5-1-PAYG-westus3',
    'gpt-5-1-PAYG-southcentralus',
    'gpt-4-1-mini-PTU-eastus2',
    'gpt-4-1-mini-PAYG-eastus2',
    'gpt-4-1-mini-PTU-westus3',
    'gpt-4-1-mini-PAYG-southcentralus',
}


def _load_workbook() -> dict:
    """Read and parse the failover workbook source."""
    return json.loads(WORKBOOK_PATH.read_text(encoding='utf-8'))


def _collect_item_names(items: list[dict]) -> set[str]:
    """Collect workbook item names recursively from nested tab groups."""
    names = {item['name'] for item in items if item.get('name')}
    for item in items:
        names.update(_collect_item_names(item.get('content', {}).get('items', [])))
    return names


def _find_workbook_item(items: list[dict], name: str) -> dict:
    """Find a workbook item recursively by name."""
    for item in items:
        if item.get('name') == name:
            return item
        nested_items = item.get('content', {}).get('items', [])
        if nested_items:
            try:
                return _find_workbook_item(nested_items, name)
            except KeyError:
                pass
    raise KeyError(name)


def test_inference_failover_workbook_is_aoai_only_and_query_backed() -> None:
    """Keep the workbook focused on inference telemetry rather than cost/showback features."""
    workbook = _load_workbook()
    serialized = json.dumps(workbook).lower()
    item_names = _collect_item_names(workbook['items'])

    assert workbook['$schema'].endswith('/schema/workbook.json')
    assert 'query - outcome-summary' in item_names
    assert 'query - outcome-status-matrix' in item_names
    assert 'query - backend-distribution' in item_names
    assert 'query - failover-summary' in item_names
    assert 'query - failover-request-trails' in item_names
    assert 'query - failure-taxonomy' in item_names
    assert 'query - raw-failure-explorer' in item_names
    assert 'query - token-throughput' in item_names
    assert 'query - llm-telemetry-coverage' in item_names
    assert 'query - backend-latency-trend' in item_names
    assert 'query - request-explorer' in item_names
    assert 'apimanagementgatewayllmlog' in serialized
    assert 'inferenceattempt' in serialized
    assert 'inferencebackendattemptcomplete' not in serialized
    assert 'inferencefallbackexhausted' not in serialized
    assert "lasterrorreason in ('backendconnectionfailure', 'timeout')" in serialized
    assert 'max_of(attempts - 1, 0)' in serialized
    assert 'cost export' not in serialized
    assert 'business unit' not in serialized
    assert 'budget' not in serialized


def test_inference_failover_workbook_leaves_missing_numeric_aggregates_empty() -> None:
    """Render absent backend latency values as empty numeric cells rather than NaN text."""
    serialized = json.dumps(_load_workbook())

    assert 'round(avg(' not in serialized
    assert 'round(percentile(' not in serialized
    assert 'AverageBackendMs = avg(BackendTime)' in serialized
    assert 'P95BackendMs = percentile(BackendTime, 95)' in serialized
    assert 'AverageBackendMs = iff(isfinite(toreal(AverageBackendMs)), round(AverageBackendMs, 1), real(null))' in serialized
    assert 'P95BackendMs = iff(isfinite(toreal(P95BackendMs)), round(P95BackendMs, 1), real(null))' in serialized


def test_inference_failover_request_explorer_shows_many_rows() -> None:
    """Keep Request Explorer auto-sized with a high row limit and filtering."""
    request_explorer = _find_workbook_item(_load_workbook()['items'], 'query - request-explorer')['content']

    assert request_explorer['size'] == 0
    assert request_explorer['gridSettings'] == {'filter': True, 'rowLimit': 10000}


def test_inference_failover_kql_queries_scope_to_ai_gateway_signals() -> None:
    """Ensure focused KQL query files remain available and tied to AI telemetry tables."""
    query_text = '\n'.join(path.read_text(encoding='utf-8') for path in KQL_PATHS)

    assert all(path.exists() for path in KQL_PATHS)
    assert 'ApiManagementGatewayLogs' in query_text
    assert 'ApiManagementGatewayLlmLog' in query_text
    assert 'BackendResponseCode' in query_text
    assert 'BackendUrl' in query_text
    assert 'TraceRecords' in query_text
    assert 'LastErrorReason' in query_text
    assert 'InferenceAttempt' in query_text
    assert 'InferenceBackendAttemptComplete' not in query_text
    assert 'InferenceFallbackExhausted' not in query_text
    assert "LastErrorReason in ('BackendConnectionFailure', 'Timeout')" in query_text
    assert 'inference-gpt-5-1' in query_text
    assert 'inference-gpt-4-1-mini' in query_text
    assert 'CostManagement' not in query_text


def test_inference_policies_use_managed_identity_retries_and_generic_terminal_error() -> None:
    """Protect managed identity routing and the non-disclosing terminal response contract."""
    api_policy = POLICY_PATH.read_text(encoding='utf-8')
    policy_root = ElementTree.fromstring(api_policy)
    backend = policy_root.find('backend')

    assert backend is not None
    assert [policy.tag for policy in backend] == ['retry']
    retry = backend.find('retry')
    assert retry is not None
    retry_condition = retry.attrib['condition']
    terminal_condition = policy_root.find('outbound/choose/when').attrib['condition']
    on_error_conditions = [branch.attrib['condition'] for branch in policy_root.findall('on-error/choose/when')]
    capacity_condition = next(condition for condition in on_error_conditions if 'updatedRetryEpoch' in condition)
    generic_failure_condition = next(condition for condition in on_error_conditions if 'BackendConnectionFailure' in condition)
    assert 'count="RETRY_COUNT"' in api_policy
    assert 'api-key' not in api_policy
    assert all(f'StatusCode == {status_code}' in retry_condition for status_code in (408, 409, 429, 499, 500, 502, 503, 504))
    assert 'Headers.ContainsKey("Retry-After")' in retry_condition
    assert all(f'StatusCode == {status_code}' in terminal_condition for status_code in (500, 502, 503, 504))
    assert all(f'StatusCode == {status_code}' not in terminal_condition for status_code in (408, 409, 429, 499))
    assert 'context.Response == null' in retry_condition
    assert all(f'StatusCode == {status_code}' in generic_failure_condition for status_code in (500, 502, 503, 504))
    assert 'BackendConnectionFailure' in generic_failure_condition
    assert 'Timeout' in generic_failure_condition
    assert 'ClientConnectionFailure' not in generic_failure_condition
    assert all(f'StatusCode == {status_code}' in capacity_condition for status_code in (429, 503))
    assert retry.attrib['interval'] == '0'
    assert 'interval="1"' not in api_policy
    assert 'buffer-request-body="true"' in api_policy
    assert 'Inference service is temporarily unavailable.' in api_policy
    assert 'BackendId' not in api_policy
    assert 'InferenceAttempt|n=' in api_policy
    assert '|code=' in api_policy
    assert 'InferenceBackendAttemptComplete' not in api_policy
    assert 'InferenceFallbackExhausted' not in api_policy
    assert 'InferenceTransportFailure' not in api_policy
    assert 'InferenceRequestAccepted' not in api_policy
    assert 'InferenceGatewayResponse' not in api_policy
    assert api_policy.count('<trace source="InferenceFailover"') == 1
    assert '<metadata ' not in api_policy
    assert api_policy.count('<set-header name="X-Backend-Retry" exists-action="override">') == 2
    assert api_policy.count('<set-variable name="backendRetry"') == 2
    assert api_policy.count('@((string)context.Variables["backendRetry"])') == 2
    assert '<set-variable name="willRetry"' not in api_policy
    assert api_policy.index('name="backendAttempt"') < api_policy.index('<authentication-managed-identity')
    assert not (SAMPLE_PATH / 'inference-api-policy.xml').exists()


def test_inference_policy_tracks_soonest_retry_after_and_returns_capacity_from_on_error() -> None:
    """Keep exhausted capacity responses aligned with the earliest backend recovery time."""
    api_policy = POLICY_PATH.read_text(encoding='utf-8')
    policy_root = ElementTree.fromstring(api_policy)
    retry = policy_root.find('backend/retry')
    on_error = policy_root.find('on-error')

    assert retry is not None
    assert on_error is not None
    retry_tracking_condition = retry.find('choose/when').attrib['condition']
    capacity_branch = next(branch for branch in on_error.findall('choose/when') if 'updatedRetryEpoch' in branch.attrib['condition'])
    response_branch = next(branch for branch in on_error.findall('choose/when') if 'terminalStatus' in branch.attrib['condition'])

    assert all(f'StatusCode == {status_code}' in retry_tracking_condition for status_code in (429, 503))
    assert 'Headers.ContainsKey("Retry-After")' in retry_tracking_condition
    assert api_policy.count('key="inference-retry-min-BACKEND_POOL_ID"') == 2
    assert 'cachedEpoch &gt; nowEpoch &amp;&amp; cachedEpoch &lt; candidateEpoch' in api_policy
    assert 'parsedEpoch &lt;= nowEpoch' in api_policy
    assert 'Math.Max(0L, parsedEpoch - nowEpoch) + 1L' in api_policy
    assert capacity_branch.find("set-variable[@name='terminalStatus']").attrib['value'] == '@(429)'
    assert response_branch.find('set-status').attrib == {
        'code': '@((int)context.Variables["terminalStatus"])',
        'reason': '@((int)context.Variables["terminalStatus"] == 429 ? "Too Many Requests" : "Inference Service Unavailable")',
    }
    assert on_error.findall('.//return-response') == []
    assert on_error.findall('.//trace') == []
    assert len(on_error.findall('.//set-status')) == 1
    assert len(on_error.findall(".//set-header[@name='X-Backend-Retry']")) == 1
    assert len(on_error.findall(".//set-header[@name='Content-Type']")) == 1
    assert len(on_error.findall('.//set-body')) == 1
    retry_after_header = response_branch.find("choose/when/set-header[@name='Retry-After']")
    assert retry_after_header is not None
    assert retry_after_header.find('value') is not None
    assert 'Inference capacity is temporarily unavailable.' in api_policy
    assert 'GetValueOrDefault&lt;int&gt;("backendAttempt", 0)' in api_policy
    assert 'capacityRetryAfterObserved' not in api_policy
    assert 'context.Variables.ContainsKey("updatedRetryEpoch")' in api_policy
    assert 'terminalReason' not in api_policy
    assert 'terminalBody' not in api_policy
    assert 'terminalEvent' not in api_policy
    assert '&quot;' not in api_policy


def test_inference_policy_uses_exact_managed_identity_resource() -> None:
    """Require the exact Cognitive Services resource in the parsed policy structure."""
    policy_root = ElementTree.fromstring(POLICY_PATH.read_text(encoding='utf-8'))
    managed_identity = policy_root.find('inbound/authentication-managed-identity')

    assert managed_identity is not None
    assert managed_identity.attrib['resource'] == 'https://cognitiveservices.azure.com'


def test_inference_policy_decisions_cover_every_documented_status() -> None:
    """Lock retry and terminal-failover decisions for every response-matrix row."""
    policy_root = ElementTree.fromstring(POLICY_PATH.read_text(encoding='utf-8'))
    retry_condition = policy_root.find('backend/retry').attrib['condition']
    terminal_condition = policy_root.find('outbound/choose/when').attrib['condition']
    retry_statuses = {int(value) for value in re.findall(r'StatusCode == (\d+)', retry_condition)}
    terminal_statuses = {int(value) for value in re.findall(r'StatusCode == (\d+)', terminal_condition)}
    expected_decisions = {
        200: (False, False),
        400: (False, False),
        401: (False, False),
        403: (False, False),
        404: (False, False),
        408: (True, False),
        409: (True, False),
        429: (True, False),
        499: (True, False),
        500: (True, True),
        501: (False, False),
        502: (True, True),
        503: (True, True),
        504: (True, True),
    }

    for status_code, (should_retry, should_failover) in expected_decisions.items():
        assert (status_code in retry_statuses) is should_retry, f'Unexpected retry decision for HTTP {status_code}'
        assert (status_code in terminal_statuses) is should_failover, f'Unexpected failover decision for HTTP {status_code}'

    assert '(context.Response.StatusCode == 409 && context.Response.Headers.ContainsKey("Retry-After"))' in retry_condition


def test_inference_readme_documents_exact_response_handling_matrix() -> None:
    """Keep the documented status-code contract synchronized with the policy."""
    readme = README_PATH.read_text(encoding='utf-8')
    expected_rows = [
        '| 200 | - | - | 200 | Success | None | Return the successful response. |',
        '| 400 | No | No | 400 | Client | Low | Return unchanged; may indicate an invalid request or content filtering. |',
        '| 401 | No | No | 401 | Auth | Medium | Return unchanged; correct backend authentication. |',
        '| 403 | No | No | 403 | AuthZ | Medium | Return unchanged; correct backend authorization. |',
        '| 404 | No | No | 404 | Config | Medium | Return unchanged; correct the backend URL or deployment name. |',
        (
            '| 408 | Yes | Yes | 200 or 408 | Timeout | Medium | Retry another backend; return the explicit HTTP timeout if the fallback '
            'chain is exhausted. |'
        ),
        '| 409 | No | Sometimes | 200 or 409 | Conflict | Medium | Retry only when `Retry-After` marks the conflict as transient. |',
        (
            '| 429 | Yes | Yes | 200 or 429 | Capacity | Medium | Retry another eligible backend; return exhausted '
            'capacity with the soonest `Retry-After`. |'
        ),
        ('| 499 | Yes | Yes | 200 or 499 | Custom | Medium | Retry another backend when PTU exhaustion is represented by a transformed `408`. |'),
        '| 500 | Yes | Yes | 200 or 503 | Infra | High | Retry another eligible backend; normalize an exhausted chain to `503`. |',
        '| 502 | Yes | Yes | 200 or 503 | Infra | High | Retry another eligible backend; normalize an exhausted chain to `503`. |',
        (
            '| 503 | Yes | Yes | 200, 429, or 503 | Infra | High | Retry another backend; return `429` when `Retry-After` '
            'identifies capacity, otherwise normalize exhaustion to `503`. |'
        ),
        '| 504 | Yes | Yes | 200 or 503 | Infra | High | Retry another eligible backend; normalize an exhausted chain to `503`. |',
        ('| null | No | Yes | 200 or 503 | Transport | High | Retry after no backend response; normalize handled transport failures to `503`. |'),
    ]

    assert all(row in readme for row in expected_rows)
    assert '| Backend Code | Trip Breaker | Retry | Caller Codes | Category | Severity | Handling |' in readme
    assert '"Trip Breaker" applies to the backend that returned the response' in readme
    assert '`https://unresolvable.invalid`' in readme
    assert 'does **not** simulate a client disconnect' in readme
    assert '`409` without `Retry-After`' in readme
    assert '`409` with `Retry-After`' in readme
    assert '`curl --max-time 1`' in readme


def test_inference_bicep_contains_only_compatible_model_backend_pools() -> None:
    """Check the model deployment constellation, pool scope, and circuit breaker contract."""
    bicep = BICEP_PATH.read_text(encoding='utf-8')
    single_quote = chr(39)

    assert all(backend in bicep for backend in EXPECTED_BACKENDS)
    assert bicep.count(f'modelName: {single_quote}gpt-5.1{single_quote}') == 5
    assert bicep.count(f'modelName: {single_quote}gpt-4.1-mini{single_quote}') == 4
    assert 'capacity: 1' in bicep
    assert f'name: {single_quote}Standard{single_quote}' in bicep
    assert 'acceptRetryAfter: true' in bicep
    assert bicep.count("name: 'failover-on-capacity-or-infrastructure-failure'") == 1
    assert "name: 'capacity-throttled'" not in bicep
    assert "name: 'sustained-internal-error'" not in bicep
    assert "name: 'infrastructure-unavailable'" not in bicep
    circuit_breaker_block = re.search(
        r"name: 'failover-on-capacity-or-infrastructure-failure'(?P<body>.*?)tripDuration: 'PT1M'",
        bicep,
        re.DOTALL,
    )
    assert circuit_breaker_block is not None
    breaker_body = circuit_breaker_block.group('body')
    assert re.search(r'count:\s*1\b', breaker_body)

    status_ranges = {
        status_code
        for minimum, maximum in re.findall(r'min:\s*(\d+)\s+max:\s*(\d+)', breaker_body)
        for status_code in range(int(minimum), int(maximum) + 1)
    }
    assert status_ranges == {408, 429, 499, 500, 502, 503, 504}
    assert 'enableLlmLogs: true' in bicep
    assert f'backendPoolName: {single_quote}inference-gpt-5-1-pool{single_quote}' in bicep
    assert f'backendPoolName: {single_quote}inference-gpt-4-1-mini-pool{single_quote}' in bicep
    assert "name: 'gpt-5-1-PTU-westus3'\n        priority: 2" in bicep
    assert "name: 'gpt-5-1-PAYG-eastus2'\n        priority: 3" in bicep
    assert "name: 'gpt-4-1-mini-PTU-westus3'\n        priority: 2" in bicep
    assert "name: 'gpt-4-1-mini-PAYG-eastus2'\n        priority: 3" in bicep
    backend_declaration_order = [
        'gpt-5-1-PTU-eastus2',
        'gpt-5-1-PTU-westus3',
        'gpt-5-1-PAYG-eastus2',
        'gpt-5-1-PAYG-westus3',
        'gpt-5-1-PAYG-southcentralus',
        'gpt-4-1-mini-PTU-eastus2',
        'gpt-4-1-mini-PTU-westus3',
        'gpt-4-1-mini-PAYG-eastus2',
        'gpt-4-1-mini-PAYG-southcentralus',
    ]
    declaration_offsets = [bicep.index(f"backendName: '{backend}'") for backend in backend_declaration_order]
    assert declaration_offsets == sorted(declaration_offsets)


def test_inference_event_hub_export_is_regional_comprehensive_and_default_off() -> None:
    """Keep external APIM telemetry streaming optional, regional, and broadly configured."""
    bicep = BICEP_PATH.read_text(encoding='utf-8')
    diagnostics_bicep = DIAGNOSTICS_BICEP_PATH.read_text(encoding='utf-8')

    assert 'param enableEventHubExport bool = false' in bicep
    assert "resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = if (enableEventHubExport)" in bicep
    assert 'location: location' in bicep
    assert "resource eventHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = if (enableEventHubExport)" in bicep
    assert 'messageRetentionInDays: 7' in bicep
    assert 'partitionCount: 4' in bicep
    assert "resource eventHubConsumerGroup 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01'" in bicep
    assert "var eventHubConsumerGroupName = 'external-observability'" in bicep
    assert "resource eventHubExportAuthorizationRule 'Microsoft.EventHub/namespaces/authorizationRules@2024-01-01'" in bicep
    assert "'Listen'\n      'Send'\n      'Manage'" in bicep
    assert 'enableEventHub: enableEventHubExport' in bicep
    assert "eventHubAuthorizationRuleId: enableEventHubExport ? eventHubExportAuthorizationRule.id : ''" in bicep
    assert "eventHubName: enableEventHubExport ? eventHub.name : ''" in bicep
    assert 'output eventHubExportEnabled bool = enableEventHubExport' in bicep
    assert 'output eventHubId string' in bicep
    assert 'output eventHubConsumerGroupName string' in bicep
    assert 'listKeys(' not in bicep

    assert 'param enableEventHub bool = false' in diagnostics_bicep
    assert 'eventHubAuthorizationRuleId: enableEventHubDestination ? eventHubAuthorizationRuleId : null' in diagnostics_bicep
    assert 'eventHubName: enableEventHubDestination ? eventHubName : null' in diagnostics_bicep
    assert "category: 'GatewayLogs'" in diagnostics_bicep
    assert "category: 'GatewayLlmLogs'" in diagnostics_bicep
    assert "category: 'WebSocketConnectionLogs'" in diagnostics_bicep
    assert "category: 'AllMetrics'" in diagnostics_bicep


def test_inference_notebook_is_clean_and_defaults_to_simple_apim() -> None:
    """Retain the intended first-run experience and output-free checked-in notebook."""
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding='utf-8'))
    code_cells = [cell for cell in notebook['cells'] if cell['cell_type'] == 'code']
    code_source = '\n'.join(''.join(cell['source']) for cell in code_cells)

    assert all(not cell['outputs'] for cell in code_cells)
    assert 'index = 1' in ''.join(code_cells[0]['source'])
    assert 'deployment = INFRASTRUCTURE.SIMPLE_APIM' in code_source
    assert 'enable_event_hub_export = False' in code_source
    assert "'enableEventHubExport': {'value': enable_event_hub_export}" in code_source
    assert "output.get('eventHubNamespaceId', 'Event Hubs namespace ID')" in code_source
    assert "importlib.import_module('inference_failover_helpers')" in code_source
    assert "utils.enable_module_autoreload('inference_failover_helpers')" in code_source
    assert 'inference_failover_helpers.InferenceTrafficRunner(' in code_source
    assert 'probe_runner.run_contract_probes(' in code_source
    assert 'traffic_runner.run_scenario(scenario)' in code_source
    assert 'probe_results.unknown_operation.status_code, 404' in code_source
    assert "probe_results.malformed.headers.get('X-Backend-Retry'), '0'" in code_source
    assert "'X-Backend-Retry' in probe_results.missing_key.headers" in code_source
    assert "'X-Backend-Retry' in probe_results.unknown_operation.headers" in code_source
    assert 'X-Backend-Id' not in code_source
    assert "queries_path = Path(utils.get_project_root()) / 'samples' / sample_folder / 'queries'" in code_source
    assert "queries_path / 'verify-llm-ingestion.kql'" in code_source
    assert "queries_path / 'backend-distribution.kql'" in code_source
    assert "queries_path / 'token-throughput.kql'" in code_source
    assert "columns=['API', 'Backend URL', 'Requests', 'Successes', 'Throttled', 'Failures', 'AverageBackendMs', 'SuccessRate']" in code_source
    assert 'def with_backend_identifier(' not in code_source
    assert 'def format_gateway_distribution(' not in code_source
    assert 'distribution_frame = inference_failover_helpers.with_backend_identifier(distribution_frame)' in code_source
    assert 'distribution_frame = inference_failover_helpers.format_gateway_distribution(distribution_frame)' in code_source
    assert code_source.count("distribution_frame.pivot(index='API', columns='Backend', values='Requests')") == 1
    assert "columns=['API', 'Backend URL', 'Model', 'Requests', 'PromptTokens', 'CompletionTokens', 'TotalTokens']" in code_source
    assert 'token_frame = inference_failover_helpers.with_backend_identifier(token_frame)' in code_source
    assert 'plt.show()' in code_source
    assert 'Route Graph' in '\n'.join(''.join(cell['source']) for cell in notebook['cells'])


def test_inference_notebook_generates_local_html_report() -> None:
    """Keep the end-of-run local report and link in the notebook flow."""
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding='utf-8'))
    code_source = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code')

    assert 'inference_failover_helpers.InferenceReportContext(' in code_source
    assert 'inference_failover_helpers = importlib.reload(inference_failover_helpers)' in code_source
    assert 'inference_failover_helpers.generate_local_html_report(' in code_source
    assert 'scenario_results=scenario_results' in code_source
    assert "'gpt-5.1': gpt_5_1_backend_url_index" in code_source
    assert "'gpt-4.1-mini': gpt_4_1_mini_backend_labels" in code_source
    assert "distribution_frame=distribution_frame if 'distribution_frame' in locals() else None" in code_source
    assert "token_frame=token_frame if 'token_frame' in locals() else None" in code_source
    assert 'htmlreport.HtmlReport' not in code_source
    assert 'def add_scenario_figure(' not in code_source
    assert 'report.add_table(' not in code_source
    assert 'report.add_figure(' not in code_source
    assert "print_ok(f'Local HTML report ready: {report_url}')" in code_source


def test_inference_notebook_uses_tuned_gpt_4_1_mini_pressure_window() -> None:
    """Keep the independent pool pressure run demonstrative without flooding callers with terminal failures."""
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding='utf-8'))
    notebook_source = '\n'.join(''.join(cell['source']) for cell in notebook['cells'])

    assert '| 3 | Sustained pressure | gpt-4.1-mini | 15 | none |' in notebook_source
    assert "'3/5: Sustained pressure - gpt-4.1-mini (no spacing)'" in notebook_source
    assert "('gpt-4.1-mini sustained pressure', scenario3_gpt_4_1_mini, 15)" in notebook_source
    assert '(`134` requests)' in notebook_source


def test_simple_apim_exposes_backend_url_for_learning_by_default() -> None:
    """Keep the default infrastructure consistent with the learn-only routing test harness."""
    bicep = SIMPLE_APIM_BICEP_PATH.read_text(encoding='utf-8')

    assert 'param revealBackendApiInfo bool = true' in bicep
    assert "revealBackendApiInfo ? loadTextContent('../../shared/apim-policies/all-apis-reveal-backend.xml')" in bicep


def test_inference_workbook_update_preserves_live_parameter_values() -> None:
    """Keep portal-edited workbook parameters intact when source visuals are republished."""
    update_script = WORKBOOK_UPDATE_PATH.read_text(encoding='utf-8')

    assert '$existingParameterValues' in update_script
    assert '$parameter.value = $existingParameterValues[$parameter.name]' in update_script
