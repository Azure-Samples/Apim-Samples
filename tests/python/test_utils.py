"""
Unit tests for utils.py.
"""
import pytest
from shared.python import utils

# ------------------------------
#    PUBLIC METHODS
# ------------------------------


@pytest.mark.parametrize(
    "input_str,expected",
    [
        ('{"a": 1}', True),
        ('[1, 2, 3]', True),
        ('not json', False),
        ('{"a": 1', False),
    ]
)
def test_is_string_json(input_str, expected):
    """Test is_string_json with valid and invalid JSON strings."""
    assert utils.is_string_json(input_str) is expected

def test_extract_json_object():
    """Test extract_json extracts JSON object from string."""
    s = 'prefix {"foo": 42, "bar": "baz"} suffix'
    result = utils.extract_json(s)
    assert isinstance(result, dict)
    assert result["foo"] == 42
    assert result["bar"] == "baz"

def test_extract_json_array():
    """Test extract_json extracts JSON array from string."""
    s = 'prefix [1, 2, 3] suffix'
    result = utils.extract_json(s)
    assert isinstance(result, list)
    assert result == [1, 2, 3]

def test_extract_json_none():
    """Test extract_json returns None if no JSON found."""
    s = 'no json here'
    assert utils.extract_json(s) is None

def test_get_rg_name_basic():
    """Test get_rg_name returns correct resource group name."""
    assert utils.get_rg_name("foo") == "apim-sample-foo"

def test_get_rg_name_with_index():
    """Test get_rg_name with index appends index."""
    assert utils.get_rg_name("foo", 2) == "apim-sample-foo-2"

def test_get_infra_rg_name(monkeypatch):
    """Test get_infra_rg_name returns correct name and validates infra."""
    class DummyInfra:
        value = "bar"
    # Patch validate_infrastructure to a no-op
    monkeypatch.setattr(utils, "validate_infrastructure", lambda x: x)
    assert utils.get_infra_rg_name(DummyInfra) == "apim-infra-bar"
    assert utils.get_infra_rg_name(DummyInfra, 3) == "apim-infra-bar-3"