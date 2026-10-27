"""JSON helpers and utilities

Autoreload: reload_safe
Stateless parsing and formatting functions support automatic reload.
"""

import json
import ast
from typing import Any


def is_string_json(text: str) -> bool:
    """
    Check if the provided string is a valid JSON object or array.

    Args:
        text (str): The string to check.

    Returns:
        bool: True if the string is valid JSON, False otherwise.
    """

    # Accept only str, bytes, or bytearray as valid input for JSON parsing.
    if not isinstance(text, (str, bytes, bytearray)):
        return False

    # Skip empty or whitespace-only strings
    if not text or not text.strip():
        return False

    # First try JSON parsing (handles double quotes)
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        pass

    # If JSON fails, try Python literal evaluation (handles single quotes)
    try:
        ast.literal_eval(text)
        return True
    except (ValueError, SyntaxError):
        pass

    return False


def pretty_json(value: Any, indent: int = 4) -> str:
    """
    Return indented JSON for mappings, lists, and JSON text; otherwise return the value as text.

    Args:
        value (Any): A dict, list, mapping-like object (e.g. response headers), or a string that may contain JSON.
        indent (int): Number of spaces per indentation level.

    Returns:
        str: The pretty-printed JSON, or the original text when the value is not JSON.
    """

    if isinstance(value, (str, bytes, bytearray)):
        try:
            value = json.loads(value)
        except ValueError:
            return value.decode('utf-8', errors='replace') if isinstance(value, (bytes, bytearray)) else value

    if hasattr(value, 'items'):
        value = dict(value)

    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=indent, ensure_ascii=False, default=str)

    return str(value)


def extract_json(text: str) -> Any:
    """
    Extract the first valid JSON object or array from a string and return it as a Python object.

    This function searches the input string for the first occurrence of a JSON object or array (delimited by '{' or '['),
    and attempts to decode it using json.JSONDecoder().raw_decode. If the input is already valid JSON, it is returned as a Python object.
    If no valid JSON is found, None is returned.

    Args:
        text (str): The string to search for a JSON object or array.

    Returns:
        Any | None: The extracted JSON as a Python object (dict or list), or None if not found or not valid.
    """

    if not isinstance(text, str):
        return None

    # If the string is already valid JSON, parse and return it as a Python object.
    if is_string_json(text):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # If JSON parsing fails despite is_string_json returning True,
            # fall through to substring search
            pass

    decoder = json.JSONDecoder()

    for start, char in enumerate(text):
        if char in ('{', '['):
            try:
                obj, _ = decoder.raw_decode(text[start:])
                return obj
            except Exception:
                continue

    return None
