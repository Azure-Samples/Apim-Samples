"""Offline tests for authenticated, non-destructive MockAPI dashboard configuration."""

import json
import traceback
from copy import deepcopy
from unittest.mock import MagicMock
from urllib.parse import urlsplit

import pytest
import requests

# APIM Samples imports
from mockapi_dashboard import MockApiDashboardClient


def _endpoint(index: int = 1, *, path: str = '/hello', methods: list[str] | None = None) -> dict:
    return {
        'id': f'00000000-0000-4000-8000-{index:012d}',
        'name': 'Hello World',
        'enabled': True,
        'methods': ['GET'] if methods is None else methods,
        'path': path,
        'response': {'statusCode': 200, 'headers': {}, 'body': 'Hello World'},
    }


def _response(status: int = 200, *, endpoints: list | None = None, document: object = None, etag: str = '"0"') -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.headers = {'ETag': etag}
    response.json.return_value = document if document is not None else {
        'schemaVersion': '1.0',
        'apiDescriptions': {'/inventory': 'Preserve user metadata'},
        'endpoints': [] if endpoints is None else endpoints,
    }

    return response


def _client(*responses: MagicMock) -> tuple[MockApiDashboardClient, MagicMock]:
    session = MagicMock()
    if responses:
        session.request.side_effect = responses
    client = MockApiDashboardClient(
        'https://mockapi.example/',
        'saved-password',
        session_factory = lambda: session,
    )

    return client, session


@pytest.mark.unit
def test_empty_bootstrap_creates_endpoint_with_quoted_revision_and_closes_session():
    endpoint = _endpoint()
    client, session = _client(_response(), _response(201))

    with client:
        client.ensure_endpoint(endpoint, preserve_existing = True)

    assert session.auth == ('admin', 'saved-password')
    assert session.verify is True
    calls = session.request.call_args_list
    assert calls[0].args == ('GET', 'https://mockapi.example/__mockapi/api/configuration/export')
    assert calls[1].args == ('POST', 'https://mockapi.example/__mockapi/api/endpoints')
    assert calls[1].kwargs['json'] == endpoint
    assert calls[1].kwargs['headers'] == {'If-Match': '"0"'}
    assert all(call.kwargs['allow_redirects'] is False and call.kwargs['timeout'] == 30 for call in calls)
    session.close.assert_called_once()


@pytest.mark.unit
@pytest.mark.parametrize('same_id', [True, False])
def test_preserve_mode_matches_edited_disabled_hello_by_path_and_methods_not_id(same_id):
    desired = _endpoint()
    existing = _endpoint(1 if same_id else 2, methods = ['get', 'POST'])
    existing['enabled'] = False
    existing['response']['body'] = 'User-edited fixture'
    before = deepcopy(existing)
    client, session = _client(_response(endpoints = [existing]))

    with client:
        client.ensure_endpoint(desired, preserve_existing = True)

    assert session.request.call_count == 1
    assert existing == before


@pytest.mark.unit
def test_preserve_mode_does_not_mistake_post_hello_for_get_hello():
    existing = _endpoint(2, methods = ['POST'])
    client, session = _client(_response(endpoints = [existing]), _response(201))

    with client:
        client.ensure_endpoint(_endpoint(), preserve_existing = True)

    assert session.request.call_args.args[0] == 'POST'
    assert session.request.call_args.kwargs['json']['methods'] == ['GET']
    assert existing['methods'] == ['POST']


@pytest.mark.unit
def test_preserve_mode_never_repurposes_an_existing_id_with_different_methods():
    client, session = _client(_response(endpoints = [_endpoint(methods = ['POST'])]))

    with client, pytest.raises(ValueError, match='different methods'):
        client.ensure_endpoint(_endpoint(), preserve_existing = True)

    assert session.request.call_count == 1


@pytest.mark.unit
def test_owned_endpoint_update_uses_put_and_preserves_unrelated_configuration():
    old = _endpoint()
    old['response']['body'] = 'Old sample configuration'
    unrelated = _endpoint(2, path = '/inventory')
    document = {'schemaVersion': '1.0', 'endpoints': [old, unrelated], 'apiDescriptions': {'/inventory': 'User edit'}}
    before = deepcopy(document)
    client, session = _client(_response(document = document, etag = '"7"'), _response())

    with client:
        client.ensure_endpoint(_endpoint())

    call = session.request.call_args
    assert call.args[0] == 'PUT'
    assert urlsplit(call.args[1]).path == f'/__mockapi/api/endpoints/{old["id"]}'
    assert call.kwargs['headers'] == {'If-Match': '"7"'}
    assert call.kwargs['json'] == _endpoint()
    assert document == before


@pytest.mark.unit
def test_identical_owned_endpoint_requires_no_mutation():
    client, session = _client(_response(endpoints = [_endpoint()]))

    with client:
        client.ensure_endpoint(_endpoint())

    assert session.request.call_count == 1


@pytest.mark.unit
@pytest.mark.parametrize('methods', [['GET'], ['POST']])
def test_ordinary_upsert_rejects_every_unrelated_id_sharing_path(methods):
    client, session = _client(_response(endpoints = [_endpoint(2, methods = methods)]))

    with client, pytest.raises(ValueError, match='non-owned endpoint'):
        client.ensure_endpoint(_endpoint())

    assert session.request.call_count == 1


@pytest.mark.unit
@pytest.mark.parametrize('endpoints', [[_endpoint(path = '/inventory')], [_endpoint(), _endpoint()]])
def test_conflicting_or_duplicate_ids_fail_without_changes(endpoints):
    client, session = _client(_response(endpoints = endpoints))

    with client, pytest.raises(ValueError, match='ID conflicts'):
        client.ensure_endpoint(_endpoint())

    assert session.request.call_count == 1


@pytest.mark.unit
def test_412_refetches_and_preserves_concurrently_created_hello():
    client, session = _client(
        _response(),
        _response(412),
        _response(endpoints = [_endpoint(2)], etag = '"1"'),
    )

    with client:
        client.ensure_endpoint(_endpoint(), preserve_existing = True)

    assert [call.args[0] for call in session.request.call_args_list] == ['GET', 'POST', 'GET']


@pytest.mark.unit
def test_412_upsert_retry_uses_new_etag_not_stale_export():
    client, session = _client(_response(), _response(412), _response(etag = '"9"'), _response(201))

    with client:
        client.ensure_endpoint(_endpoint())

    assert session.request.call_args.kwargs['headers'] == {'If-Match': '"9"'}


@pytest.mark.unit
def test_repeated_upsert_conflicts_are_bounded():
    client, session = _client(*[_response(), _response(412)] * 3)

    with client, pytest.raises(RuntimeError, match='changed repeatedly'):
        client.ensure_endpoint(_endpoint())

    assert session.request.call_count == 6
    session.close.assert_called_once()


@pytest.mark.unit
def test_autosave_failure_saves_active_change_without_replaying_mutation():
    client, session = _client(
        _response(),
        _response(500, document = {'type': 'https://mockapi.local/problems/autosave-failed'}),
        _response(endpoints = [_endpoint()], etag = '"1"'),
        _response(),
    )

    with client:
        client.ensure_endpoint(_endpoint())

    calls = session.request.call_args_list
    assert [urlsplit(call.args[1]).path for call in calls] == [
        '/__mockapi/api/configuration/export',
        '/__mockapi/api/endpoints',
        '/__mockapi/api/configuration/export',
        '/__mockapi/api/configuration/save',
    ]
    assert calls[-1].kwargs['headers'] == {'If-Match': '"1"'}
    assert calls[-1].kwargs['json'] is None


@pytest.mark.unit
def test_save_conflict_refetches_before_retrying_persistence_only():
    client, session = _client(
        _response(),
        _response(500, document = {'type': 'https://mockapi.local/problems/autosave-failed'}),
        _response(etag = '"1"'),
        _response(412),
        _response(etag = '"2"'),
        _response(),
    )

    with client:
        client.ensure_endpoint(_endpoint())

    assert session.request.call_args.kwargs['headers'] == {'If-Match': '"2"'}
    assert sum(urlsplit(call.args[1]).path == '/__mockapi/api/endpoints' for call in session.request.call_args_list) == 1


@pytest.mark.unit
def test_repeated_save_conflicts_are_bounded_and_report_unsaved_active_state():
    client, session = _client(
        _response(),
        _response(500, document = {'type': 'https://mockapi.local/problems/autosave-failed'}),
        *[_response(etag = '"1"'), _response(412)] * 3,
    )

    with client, pytest.raises(RuntimeError, match='remains active but may be unsaved'):
        client.ensure_endpoint(_endpoint())

    assert session.request.call_count == 8


@pytest.mark.unit
def test_save_failure_does_not_replay_endpoint_creation():
    client, session = _client(
        _response(),
        _response(500, document = {'type': 'https://mockapi.local/problems/autosave-failed'}),
        _response(etag = '"1"'),
        _response(403),
    )

    with client, pytest.raises(RuntimeError, match='HTTP 403'):
        client.ensure_endpoint(_endpoint())

    assert session.request.call_count == 4


@pytest.mark.unit
@pytest.mark.parametrize('document', [[], {'schemaVersion': '2.0', 'endpoints': []}, {'schemaVersion': '1.0', 'endpoints': None}, {'schemaVersion': '1.0', 'endpoints': [None]}])
def test_invalid_exports_fail_before_mutation(document):
    client, session = _client(_response(document = document))

    with client, pytest.raises(ValueError, match='invalid configuration|invalid endpoint'):
        client.ensure_endpoint(_endpoint())

    assert session.request.call_count == 1


@pytest.mark.unit
@pytest.mark.parametrize('etag', ['', '1', 'W/"1"', '""', '"1"\r\nInjected: value', '"1"trailing'])
def test_strong_etag_is_required(etag):
    client, session = _client(_response(etag = etag))

    with client, pytest.raises(ValueError, match='strong ETag'):
        client.ensure_endpoint(_endpoint())

    assert session.request.call_count == 1


@pytest.mark.unit
@pytest.mark.parametrize('status', [302, 401, 403, 500])
def test_export_failures_do_not_expose_credentials_or_response_bodies(status):
    client, session = _client(_response(status, document = {'secret': 'saved-password'}))

    with client, pytest.raises(RuntimeError, match=f'HTTP {status}') as error:
        client.ensure_endpoint(_endpoint())

    assert 'saved-password' not in str(error.value)
    assert session.request.call_count == 1


@pytest.mark.unit
def test_non_autosave_500_is_not_retried_or_saved():
    client, session = _client(_response(), _response(500, document = {'type': 'https://mockapi.local/problems/other'}))

    with client, pytest.raises(RuntimeError, match='HTTP 500'):
        client.ensure_endpoint(_endpoint())

    assert session.request.call_count == 2


@pytest.mark.unit
def test_malformed_json_is_reported_without_response_content():
    response = _response()
    response.json.side_effect = ValueError('saved-password in malformed response')
    client, session = _client(response)

    with client, pytest.raises(ValueError, match='invalid JSON') as error:
        client.ensure_endpoint(_endpoint())

    assert 'saved-password' not in ''.join(traceback.format_exception(error.value))
    session.close.assert_called_once()


@pytest.mark.unit
def test_request_exceptions_are_redacted_and_session_is_closed():
    client, session = _client()
    session.request.side_effect = requests.ConnectionError('saved-password in upstream error')

    with client, pytest.raises(RuntimeError, match='HTTPS connectivity') as error:
        client.ensure_endpoint(_endpoint())

    assert 'saved-password' not in ''.join(traceback.format_exception(error.value))
    session.close.assert_called_once()


@pytest.mark.unit
@pytest.mark.parametrize('endpoint', [{}, {'id': 'invalid', 'path': '/hello'}, _endpoint(methods = []), {**_endpoint(), 'methods': ['']}, {**_endpoint(), 'methods': ['GET', 1]}])
def test_invalid_candidate_is_rejected_without_remote_work(endpoint):
    client, session = _client()

    with client, pytest.raises(ValueError):
        client.ensure_endpoint(endpoint)

    session.request.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize('url', ['http://a.example', 'https://a.example:444', 'https://user:pass@a.example', 'https://a.example/hello', 'https://a.example?query=1', 'https://a.example/#fragment'])
def test_invalid_origins_are_rejected(url):
    with pytest.raises(ValueError, match='HTTPS origins'):
        MockApiDashboardClient(url, 'password')


@pytest.mark.unit
def test_empty_password_is_rejected():
    with pytest.raises(ValueError, match='password'):
        MockApiDashboardClient('https://a.example/', '')


@pytest.mark.unit
def test_origin_normalization_and_ipv6_support():
    assert MockApiDashboardClient('https://MOCKAPI.example:443', 'password').dashboard_url == 'https://mockapi.example/'
    assert MockApiDashboardClient('https://[::1]:443/', 'password').dashboard_url == 'https://[::1]/'


@pytest.mark.unit
def test_client_requires_context_and_rejects_nested_entry_without_leaking_session():
    client, session = _client()
    with pytest.raises(RuntimeError, match='context manager'):
        client.ensure_endpoint(_endpoint())
    with client, pytest.raises(RuntimeError, match='already open'):
        client.__enter__()
    client.close()
    session.close.assert_called_once()


@pytest.mark.unit
def test_client_accepts_loaded_json_endpoint_without_mutating_it():
    endpoint = json.loads(json.dumps(_endpoint()))
    original = deepcopy(endpoint)
    client, _ = _client(_response(), _response(201))

    with client:
        client.ensure_endpoint(endpoint)

    assert endpoint == original
