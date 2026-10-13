"""Offline contracts for the parallel advanced inference-failover API policies."""

import xml.etree.ElementTree as ET
from dataclasses import replace
from types import SimpleNamespace

import pytest

# APIM Samples imports
from test_aoai_v1_migration_contracts import SAMPLE, evidence_namespace, notebook
from test_aoai_v1_migration_helpers import client_for, helpers, report_probes, response


@pytest.mark.parametrize('contract', ['legacy', 'v1'])
def test_advanced_retry_matrix_and_streaming_safety(contract):
    """Match the peer retry matrix with an explicit streaming replay guard."""
    policy = ET.parse(SAMPLE / 'apim-policies' / f'{contract}-advanced.xml').getroot()
    peer = ET.parse(SAMPLE.parent / 'inference-failover' / 'apim-policies' / 'inference-api-policy.xml').getroot()
    backend = policy.find('backend')
    assert len(backend) == 1 and backend[0].tag == 'retry'
    retry = backend[0]
    assert retry.attrib['count'] == '2'
    assert retry.attrib['interval'] == '0' and retry.attrib['first-fast-retry'] == 'true'
    peer_condition = peer.find('backend/retry').attrib['condition'][2:-1]
    assert retry.attrib['condition'] == f'@(!(bool)context.Variables["isStreaming"] && ({peer_condition}))'
    assert retry.find('forward-request').attrib == {
        'timeout': '60', 'buffer-request-body': 'true', 'buffer-response': 'false', 'fail-on-error-status-code': 'false',
    }
    streaming = policy.find("inbound/set-variable[@name='isStreaming']").attrib['value']
    assert 'JTokenType.Boolean' in streaming and '(bool)body["stream"]' in streaming
    assert not list(policy.find('inbound').iter('set-body'))
    assert not list(policy.iter('set-query-parameter'))
    assert policy.find('inbound/authentication-managed-identity').attrib == {'resource': 'https://cognitiveservices.azure.com'}
    removed = {header.attrib['name'] for header in policy.find('inbound').iter('set-header') if header.attrib['exists-action'] == 'delete'}
    assert removed == {'api-key', 'Authorization', 'Ocp-Apim-Subscription-Key'}
    routing = policy.find("inbound/set-variable[@name='backendPool']").attrib['value']
    assert '"-advanced-pool"' in routing and 'Dictionary' not in routing
    rewrite = policy.find('inbound/rewrite-uri').attrib
    if contract == 'legacy':
        assert rewrite['copy-unmatched-params'] == 'true'
        assert 'Uri.EscapeDataString(context.Request.MatchedParameters["deployment"])' in rewrite['template']
    else:
        assert rewrite == {'template': '/openai/v1/chat/completions', 'copy-unmatched-params': 'false'}
        assert 'selector.Type == JTokenType.String' in routing


def test_advanced_pairs_have_identical_retry_and_error_semantics():
    """Routing and telemetry labels may differ, but not the failure-handling matrix."""
    legacy = ET.parse(SAMPLE / 'apim-policies' / 'legacy-advanced.xml').getroot()
    v1 = ET.parse(SAMPLE / 'apim-policies' / 'v1-advanced.xml').getroot()
    for root in (legacy, v1):
        for metadata in root.findall(".//metadata[@name='contract']"):
            metadata.set('value', 'contract')
    for section in ('backend', 'outbound', 'on-error'):
        assert ET.tostring(legacy.find(section)) == ET.tostring(v1.find(section))
    normalized = legacy.find('outbound/choose/when')
    assert normalized.attrib['condition'] == (
        '@(context.Response != null && (context.Response.StatusCode == 500 || context.Response.StatusCode == 502 '
        '|| context.Response.StatusCode == 503 || context.Response.StatusCode == 504))'
    )
    assert normalized.find('set-status').attrib['code'] == '503'
    for section in ('outbound', 'on-error'):
        assert legacy.find(f"{section}/set-header[@name='X-Backend-Retry']") is not None
        assert legacy.find(section)[-1 if section == 'outbound' else -2].tag == 'set-header'
    error_status = legacy.find("on-error/set-variable[@name='errorStatus']").attrib['value']
    assert '"BackendConnectionFailure"' in error_status and '"Timeout"' in error_status
    assert '? 503 : 500' in error_status
    for trace in legacy.iter('trace'):
        assert {metadata.attrib['name'] for metadata in trace.findall('metadata')} <= {
            'contract', 'requestId', 'attempt', 'status', 'source', 'reason',
        }
        assert 'context.Request.Url' not in ET.tostring(trace, encoding = 'unicode')


def test_advanced_breakers_are_isolated_without_extra_capacity():
    """Use the peer failure ranges on distinct APIM destinations, not extra OpenAI deployments."""
    main = (SAMPLE / 'main.bicep').read_text(encoding = 'utf-8')
    advanced_backends = main.split('module advancedBackends', 1)[1].split('module advancedPools', 1)[0]
    assert "backendName: '${model.deploymentName}-advanced-backend'" in advanced_backends
    assert 'url: openAiAccount.properties.endpoint' in advanced_backends
    assert "name: 'failover-on-capacity-or-infrastructure-failure'" in advanced_backends
    assert 'acceptRetryAfter: true' in advanced_backends
    assert "interval: 'PT1M'" in advanced_backends and "tripDuration: 'PT1M'" in advanced_backends
    for minimum, maximum in ((408, 408), (429, 429), (499, 500), (502, 504)):
        assert f'{{ min: {minimum}, max: {maximum} }}' in advanced_backends
    assert main.count("resource openAiAccount 'Microsoft.CognitiveServices/accounts@") == 1
    assert main.count("resource modelDeploymentResources 'Microsoft.CognitiveServices/accounts/deployments@") == 1
    assert "backendPoolName: '${model.deploymentName}-advanced-pool'" in main
    assert 'dependsOn: [advancedBackends]' in main


@pytest.mark.parametrize('name', ['X-Backend-Retry', 'x-backend-retry'])
@pytest.mark.parametrize('count', ['0', '1', '2'])
def test_smoke_retains_bounded_backend_retry_evidence(name, count):
    """APIM retries are distinct from client readiness attempts."""
    rows = response()
    rows[0]['headers'] = {name: count}
    client = client_for(rows)
    result = helpers.test(lambda: client, '/advanced', {}, require_backend_retries = True)
    assert result.backend_retries == int(count) and result.attempts == 1
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('value', [None, '', '3', '-1', '1.0', '01', True, 1])
def test_smoke_rejects_missing_or_malformed_retry_evidence(value):
    """Do not accept an advanced API with missing or invalid attempt telemetry."""
    rows = response()
    rows[0]['headers'] = {} if value is None else {'X-Backend-Retry': value}
    client = client_for(rows)
    with pytest.raises(ValueError, match = 'backend retry'):
        helpers.test(lambda: client, '/advanced', {}, require_backend_retries = True)
    client.__exit__.assert_called_once()


@pytest.mark.parametrize('stage', ['advanced_legacy_success', 'advanced_v1_success'])
def test_report_rejects_partial_advanced_evidence(stage):
    """A successful simple migration cannot hide an incomplete advanced API probe."""
    namespace = evidence_namespace()
    namespace[stage].pop('gpt-5-mini')
    source = next(''.join(cell['source']) for cell in notebook()['cells'] if cell['id'] == 'migration-evidence')
    with pytest.raises(AssertionError, match = 'Run all advanced probes'):
        exec(source, namespace)
    namespace['migration_helpers'].generate_report.assert_not_called()


def test_report_requires_advanced_rejection():
    """The advanced missing-pool check is a required probe, not optional evidence."""
    namespace = evidence_namespace()
    namespace['advanced_v1_rejection'] = None
    source = next(''.join(cell['source']) for cell in notebook()['cells'] if cell['id'] == 'migration-evidence')
    with pytest.raises(AssertionError, match = 'advanced unknown-model rejection'):
        exec(source, namespace)
    namespace['migration_helpers'].generate_report.assert_not_called()


@pytest.mark.parametrize('stage', ['advanced_legacy_success', 'advanced_v1_success'])
@pytest.mark.parametrize('count', [None, -1, 3])
def test_report_rejects_invalid_advanced_retry_counts(stage, count):
    """A successful HTTP response cannot hide missing or unbounded retry evidence."""
    namespace = evidence_namespace()
    result = namespace[stage]['gpt-5-mini']
    namespace[stage]['gpt-5-mini'] = SimpleNamespace(**{**vars(result), 'backend_retries': count})
    source = next(''.join(cell['source']) for cell in notebook()['cells'] if cell['id'] == 'migration-evidence')
    with pytest.raises(AssertionError, match = 'Migration checks failed'):
        exec(source, namespace)
    assert namespace['tests'].total_tests == 48
    assert namespace['tests'].tests_failed == 1
    namespace['migration_helpers'].generate_report.assert_not_called()


def test_combined_report_contains_advanced_stages_and_retry_measurements(tmp_path, monkeypatch):
    """Render the full twelve-probe report with real shared chart and table components."""
    probes = report_probes()
    for stage in ('Advanced Legacy', 'Advanced v1'):
        for baseline in probes[:2]:
            probes.append(helpers.ProbeEvidence(
                stage, baseline.model_name,
                replace(baseline.result, backend_pool = f'{baseline.model_name}-advanced-pool', backend_retries = 2),
            ))
    probes.append(helpers.ProbeEvidence(
        'Advanced v1 Rejection', 'Unknown model', helpers.SmokeResult(500, 1, False), expected_status = 500,
    ))
    monkeypatch.setattr(helpers.plt, 'show', lambda: None)
    figures_before = helpers.plt.get_fignums()
    document = helpers.generate_report(probes, tmp_path / 'advanced.html').read_text(encoding = 'utf-8')
    assert len(probes) == 12
    assert document.count('data:image/png;base64,') == 2
    assert '<th scope="col">Backend Retries</th>' in document
    assert 'Advanced Legacy' in document and 'Advanced v1' in document and 'Advanced v1 Rejection' in document
    assert 'Legacy Before / v1 / Legacy After / Advanced Legacy / Advanced v1' in document
    assert 'gpt-5-mini-advanced-pool' in document and '<td>2</td>' in document
    assert helpers.plt.get_fignums() == figures_before
