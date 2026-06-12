"""Tests for the inference-failover sample-local runtime helpers."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

INFERENCE_FAILOVER_DIR = Path(__file__).resolve().parents[2] / 'samples' / 'inference-failover'
sys.path.insert(0, str(INFERENCE_FAILOVER_DIR))

import inference_failover_helpers as helpers  # noqa: E402
from htmlreport import HtmlList, HtmlSuccess, HtmlText, HtmlWarning  # noqa: E402
from inference_failover_helpers import (  # noqa: E402
    InferenceReportContext,
    InferenceScenario,
    InferenceTrafficRunner,
    build_scenario_report_row,
    format_backend_url_counts,
    format_gateway_distribution,
    generate_local_html_report,
    get_backend_index,
    get_priority_and_weight,
    parse_backend_retry,
    summarize_scenario,
    validate_status,
    with_backend_identifier,
)


def _response(status_code=200, *, headers=None, text='response'):
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {'X-Backend-Retry': '0'}
    response.text = text
    return response


def _create_runner(*, responses=None, sleep=None, clock=None):
    session = MagicMock()
    session.headers = {}
    if responses is not None:
        session.post.side_effect = responses
    runner = InferenceTrafficRunner(
        'https://gateway.example/',
        {'X-Infrastructure': 'test'},
        True,
        session_factory=lambda: session,
        sleep=sleep or MagicMock(),
        clock=clock or MagicMock(side_effect=[1.0, 1.25]),
    )
    return runner, session


@pytest.mark.unit
def test_run_scenario_normalizes_success_and_preserves_model_response():
    response = _response(headers={'X-Backend-Retry': '2', 'X-Backend-URL': 'https://aoai/openai/deployments/a-model'}, text='model output')
    runner, session = _create_runner(responses=[response])
    scenario = InferenceScenario('baseline', '/inference', 'key', {'messages': []}, 1, {'/deployments/a-model': 4})

    results = runner.run_scenario(scenario)

    session.post.assert_called_once_with(
        'https://gateway.example/inference',
        headers={'api-key': 'key'},
        json={'messages': []},
        timeout=120,
    )
    assert session.verify is False
    assert session.headers == {'X-Infrastructure': 'test', 'Content-Type': 'application/json'}
    assert json.loads(results[0]['response']) == {'index': 4, 'backendUrl': response.headers['X-Backend-URL'], 'backendRetry': 2}
    assert results[0]['model_response'] == 'model output'
    assert results[0]['response_time'] == pytest.approx(0.25)


@pytest.mark.unit
def test_run_scenario_keeps_error_body_and_skips_final_sleep():
    responses = [
        _response(429, headers={'X-Backend-Retry': '1'}, text='limited'),
        _response(503, headers={'X-Backend-Retry': '2'}, text='unavailable'),
    ]
    sleep = MagicMock()
    clock = MagicMock(side_effect=[1.0, 1.1, 2.0, 2.2])
    runner, _ = _create_runner(responses=responses, sleep=sleep, clock=clock)
    scenario = InferenceScenario('pressure', 'inference', 'key', {}, 2, {}, sleep_ms=1500)

    results = runner.run_scenario(scenario)

    assert [result['response'] for result in results] == ['limited', 'unavailable']
    sleep.assert_called_once_with(1.5)


@pytest.mark.unit
@pytest.mark.parametrize(('runs', 'sleep_ms', 'message'), [(0, 0, 'runs'), (1, -1, 'sleep')])
def test_run_scenario_rejects_invalid_configuration(runs, sleep_ms, message):
    runner, _ = _create_runner()
    scenario = InferenceScenario('invalid', '/inference', 'key', {}, runs, {}, sleep_ms)

    with pytest.raises(ValueError, match=message):
        runner.run_scenario(scenario)


@pytest.mark.unit
def test_retry_and_status_validation_reject_malformed_responses():
    with pytest.raises(ValueError, match='missing'):
        parse_backend_retry(_response(headers={'Other': 'value'}))
    with pytest.raises(ValueError, match='Invalid X-Backend-Retry'):
        parse_backend_retry(_response(headers={'X-Backend-Retry': 'later'}))
    with pytest.raises(ValueError, match='negative'):
        parse_backend_retry(_response(headers={'X-Backend-Retry': '-1'}))
    with pytest.raises(ValueError, match='Unexpected HTTP 302'):
        validate_status(_response(302, text='redirect'))

    validate_status(_response(200))
    validate_status(_response(400))
    validate_status(_response(599))


@pytest.mark.unit
def test_contract_probes_construct_each_gateway_case():
    responses = [_response(), _response(400), _response(401), _response(404)]
    runner, session = _create_runner(responses=responses)

    results = runner.run_contract_probes('https://gateway.example/inference', 'https://gateway.example/unknown', 'key', {'messages': []})

    assert [results.success.status_code, results.malformed.status_code, results.missing_key.status_code, results.unknown_operation.status_code] == [
        200,
        400,
        401,
        404,
    ]
    assert session.post.call_args_list[1].kwargs['data'] == '{"messages":'
    assert 'headers' not in session.post.call_args_list[2].kwargs
    assert session.post.call_args_list[3].args[0] == 'https://gateway.example/unknown'


@pytest.mark.unit
def test_context_manager_closes_session_after_exception():
    runner, session = _create_runner(responses=[RuntimeError('request failed')])
    scenario = InferenceScenario('failure', '/inference', 'key', {}, 1, {})

    with pytest.raises(RuntimeError, match='request failed'):
        with runner:
            runner.run_scenario(scenario)

    session.close.assert_called_once_with()


@pytest.mark.unit
def test_close_is_idempotent_without_an_open_session():
    runner, session = _create_runner()

    runner.close()
    runner.close()

    session.close.assert_not_called()


@pytest.mark.unit
def test_pause_uses_injected_sleep_and_rejects_negative_values():
    sleep = MagicMock()
    runner, _ = _create_runner(sleep=sleep)

    runner.pause(2)
    runner.pause(0)

    sleep.assert_called_once_with(2)
    with pytest.raises(ValueError, match='must not be negative'):
        runner.pause(-1)


@pytest.mark.unit
def test_summary_and_backend_formatting_cover_success_errors_and_unknown_urls():
    results = [
        {'status_code': 200, 'backend_retry': 0, 'backend_url': 'https://backend-a'},
        {'status_code': 429, 'backend_retry': 1, 'backend_url': 'unknown'},
        {'status_code': 503, 'backend_retry': 2, 'backend_url': 'unknown'},
    ]

    summary = summarize_scenario(results)

    assert summary.successes == 1
    assert summary.client_errors == 1
    assert summary.server_errors == 1
    assert summary.status_code_counts == {200: 1, 429: 1, 503: 1}
    assert summary.retry_counts == {0: 1, 1: 1, 2: 1}
    assert summary.served_backend_urls == ['https://backend-a']
    assert get_backend_index('https://backend-a', {'backend-a': 3}) == 3
    assert get_backend_index('https://other', {'backend-a': 3}) == 99
    assert format_backend_url_counts(results) == '- https://backend-a: 1 request\n- unknown: 2 requests'


@pytest.mark.unit
def test_dataframe_helpers_are_non_mutating_and_idempotent():
    source = pd.DataFrame(
        [['api', 'https://host/openai/deployments/a-model', 1, '1,234.5', '98.2%']],
        columns=['API', 'Backend URL', 'Requests', 'AverageBackendMs', 'SuccessRate'],
    )

    identified = with_backend_identifier(source)
    formatted = format_gateway_distribution(identified)
    repeated = with_backend_identifier(identified)

    assert 'Backend' not in source.columns
    assert identified['Backend'].tolist() == ['a']
    assert repeated.equals(identified)
    assert formatted['Backend'].tolist() == ['a) model']
    assert formatted['AverageBackendMs'].tolist() == ['1,234.5']
    assert formatted['SuccessRate'].tolist() == ['98.20%']
    assert 'Backend URL' not in formatted.columns


@pytest.mark.unit
def test_with_backend_identifier_leaves_frames_without_urls_unchanged():
    source = pd.DataFrame([['api']], columns=['API'])

    result = with_backend_identifier(source)

    assert result.equals(source)
    assert result is not source


@pytest.mark.unit
def test_format_gateway_distribution_leaves_frames_without_backend_urls():
    source = pd.DataFrame([['api', 'not available', 'not available']], columns=['API', 'AverageBackendMs', 'SuccessRate'])

    result = format_gateway_distribution(source)

    assert result['AverageBackendMs'].tolist() == ['']
    assert result['SuccessRate'].tolist() == ['']
    assert 'Backend' not in result.columns
    assert result is not source


@pytest.mark.unit
def test_get_priority_and_weight_parses_legend_label():
    labels = {
        0: 'Priority 1 / Weight 100: PTU (East US 2)',
        3: 'Priority 4 / Weight 50: PAYG (West US 3)',
    }

    assert get_priority_and_weight(0, labels) == (1, 100)
    assert get_priority_and_weight(3, labels) == (4, 50)


@pytest.mark.unit
def test_build_scenario_report_row_handles_empty_results():
    row = build_scenario_report_row('A-1', 'Baseline', [], {}, {})

    assert row == ['', 'A-1', 'Baseline', 0, 0, 0, 'None', 'No requests', 'No scenario requests were captured.']


@pytest.mark.unit
def test_build_scenario_report_row_all_success_without_retries():
    labels = {0: 'Priority 1 / Weight 100: PTU (East US 2)'}
    backend_url_index = {'/deployments/a-model': 0}
    results = [
        {'status_code': 200, 'backend_retry': 0, 'backend_url': 'https://host/deployments/a-model'},
        {'status_code': 200, 'backend_retry': 0, 'backend_url': 'https://host/deployments/a-model'},
    ]

    row = build_scenario_report_row('A-1', 'Baseline', results, backend_url_index, labels)

    assert isinstance(row[0], HtmlSuccess)
    assert row[1:6] == ['A-1', 'Baseline', 2, 2, 0]
    assert row[6] == HtmlText('None', preserve_line_breaks=True)
    assert isinstance(row[7], HtmlText)
    assert 'P1' in row[7].text
    assert isinstance(row[8], HtmlList)
    observations = '\n'.join(row[8].items)
    assert 'All requests returned HTTP 200' in observations
    assert 'no failover beyond P1 observed' in observations
    assert 'no backend failures occurred' in observations


@pytest.mark.unit
def test_build_scenario_report_row_reports_failover_retries_and_terminal_503():
    labels = {
        0: 'Priority 1 / Weight 100: PTU (East US 2)',
        1: 'Priority 2 / Weight 100: PTU (West US 3)',
    }
    backend_url_index = {'/deployments/a-model': 0, '/deployments/b-model': 1}
    results = [
        {'status_code': 200, 'backend_retry': 1, 'backend_url': 'https://host/deployments/b-model'},
        {'status_code': 503, 'backend_retry': 3, 'backend_url': 'unknown'},
    ]

    row = build_scenario_report_row('A-2', 'Sustained Pressure', results, backend_url_index, labels)

    assert isinstance(row[0], HtmlWarning)
    assert row[3:6] == [2, 1, 1]
    assert isinstance(row[6], HtmlText)
    assert '1:' in row[6].text and '3:' in row[6].text
    observations = '\n'.join(row[8].items)
    assert 'routed beyond P1' in observations
    assert 'no resolved backend' in observations
    assert 'HTTP 503 responses' in observations
    assert 'APIM prevented 80.0%' in observations


@pytest.mark.unit
def test_build_scenario_report_row_reports_unresolved_non_503_failure():
    results = [{'status_code': 429, 'backend_retry': 0, 'backend_url': 'unknown'}]

    row = build_scenario_report_row('A-3', 'Capacity Exhausted', results, {}, {})

    assert isinstance(row[0], HtmlWarning)
    assert row[7] == HtmlText('No resolved backend: 1 (100.0%)', preserve_line_breaks=True)
    observations = '\n'.join(row[8].items)
    assert 'caller-visible failures remained' in observations
    assert 'Deepest routed tier' not in observations


def _report_context() -> InferenceReportContext:
    return InferenceReportContext(
        sample_folder='inference-failover',
        apim_source_region='East US 2',
        deployment_name='SIMPLE_APIM',
        resource_group_name='rg-test',
        tenant_id='tenant-id',
        subscription_id='subscription-id',
        apim_name='apim-test',
        workbook_id='/subscriptions/subscription-id/resourceGroups/rg-test/providers/microsoft.insights/workbooks/report',
        log_analytics_id='/subscriptions/subscription-id/resourceGroups/rg-test/providers/Microsoft.OperationalInsights/workspaces/logs',
    )


def _report_results() -> list[list[dict]]:
    result = {
        'run': 1,
        'response': json.dumps({'index': 0}),
        'status_code': 200,
        'response_time': 0.1,
        'backend_retry': 0,
        'backend_url': 'https://host/openai/deployments/a-model',
    }

    return [[result.copy()] for _ in range(6)]


@pytest.mark.unit
def test_generate_local_html_report_owns_rendering_links_and_output(monkeypatch, tmp_path):
    report = MagicMock()
    close_figure = MagicMock()
    output_path = tmp_path / 'report.html'
    report.write.return_value = output_path
    monkeypatch.setattr(helpers, 'HtmlReport', MagicMock(return_value=report))
    monkeypatch.setattr(helpers.plt, 'close', close_figure)
    scenario_figures = [MagicMock() for _ in range(6)]
    monkeypatch.setattr(helpers.charts, 'BarChart', MagicMock(return_value=MagicMock(render=MagicMock(side_effect=scenario_figures))))
    tests = MagicMock(total_tests=3, tests_passed=3, tests_failed=0, errors=[])
    labels = {
        'gpt-5.1': {0: 'Priority 1 / Weight 100: PTU (East US 2)'},
        'gpt-4.1-mini': {0: 'Priority 1 / Weight 100: PTU (East US 2)'},
    }
    indexes = {
        'gpt-5.1': {'/deployments/a-model': 0},
        'gpt-4.1-mini': {'/deployments/a-model': 0},
    }

    result = generate_local_html_report(_report_context(), tests, _report_results(), indexes, labels, output_path=output_path)

    assert result == output_path
    assert report.add_table.call_count == 2
    assert report.add_figure.call_count == 6
    report.add_success_callout.assert_called_once()
    report.add_links.assert_called_once()
    azure_links = report.add_links.call_args.args[1]
    assert azure_links['Workbook'].endswith('/workbook')
    assert azure_links['API Management'].endswith('/overview')
    assert close_figure.call_count == 6
    report.write.assert_called_once_with(output_path)


@pytest.mark.unit
def test_generate_local_html_report_adds_available_telemetry(monkeypatch, tmp_path):
    report = MagicMock()
    close_figure = MagicMock()
    report.write.return_value = tmp_path / 'report.html'
    monkeypatch.setattr(helpers, 'HtmlReport', MagicMock(return_value=report))
    monkeypatch.setattr(helpers.plt, 'close', close_figure)
    scenario_figure = MagicMock()
    monkeypatch.setattr(helpers.charts, 'BarChart', MagicMock(return_value=MagicMock(render=MagicMock(return_value=scenario_figure))))
    tests = MagicMock(total_tests=1, tests_passed=0, tests_failed=1, errors=['failed assertion'])
    labels = {
        'gpt-5.1': {0: 'Priority 1 / Weight 100: PTU (East US 2)'},
        'gpt-4.1-mini': {0: 'Priority 1 / Weight 100: PTU (East US 2)'},
    }
    indexes = {
        'gpt-5.1': {'/deployments/a-model': 0},
        'gpt-4.1-mini': {'/deployments/a-model': 0},
    }
    distribution_frame = pd.DataFrame(
        [['inference-gpt-5-1', 'https://host/openai/deployments/a-model', 1]],
        columns=['API', 'Backend URL', 'Requests'],
    )
    token_frame = pd.DataFrame([['inference-gpt-5-1', 20]], columns=['API', 'TotalTokens'])
    scenario_results = _report_results()
    scenario_results[0][0]['status_code'] = 503

    generate_local_html_report(
        _report_context(),
        tests,
        scenario_results,
        indexes,
        labels,
        distribution_frame,
        token_frame,
        tmp_path / 'report.html',
    )

    assert report.add_table.call_count == 5
    assert report.add_figure.call_count == 8
    report.add_success_callout.assert_not_called()
    assert report.add_table.call_args_list[0].args[0] == 'Assertion Failures'
    assert close_figure.call_count == 8


@pytest.mark.unit
@pytest.mark.parametrize(
    ('scenario_results', 'indexes', 'labels', 'message'),
    (
        ([], {'gpt-5.1': {}, 'gpt-4.1-mini': {}}, {'gpt-5.1': {}, 'gpt-4.1-mini': {}}, 'six scenario'),
        ([[] for _ in range(6)], {'gpt-5.1': {}}, {'gpt-5.1': {}, 'gpt-4.1-mini': {}}, 'gpt-4.1-mini'),
    ),
)
def test_generate_local_html_report_rejects_incomplete_inputs(scenario_results, indexes, labels, message):
    with pytest.raises(ValueError, match=message):
        generate_local_html_report(_report_context(), MagicMock(), scenario_results, indexes, labels)
