"""
Unit tests for test_utils.py.
"""

import json
import pytest
import json_utils


# ------------------------------
#    is_string_json
# ------------------------------

@pytest.mark.parametrize(
    'input_str,expected',
    [
        ('{\"a\": 1}', True),
        ('[1, 2, 3]', True),
        ('not json', False),
        ('{\"a\": 1', False),
        ('', False),
        (None, False),
        (123, False),
    ]
)
def test_is_string_json(input_str, expected):
    assert json_utils.is_string_json(input_str) is expected


# ------------------------------
#    EXTRACT_JSON EDGE CASES
# ------------------------------

@pytest.mark.parametrize(
    'input_val,expected',
    [
        (None, None),
        (123, None),
        ([], None),
        ('', None),
        ('   ', None),
        ('not json', None),
        ('{\"a\": 1}', {'a': 1}),
        ('[1, 2, 3]', [1, 2, 3]),
        ('  {\"a\": 1}  ', {'a': 1}),
        ('prefix {\"foo\": 42} suffix', {'foo': 42}),
        ('prefix [1, 2, 3] suffix', [1, 2, 3]),
        ('{\"a\": 1}{\"b\": 2}', {'a': 1}),  # Only first JSON object
        ('[1, 2, 3][4, 5, 6]', [1, 2, 3]),  # Only first JSON array
        ('{\"a\": [1, 2, {\"b\": 3}]}', {'a': [1, 2, {'b': 3}]}),
        ('\n\t{\"a\": 1}\n', {'a': 1}),
        ('{\"a\": \"b \\u1234\"}', {'a': 'b \u1234'}),
        ('{\"a\": 1} [2, 3]', {'a': 1}),  # Object before array
        ('[2, 3] {\"a\": 1}', [2, 3]),  # Array before object
        ('{\"a\": 1, \"b\": {\"c\": 2}}', {'a': 1, 'b': {'c': 2}}),
        ('{\"a\": 1, \"b\": [1, 2, 3]}', {'a': 1, 'b': [1, 2, 3]}),
        ('\n\n[\n1, 2, 3\n]\n', [1, 2, 3]),
        ('{\"a\": 1, \"b\": null}', {'a': 1, 'b': None}),
        ('{\"a\": true, \"b\": false}', {'a': True, 'b': False}),
        ('{\"a\": 1, \"b\": \"c\"}', {'a': 1, 'b': 'c'}),
        ('{\"a\": 1, \"b\": [1, 2, {\"c\": 3}]} ', {'a': 1, 'b': [1, 2, {'c': 3}]}),
        ('{\"a\": 1, \"b\": [1, 2, {\"c\": 3, \"d\": [4, 5]}]} ', {'a': 1, 'b': [1, 2, {'c': 3, 'd': [4, 5]}]}),
    ]
)
def test_extract_json_edge_cases(input_val, expected):
    """Test extract_json with a wide range of edge cases and malformed input."""
    result = json_utils.extract_json(input_val)
    assert result == expected

def test_extract_json_large_object():
    """Test extract_json with a large JSON object."""
    large_obj = {'a': list(range(1000)), 'b': {'c': 'x' * 1000}}
    s = json.dumps(large_obj)
    assert json_utils.extract_json(s) == large_obj

def test_extract_json_multiple_json_types():
    """Test extract_json returns the first valid JSON (object or array) in the string."""
    s = '[1,2,3]{"a": 1}'
    assert json_utils.extract_json(s) == [1, 2, 3]
    s2 = '{"a": 1}[1,2,3]'
    assert json_utils.extract_json(s2) == {'a': 1}
