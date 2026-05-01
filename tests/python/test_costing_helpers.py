"""Tests for `samples/costing/_helpers.py` 6-mode AOAI traffic dispatcher."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests as http_requests

# APIM Samples imports
COSTING_DIR = Path(__file__).resolve().parents[2] / 'samples' / 'costing'
sys.path.insert(0, str(COSTING_DIR))

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


@pytest.mark.parametrize('count', [0, 1, 7, 13])
def test_planned_count_always_equals_request_count(count):
    session = _make_session()

    _delivered, planned, _ = send_aoai_traffic(session, CHAT_URL, CALLER_HEADERS, count, **_full_kwargs())

    assert sum(planned.values()) == count
