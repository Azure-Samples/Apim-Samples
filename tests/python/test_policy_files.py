"""Tests for the extracted policy_files capability."""

import importlib.util
import inspect
import logging
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from test_helpers import (
    patch_open_for_text_read,
)
import policy_files


@pytest.mark.parametrize('import_from', ['utils', 'policy_files'])
def test_policy_autodetection_uses_real_caller_frame(monkeypatch, tmp_path, import_from):
    """Direct and compatibility imports resolve the calling sample unchanged."""
    sample_dir = tmp_path / 'samples' / 'demo'
    policy_dir = sample_dir / 'apim-policies'
    policy_dir.mkdir(parents=True)
    policy = policy_dir / 'policy.xml'
    policy.write_text('<policies />', encoding='utf-8')
    caller = sample_dir / 'probe.py'
    caller.write_text(f'from {import_from} import determine_policy_path\nresolved = determine_policy_path("policy.xml")\n', encoding='utf-8')
    monkeypatch.setattr(policy_files, 'get_project_root', lambda: str(tmp_path))
    spec = importlib.util.spec_from_file_location('policy_caller', caller)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    assert Path(module.resolved) == policy


def test_shared_policy_path_uses_discovered_root(monkeypatch):
    """Construct the exact fragment path below the discovered repository root."""
    monkeypatch.setattr(policy_files, 'find_project_root', lambda: '/project/root')

    assert policy_files.determine_shared_policy_path('my-fragment.xml') == str(Path('/project/root') / 'shared' / 'apim-policies' / 'fragments' / 'my-fragment.xml')


def test_read_policy_xml_success(monkeypatch):
    """Test reading a valid XML file returns its contents."""
    xml_content = '<policies><inbound><base /></inbound></policies>'
    monkeypatch.setattr(policy_files, 'determine_policy_path', lambda *a, **k: '/path/to/dummy.xml')
    patch_open_for_text_read(monkeypatch, match='/path/to/dummy.xml', read_data=xml_content)
    # Use full path to avoid sample name auto-detection
    result = policy_files.read_policy_xml('/path/to/dummy.xml')
    assert result == xml_content


def test_read_policy_xml_file_not_found(monkeypatch):
    """Test reading a missing XML file raises FileNotFoundError."""
    patch_open_for_text_read(monkeypatch, match='/path/to/missing.xml', raises=FileNotFoundError('File not found'))
    with pytest.raises(FileNotFoundError):
        policy_files.read_policy_xml('/path/to/missing.xml')


def test_read_policy_xml_empty_file(monkeypatch):
    """Test reading an empty XML file returns an empty string."""
    patch_open_for_text_read(monkeypatch, match='/path/to/empty.xml', read_data='')
    result = policy_files.read_policy_xml('/path/to/empty.xml')
    assert not result


def test_read_policy_xml_with_named_values(monkeypatch):
    """Test reading policy XML with named values formatting."""
    xml_content = '<policy><validate-jwt><issuer-signing-keys><key>{jwt_signing_key}</key></issuer-signing-keys></validate-jwt></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: p.endswith('hr_all_operations.xml'), read_data=xml_content)

    # Mock the auto-detection to return 'authX'
    def mock_inspect_currentframe():
        frame = MagicMock()
        caller_frame = MagicMock()
        caller_frame.f_globals = {'__file__': '/project/samples/authX/create.ipynb'}
        frame.f_back = caller_frame
        return frame

    monkeypatch.setattr('inspect.currentframe', mock_inspect_currentframe)
    monkeypatch.setattr('policy_files.get_project_root', lambda: Path('/project'))

    named_values = {'jwt_signing_key': 'JwtSigningKey123'}

    result = policy_files.read_policy_xml('hr_all_operations.xml', named_values)
    expected = '<policy><validate-jwt><issuer-signing-keys><key>{{JwtSigningKey123}}</key></issuer-signing-keys></validate-jwt></policy>'
    assert result == expected


def test_read_policy_xml_legacy_mode(monkeypatch):
    """Test that legacy mode (full path) still works."""
    xml_content = '<policies><inbound><base /></inbound></policies>'
    patch_open_for_text_read(monkeypatch, match='/full/path/to/policy.xml', read_data=xml_content)
    result = policy_files.read_policy_xml('/full/path/to/policy.xml')
    assert result == xml_content


def test_read_policy_xml_auto_detection_failure(monkeypatch):
    """Test that auto-detection failure provides helpful error."""
    # Avoid patching builtins.open here, since the failure should happen before any file IO.

    # Mock the auto-detection to fail
    def mock_inspect_currentframe():
        frame = MagicMock()
        caller_frame = MagicMock()
        caller_frame.f_globals = {'__file__': '/project/notsamples/test/create.ipynb'}
        frame.f_back = caller_frame
        return frame

    monkeypatch.setattr('inspect.currentframe', mock_inspect_currentframe)

    with pytest.raises(ValueError, match='Could not auto-detect sample name'):
        policy_files.read_policy_xml('policy.xml', {'key': 'value'})


def test_determine_policy_path_filename_mode(monkeypatch):
    """Test determine_policy_path with filename mode."""

    # Mock the project root
    mock_project_root = Path('/mock/project/root')
    monkeypatch.setattr('policy_files.get_project_root', lambda: mock_project_root)

    # Mock current frame to simulate being in samples/test-sample
    class MockFrame:
        def __init__(self):
            self.f_globals = {'__file__': '/mock/project/root/samples/test-sample/create.ipynb'}

    def mock_currentframe():
        frame = MockFrame()
        return frame

    monkeypatch.setattr(inspect, 'currentframe', mock_currentframe)

    result = policy_files.determine_policy_path('policy.xml', 'test-sample')
    expected = str(mock_project_root / 'samples' / 'test-sample' / 'policy.xml')
    assert result == expected


def test_determine_policy_path_full_path():
    """Test determine_policy_path with full path."""
    full_path = '/path/to/policy.xml'
    result = policy_files.determine_policy_path(full_path)
    assert result == full_path


def test_determine_policy_path_prefers_canonical_directory(monkeypatch, tmp_path):
    """Test canonical sample policy paths take precedence over legacy paths."""
    sample_path = tmp_path / 'samples' / 'test-sample'
    canonical_path = sample_path / 'apim-policies' / 'policy.xml'
    canonical_path.parent.mkdir(parents=True)
    canonical_path.write_text('<canonical />', encoding='utf-8')
    (sample_path / 'policy.xml').write_text('<legacy />', encoding='utf-8')
    monkeypatch.setattr(policy_files, 'get_project_root', lambda: tmp_path)

    result = policy_files.determine_policy_path('policy.xml', 'test-sample')

    assert result == str(canonical_path)


def test_determine_policy_path_falls_back_to_sample_root(monkeypatch, tmp_path):
    """Test unmigrated sample policies still resolve from the sample root."""
    legacy_path = tmp_path / 'samples' / 'test-sample' / 'policy.xml'
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text('<legacy />', encoding='utf-8')
    monkeypatch.setattr(policy_files, 'get_project_root', lambda: tmp_path)

    result = policy_files.determine_policy_path('policy.xml', 'test-sample')

    assert result == str(legacy_path)


def test_determine_policy_path_auto_detects_canonical_directory(monkeypatch, tmp_path):
    """Test auto-detected sample names resolve canonical policy paths."""
    canonical_path = tmp_path / 'samples' / 'test-sample' / 'apim-policies' / 'policy.xml'
    canonical_path.parent.mkdir(parents=True)
    canonical_path.write_text('<canonical />', encoding='utf-8')

    class FakeFrame:
        def __init__(self):
            self.f_back = MagicMock()
            self.f_back.f_globals = {'__file__': str(tmp_path / 'samples' / 'test-sample' / 'helper.py')}

    monkeypatch.setattr(policy_files, 'get_project_root', lambda: tmp_path)
    monkeypatch.setattr(policy_files.inspect, 'currentframe', FakeFrame)

    result = policy_files.determine_policy_path('policy.xml')

    assert result == str(canonical_path)


def test_read_policy_xml_missing_filename_raises(monkeypatch, tmp_path):
    """Test missing filename-only policies raise FileNotFoundError after fallback."""
    monkeypatch.setattr(policy_files, 'get_project_root', lambda: tmp_path)

    with pytest.raises(FileNotFoundError):
        policy_files.read_policy_xml('missing.xml', sample_name='test-sample')


def test_read_policy_xml_with_sample_name_explicit(monkeypatch):
    """Test read_policy_xml with explicit sample name."""
    mock_project_root = Path('/mock/project/root')
    monkeypatch.setattr('policy_files.get_project_root', lambda: mock_project_root)

    xml_content = '<policies><inbound><base /></inbound></policies>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in str(p), read_data=xml_content)

    result = policy_files.read_policy_xml('policy.xml', sample_name='test-sample')
    assert result == xml_content


def test_read_policy_xml_with_named_values_formatting(monkeypatch):
    """Test read_policy_xml with named values formatting."""
    xml_content = '<policy><key>{jwt_key}</key></policy>'
    expected = '<policy><key>{{JwtSigningKey}}</key></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in str(p), read_data=xml_content)

    named_values = {'jwt_key': 'JwtSigningKey'}
    result = policy_files.read_policy_xml('/path/to/policy.xml', named_values)
    assert result == expected


def test_determine_policy_path_with_full_path():
    """Test determine_policy_path with full file path."""
    full_path = '/full/path/to/policy.xml'
    result = policy_files.determine_policy_path(full_path)
    assert result == full_path


def test_determine_policy_path_with_sample_name(monkeypatch):
    """Test determine_policy_path with sample name."""
    mock_root = Path('/mock/root')
    monkeypatch.setattr('policy_files.get_project_root', lambda: mock_root)

    result = policy_files.determine_policy_path('policy.xml', 'test-sample')
    expected = str(mock_root / 'samples' / 'test-sample' / 'policy.xml')
    assert result == expected


def test_read_and_modify_policy_xml_with_replacements(monkeypatch):
    """Test read_and_modify_policy_xml with placeholders."""
    xml_content = '<policy><key>{jwt_key}</key><value>{api_value}</value></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'test-policy.xml' in p, read_data=xml_content)

    replacements = {'jwt_key': 'JwtSigningKey123', 'api_value': 'test-api'}

    result = policy_files.read_and_modify_policy_xml('/path/to/test-policy.xml', replacements)
    expected = '<policy><key>JwtSigningKey123</key><value>test-api</value></policy>'
    assert result == expected


def test_read_and_modify_policy_xml_placeholder_not_found(monkeypatch, caplog):
    """Test read_and_modify_policy_xml when placeholder doesn't exist in XML."""
    xml_content = '<policy><key>static</key></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'test-policy.xml' in p, read_data=xml_content)

    replacements = {'missing_key': 'value'}

    with caplog.at_level(logging.WARNING):
        _ = policy_files.read_and_modify_policy_xml('/path/to/test-policy.xml', replacements)

    # Should log warning about missing placeholder
    assert any('missing_key' in record.message for record in caplog.records)


def test_read_and_modify_policy_xml_none_replacements(monkeypatch):
    """Test read_and_modify_policy_xml with None replacements."""
    xml_content = '<policy><key>{jwt_key}</key></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'test-policy.xml' in p, read_data=xml_content)

    result = policy_files.read_and_modify_policy_xml('/path/to/test-policy.xml', None)
    # Should return unmodified XML
    assert result == xml_content


def test_determine_shared_policy_path(monkeypatch):
    """Test determine_shared_policy_path function."""
    monkeypatch.setattr(policy_files, 'find_project_root', lambda: 'c:\\mock\\project')

    result = policy_files.determine_shared_policy_path('test-policy.xml')
    expected = Path('c:\\mock\\project') / 'shared' / 'apim-policies' / 'fragments' / 'test-policy.xml'

    assert Path(result) == expected


def test_read_policy_xml_complex_replacements(monkeypatch):
    """Test read_and_modify_policy_xml with complex replacement scenarios."""
    xml_content = '<policy><key1>{placeholder1}</key1><key2>{placeholder2}</key2><key3>{placeholder3}</key3></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in p, read_data=xml_content)

    replacements = {'placeholder1': 'value1', 'placeholder2': 'value2', 'placeholder3': 'value3'}

    result = policy_files.read_and_modify_policy_xml('/path/to/policy.xml', replacements)

    # Verify all replacements were made
    assert 'value1' in result
    assert 'value2' in result
    assert 'value3' in result
    assert '{placeholder1}' not in result
    assert '{placeholder2}' not in result
    assert '{placeholder3}' not in result


def test_read_policy_xml_with_special_characters(monkeypatch):
    """Test read_policy_xml with special characters and Unicode."""
    xml_content = '<policy>Unicode: © ® ™ € Chinese: 中文 Arabic: العربية</policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in p, read_data=xml_content)

    result = policy_files.read_policy_xml('/path/to/policy.xml')
    assert '©' in result
    assert '中文' in result
    assert 'العربية' in result


def test_determine_policy_path_with_backslash_separators():
    """Test determine_policy_path recognizes backslash path separators."""
    path = 'C:\\path\\to\\policy.xml'
    result = policy_files.determine_policy_path(path)

    # Should treat as full path due to backslash
    assert result == path


def test_determine_policy_path_with_forward_slash():
    """Test determine_policy_path recognizes forward slash paths."""
    path = '/absolute/path/to/policy.xml'
    result = policy_files.determine_policy_path(path)

    # Should treat as full path
    assert result == path


def test_determine_policy_path_with_relative_path():
    """Test determine_policy_path recognizes relative paths with separators."""
    path = 'relative/path/policy.xml'
    result = policy_files.determine_policy_path(path)

    # Should treat as full path due to separator
    assert result == path


def test_read_policy_xml_with_multiple_named_values(monkeypatch):
    """Test read_policy_xml with multiple named values."""
    xml_content = '<policy><key1>{var1}</key1><key2>{var2}</key2><key3>{var3}</key3></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in p, read_data=xml_content)

    named_values = {'var1': 'jwt-signing-key', 'var2': 'api-key', 'var3': 'role-id'}

    result = policy_files.read_policy_xml('/path/to/policy.xml', named_values=named_values)

    # Should have double-braced named values
    assert '{{jwt-signing-key}}' in result
    assert '{{api-key}}' in result
    assert '{{role-id}}' in result


def test_read_and_modify_policy_xml_with_empty_replacements(monkeypatch):
    """Test read_and_modify_policy_xml with empty replacements dict."""
    xml_content = '<policy><key>{placeholder}</key></policy>'
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in p, read_data=xml_content)

    result = policy_files.read_and_modify_policy_xml('/path/to/policy.xml', {})

    # With empty replacements, content should be unchanged
    assert result == xml_content


def test_read_and_modify_policy_xml_preserves_formatting(monkeypatch):
    """Test read_and_modify_policy_xml preserves XML formatting."""
    xml_content = """<policy>
    <inbound>
        <base />
        <set-variable name="test" value="{placeholder}" />
    </inbound>
</policy>"""
    patch_open_for_text_read(monkeypatch, match=lambda p: 'policy.xml' in p, read_data=xml_content)

    replacements = {'placeholder': 'actual-value'}
    result = policy_files.read_and_modify_policy_xml('/path/to/policy.xml', replacements)

    # Should preserve indentation and newlines
    assert '\n    <inbound>\n' in result
    assert 'actual-value' in result


def test_determine_policy_path_missing_sample_name(monkeypatch):
    class FakeFrame:
        def __init__(self):
            self.f_back = MagicMock()
            self.f_back.f_globals = {'__file__': str(Path('/tmp/samples'))}

    monkeypatch.setattr(policy_files.inspect, 'currentframe', FakeFrame)

    with pytest.raises(ValueError, match='Could not detect sample name'):
        policy_files.determine_policy_path('policy.xml')


def test_determine_policy_path_fallback_to_cwd(monkeypatch, tmp_path):
    class FakeFrame:
        def __init__(self):
            self.f_back = MagicMock()
            self.f_back.f_globals = {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(policy_files.inspect, 'currentframe', FakeFrame)

    with pytest.raises(ValueError, match='Not running from within a samples directory'):
        policy_files.determine_policy_path('policy.xml')
