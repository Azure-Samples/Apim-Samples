import os
import builtins
import pytest
from unittest.mock import patch, MagicMock, mock_open
from shared.python import utils
from apimtypes import INFRASTRUCTURE

# ------------------------------
#    is_string_json
# ------------------------------

@pytest.mark.parametrize(
    "input_str,expected",
    [
        ("{\"a\": 1}", True),
        ("[1, 2, 3]", True),
        ("not json", False),
        ("{\"a\": 1", False),
        ("", False),
        (None, False),
        (123, False),
    ]
)
def test_is_string_json(input_str, expected):
    assert utils.is_string_json(input_str) is expected

# ------------------------------
#    get_account_info
# ------------------------------

def test_get_account_info_success(monkeypatch):
    mock_json = {
        'user': {'name': 'testuser'},
        'tenantId': 'tenant',
        'id': 'subid'
    }
    mock_output = MagicMock(success=True, json_data=mock_json)
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: mock_output)
    result = utils.get_account_info()
    assert result == ('testuser', 'tenant', 'subid')

def test_get_account_info_failure(monkeypatch):
    mock_output = MagicMock(success=False, json_data=None)
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: mock_output)
    with pytest.raises(Exception):
        utils.get_account_info()

# ------------------------------
#    get_deployment_name
# ------------------------------

def test_get_deployment_name(monkeypatch):
    monkeypatch.setattr(os, 'getcwd', lambda: '/foo/bar/baz')
    assert utils.get_deployment_name() == 'baz'

def test_get_deployment_name_error(monkeypatch):
    monkeypatch.setattr(os, 'getcwd', lambda: '')
    with pytest.raises(RuntimeError):
        utils.get_deployment_name()

# ------------------------------
#    get_frontdoor_url
# ------------------------------

def test_get_frontdoor_url_success(monkeypatch):
    mock_profile = [{"name": "afd1"}]
    mock_endpoints = [{"hostName": "foo.azurefd.net"}]
    def run_side_effect(cmd, *a, **kw):
        if 'profile list' in cmd:
            return MagicMock(success=True, json_data=mock_profile)
        if 'endpoint list' in cmd:
            return MagicMock(success=True, json_data=mock_endpoints)
        return MagicMock(success=False, json_data=None)
    monkeypatch.setattr(utils, 'run', run_side_effect)
    url = utils.get_frontdoor_url(INFRASTRUCTURE.AFD_APIM_PE, 'rg')
    assert url == 'https://foo.azurefd.net'

def test_get_frontdoor_url_none(monkeypatch):
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: MagicMock(success=False, json_data=None))
    url = utils.get_frontdoor_url(INFRASTRUCTURE.AFD_APIM_PE, 'rg')
    assert url is None

# ------------------------------
#    get_infra_rg_name & get_rg_name
# ------------------------------

def test_get_infra_rg_name(monkeypatch):
    class DummyInfra:
        value = 'foo'
    monkeypatch.setattr(utils, 'validate_infrastructure', lambda x: x)
    assert utils.get_infra_rg_name(DummyInfra) == 'apim-infra-foo'
    assert utils.get_infra_rg_name(DummyInfra, 2) == 'apim-infra-foo-2'

def test_get_rg_name():
    assert utils.get_rg_name('foo') == 'apim-sample-foo'
    assert utils.get_rg_name('foo', 3) == 'apim-sample-foo-3'

# ------------------------------
#    run
# ------------------------------

def test_run_success(monkeypatch):
    monkeypatch.setattr('subprocess.check_output', lambda *a, **kw: b'{"a": 1}')
    out = utils.run('echo', print_command_to_run=False)
    assert out.success is True
    assert out.json_data == {"a": 1}

def test_run_failure(monkeypatch):
    class DummyErr(Exception):
        output = b'fail'
    def fail(*a, **kw):
        raise DummyErr()
    monkeypatch.setattr('subprocess.check_output', fail)
    out = utils.run('bad', print_command_to_run=False)
    assert out.success is False
    assert isinstance(out.text, str)

# ------------------------------
#    create_resource_group & does_resource_group_exist
# ------------------------------

def test_does_resource_group_exist(monkeypatch):
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: MagicMock(success=True))
    assert utils.does_resource_group_exist('foo') is True
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: MagicMock(success=False))
    assert utils.does_resource_group_exist('foo') is False

def test_create_resource_group(monkeypatch):
    called = {}
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda rg: False)
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: called.setdefault('info', True))
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: called.setdefault('run', True))
    utils.create_resource_group('foo', 'bar')
    assert called['info'] and called['run']

# ------------------------------
#    policy_xml_replacement
# ------------------------------

def test_policy_xml_replacement(monkeypatch):
    m = mock_open(read_data='<xml>foo</xml>')
    monkeypatch.setattr(builtins, 'open', m)
    assert utils.policy_xml_replacement('dummy.xml') == '<xml>foo</xml>'

# ------------------------------
#    cleanup_resources (smoke)
# ------------------------------

def test_cleanup_resources_smoke(monkeypatch):
    monkeypatch.setattr(utils, 'run', lambda *a, **kw: MagicMock(success=True, json_data={}))
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_error', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_message', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_ok', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_warning', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_val', lambda *a, **kw: None)
    # Direct private method call for legacy test (should still work)
    utils._cleanup_resources(INFRASTRUCTURE.SIMPLE_APIM.value, 'rg')

def test_cleanup_infra_deployment_single(monkeypatch):
    monkeypatch.setattr(utils, '_cleanup_resources', lambda deployment_name, rg_name: None)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, None)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, 1)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1, 2])

def test_cleanup_deployment_single(monkeypatch):
    monkeypatch.setattr(utils, '_cleanup_resources', lambda deployment_name, rg_name: None)
    utils.cleanup_deployment('foo', None)
    utils.cleanup_deployment('foo', 1)
    utils.cleanup_deployment('foo', [1, 2])

# ------------------------------
#    EXTRACT_JSON EDGE CASES
# ------------------------------

@pytest.mark.parametrize(
    "input_val,expected",
    [
        (None, None),
        (123, None),
        ([], None),
        ("", None),
        ("   ", None),
        ("not json", None),
        ("{\"a\": 1}", {"a": 1}),
        ("[1, 2, 3]", [1, 2, 3]),
        ("  {\"a\": 1}  ", {"a": 1}),
        ("prefix {\"foo\": 42} suffix", {"foo": 42}),
        ("prefix [1, 2, 3] suffix", [1, 2, 3]),
        ("{\"a\": 1}{\"b\": 2}", {"a": 1}),  # Only first JSON object
        ("[1, 2, 3][4, 5, 6]", [1, 2, 3]),  # Only first JSON array
        ("{\"a\": 1,}", None),  # Trailing comma
        ("[1, 2,]", None),  # Trailing comma in array
        ("{\"a\": [1, 2, {\"b\": 3}]}", {"a": [1, 2, {"b": 3}]}),
        ("\n\t{\"a\": 1}\n", {"a": 1}),
        ("{\"a\": \"b \\u1234\"}", {"a": "b \u1234"}),
        ("{\"a\": 1} [2, 3]", {"a": 1}),  # Object before array
        ("[2, 3] {\"a\": 1}", [2, 3]),  # Array before object
        ("{\"a\": 1, \"b\": {\"c\": 2}}", {"a": 1, "b": {"c": 2}}),
        ("{\"a\": 1, \"b\": [1, 2, 3]}", {"a": 1, "b": [1, 2, 3]}),
        ("\n\n[\n1, 2, 3\n]\n", [1, 2, 3]),
        ("{\"a\": 1, \"b\": null}", {"a": 1, "b": None}),
        ("{\"a\": true, \"b\": false}", {"a": True, "b": False}),
        ("{\"a\": 1, \"b\": \"c\"}", {"a": 1, "b": "c"}),
        ("{\"a\": 1, \"b\": [1, 2, {\"c\": 3}]} ", {"a": 1, "b": [1, 2, {"c": 3}]}),
        ("{\"a\": 1, \"b\": [1, 2, {\"c\": 3, \"d\": [4, 5]}]} ", {"a": 1, "b": [1, 2, {"c": 3, "d": [4, 5]}]}),
    ]
)
def test_extract_json_edge_cases(input_val, expected):
    """Test extract_json with a wide range of edge cases and malformed input."""
    result = utils.extract_json(input_val)
    assert result == expected

def test_extract_json_large_object():
    """Test extract_json with a large JSON object."""
    large_obj = {"a": list(range(1000)), "b": {"c": "x" * 1000}}
    import json
    s = json.dumps(large_obj)
    assert utils.extract_json(s) == large_obj

def test_extract_json_multiple_json_types():
    """Test extract_json returns the first valid JSON (object or array) in the string."""
    s = '[1,2,3]{"a": 1}'
    assert utils.extract_json(s) == [1, 2, 3]
    s2 = '{"a": 1}[1,2,3]'
    assert utils.extract_json(s2) == {"a": 1}
