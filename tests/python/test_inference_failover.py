"""Regression tests for the AOAI-only Inference Failover sample assets."""

import json
from pathlib import Path
from xml.etree import ElementTree

SAMPLE_PATH = Path(__file__).resolve().parents[2] / 'samples' / 'inference-failover'
SIMPLE_APIM_BICEP_PATH = Path(__file__).resolve().parents[2] / 'infrastructure' / 'simple-apim' / 'main.bicep'
BICEP_PATH = SAMPLE_PATH / 'main.bicep'
NOTEBOOK_PATH = SAMPLE_PATH / 'create.ipynb'
POLICY_PATH = SAMPLE_PATH / 'inference-api-policy.xml'
WORKBOOK_PATH = SAMPLE_PATH / 'inference-failover.workbook.json'
WORKBOOK_UPDATE_PATH = SAMPLE_PATH / 'update-workbook.ps1'
KQL_PATHS = [
    SAMPLE_PATH / 'backend-distribution.kql',
    SAMPLE_PATH / 'failover-outcomes.kql',
    SAMPLE_PATH / 'token-throughput.kql',
    SAMPLE_PATH / 'verify-llm-ingestion.kql',
]
EXPECTED_BACKENDS = {
    'gpt-5-1-PTU-eastus2',
    'gpt-5-1-PAYGO-eastus2',
    'gpt-5-1-PTU-westus3',
    'gpt-5-1-PAYGO-westus3',
    'gpt-5-1-PAYGO-southcentralus',
    'gpt-4-1-mini-PTU-eastus2',
    'gpt-4-1-mini-PAYGO-eastus2',
    'gpt-4-1-mini-PTU-westus3',
    'gpt-4-1-mini-PAYGO-southcentralus',
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
    assert 'query - backend-distribution' in item_names
    assert 'query - token-throughput' in item_names
    assert 'query - backend-latency-trend' in item_names
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
    assert "name: 'gpt-5-1-PAYGO-eastus2'\n        priority: 3" in bicep
    assert "name: 'gpt-4-1-mini-PTU-westus3'\n        priority: 2" in bicep
    assert "name: 'gpt-4-1-mini-PAYGO-eastus2'\n        priority: 3" in bicep
    backend_declaration_order = [
        'gpt-5-1-PTU-eastus2',
        'gpt-5-1-PTU-westus3',
        'gpt-5-1-PAYGO-eastus2',
        'gpt-5-1-PAYGO-westus3',
        'gpt-5-1-PAYGO-southcentralus',
        'gpt-4-1-mini-PTU-eastus2',
        'gpt-4-1-mini-PTU-westus3',
        'gpt-4-1-mini-PAYGO-eastus2',
        'gpt-4-1-mini-PAYGO-southcentralus',
    ]
    declaration_offsets = [bicep.index(f"backendName: '{backend}'") for backend in backend_declaration_order]
    assert declaration_offsets == sorted(declaration_offsets)


def test_inference_notebook_is_clean_and_defaults_to_simple_apim() -> None:
    """Retain the intended first-run experience and output-free checked-in notebook."""
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding='utf-8'))
    code_cells = [cell for cell in notebook['cells'] if cell['cell_type'] == 'code']
    code_source = '\n'.join(''.join(cell['source']) for cell in code_cells)

    assert all(not cell['outputs'] for cell in code_cells)
    assert 'index = 1' in ''.join(code_cells[0]['source'])
    assert 'deployment = INFRASTRUCTURE.SIMPLE_APIM' in code_source
    assert "response.headers.get('X-Backend-URL', '')" in code_source
    assert 'X-Backend-Id' not in code_source
    assert 'plt.show()' in code_source
    assert 'Route Graph' in '\n'.join(''.join(cell['source']) for cell in notebook['cells'])


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
