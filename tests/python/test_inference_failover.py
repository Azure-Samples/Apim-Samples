"""Regression tests for the AOAI-only Inference Failover sample assets."""

import json
from pathlib import Path
from xml.etree import ElementTree

SAMPLE_PATH = Path(__file__).resolve().parents[2] / 'samples' / 'inference-failover'
SIMPLE_APIM_BICEP_PATH = Path(__file__).resolve().parents[2] / 'infrastructure' / 'simple-apim' / 'main.bicep'
BICEP_PATH = SAMPLE_PATH / 'main.bicep'
DIAGNOSTICS_BICEP_PATH = Path(__file__).resolve().parents[2] / 'shared' / 'bicep' / 'modules' / 'apim' / 'v1' / 'diagnostics.bicep'
NOTEBOOK_PATH = SAMPLE_PATH / 'create.ipynb'
POLICY_PATH = SAMPLE_PATH / 'inference-api-policy.xml'
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
    assert 'cost export' not in serialized
    assert 'business unit' not in serialized
    assert 'budget' not in serialized


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
    assert 'InferenceFallbackExhausted' in query_text
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
    assert 'authentication-managed-identity' in api_policy
    assert 'https://cognitiveservices.azure.com' in api_policy
    assert 'count="RETRY_COUNT"' in api_policy
    assert 'api-key' not in api_policy
    assert 'StatusCode == 429' in api_policy
    assert 'StatusCode == 503' in api_policy
    assert 'interval="1"' in api_policy
    assert 'interval="0"' not in api_policy
    assert 'buffer-request-body="true"' in api_policy
    assert 'Inference service is temporarily unavailable.' in api_policy
    assert 'BackendId' not in api_policy
    assert 'InferenceRequestAccepted' in api_policy
    assert 'InferenceBackendAttemptComplete' in api_policy
    assert 'InferenceGatewayResponse' in api_policy
    assert 'InferenceFallbackExhausted' in api_policy
    assert api_policy.count('<trace source="InferenceFailover"') == 4
    assert api_policy.count('<set-header name="X-Backend-Retry" exists-action="override">') == 3
    assert '((int)context.Variables["backendAttempt"]) - 1 : 0' in api_policy
    assert api_policy.index('<set-variable name="backendAttempt" value="@(0)" />') < api_policy.index('<authentication-managed-identity')


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
    assert 'min: 429' in bicep
    assert 'min: 503' in bicep
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
    assert "response.headers.get('X-Backend-URL', 'unknown')" in code_source
    assert "response.headers.get('X-Backend-Retry')" in code_source
    assert "'backend_retry': backend_retry" in code_source
    assert 'X-Backend-Id' not in code_source
    assert "queries_path = Path(utils.determine_policy_path('queries', sample_folder))" in code_source
    assert "queries_path / 'verify-llm-ingestion.kql'" in code_source
    assert "queries_path / 'backend-distribution.kql'" in code_source
    assert "queries_path / 'token-throughput.kql'" in code_source
    assert "columns=['API', 'Backend URL', 'Requests', 'Successes', 'Throttled', 'Failures', 'AverageBackendMs', 'SuccessRate']" in code_source
    assert 'def with_backend_identifier(frame: pd.DataFrame) -> pd.DataFrame:' in code_source
    assert "backend_identifiers = frame['Backend URL'].str.extract(r'/deployments/([a-z])-', expand=False).fillna('')" in code_source
    assert "frame.insert(1, 'Backend', backend_identifiers)" in code_source
    assert "frame['Backend'] = frame['Backend'].replace('?', '')" in code_source
    assert 'distribution_frame = with_backend_identifier(distribution_frame)' in code_source
    assert 'def format_gateway_distribution(frame: pd.DataFrame) -> pd.DataFrame:' in code_source
    assert "backend_names = display_frame['Backend URL'].str.extract(r'/deployments/([a-z]-[^/]+)', expand=False).fillna('')" in code_source
    assert "display_frame['Backend'] = backend_names.str.replace('-', ') ', n=1, regex=False)" in code_source
    assert "display_frame = display_frame.drop(columns=['Backend URL'])" in code_source
    assert "display_frame['AverageBackendMs'] = average_backend_ms.map(lambda value: '' if pd.isna(value) else f'{value:,.1f}')" in code_source
    assert "display_frame['SuccessRate'] = success_rate.map(lambda value: '' if pd.isna(value) else f'{value:.2f}%')" in code_source
    assert 'distribution_frame = format_gateway_distribution(distribution_frame)' in code_source
    assert code_source.count("distribution_frame.pivot(index='API', columns='Backend', values='Requests')") == 2
    assert "columns=['API', 'Backend URL', 'Model', 'Requests', 'PromptTokens', 'CompletionTokens', 'TotalTokens']" in code_source
    assert 'token_frame = with_backend_identifier(token_frame)' in code_source
    assert 'plt.show()' in code_source
    assert 'Route Graph' in '\n'.join(''.join(cell['source']) for cell in notebook['cells'])


def test_inference_notebook_generates_local_html_report() -> None:
    """Keep the end-of-run local report and link in the notebook flow."""
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding='utf-8'))
    code_source = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code')

    assert 'import htmlreport' in code_source
    assert 'importlib.reload(htmlreport)' in code_source
    assert "'inference-failover-report.html'" in code_source
    assert "'', 'Test #', 'Scenario', 'Requests', 'HTTP 200', 'Other', 'APIM retries', 'Priority / weight mix', 'What the data says'" in code_source
    assert "htmlreport.HtmlText(f'Scenario Outcomes: {model_name}', bold_tokens=(model_name,))" in code_source
    assert 'if retry_count > 0' in code_source
    assert 'caller_succeeded = not non_200_responses' in code_source
    assert "htmlreport.HtmlSuccess('All requests returned HTTP 200')" in code_source
    assert "else htmlreport.HtmlWarning('Some requests returned non-200 responses')" in code_source
    assert "observation_items = tuple(f'{item.strip()}' for item in '; '.join(observations).split(';'))" in code_source
    assert 'htmlreport.HtmlList(observation_items)' in code_source
    assert 'htmlreport.HtmlText(retry_mix, preserve_line_breaks=True)' in code_source
    assert 'def get_priority_and_weight(' in code_source
    assert "weights_by_priority.setdefault(priority, []).append(f'W{weight}: {count} ({count / total_requests:.1%})')" in code_source
    assert "priority_mix = '\\n'.join(f'P{priority}: {\", \".join(weight_mix)}'" in code_source
    assert 'htmlreport.HtmlText(priority_mix, bold_tokens=priority_tokens, preserve_line_breaks=True)' in code_source
    assert "column_widths=['4%', '5%', '10%', '6%', '6%', '5%', '11%', '17%', '36%']" in code_source
    assert "'A-1',\n                'Baseline Warm Path'" in code_source
    assert "'B-1',\n                'Baseline Warm Path'" in code_source
    assert "add_scenario_figure(report, f'{test_id}) {title}', description, api_results, backend_labels)" in code_source
    assert "'The green checkmark indicates that every request returned HTTP 200'," in code_source
    assert 'highlight_success=False' in code_source
    assert 'The amber warning triangle indicates that one or more requests returned a caller-visible non-200 response' in code_source
    assert "f'APIM source region: {apim_source_region} | Deployment: {nb_helper.deployment.name} | Resource group: {rg_name}'" in code_source
    assert 'report.add_info_callout(' in code_source
    assert "'Lab Capacity Is Intentionally Low'" in code_source
    assert "'Each regional Azure OpenAI deployment is intentionally configured at 1,000 TPM so that" in code_source
    assert 'observed_backend_failures = backend_retries_absorbed + caller_visible_failures' in code_source
    assert 'shielded_percentage = backend_retries_absorbed / observed_backend_failures * 100' in code_source
    assert "f'APIM absorbed {backend_retries_absorbed} backend failures and sent {caller_visible_failures} failures to callers'" in code_source
    assert "f'APIM prevented {shielded_percentage:.1f}% of observed failed backend attempts from reaching callers'" in code_source
    assert 'terminal_503_responses = status_counts.get(503, 0)' in code_source
    assert 'caller-visible HTTP 503 responses followed eligible-capacity exhaustion in the low-TPM pool' in code_source
    assert "'Observed X-Backend-URL values'" not in code_source.split('report = htmlreport.HtmlReport(', maxsplit=1)[1]
    assert 'if all_scenario_requests_succeeded:' in code_source
    assert 'report.add_success_callout(' in code_source
    assert "'All scenario requests returned HTTP 200'" in code_source
    assert "print_val('Local HTML report', report_url)" in code_source


def test_inference_notebook_uses_tuned_gpt_4_1_mini_pressure_window() -> None:
    """Keep the independent pool pressure run demonstrative without flooding callers with terminal failures."""
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding='utf-8'))
    notebook_source = '\n'.join(''.join(cell['source']) for cell in notebook['cells'])

    assert '| 3 | Sustained pressure | gpt-4.1-mini | 15 | none |' in notebook_source
    assert 'pressure_payload, 15, gpt_4_1_mini_backend_url_index' in notebook_source
    assert 'tests.verify(len(scenario3_gpt_4_1_mini), 15)' in notebook_source
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
