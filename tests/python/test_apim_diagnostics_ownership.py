"""Validate APIM resource diagnostic-setting ownership across infrastructures and samples."""

from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
INFRASTRUCTURE_TEMPLATES = (
    'afd-apim-pe',
    'apim-aca',
    'appgw-apim',
    'appgw-apim-pe',
    'simple-apim',
)


@pytest.mark.parametrize('infrastructure_name', INFRASTRUCTURE_TEMPLATES)
def test_infrastructure_owns_canonical_apim_log_analytics_diagnostics(infrastructure_name: str) -> None:
    """Every infrastructure should provision the same gateway diagnostic categories and sink."""
    template = (REPOSITORY_ROOT / 'infrastructure' / infrastructure_name / 'main.bicep').read_text(encoding='utf-8')

    assert '../../shared/bicep/modules/apim/v1/diagnostics.bicep' in template
    assert "diagnosticSettingsNameSuffix: 'diagnostics'" in template
    assert 'enableEventHub: false' in template
    assert 'enableLlmLogs: true' in template
    assert 'enableLogAnalytics: true' in template
    assert 'logAnalyticsWorkspaceId: lawId' in template


def test_telemetry_samples_reuse_canonical_apim_log_analytics_diagnostics() -> None:
    """Samples sharing an APIM instance should update one canonical Log Analytics setting."""
    costing_template = (REPOSITORY_ROOT / 'samples' / 'costing' / 'main.bicep').read_text(encoding='utf-8')
    inference_template = (REPOSITORY_ROOT / 'samples' / 'inference-failover' / 'main.bicep').read_text(encoding='utf-8')

    assert "var diagnosticSettingsNameSuffix = 'diagnostics'" in costing_template
    assert 'enableLlmLogs: true' in costing_template
    assert "diagnosticSettingsNameSuffix: 'diagnostics'" in inference_template


def test_inference_event_hub_diagnostics_do_not_reuse_log_analytics_sink() -> None:
    """The optional Event Hub setting should remain independent from the canonical workspace setting."""
    template = (REPOSITORY_ROOT / 'samples' / 'inference-failover' / 'main.bicep').read_text(encoding='utf-8')
    event_hub_module = template.split('module apimEventHubDiagnostics', maxsplit=1)[1].split('module inferenceApis', maxsplit=1)[0]

    assert 'enableEventHub: true' in event_hub_module
    assert 'enableLogAnalytics: false' in event_hub_module
    assert "logAnalyticsWorkspaceId: ''" in event_hub_module
    assert 'diagnosticSettingsNameSuffix: eventHubDiagnosticsSuffix' in event_hub_module
