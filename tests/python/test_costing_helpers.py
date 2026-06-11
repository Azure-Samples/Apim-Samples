"""Tests for `samples/costing/_helpers.py` 6-mode AOAI traffic dispatcher."""

import base64
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest
import requests as http_requests

# APIM Samples imports
COSTING_DIR = Path(__file__).resolve().parents[2] / 'samples' / 'costing'
sys.path.insert(0, str(COSTING_DIR))

import _helpers as costing_helpers  # noqa: E402
from _helpers import send_aoai_traffic  # noqa: E402

CHAT_URL = 'https://apim.example.com/aoai/deployments/gpt/chat/completions'
RESPONSES_URL = 'https://apim.example.com/aoai/responses'
CALLER_HEADERS = {'Ocp-Apim-Subscription-Key': 'k', 'Authorization': 'Bearer t'}

CHAT_BODY = {'messages': [{'role': 'user', 'content': 'hi'}], 'max_completion_tokens': 50}
STREAM_BODY = {**CHAT_BODY, 'stream': True, 'stream_options': {'include_usage': True}}
STREAM_BODY_NO_USAGE = {**CHAT_BODY, 'stream': True}
RESPONSES_BODY = {'model': 'gpt', 'input': 'hi', 'max_output_tokens': 50}
RESPONSES_STREAM_BODY = {**RESPONSES_BODY, 'stream': True}
RESPONSES_STATELESS_BODY = {**RESPONSES_BODY, 'store': False}

ALL_KEYS = (
    'chat_non_streaming',
    'chat_stream_with_usage',
    'chat_stream_without_usage',
    'responses_non_streaming',
    'responses_stream',
    'responses_non_streaming_stateless',
)


def _make_session() -> MagicMock:
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.iter_lines.return_value = iter([])
    session.post.return_value = response
    return session


def _full_kwargs() -> dict:
    return {
        'chat_body': CHAT_BODY,
        'stream_body': STREAM_BODY,
        'stream_body_without_usage': STREAM_BODY_NO_USAGE,
        'responses_url': RESPONSES_URL,
        'responses_body': RESPONSES_BODY,
        'responses_stream_body': RESPONSES_STREAM_BODY,
        'responses_stateless_body': RESPONSES_STATELESS_BODY,
    }


def test_six_requests_cycle_all_six_modes_exactly_once():
    session = _make_session()

    delivered, planned, bailed = send_aoai_traffic(session, CHAT_URL, CALLER_HEADERS, 6, **_full_kwargs())

    assert bailed is False
    for key in ALL_KEYS:
        assert delivered[key] == 1, f'{key} should have exactly one delivered request'
        assert planned[key] == 1, f'{key} should have exactly one planned request'
    assert session.post.call_count == 6


def test_dispatcher_routes_each_mode_to_correct_url_and_body():
    session = _make_session()

    send_aoai_traffic(session, CHAT_URL, CALLER_HEADERS, 6, **_full_kwargs())

    calls = session.post.call_args_list
    expected = [
        (CHAT_URL, CHAT_BODY),
        (CHAT_URL, STREAM_BODY),
        (CHAT_URL, STREAM_BODY_NO_USAGE),
        (RESPONSES_URL, RESPONSES_BODY),
        (RESPONSES_URL, RESPONSES_STREAM_BODY),
        (RESPONSES_URL, RESPONSES_STATELESS_BODY),
    ]

    for j, (url, body) in enumerate(expected):
        args, kwargs = calls[j]
        assert args[0] == url, f'mode {j} url mismatch'
        assert kwargs['json'] == body, f'mode {j} body mismatch'


def test_responses_stateless_body_carries_store_false():
    session = _make_session()

    send_aoai_traffic(session, CHAT_URL, CALLER_HEADERS, 6, **_full_kwargs())

    mode_5_call = session.post.call_args_list[5]
    assert mode_5_call.kwargs['json'].get('store') is False


def test_streaming_modes_drain_response_lines():
    session = _make_session()
    session.post.return_value.iter_lines.return_value = iter(['data: chunk'])

    send_aoai_traffic(session, CHAT_URL, CALLER_HEADERS, 6, **_full_kwargs())

    # Modes 1, 2, 4 are streaming; iter_lines must be called for each.
    response = session.post.return_value
    assert response.iter_lines.call_count == 3


def test_falls_back_to_chat_when_responses_inputs_missing():
    session = _make_session()

    kwargs = _full_kwargs()
    kwargs['responses_url'] = None
    kwargs['responses_body'] = None
    kwargs['responses_stream_body'] = None
    kwargs['responses_stateless_body'] = None

    delivered, planned, _ = send_aoai_traffic(session, CHAT_URL, CALLER_HEADERS, 6, **kwargs)

    # Modes 3 and 5 should fall back to mode 0 (chat non-streaming);
    # mode 4 should fall back to mode 1 (chat streaming with usage).
    assert delivered['responses_non_streaming'] == 0
    assert delivered['responses_stream'] == 0
    assert delivered['responses_non_streaming_stateless'] == 0
    assert delivered['chat_non_streaming'] == 3  # j=0, j=3 (fallback), j=5 (fallback) -> wait recount
    assert delivered['chat_stream_with_usage'] == 2  # j=1, j=4 (fallback)
    assert delivered['chat_stream_without_usage'] == 1  # j=2
    assert sum(planned.values()) == 6


def test_falls_back_when_stream_body_without_usage_missing():
    session = _make_session()

    kwargs = _full_kwargs()
    kwargs['stream_body_without_usage'] = None

    delivered, _planned, _ = send_aoai_traffic(session, CHAT_URL, CALLER_HEADERS, 6, **kwargs)

    # Mode 2 should fall back to mode 1 (stream_body with usage).
    assert delivered['chat_stream_without_usage'] == 0
    assert delivered['chat_stream_with_usage'] == 2  # j=1 + j=2 (fallback)


def test_timeout_bails_remaining_requests():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.iter_lines.return_value = iter([])

    # First call succeeds, second times out, remainder should be skipped.
    session.post.side_effect = [response, http_requests.Timeout()]

    delivered, planned, bailed = send_aoai_traffic(session, CHAT_URL, CALLER_HEADERS, 6, **_full_kwargs())

    assert bailed is True
    assert sum(delivered.values()) == 1
    assert sum(planned.values()) == 2  # planned is incremented before the post call
    assert session.post.call_count == 2


def test_timeout_prints_warning(monkeypatch):
    session = MagicMock()
    session.post.side_effect = http_requests.Timeout()
    warning = MagicMock()
    monkeypatch.setattr(costing_helpers, 'print_warning', warning)

    _delivered, _planned, bailed = send_aoai_traffic(session, CHAT_URL, CALLER_HEADERS, 1, **_full_kwargs())

    assert bailed is True
    assert '1/1' in warning.call_args.args[0]


@pytest.mark.parametrize('count', [0, 1, 7, 13])
def test_planned_count_always_equals_request_count(count):
    session = _make_session()

    _delivered, planned, _ = send_aoai_traffic(session, CHAT_URL, CALLER_HEADERS, count, **_full_kwargs())

    assert sum(planned.values()) == count


def _result(*, success=True, text='', json_data=None):
    result = MagicMock()
    result.success = success
    result.text = text
    result.json_data = json_data or {}
    return result


def test_make_fake_jwt_contains_unsigned_appid_claim():
    token = costing_helpers.make_fake_jwt('app-123')
    header_part, payload_part, signature = token.split('.')

    header = json.loads(base64.urlsafe_b64decode(f'{header_part}=='))
    payload = json.loads(base64.urlsafe_b64decode(f'{payload_part}=='))

    assert header == {'alg': 'none', 'typ': 'JWT'}
    assert payload == {'appid': 'app-123'}
    assert not signature


def test_build_session_configures_headers_tls_and_retries(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(costing_helpers.http_requests, 'Session', lambda: session)

    returned = costing_helpers.build_session(
        {'Host': 'gateway.example'},
        True,
        extra_headers={'Authorization': 'Bearer token'},
        with_retries=True,
    )

    assert returned is session
    assert session.verify is False
    assert session.headers.update.call_args_list == [call({'Host': 'gateway.example'}), call({'Authorization': 'Bearer token'})]
    assert [mount.args[0] for mount in session.mount.call_args_list] == ['https://', 'http://']
    retry = session.mount.call_args_list[0].args[1].max_retries
    assert retry.total == 4
    assert retry.status_forcelist == [502, 503, 504]


def test_build_session_accepts_empty_headers_without_retries(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(costing_helpers.http_requests, 'Session', lambda: session)

    costing_helpers.build_session(None, False)

    assert session.verify is True
    session.headers.update.assert_not_called()
    session.mount.assert_not_called()


def test_purge_traffic_source_handles_missing_unchanged_and_removed(tmp_path):
    path = tmp_path / 'traffic.json'
    assert costing_helpers.purge_traffic_source(path, 'remove') is False

    path.write_text(json.dumps({'trafficSources': [{'name': 'keep'}]}), encoding='utf-8')
    assert costing_helpers.purge_traffic_source(path, 'remove') is False

    path.write_text(json.dumps({'trafficSources': [{'name': 'remove'}, {'name': 'keep'}]}), encoding='utf-8')
    assert costing_helpers.purge_traffic_source(path, 'remove') is True
    persisted = json.loads(path.read_text(encoding='utf-8'))
    assert persisted['trafficSources'] == [{'name': 'keep'}]
    assert persisted['generatedUtc'].endswith('+00:00')


def test_persist_traffic_source_creates_then_replaces_named_entry(tmp_path):
    path = tmp_path / 'traffic.json'
    common = {'sample_folder': 'costing', 'rg_name': 'rg', 'apim_name': 'apim'}

    costing_helpers.persist_traffic_source(path, source_entry={'name': 'one', 'totalRequests': 1}, **common)
    costing_helpers.persist_traffic_source(path, source_entry={'name': 'two', 'totalRequests': 2}, **common)
    costing_helpers.persist_traffic_source(path, source_entry={'name': 'one', 'totalRequests': 3}, **common)

    persisted = json.loads(path.read_text(encoding='utf-8'))
    assert persisted['sampleFolder'] == 'costing'
    assert persisted['resourceGroup'] == 'rg'
    assert persisted['apimService'] == 'apim'
    assert persisted['trafficSources'] == [
        {'name': 'two', 'totalRequests': 2},
        {'name': 'one', 'totalRequests': 3},
    ]


def test_send_requests_counts_responses_and_ignores_transport_errors():
    session = MagicMock()
    session.request.side_effect = [MagicMock(), http_requests.ConnectionError('reset'), MagicMock()]

    delivered = costing_helpers.send_requests(session, 'POST', 'https://example', 3, headers={'x': 'y'}, timeout=7)

    assert delivered == 2
    assert session.request.call_count == 3
    session.request.assert_called_with('POST', 'https://example', headers={'x': 'y'}, timeout=7)


def test_get_traffic_endpoint_returns_resolved_values(monkeypatch):
    monkeypatch.setattr(costing_helpers.utils, 'get_endpoint', lambda *_: ('https://endpoint', {'Host': 'example'}, True))
    key_mock = MagicMock(return_value='subscription-key')
    monkeypatch.setattr(costing_helpers, 'get_apim_subscription_key', key_mock)

    result = costing_helpers.get_traffic_endpoint('deployment', 'rg', 'gateway', 'apim', api_id='api-id')

    assert result == ('https://endpoint', {'Host': 'example'}, True, 'subscription-key')
    key_mock.assert_called_once_with('apim', 'rg', sid='api-id')


def test_get_traffic_endpoint_rejects_missing_subscription_key(monkeypatch):
    monkeypatch.setattr(costing_helpers.utils, 'get_endpoint', lambda *_: ('https://endpoint', {}, False))
    monkeypatch.setattr(costing_helpers, 'get_apim_subscription_key', lambda *_args, **_kwargs: '')

    with pytest.raises(RuntimeError, match='api-id'):
        costing_helpers.get_traffic_endpoint('deployment', 'rg', 'gateway', 'apim', api_id='api-id')


def test_acquire_entraid_token_returns_claims(monkeypatch):
    payload = base64.urlsafe_b64encode(json.dumps({'appid': 'client'}).encode()).rstrip(b'=').decode()
    response = MagicMock(status_code=200)
    response.json.return_value = {'access_token': f'header.{payload}.signature'}
    post = MagicMock(return_value=response)
    monkeypatch.setattr(costing_helpers.http_requests, 'post', post)

    token, claims = costing_helpers.acquire_entraid_token('tenant', 'client', 'secret')

    assert token == f'header.{payload}.signature'
    assert claims == {'appid': 'client'}
    assert post.call_args.kwargs['data']['scope'] == 'api://client/.default'


def test_acquire_entraid_token_reports_http_failure(monkeypatch):
    response = MagicMock(status_code=401, text='invalid credentials')
    monkeypatch.setattr(costing_helpers.http_requests, 'post', lambda *_args, **_kwargs: response)
    print_error = MagicMock()
    monkeypatch.setattr(costing_helpers, 'print_error', print_error)

    assert costing_helpers.acquire_entraid_token('tenant', 'client', 'secret') is None
    assert '401' in print_error.call_args.args[0]


def test_dispatcher_ignores_request_errors_and_non_200_streams():
    session = _make_session()
    failed_stream = MagicMock(status_code=500)
    session.post.side_effect = [http_requests.ConnectionError('reset'), failed_stream]

    delivered, planned, bailed = send_aoai_traffic(session, CHAT_URL, CALLER_HEADERS, 2, **_full_kwargs())

    assert bailed is False
    assert sum(planned.values()) == 2
    assert sum(delivered.values()) == 1
    failed_stream.iter_lines.assert_not_called()


def test_print_portal_links_formats_deployed_and_missing_urls(monkeypatch):
    print_info = MagicMock()
    print_plain = MagicMock()
    print_val = MagicMock()
    monkeypatch.setattr(costing_helpers, 'print_info', print_info)
    monkeypatch.setattr(costing_helpers, 'print_plain', print_plain)
    monkeypatch.setattr(costing_helpers, 'print_val', print_val)

    costing_helpers.print_portal_links([('Workbook', 'https://workbook'), ('Optional', None)])

    print_plain.assert_any_call('       https://workbook')
    print_plain.assert_any_call('   (not deployed)')
    print_val.assert_called_once_with('WORKBOOK URL', 'https://workbook')


def _write_costing_policy_files(root: Path) -> None:
    (root / 'shared' / 'apim-policies' / 'fragments').mkdir(parents=True)
    (root / 'shared' / 'apim-policies' / 'fragments' / 'pf-ensure-stream-include-usage.xml').write_text('<fragment />', encoding='utf-8')
    for name in (
        'pf-extract-caller-id.xml',
        'emit_metric_caller_id.xml',
        'mock-ai-response.xml',
        'aoai-gateway-operation.xml',
        'aoai-gateway-responses-operation.xml',
    ):
        (root / name).write_text(f'<policies>{name}</policies>', encoding='utf-8')
    (root / 'emit_metric_caller_tokens.xml').write_text(
        '<policies>\n<!-- Ensure streaming AI requests include stream_options.include_usage = true (reusable fragment) -->\n'
        '<include-fragment fragment-id="Ensure-Stream-Include-Usage" />\n</policies>',
        encoding='utf-8',
    )


@pytest.mark.parametrize(
    ('entraid', 'tokens', 'foundry', 'force_stream', 'expected_api_count', 'expected_fragment_count'),
    [
        (False, False, False, False, 1, 1),
        (True, True, False, False, 3, 1),
        (False, True, True, True, 3, 2),
        (False, False, True, True, 1, 1),
    ],
)
def test_build_costing_apis_honors_feature_toggles(
    monkeypatch, tmp_path, entraid, tokens, foundry, force_stream, expected_api_count, expected_fragment_count
):
    _write_costing_policy_files(tmp_path)
    monkeypatch.setattr(costing_helpers.utils, 'determine_policy_path', lambda name, _folder: tmp_path / name)
    monkeypatch.setattr(costing_helpers.utils, 'get_project_root', lambda: tmp_path)

    apis, fragments, paths = costing_helpers.build_costing_apis(
        'prefix-',
        'costing',
        ['base'],
        enable_entraid_tracking=entraid,
        enable_token_tracking=tokens,
        enable_foundry=foundry,
        force_stream_include_usage=force_stream,
    )

    assert len(apis) == expected_api_count
    assert len(fragments) == expected_fragment_count
    assert bool(paths['entraid_api_path']) is entraid
    assert bool(paths['token_api_path']) is tokens
    assert bool(paths['aoai_api_path']) is (tokens and foundry)
    if tokens and not force_stream:
        assert 'Ensure-Stream-Include-Usage' not in apis[-1].policyXml


@pytest.mark.parametrize(
    ('provider_result', 'expected_message'),
    [(_result(success=False), 'not registered'), (_result(text='Registering'), 'not registered')],
)
def test_configure_cost_export_stops_when_provider_is_unavailable(monkeypatch, provider_result, expected_message):
    monkeypatch.setattr(costing_helpers, 'run', MagicMock(return_value=provider_result))
    print_error = MagicMock()
    monkeypatch.setattr(costing_helpers, 'print_error', print_error)

    result = costing_helpers.configure_cost_export(subscription_id='sub', rg_name='rg', storage_account_name='storage', cost_export_name='export')

    assert result is False
    assert expected_message in print_error.call_args.args[0]


def test_configure_cost_export_recreates_assigns_role_and_cleans_temp_file(monkeypatch):
    responses = [
        _result(text='Registered'),
        _result(success=True),
        _result(success=True),
        _result(success=True, text=json.dumps({'identity': {'principalId': 'principal'}})),
        _result(success=True),
    ]
    run = MagicMock(side_effect=responses)
    monkeypatch.setattr(costing_helpers, 'run', run)
    print_val = MagicMock()
    monkeypatch.setattr(costing_helpers, 'print_val', print_val)

    assert costing_helpers.configure_cost_export(
        subscription_id='sub', rg_name='rg', storage_account_name='storage', cost_export_name='export', cost_export_frequency='Weekly'
    )

    put_command = run.call_args_list[3].args[0]
    body_path = Path(put_command.split('--body @', maxsplit=1)[1].split(' -o json', maxsplit=1)[0])
    assert not body_path.exists()
    print_val.assert_any_call('Export frequency', 'Weekly')
    assert 'az role assignment create' in run.call_args_list[4].args[0]


@pytest.mark.parametrize(
    ('export_result', 'role_success', 'expected'),
    [
        (_result(success=False), True, False),
        (_result(success=True, text='{}'), True, True),
        (_result(success=True, text='{"identity":{"principalId":"p"}}'), False, True),
    ],
)
def test_configure_cost_export_handles_create_identity_and_role_failures(monkeypatch, export_result, role_success, expected):
    responses = [_result(text='Registered'), _result(success=False), export_result, _result(success=role_success)]
    monkeypatch.setattr(costing_helpers, 'run', MagicMock(side_effect=responses))

    result = costing_helpers.configure_cost_export(
        subscription_id='sub', rg_name='rg', storage_account_name='storage', cost_export_name='export', cost_export_frequency='unknown'
    )

    assert result is expected


def test_create_bu_budget_alerts_skips_without_email(monkeypatch):
    run = MagicMock()
    monkeypatch.setattr(costing_helpers, 'run', run)

    costing_helpers.create_bu_budget_alerts(
        subscription_id='sub',
        rg_name='rg',
        rg_location='eastus',
        log_analytics_name='law',
        alert_email='',
        alert_threshold=10,
        bu_names=['bu-one'],
        sample_folder='costing',
        index=1,
    )

    run.assert_not_called()


def test_create_bu_budget_alerts_stops_when_action_group_fails(monkeypatch):
    run = MagicMock(side_effect=[_result(text='workspace-id'), _result(success=False, text='denied')])
    monkeypatch.setattr(costing_helpers, 'run', run)

    costing_helpers.create_bu_budget_alerts(
        subscription_id='sub',
        rg_name='rg',
        rg_location='eastus',
        log_analytics_name='law',
        alert_email='a@example.com',
        alert_threshold=10,
        bu_names=['bu-one'],
        sample_folder='costing',
        index=1,
    )

    assert run.call_count == 2


def test_create_bu_budget_alerts_reports_per_bu_results_and_cleans_files(monkeypatch, tmp_path):
    query_dir = tmp_path / 'samples' / 'costing' / 'queries'
    query_dir.mkdir(parents=True)
    (query_dir / 'budget-alert-threshold.kql').write_text('Logs | count', encoding='utf-8')
    monkeypatch.setattr(costing_helpers.utils, 'get_project_root', lambda: tmp_path)
    run = MagicMock(
        side_effect=[
            _result(text='workspace-id'),
            _result(json_data={'id': 'action-group-id'}),
            _result(success=True),
            _result(success=False, text='bad query'),
        ]
    )
    monkeypatch.setattr(costing_helpers, 'run', run)

    costing_helpers.create_bu_budget_alerts(
        subscription_id='sub',
        rg_name='rg',
        rg_location='eastus',
        log_analytics_name='law',
        alert_email='a@example.com',
        alert_threshold=10,
        bu_names=['bu-one', 'bu-two'],
        sample_folder='costing',
        index=2,
    )

    for alert_call in run.call_args_list[2:]:
        body_path = Path(alert_call.args[0].split('--body @', maxsplit=1)[1])
        assert not body_path.exists()


class _TableSpy:
    instances = []

    def __init__(self):
        self.rows = None
        self.total_args = None
        self.__class__.instances.append(self)

    def header(self, *_args):
        pass

    def populate(self, rows):
        self.rows = rows

    def total(self, *args):
        self.total_args = args

    def print(self):
        pass


def test_print_aoai_traffic_summary_aggregates_all_modes(monkeypatch):
    _TableSpy.instances = []
    monkeypatch.setattr(costing_helpers, 'TableLogger', _TableSpy)
    counts = {
        'chat_non_streaming': 1,
        'chat_stream_with_usage': 2,
        'chat_stream_without_usage': 3,
        'responses_non_streaming': 4,
        'responses_stream': 5,
        'responses_non_streaming_stateless': 6,
    }

    totals = costing_helpers.print_aoai_traffic_summary({'model': counts}, {('bu', 'model'): counts})

    assert totals == (6, 15, 21)
    assert _TableSpy.instances[0].rows == [['model', 1, 5, 10, 5, 21]]
    assert _TableSpy.instances[1].rows == [['bu', 'model', 1, 5, 10, 5, 21]]


def test_persist_aoai_traffic_rolls_up_models_and_defaults(tmp_path):
    path = tmp_path / 'traffic.json'
    delivered = {
        ('bu-one', 'model-a'): {'chat_non_streaming': 2, 'responses_stream': 1},
        ('bu-one', 'model-b'): {'chat_stream_with_usage': 3},
        ('bu-unknown', 'model-a'): {},
    }
    planned = {
        ('bu-one', 'model-a'): {'chat_non_streaming': 3, 'responses_stream': 1},
        ('bu-one', 'model-b'): {'chat_stream_with_usage': 4},
        ('unused', 'model'): {'responses_non_streaming': 2},
    }

    total = costing_helpers.persist_aoai_traffic(
        path,
        sample_folder='costing',
        rg_name='rg',
        apim_name='apim',
        aoai_api_path='aoai',
        subscriptions={'bu-one': {'display_name': 'One', 'request_weight': '2.5'}},
        bu_model_counts=delivered,
        bu_model_planned=planned,
    )

    assert total == 10
    source = json.loads(path.read_text(encoding='utf-8'))['trafficSources'][0]
    assert source['totalRequests'] == 6
    assert source['businessUnits'][0]['weight'] == 2.5
    assert source['businessUnits'][0]['planned'] == 8
    assert source['businessUnits'][1]['display_name'] == ''


def test_print_workbook_cross_reference_handles_missing_file(monkeypatch, tmp_path):
    warning = MagicMock()
    monkeypatch.setattr(costing_helpers, 'print_warning', warning)

    costing_helpers.print_workbook_cross_reference(tmp_path / 'missing.json')

    warning.assert_called_once()


def test_print_workbook_cross_reference_builds_source_bu_and_caller_tables(monkeypatch, tmp_path):
    path = tmp_path / 'traffic.json'
    path.write_text(
        json.dumps(
            {
                'generatedUtc': 'now',
                'resourceGroup': 'rg',
                'apimService': 'apim',
                'trafficSources': [
                    {
                        'name': 'non-ai',
                        'apiName': 'basic',
                        'isAi': False,
                        'plannedRequests': 4,
                        'totalRequests': 3,
                        'businessUnits': [{'name': 'bu-one', 'display_name': 'One', 'planned': 4, 'requests': 3}],
                    },
                    {
                        'name': 'ai-bu',
                        'apiName': 'aoai',
                        'isAi': True,
                        'plannedRequests': 2,
                        'totalRequests': 2,
                        'businessUnits': [{'name': 'bu-one', 'planned': 2, 'requests': 2}],
                    },
                    {
                        'name': 'ai-callers',
                        'apiName': 'tokens',
                        'isAi': True,
                        'plannedRequests': 1,
                        'totalRequests': 0,
                        'callers': [{'appid': 'app', 'name': 'Caller', 'planned': 1, 'requests': 0}],
                    },
                    {'name': 'plain', 'isAi': False},
                ],
            }
        ),
        encoding='utf-8',
    )
    _TableSpy.instances = []
    monkeypatch.setattr(costing_helpers, 'TableLogger', _TableSpy)

    costing_helpers.print_workbook_cross_reference(path)

    assert len(_TableSpy.instances) == 4
    assert _TableSpy.instances[0].rows[0] == ['Total APIM Requests (all subs, all APIs)', 7, 5]
    assert _TableSpy.instances[2].rows == [['bu-one', 'One', 6, 5, 2, 2]]
    assert _TableSpy.instances[3].rows == [['app', 'Caller', 1, 0]]


def test_print_workbook_cross_reference_handles_sources_without_attribution(monkeypatch, tmp_path):
    path = tmp_path / 'traffic.json'
    path.write_text(
        json.dumps({'trafficSources': [{'name': 'plain', 'isAi': False, 'plannedRequests': 1, 'totalRequests': 1}]}),
        encoding='utf-8',
    )
    _TableSpy.instances = []
    monkeypatch.setattr(costing_helpers, 'TableLogger', _TableSpy)

    costing_helpers.print_workbook_cross_reference(path)

    assert len(_TableSpy.instances) == 2
    assert _TableSpy.instances[1].rows[0][3] == '-'
