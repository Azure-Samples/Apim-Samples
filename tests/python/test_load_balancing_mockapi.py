"""Contract and failure-path tests for infrastructure-owned MockAPI sample setup."""

import ast
import json
import sys
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import urlsplit
from uuid import UUID

import pytest

from apimtypes import HttpStatusCode

LOAD_BALANCING_DIR = Path(__file__).resolve().parents[2] / 'samples' / 'load-balancing'
sys.path.insert(0, str(LOAD_BALANCING_DIR))

from load_balancing_helpers import LoadBalancingBackendSetup, LoadBalancingScenario, LoadBalancingTrafficRunner, throttled_endpoint  # noqa: E402


def test_notebook_imports_resolve_in_the_supported_python_environment():
    """Catch invalid symbol imports that static notebook lint cannot detect."""
    notebook = json.loads((LOAD_BALANCING_DIR / 'create.ipynb').read_text(encoding = 'utf-8'))
    namespace = {}
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            tree = ast.parse(''.join(cell['source']))
            imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
            exec(compile(ast.Module(body = imports, type_ignores = []), '<notebook imports>', 'exec'), namespace)


def _response(status=200, *, document=None, etag='"revision-1"'):
    response = MagicMock()
    response.status_code = status
    response.headers = {'ETag': etag}
    response.json.return_value = document

    return response


def _setup():
    session = MagicMock()
    session.request.side_effect = lambda method, url, **kwargs: getattr(session, method.lower())(url, **kwargs)
    setup = LoadBalancingBackendSetup(
        ['https://mockapi-1.example/', 'https://mockapi-2.example/'],
        'saved-dashboard-password',
        session_factory=lambda: session,
    )

    return setup, session


@pytest.mark.unit
def test_endpoint_preserves_original_capacity_and_cooldown():
    """Use exact schema fields, static response bodies, and three distinct permit budgets."""
    endpoints = [throttled_endpoint(index) for index in range(3)]
    assert len({endpoint['id'] for endpoint in endpoints}) == 3
    for index, endpoint in enumerate(endpoints):
        assert str(UUID(endpoint['id'])) == endpoint['id']
        assert endpoint['path'] == f'/load-balancing/backend-{index}'
        assert endpoint['methods'] == ['GET']
        assert endpoint['enabled'] is True
        response = endpoint['response']
        assert response['statusCode'] == 429
        assert response['headers'] == {'Retry-After': ['3']}
        assert response['rateLimit']['requestLimit'] == 5
        assert response['rateLimit']['windowSeconds'] == 3
        assert response['rateLimit']['successResponse']['statusCode'] == 200
        assert response['rateLimit']['successResponse']['headers'] == {}
        assert json.loads(response['rateLimit']['successResponse']['body']) == {'index': index}
        assert json.loads(response['body'])['index'] == index


@pytest.mark.unit
@pytest.mark.parametrize(
    ('index', 'limit', 'window'),
    [(-1, 4, 10), (3, 4, 10), (True, 4, 10), (0, 0, 10), (0, True, 10), (0, 4, 0), (0, 4, 86401), (0, 4, 1.5)],
)
def test_endpoint_rejects_invalid_budget_or_backend(index, limit, window):
    with pytest.raises(ValueError):
        throttled_endpoint(index, request_limit=limit, window_seconds=window)


@pytest.mark.unit
@pytest.mark.parametrize(
    'urls',
    [
        [],
        ['https://a.example', 'https://a.example'],
        ['http://a.example', 'https://b.example'],
        ['https://a.example:444', 'https://b.example'],
        ['https://user:secret@a.example', 'https://b.example'],
        ['https://a.example/hello', 'https://b.example'],
        ['https://a.example?query=1', 'https://b.example'],
        ['https://a.example/#fragment', 'https://b.example'],
    ],
)
def test_setup_rejects_non_origin_dashboard_urls(urls):
    with pytest.raises(ValueError):
        LoadBalancingBackendSetup(urls, 'password')


@pytest.mark.unit
def test_setup_adds_only_sample_endpoints_and_preserves_hello_and_metadata():
    setup, session = _setup()
    hello = {'id': 'hello-id', 'path': '/hello', 'response': {'body': 'user edit'}}
    unrelated = {'id': 'other-id', 'path': '/inventory', 'enabled': False}
    document = {'schemaVersion': '1.0', 'apiDescriptions': {'/hello': 'preserve this'}, 'endpoints': [hello, unrelated]}
    before = deepcopy(document)
    session.get.return_value = _response(document=document)
    session.post.return_value = _response(201)

    setup.configure()

    assert session.auth == ('admin', 'saved-dashboard-password')
    assert document == before
    assert session.post.call_count == 3
    expected_hosts = ['mockapi-1.example', 'mockapi-2.example', 'mockapi-1.example']
    for index, call in enumerate(session.post.call_args_list):
        parsed = urlsplit(call.args[0])
        assert parsed.scheme == 'https'
        assert parsed.hostname == expected_hosts[index]
        assert parsed.path == '/__mockapi/api/endpoints'
        assert call.kwargs['json'] == throttled_endpoint(index)
        assert call.kwargs['headers'] == {'If-Match': '"revision-1"'}
        assert call.kwargs['allow_redirects'] is False
        assert call.kwargs['timeout'] == 30
    assert session.close.call_count == 2


@pytest.mark.unit
def test_setup_is_idempotent_for_identical_endpoints():
    setup, session = _setup()
    session.get.return_value = _response(document={'schemaVersion': '1.0', 'endpoints': [throttled_endpoint(index) for index in range(3)]})

    setup.configure()

    session.post.assert_not_called()
    session.put.assert_not_called()


@pytest.mark.unit
def test_setup_replaces_only_owned_endpoint_using_current_etag():
    setup, session = _setup()
    old = throttled_endpoint(0, request_limit=1)
    session.get.side_effect = [
        _response(document={'schemaVersion': '1.0', 'endpoints': [old]}),
        _response(document={'schemaVersion': '1.0', 'endpoints': [throttled_endpoint(1), throttled_endpoint(2)]}),
        _response(document={'schemaVersion': '1.0', 'endpoints': [throttled_endpoint(1), throttled_endpoint(2)]}),
    ]
    session.put.return_value = _response(200)

    setup.configure()

    session.put.assert_called_once()
    call = session.put.call_args
    assert urlsplit(call.args[0]).path == f'/__mockapi/api/endpoints/{old["id"]}'
    assert call.kwargs['json'] == throttled_endpoint(0)
    assert call.kwargs['headers'] == {'If-Match': '"revision-1"'}
    session.post.assert_not_called()


@pytest.mark.unit
def test_precondition_failure_refetches_instead_of_clobbering_dashboard_edits():
    setup, session = _setup()
    original = {'schemaVersion': '1.0', 'endpoints': []}
    edited = {'schemaVersion': '1.0', 'endpoints': [{'id': 'new', 'path': '/hello'}]}
    session.get.side_effect = [
        _response(document=original),
        _response(document=edited, etag='"revision-2"'),
        _response(document=edited, etag='"revision-3"'),
        _response(document=edited, etag='"revision-4"'),
    ]
    session.post.side_effect = [_response(412), _response(201), _response(201), _response(201)]

    setup.configure()

    assert session.post.call_args_list[1].kwargs['headers'] == {'If-Match': '"revision-2"'}
    assert edited['endpoints'] == [{'id': 'new', 'path': '/hello'}]


@pytest.mark.unit
def test_repeated_concurrency_conflicts_are_bounded_and_close_session():
    setup, session = _setup()
    session.get.return_value = _response(document={'schemaVersion': '1.0', 'endpoints': []})
    session.post.return_value = _response(412)

    with pytest.raises(RuntimeError, match='changed repeatedly'):
        setup.configure()

    assert session.post.call_count == 3
    assert session.close.call_count == 2


@pytest.mark.unit
@pytest.mark.parametrize(
    ('document', 'etag', 'message'),
    [
        ({'schemaVersion': '2.0', 'endpoints': []}, '"x"', 'invalid configuration'),
        ({'schemaVersion': '1.0', 'endpoints': [None]}, '"x"', 'invalid endpoint'),
        ({'schemaVersion': '1.0', 'endpoints': []}, 'W/"x"', 'strong ETag'),
        ({'schemaVersion': '1.0', 'endpoints': [{'id': 'user-id', 'path': '/load-balancing/backend-0'}]}, '"x"', 'non-owned endpoint'),
        ({'schemaVersion': '1.0', 'endpoints': [{'id': throttled_endpoint(0)['id'], 'path': '/hello'}]}, '"x"', 'ID conflicts'),
    ],
)
def test_setup_fails_closed_on_malformed_export_or_ownership_collision(document, etag, message):
    setup, session = _setup()
    session.get.return_value = _response(document=document, etag=etag)

    with pytest.raises(ValueError, match=message):
        setup.configure()

    session.post.assert_not_called()
    session.put.assert_not_called()
    assert session.close.call_count == 2


@pytest.mark.unit
def test_autosave_failure_retries_persistence_not_the_active_mutation():
    setup, session = _setup()
    empty = {'schemaVersion': '1.0', 'endpoints': []}
    session.get.side_effect = [
        _response(document=empty),
        _response(document=empty, etag='"active-unsaved"'),
        _response(document=empty),
        _response(document=empty),
    ]
    session.post.side_effect = [
        _response(500, document={'type': 'https://mockapi.local/problems/autosave-failed'}),
        _response(200),
        _response(201),
        _response(201),
    ]

    setup.configure()

    assert session.post.call_count == 4
    save = session.post.call_args_list[1]
    assert urlsplit(save.args[0]).path == '/__mockapi/api/configuration/save'
    assert save.kwargs['headers'] == {'If-Match': '"active-unsaved"'}
    assert save.kwargs['json'] is None


@pytest.mark.unit
@pytest.mark.parametrize('status', [302, 401, 403, 500])
def test_management_failures_stop_without_exposing_credentials(status):
    setup, session = _setup()
    session.get.return_value = _response(status)

    with pytest.raises(RuntimeError, match=f'HTTP {status}') as error:
        setup.configure()

    assert 'saved-dashboard-password' not in str(error.value)
    session.post.assert_not_called()
    assert session.close.call_count == 2


@pytest.mark.unit
def test_setup_requires_saved_dashboard_password():
    with pytest.raises(ValueError, match='password'):
        LoadBalancingBackendSetup(['https://one.example', 'https://two.example'], '')


@pytest.mark.unit
def test_setup_rejects_duplicate_normalized_dashboard_origins():
    with pytest.raises(ValueError, match='distinct'):
        LoadBalancingBackendSetup(['https://ONE.example:443', 'https://one.example/'], 'password')


@pytest.mark.unit
def test_setup_owns_two_independent_clients_and_keeps_three_budgets_separate():
    first, second = MagicMock(), MagicMock()
    first.request.side_effect = [_response(document={'schemaVersion': '1.0', 'endpoints': []}), _response(201)] * 2
    second.request.side_effect = [_response(document={'schemaVersion': '1.0', 'endpoints': []}), _response(201)]
    factory = MagicMock(side_effect=[first, second])
    setup = LoadBalancingBackendSetup(
        ['https://first.example/', 'https://second.example/'], 'password', session_factory=factory,
    )

    setup.configure()

    first_payloads = [call.kwargs['json'] for call in first.request.call_args_list if call.args[0] == 'POST']
    second_payloads = [call.kwargs['json'] for call in second.request.call_args_list if call.args[0] == 'POST']
    assert first_payloads == [throttled_endpoint(0), throttled_endpoint(2)]
    assert second_payloads == [throttled_endpoint(1)]
    first.close.assert_called_once()
    second.close.assert_called_once()


@pytest.mark.unit
def test_setup_closes_first_dashboard_if_opening_second_session_fails():
    first = MagicMock()
    factory = MagicMock(side_effect=[first, RuntimeError('second session unavailable')])
    setup = LoadBalancingBackendSetup(
        ['https://first.example/', 'https://second.example/'], 'password', session_factory=factory,
    )

    with pytest.raises(RuntimeError, match='second session'):
        setup.configure()

    first.close.assert_called_once()
    first.request.assert_not_called()


@pytest.mark.unit
def test_network_failure_closes_management_session():
    setup, session = _setup()
    session.get.side_effect = ConnectionError('dashboard unavailable')

    with pytest.raises(ConnectionError, match='dashboard unavailable'):
        setup.configure()

    assert session.close.call_count == 2


@pytest.mark.unit
def test_retry_flow_honors_initial_recovery_pause():
    requests = MagicMock()
    requests.headers = {}
    session = MagicMock()
    session.headers = {}
    session.get.return_value.status_code = 200
    session.get.return_value.headers = {'Content-Type': 'text/plain'}
    session.get.return_value.text = 'recovered'
    sleep = MagicMock()
    with LoadBalancingTrafficRunner(requests, 'https://gateway.example', False, session_factory=lambda: session, sleep=sleep) as runner:
        result = runner.run_retry_tracking('/retry', 1, 'subscription-key', pause_seconds=11)

    sleep.assert_called_once_with(11)
    assert result.api_results[0]['response'] == 'recovered'


@pytest.mark.unit
@pytest.mark.parametrize('body', ['invalid json', '[]', '{"index": true}', '{"index": 9}', '{"message": "no backend"}'])
def test_observed_counts_leave_malformed_or_unrelated_responses_unchanged(body):
    requests = MagicMock()
    requests.multiGet.return_value = [{'status_code': 200, 'response': body}]
    with LoadBalancingTrafficRunner(requests, 'https://gateway.example', False) as runner:
        result = runner.run_structured([LoadBalancingScenario('one', 0, '/one', 1)], ['key'])

    assert result[0][0]['response'] == body


@pytest.mark.unit
def test_observed_counts_are_per_backend_per_scenario_and_do_not_count_errors():
    requests = MagicMock()
    results = [
        {'status_code': status, 'response': json.dumps(body)}
        for status, body in [(200, {'index': 0}), (200, {'index': 1}), (429, {'index': 0}), (200, {'index': 0})]
    ]
    requests.multiGet.side_effect = [results, [{'status_code': 200, 'response': '{"index": 0}'}]]
    sleep = MagicMock()
    with LoadBalancingTrafficRunner(requests, 'https://gateway.example', False, sleep=sleep) as runner:
        observed = runner.run_structured(
            [LoadBalancingScenario('one', 0, '/one', 4), LoadBalancingScenario('two', 0, '/two', 1)],
            ['subscription-key'],
            pause_seconds=11,
            initial_pause_seconds=11,
        )

    assert [json.loads(item['response']).get('count') for item in observed[0]] == [1, 1, None, 2]
    assert json.loads(observed[1][0]['response'])['count'] == 1
    assert [call.args for call in sleep.call_args_list] == [(11,), (11,)]


@pytest.mark.unit
def test_notebook_isolates_flows_after_the_backend_recovery_window():
    notebook = json.loads((LOAD_BALANCING_DIR / 'create.ipynb').read_text(encoding='utf-8'))
    source = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code')
    tree = ast.parse(source)
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in ('run_structured', 'run_retry_tracking')
    ]

    assert len(calls) == 3
    structured = [node for node in calls if node.func.attr == 'run_structured']
    assert [(keyword.arg, ast.literal_eval(keyword.value)) for keyword in structured[0].keywords] == [('pause_seconds', 4), ('initial_pause_seconds', 4)]
    assert [(keyword.arg, ast.literal_eval(keyword.value)) for keyword in structured[1].keywords] == [('pause_seconds', 0), ('initial_pause_seconds', 4)]
    retry, = [node for node in calls if node.func.attr == 'run_retry_tracking']
    assert [(keyword.arg, ast.literal_eval(keyword.value)) for keyword in retry.keywords] == [('pause_seconds', 4)]


@pytest.mark.unit
def test_notebook_retains_all_seven_flows_and_clears_outputs():
    notebook = json.loads((LOAD_BALANCING_DIR / 'create.ipynb').read_text(encoding='utf-8'))
    code_cells = [cell for cell in notebook['cells'] if cell['cell_type'] == 'code']
    source = '\n'.join(''.join(cell['source']) for cell in code_cells)
    assert all(cell['outputs'] == [] and cell['execution_count'] is None for cell in code_cells)
    assert 'index       = 1' in ''.join(code_cells[0]['source'])
    assert source.count('load_balancing_helpers.LoadBalancingScenario(') == 6
    assert 'retry_tracked_total_runs = 25' in source
    assert "tests.verify(first_prioritized_body['count'], 1)" in source
    assert 'nb_helper.deploy_sample(bicep_parameters)' in source
    assert 'backend_setup.configure(request_limit = 5, window_seconds = 3)' in source
    for cell in code_cells:
        compile(''.join(cell['source']), '<load-balancing notebook>', 'exec')


@pytest.mark.unit
def test_bicep_reuses_existing_apps_and_injects_named_value_credentials():
    source = (LOAD_BALANCING_DIR / 'main.bicep').read_text(encoding='utf-8')
    assert 'simonkurtzmsft/webapi429' not in source
    assert 'containerapp.bicep' not in source
    assert 'Microsoft.App/containerApps' not in source
    assert "resource infrastructureMockApiBackends 'Microsoft.ApiManagement/service/backends@2024-06-01-preview' existing" in source
    assert "name: 'aca-backend-${index}'" in source
    assert 'param mockApiBaseUrls array = []' in source
    assert "uri(infrastructureMockApiBackends[0].properties.url, '/')" in source
    assert "uri(infrastructureMockApiBackends[1].properties.url, '/')" in source
    assert "map(mockApiBaseUrls, url => uri(string(url), '/'))" in source
    assert 'mockwebapi' not in source
    assert "'X-MockAPI-Key': ['{{mockapi-key}}']" in source
    assert source.count('credentialHeaders: mockApiCredentialHeaders') == 3
    assert source.count('circuitBreaker: mockApiCircuitBreaker') == 3
    assert "tripDuration: 'PT3S'" in source
    assert "interval: 'PT3S'" in source
    assert 'acceptRetryAfter: true' in source
    for index in range(3):
        assert f'load-balancing/backend-{index}' in source


@pytest.mark.unit
def test_error_policy_falls_back_to_the_configured_window_without_exposing_backend_secrets():
    policy = (LOAD_BALANCING_DIR / 'apim-policies' / 'aca-backend-pool-load-balancing-with-429.xml').read_text(encoding='utf-8')
    rendered = ET.fromstring(policy.format(backend_id='pool', retry_count=2))
    backend = rendered.find('backend')
    assert backend is not None and [child.tag for child in backend] == ['retry']
    header = rendered.find('on-error/choose/when/set-header')
    assert header is not None and header.attrib == {'name': 'Retry-After', 'exists-action': 'override'}
    assert header.findtext('value') == '@(context.Response.Headers.GetValueOrDefault("Retry-After", "3"))'
    assert throttled_endpoint(0)['response']['headers']['Retry-After'] == ['3']


@pytest.mark.unit
@pytest.mark.parametrize(
    ('statuses', 'expected'),
    [
        ([503] * 15, [True, False, True]),
        ([429] * 15, [True, False, True]),
        ([200] * 5 + [503] * 10, [True, True, True]),
        ([200] * 14 + [401], [True, True, False]),
        ([200] * 14 + [500], [True, True, False]),
        ([200] * 14, [False, True, True]),
    ],
)
def test_notebook_does_not_pass_empty_demonstrations_or_unexpected_errors(statuses, expected):
    """Execute the notebook's actual per-flow assertions, including negative cases."""
    notebook = json.loads((LOAD_BALANCING_DIR / 'create.ipynb').read_text(encoding='utf-8'))
    source = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code')
    loop, = [
        node for node in ast.parse(source).body
        if isinstance(node, ast.For) and isinstance(node.target, ast.Tuple)
        and [item.id for item in node.target.elts] == ['scenario', 'results']
        and isinstance(node.iter.args[0], ast.Name)
    ]
    tests = MagicMock()
    namespace = {
        'structured_scenarios': [LoadBalancingScenario('weighted', 0, '/weighted', 15)],
        'structured_results': [[{'status_code': status} for status in statuses]],
        'HttpStatusCode': HttpStatusCode,
        'tests': tests,
    }

    exec(compile(ast.Module(body=[loop], type_ignores=[]), '<notebook flow assertions>', 'exec'), namespace)

    assert [call.args[0] == call.args[1] for call in tests.verify.call_args_list] == expected


@pytest.mark.unit
def test_weighted_scenarios_stay_below_one_backends_capacity_even_if_every_request_selects_it():
    notebook = json.loads((LOAD_BALANCING_DIR / 'create.ipynb').read_text(encoding='utf-8'))
    source = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code')
    assignment, = [
        node for node in ast.parse(source).body
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'structured_scenarios' for target in node.targets)
    ]
    namespace = {'load_balancing_helpers': sys.modules['load_balancing_helpers']}
    namespace.update({name: name for name in ('lb_prioritized_path', 'lb_weighted_equal_path', 'lb_weighted_unequal_path', 'lb_prioritized_weighted_path')})
    exec(compile(ast.Module(body=[assignment], type_ignores=[]), '<notebook scenarios>', 'exec'), namespace)

    budget = throttled_endpoint(0)['response']['rateLimit']
    for scenario in namespace['structured_scenarios'][1:3]:
        assert scenario.runs == 30
        assert scenario.sleep_ms == 700
        assert budget['requestLimit'] * scenario.sleep_ms > budget['windowSeconds'] * 1000


@pytest.mark.unit
@pytest.mark.parametrize(
    ('statuses', 'indices', 'expected'),
    [
        ([200, 200], [0, 1], [True, True]),
        ([200, 200], [0, 0], [True, False]),
        ([503, 503], [0, 1], [False, False]),
        ([200, 503], [0, 1], [False, False]),
    ],
)
def test_weighted_notebook_assertions_reject_exhaustion_and_single_backend_traffic(statuses, indices, expected):
    notebook = json.loads((LOAD_BALANCING_DIR / 'create.ipynb').read_text(encoding='utf-8'))
    source = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code')
    loop, = [
        node for node in ast.parse(source).body
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Call)
        and isinstance(node.iter.args[0], ast.Subscript)
        and node.iter.args[0].slice.lower.value == 1
    ]
    tests = MagicMock()
    scenario = LoadBalancingScenario('weighted', 0, '/weighted', len(statuses))
    results = [{'status_code': status, 'response': json.dumps({'index': index})} for status, index in zip(statuses, indices)]
    namespace = {
        'structured_scenarios': [scenario, scenario],
        'structured_results': [results, results],
        'HttpStatusCode': HttpStatusCode,
        'json': json,
        'print_message': MagicMock(),
        'tests': tests,
    }
    exec(compile(ast.Module(body=[loop], type_ignores=[]), '<notebook weighted assertions>', 'exec'), namespace)

    assert [call.args[0] == call.args[1] for call in tests.verify.call_args_list] == expected


@pytest.mark.unit
@pytest.mark.parametrize(('status', 'index', 'expected'), [(200, 0, [True, True]), (200, 2, [True, False]), (503, 0, [False])])
def test_priority_notebook_assertions_reject_lower_priority_start_or_failure(status, index, expected):
    notebook = json.loads((LOAD_BALANCING_DIR / 'create.ipynb').read_text(encoding='utf-8'))
    source = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code')
    loop, = [
        node for node in ast.parse(source).body
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Call)
        and isinstance(node.iter.args[0], ast.Subscript)
        and node.iter.args[0].slice.lower.value == 3
    ]
    tests = MagicMock()
    scenario = LoadBalancingScenario('priority', 0, '/priority', 1)
    results = [{'status_code': status, 'response': json.dumps({'index': index})}]
    namespace = {
        'structured_scenarios': [scenario] * 4,
        'structured_results': [results] * 4,
        'HttpStatusCode': HttpStatusCode,
        'json': json,
        'tests': tests,
    }
    exec(compile(ast.Module(body=[loop], type_ignores=[]), '<notebook priority assertions>', 'exec'), namespace)

    assert [call.args[0] == call.args[1] for call in tests.verify.call_args_list] == expected
