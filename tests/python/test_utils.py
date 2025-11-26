import os
import builtins
from pathlib import Path
from unittest.mock import MagicMock, mock_open
import json
import pytest
from apimtypes import INFRASTRUCTURE, APIM_SKU
import utils

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
    mock_profile = [{'name': 'afd1'}]
    mock_endpoints = [{'hostName': 'foo.azurefd.net'}]
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
    assert out.json_data == {'a': 1}

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
#    read_policy_xml
# ------------------------------

def test_read_policy_xml_success(monkeypatch):
    """Test reading a valid XML file returns its contents."""
    xml_content = '<policies><inbound><base /></inbound></policies>'
    m = mock_open(read_data=xml_content)
    monkeypatch.setattr(builtins, 'open', m)
    # Use full path to avoid sample name auto-detection
    result = utils.read_policy_xml('/path/to/dummy.xml')
    assert result == xml_content

def test_read_policy_xml_file_not_found(monkeypatch):
    """Test reading a missing XML file raises FileNotFoundError."""
    def raise_fnf(*args, **kwargs):
        raise FileNotFoundError('File not found')
    monkeypatch.setattr(builtins, 'open', raise_fnf)
    with pytest.raises(FileNotFoundError):
        utils.read_policy_xml('/path/to/missing.xml')

def test_read_policy_xml_empty_file(monkeypatch):
    """Test reading an empty XML file returns an empty string."""
    m = mock_open(read_data='')
    monkeypatch.setattr(builtins, 'open', m)
    result = utils.read_policy_xml('/path/to/empty.xml')
    assert result == ''

def test_read_policy_xml_with_named_values(monkeypatch):
    """Test reading policy XML with named values formatting."""
    xml_content = '<policy><validate-jwt><issuer-signing-keys><key>{jwt_signing_key}</key></issuer-signing-keys></validate-jwt></policy>'
    m = mock_open(read_data=xml_content)
    monkeypatch.setattr(builtins, 'open', m)

    # Mock the auto-detection to return 'authX'
    def mock_inspect_currentframe():
        frame = MagicMock()
        caller_frame = MagicMock()
        caller_frame.f_globals = {'__file__': '/project/samples/authX/create.ipynb'}
        frame.f_back = caller_frame
        return frame

    monkeypatch.setattr('inspect.currentframe', mock_inspect_currentframe)
    monkeypatch.setattr('apimtypes._get_project_root', lambda: Path('/project'))

    named_values = {
        'jwt_signing_key': 'JwtSigningKey123'
    }

    result = utils.read_policy_xml('hr_all_operations.xml', named_values)
    expected = '<policy><validate-jwt><issuer-signing-keys><key>{{JwtSigningKey123}}</key></issuer-signing-keys></validate-jwt></policy>'
    assert result == expected

def test_read_policy_xml_legacy_mode(monkeypatch):
    """Test that legacy mode (full path) still works."""
    xml_content = '<policies><inbound><base /></inbound></policies>'
    m = mock_open(read_data=xml_content)
    monkeypatch.setattr(builtins, 'open', m)
    result = utils.read_policy_xml('/full/path/to/policy.xml')
    assert result == xml_content

def test_read_policy_xml_auto_detection_failure(monkeypatch):
    """Test that auto-detection failure provides helpful error."""
    xml_content = '<policy></policy>'
    m = mock_open(read_data=xml_content)
    monkeypatch.setattr(builtins, 'open', m)

    # Mock the auto-detection to fail
    def mock_inspect_currentframe():
        frame = MagicMock()
        caller_frame = MagicMock()
        caller_frame.f_globals = {'__file__': '/project/notsamples/test/create.ipynb'}
        frame.f_back = caller_frame
        return frame

    monkeypatch.setattr('inspect.currentframe', mock_inspect_currentframe)

    with pytest.raises(ValueError, match='Could not auto-detect sample name'):
        utils.read_policy_xml('policy.xml', {'key': 'value'})

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


def test_cleanup_resources_missing_parameters(monkeypatch):
    """Test _cleanup_resources with missing parameters."""
    print_calls = []

    def mock_print_error(message, *args, **kwargs):
        print_calls.append(message)

    monkeypatch.setattr(utils, 'print_error', mock_print_error)

    # Test missing deployment name
    utils._cleanup_resources('', 'valid-rg')
    assert 'Missing deployment name parameter.' in print_calls

    # Test missing resource group name
    print_calls.clear()
    utils._cleanup_resources('valid-deployment', '')
    assert 'Missing resource group name parameter.' in print_calls

    # Test None deployment name
    print_calls.clear()
    utils._cleanup_resources(None, 'valid-rg')
    assert 'Missing deployment name parameter.' in print_calls

    # Test None resource group name
    print_calls.clear()
    utils._cleanup_resources('valid-deployment', None)
    assert 'Missing resource group name parameter.' in print_calls


def test_cleanup_resources_with_resources(monkeypatch):
    """Test _cleanup_resources with various resource types present."""
    run_commands = []

    def mock_run(command, ok_message='', error_message='', print_command_to_run=True, print_errors=True, print_warnings=True):
        run_commands.append(command)

        # Mock deployment show response
        if 'deployment group show' in command:
            return utils.Output(success=True, text='{"properties": {"provisioningState": "Succeeded"}}')

        # Mock cognitive services list response
        if 'cognitiveservices account list' in command:
            return utils.Output(success=True, text='[{"name": "cog-service-1", "location": "eastus"}, {"name": "cog-service-2", "location": "westus"}]')

        # Mock APIM list response
        if 'apim list' in command:
            return utils.Output(success=True, text='[{"name": "apim-service-1", "location": "eastus"}, {"name": "apim-service-2", "location": "westus"}]')

        # Mock Key Vault list response
        if 'keyvault list' in command:
            return utils.Output(success=True, text='[{"name": "kv-vault-1", "location": "eastus"}, {"name": "kv-vault-2", "location": "westus"}]')

        # Default successful response for delete/purge operations
        return utils.Output(success=True, text='Operation completed')

    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_message', lambda *a, **kw: None)

    # Execute cleanup
    utils._cleanup_resources('test-deployment', 'test-rg')

    # Verify all expected commands were called
    command_patterns = [
        'az deployment group show --name test-deployment -g test-rg',
        'az cognitiveservices account list -g test-rg',
        'az cognitiveservices account delete -g test-rg -n cog-service-1',
        'az cognitiveservices account purge -g test-rg -n cog-service-1 --location "eastus"',
        'az cognitiveservices account delete -g test-rg -n cog-service-2',
        'az cognitiveservices account purge -g test-rg -n cog-service-2 --location "westus"',
        'az apim list -g test-rg',
        'az apim delete -n apim-service-1 -g test-rg -y',
        'az apim deletedservice purge --service-name apim-service-1 --location "eastus"',
        'az apim delete -n apim-service-2 -g test-rg -y',
        'az apim deletedservice purge --service-name apim-service-2 --location "westus"',
        'az keyvault list -g test-rg',
        'az keyvault delete -n kv-vault-1 -g test-rg',
        'az keyvault purge -n kv-vault-1 --location "eastus"',
        'az keyvault delete -n kv-vault-2 -g test-rg',
        'az keyvault purge -n kv-vault-2 --location "westus"',
        'az group delete --name test-rg -y'
    ]

    for pattern in command_patterns:
        assert any(pattern in cmd for cmd in run_commands), f"Expected command pattern not found: {pattern}"


def test_cleanup_resources_no_resources(monkeypatch):
    """Test _cleanup_resources when no resources exist."""
    run_commands = []

    def mock_run(command, ok_message='', error_message='', print_command_to_run=True, print_errors=True, print_warnings=True):
        run_commands.append(command)

        # Mock deployment show response
        if 'deployment group show' in command:
            return utils.Output(success=True, text='{"properties": {"provisioningState": "Succeeded"}}')

        # Mock empty resource lists
        if any(x in command for x in ['cognitiveservices account list', 'apim list', 'keyvault list']):
            return utils.Output(success=True, text='[]')

        # Default successful response
        return utils.Output(success=True, text='Operation completed')

    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_message', lambda *a, **kw: None)

    # Execute cleanup
    utils._cleanup_resources('test-deployment', 'test-rg')

    # Verify only listing and resource group deletion commands were called
    expected_commands = [
        'az deployment group show --name test-deployment -g test-rg',
        'az cognitiveservices account list -g test-rg',
        'az apim list -g test-rg',
        'az keyvault list -g test-rg',
        'az group delete --name test-rg -y'
    ]

    for expected in expected_commands:
        assert any(expected in cmd for cmd in run_commands), f"Expected command not found: {expected}"

    # Verify no delete/purge commands for individual resources
    delete_purge_patterns = ['delete -n', 'purge -n', 'deletedservice purge']
    for pattern in delete_purge_patterns:
        assert not any(pattern in cmd for cmd in run_commands), f"Unexpected delete/purge command found: {pattern}"


def test_cleanup_resources_command_failures(monkeypatch):
    """Test _cleanup_resources when commands fail."""

    def mock_run(command, ok_message='', error_message='', print_command_to_run=True, print_errors=True, print_warnings=True):
        # Mock deployment show failure
        if 'deployment group show' in command:
            return utils.Output(success=False, text='Deployment not found')

        # All other commands succeed
        return utils.Output(success=True, json_data=[])

    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_message', lambda *a, **kw: None)

    # Should not raise exception even when deployment show fails
    utils._cleanup_resources('test-deployment', 'test-rg')


def test_cleanup_resources_exception_handling(monkeypatch):
    """Test _cleanup_resources exception handling."""
    exception_caught = []

    def mock_run(command, ok_message='', error_message='', print_command_to_run=True, print_errors=True, print_warnings=True):
        raise Exception("Simulated Azure CLI error")

    def mock_print(message):
        exception_caught.append(message)

    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_message', lambda *a, **kw: None)
    monkeypatch.setattr('builtins.print', mock_print)
    monkeypatch.setattr('traceback.print_exc', lambda: None)

    # Should handle exception gracefully
    utils._cleanup_resources('test-deployment', 'test-rg')

    # Verify exception was caught and printed
    assert any('An error occurred during cleanup:' in msg for msg in exception_caught)

def test_cleanup_infra_deployment_single(monkeypatch):
    monkeypatch.setattr(utils, '_cleanup_resources', lambda deployment_name, rg_name: None)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, None)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, 1)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1])  # Single item in list should use sequential mode


def test_cleanup_infra_deployments_parallel_mode(monkeypatch):
    """Test cleanup_infra_deployments with multiple indexes using parallel execution."""
    cleanup_calls = []

    def mock_cleanup_resources_thread_safe(deployment_name, rg_name, thread_prefix, thread_color):
        cleanup_calls.append((deployment_name, rg_name, thread_prefix, thread_color))
        return True, ""  # Return success

    def mock_get_infra_rg_name(deployment, index):
        return f'apim-infra-{deployment.value}-{index}' if index else f'apim-infra-{deployment.value}'

    monkeypatch.setattr(utils, '_cleanup_resources_thread_safe', mock_cleanup_resources_thread_safe)
    monkeypatch.setattr(utils, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_ok', lambda *a, **kw: None)

    # Test with multiple indexes (should use parallel mode)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1, 2, 3])

    # Verify all cleanup calls were made
    assert len(cleanup_calls) == 3

    # Check that the correct resource groups were targeted
    expected_rgs = [
        'apim-infra-simple-apim-1',
        'apim-infra-simple-apim-2',
        'apim-infra-simple-apim-3'
    ]
    actual_rgs = [call[1] for call in cleanup_calls]
    assert set(actual_rgs) == set(expected_rgs)

    # Check that thread prefixes contain the correct infrastructure and index info
    for deployment_name, rg_name, thread_prefix, thread_color in cleanup_calls:
        assert deployment_name == 'simple-apim'
        assert 'simple-apim' in thread_prefix
        assert thread_color in utils.THREAD_COLORS


def test_cleanup_infra_deployments_parallel_with_failures(monkeypatch):
    """Test parallel cleanup handling when some threads fail."""
    cleanup_calls = []

    def mock_cleanup_resources_thread_safe(deployment_name, rg_name, thread_prefix, thread_color):
        cleanup_calls.append((deployment_name, rg_name))
        # Simulate failure for index 2
        if 'simple-apim-2' in rg_name:
            return False, "Simulated failure for testing"
        return True, ""

    def mock_get_infra_rg_name(deployment, index):
        return f'apim-infra-{deployment.value}-{index}'

    monkeypatch.setattr(utils, '_cleanup_resources_thread_safe', mock_cleanup_resources_thread_safe)
    monkeypatch.setattr(utils, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_error', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_warning', lambda *a, **kw: None)

    # Test with multiple indexes where one fails
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1, 2, 3])

    # Verify all cleanup attempts were made despite failure
    assert len(cleanup_calls) == 3


def test_cleanup_resources_thread_safe_success(monkeypatch):
    """Test the thread-safe cleanup wrapper with successful execution."""
    original_calls = []

    def mock_cleanup_resources_with_thread_safe_printing(deployment_name, rg_name, thread_prefix, thread_color):
        original_calls.append((deployment_name, rg_name))

    monkeypatch.setattr(utils, '_cleanup_resources_with_thread_safe_printing', mock_cleanup_resources_with_thread_safe_printing)

    # Test successful cleanup
    success, error_msg = utils._cleanup_resources_thread_safe(
        'test-deployment', 'test-rg', '[TEST]: ', utils.BOLD_G
    )

    assert success is True
    assert error_msg == ""
    assert len(original_calls) == 1
    assert original_calls[0] == ('test-deployment', 'test-rg')


def test_cleanup_resources_thread_safe_failure(monkeypatch):
    """Test the thread-safe cleanup wrapper with exception handling."""
    def mock_cleanup_resources_with_thread_safe_printing(deployment_name, rg_name, thread_prefix, thread_color):
        raise Exception("Simulated cleanup failure")

    monkeypatch.setattr(utils, '_cleanup_resources_with_thread_safe_printing', mock_cleanup_resources_with_thread_safe_printing)

    # Test failed cleanup
    success, error_msg = utils._cleanup_resources_thread_safe(
        'test-deployment', 'test-rg', '[TEST]: ', utils.BOLD_G
    )

    assert success is False
    assert "Simulated cleanup failure" in error_msg


def test_cleanup_infra_deployments_max_workers_limit(monkeypatch):
    """Test that parallel cleanup properly handles different numbers of indexes."""
    cleanup_calls = []

    def mock_cleanup_resources_thread_safe(deployment_name, rg_name, thread_prefix, thread_color):
        cleanup_calls.append((deployment_name, rg_name, thread_prefix, thread_color))
        return True, ""

    def mock_get_infra_rg_name(deployment, index):
        return f'rg-{deployment.value}-{index}'

    # Mock Azure CLI calls to avoid real execution
    def mock_run(*args, **kwargs):
        return utils.Output(success=True, text='{}')

    monkeypatch.setattr(utils, '_cleanup_resources_thread_safe', mock_cleanup_resources_thread_safe)
    monkeypatch.setattr(utils, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(utils, 'run', mock_run)  # Mock Azure CLI calls
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_ok', lambda *a, **kw: None)

    # Test with 6 indexes (should use parallel mode and handle all indexes)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1, 2, 3, 4, 5, 6])

    # Verify all 6 cleanup calls were made
    assert len(cleanup_calls) == 6, f"Expected 6 cleanup calls, got {len(cleanup_calls)}"

    # Check that the correct resource groups were targeted
    expected_rgs = [f'rg-simple-apim-{i}' for i in range(1, 7)]
    actual_rgs = [call[1] for call in cleanup_calls]
    assert set(actual_rgs) == set(expected_rgs), f"Expected RGs {expected_rgs}, got {actual_rgs}"

    # Test with 2 indexes (should use parallel mode)
    cleanup_calls.clear()
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1, 2])

    assert len(cleanup_calls) == 2, f"Expected 2 cleanup calls, got {len(cleanup_calls)}"

    # Test that thread prefixes and colors are assigned properly
    for call in cleanup_calls:
        deployment_name, rg_name, thread_prefix, thread_color = call
        assert deployment_name == 'simple-apim'
        assert 'simple-apim' in thread_prefix
        assert thread_color in utils.THREAD_COLORS


def test_cleanup_infra_deployments_thread_color_assignment(monkeypatch):
    """Test that thread colors are assigned correctly and cycle through available colors."""
    cleanup_calls = []

    def mock_cleanup_resources_thread_safe(deployment_name, rg_name, thread_prefix, thread_color):
        cleanup_calls.append((deployment_name, rg_name, thread_prefix, thread_color))
        return True, ""

    def mock_get_infra_rg_name(deployment, index):
        return f'apim-infra-{deployment.value}-{index}'

    # Mock Azure CLI calls to avoid real execution
    def mock_run(*args, **kwargs):
        return utils.Output(success=True, text='{}')

    monkeypatch.setattr(utils, '_cleanup_resources_thread_safe', mock_cleanup_resources_thread_safe)
    monkeypatch.setattr(utils, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(utils, 'run', mock_run)  # Mock Azure CLI calls
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_ok', lambda *a, **kw: None)

    # Test with more indexes than available colors to verify cycling
    num_colors = len(utils.THREAD_COLORS)
    test_indexes = list(range(1, num_colors + 3))  # More than available colors

    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, test_indexes)

    # Verify colors were assigned and cycled correctly
    assigned_colors = [call[3] for call in cleanup_calls]

    # Sort the calls by the index extracted from the rg_name to check in deterministic order
    cleanup_calls_sorted = sorted(cleanup_calls, key=lambda x: int(x[1].split('-')[-1]))
    assigned_colors_sorted = [call[3] for call in cleanup_calls_sorted]

    # First num_colors should use each color once
    for i in range(num_colors):
        expected_color = utils.THREAD_COLORS[i % num_colors]
        assert assigned_colors_sorted[i] == expected_color

    # Additional colors should cycle back to the beginning
    if len(assigned_colors_sorted) > num_colors:
        assert assigned_colors_sorted[num_colors] == utils.THREAD_COLORS[0]
        assert assigned_colors_sorted[num_colors + 1] == utils.THREAD_COLORS[1]


def test_cleanup_infra_deployments_all_infrastructure_types(monkeypatch):
    """Test cleanup_infra_deployments with all infrastructure types."""
    cleanup_calls = []

    def mock_cleanup_resources(deployment_name, rg_name):
        cleanup_calls.append((deployment_name, rg_name))

    def mock_get_infra_rg_name(deployment, index):
        return f'apim-infra-{deployment.value}-{index}' if index else f'apim-infra-{deployment.value}'

    monkeypatch.setattr(utils, '_cleanup_resources', mock_cleanup_resources)
    monkeypatch.setattr(utils, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)

    # Test all infrastructure types
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, 1)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.APIM_ACA, 2)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.AFD_APIM_PE, 3)

    # Verify correct calls were made
    assert ('simple-apim', 'apim-infra-simple-apim-1') in cleanup_calls
    assert ('apim-aca', 'apim-infra-apim-aca-2') in cleanup_calls
    assert ('afd-apim-pe', 'apim-infra-afd-apim-pe-3') in cleanup_calls


def test_cleanup_infra_deployments_index_scenarios(monkeypatch):
    """Test cleanup_infra_deployments with various index scenarios."""
    cleanup_calls = []
    thread_safe_calls = []

    def mock_cleanup_resources(deployment_name, rg_name):
        cleanup_calls.append((deployment_name, rg_name))

    def mock_cleanup_resources_thread_safe(deployment_name, rg_name, thread_prefix, thread_color):
        thread_safe_calls.append((deployment_name, rg_name, thread_prefix, thread_color))
        return True, ""

    def mock_get_infra_rg_name(deployment, index):
        return f'apim-infra-{deployment.value}-{index}' if index else f'apim-infra-{deployment.value}'

    # Mock Azure CLI calls to avoid real execution
    def mock_run(*args, **kwargs):
        return utils.Output(success=True, text='{}')

    monkeypatch.setattr(utils, '_cleanup_resources', mock_cleanup_resources)
    monkeypatch.setattr(utils, '_cleanup_resources_thread_safe', mock_cleanup_resources_thread_safe)
    monkeypatch.setattr(utils, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(utils, 'run', mock_run)  # Mock Azure CLI calls
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_ok', lambda *a, **kw: None)

    # Test None index (sequential)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, None)

    # Test single integer index (sequential)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, 5)

    # Test single item list (sequential)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [1])

    # Test list of integers (parallel)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [2, 3])

    # Test tuple of integers (parallel)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, (4, 5))

    # Test empty list (sequential, with no index)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, [])

    # Verify sequential calls
    expected_sequential_calls = [
        ('simple-apim', 'apim-infra-simple-apim'),        # None index
        ('simple-apim', 'apim-infra-simple-apim-5'),      # Single index 5
        ('simple-apim', 'apim-infra-simple-apim-1'),      # Single item list [1]
        ('simple-apim', 'apim-infra-simple-apim'),        # Empty list (None index)
    ]

    for expected_call in expected_sequential_calls:
        assert expected_call in cleanup_calls, f"Expected sequential call {expected_call} not found in {cleanup_calls}"

    # Verify parallel calls (extract just the deployment and rg_name parts)
    parallel_calls = [(call[0], call[1]) for call in thread_safe_calls]
    expected_parallel_calls = [
        ('simple-apim', 'apim-infra-simple-apim-2'),      # List [2, 3] - first
        ('simple-apim', 'apim-infra-simple-apim-3'),      # List [2, 3] - second
        ('simple-apim', 'apim-infra-simple-apim-4'),      # Tuple (4, 5) - first
        ('simple-apim', 'apim-infra-simple-apim-5'),      # Tuple (4, 5) - second
    ]

    for expected_call in expected_parallel_calls:
        assert expected_call in parallel_calls, f"Expected parallel call {expected_call} not found in {parallel_calls}"


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
    result = utils.extract_json(input_val)
    assert result == expected

def test_extract_json_large_object():
    """Test extract_json with a large JSON object."""
    large_obj = {'a': list(range(1000)), 'b': {'c': 'x' * 1000}}
    s = json.dumps(large_obj)
    assert utils.extract_json(s) == large_obj

def test_extract_json_multiple_json_types():
    """Test extract_json returns the first valid JSON (object or array) in the string."""
    s = '[1,2,3]{"a": 1}'
    assert utils.extract_json(s) == [1, 2, 3]
    s2 = '{"a": 1}[1,2,3]'
    assert utils.extract_json(s2) == {'a': 1}

# ------------------------------
#    validate_infrastructure
# ------------------------------

def test_validate_infrastructure_supported():
    # Should return None for supported infra
    assert utils.validate_infrastructure(INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]) is None

def test_validate_infrastructure_unsupported():
    # Should raise ValueError for unsupported infra
    with pytest.raises(ValueError) as exc:
        utils.validate_infrastructure(INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.APIM_ACA])
    assert 'Unsupported infrastructure' in str(exc.value)

def test_validate_infrastructure_multiple_supported():
    # Should return True if infra is in the supported list
    supported = [INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA]
    assert utils.validate_infrastructure(INFRASTRUCTURE.APIM_ACA, supported) is None

# ------------------------------
#    generate_signing_key
# ------------------------------

def test_generate_signing_key():
    s, b64 = utils.generate_signing_key()
    assert isinstance(s, str)
    assert isinstance(b64, str)


# ------------------------------
#    build_infrastructure_tags
# ------------------------------

def test_build_infrastructure_tags_with_enum():
    """Test build_infrastructure_tags with INFRASTRUCTURE enum."""
    result = utils.build_infrastructure_tags(INFRASTRUCTURE.SIMPLE_APIM)
    expected = {'infrastructure': 'simple-apim'}
    assert result == expected

def test_build_infrastructure_tags_with_string():
    """Test build_infrastructure_tags with string infrastructure."""
    result = utils.build_infrastructure_tags('test-infra')
    expected = {'infrastructure': 'test-infra'}
    assert result == expected

def test_build_infrastructure_tags_with_custom_tags():
    """Test build_infrastructure_tags with custom tags."""
    custom_tags = {'env': 'dev', 'team': 'platform'}
    result = utils.build_infrastructure_tags(INFRASTRUCTURE.APIM_ACA, custom_tags)
    expected = {
        'infrastructure': 'apim-aca',
        'env': 'dev',
        'team': 'platform'
    }
    assert result == expected

def test_build_infrastructure_tags_custom_tags_override():
    """Test that custom tags can override standard tags."""
    custom_tags = {'infrastructure': 'custom-override'}
    result = utils.build_infrastructure_tags(INFRASTRUCTURE.AFD_APIM_PE, custom_tags)
    expected = {'infrastructure': 'custom-override'}
    assert result == expected

def test_build_infrastructure_tags_empty_custom_tags():
    """Test build_infrastructure_tags with empty custom tags dict."""
    result = utils.build_infrastructure_tags(INFRASTRUCTURE.SIMPLE_APIM, {})
    expected = {'infrastructure': 'simple-apim'}
    assert result == expected

def test_build_infrastructure_tags_none_custom_tags():
    """Test build_infrastructure_tags with None custom tags."""
    result = utils.build_infrastructure_tags(INFRASTRUCTURE.APIM_ACA, None)
    expected = {'infrastructure': 'apim-aca'}
    assert result == expected


# ------------------------------
#    create_resource_group
# ------------------------------

def test_create_resource_group_not_exists_no_tags(monkeypatch):
    """Test create_resource_group when resource group doesn't exist and no tags provided."""
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: False)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', MagicMock())

    utils.create_resource_group('test-rg', 'eastus')

    # Verify the correct command was called
    expected_cmd = 'az group create --name test-rg --location eastus --tags source=apim-sample'
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    assert actual_cmd == expected_cmd

def test_create_resource_group_not_exists_with_tags(monkeypatch):
    """Test create_resource_group when resource group doesn't exist and tags are provided."""
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: False)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', MagicMock())

    tags = {'infrastructure': 'simple-apim', 'env': 'dev'}
    utils.create_resource_group('test-rg', 'eastus', tags)

    # Verify the correct command was called with tags
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    assert 'source=apim-sample' in actual_cmd
    assert 'infrastructure="simple-apim"' in actual_cmd
    assert 'env="dev"' in actual_cmd

def test_create_resource_group_already_exists(monkeypatch):
    """Test create_resource_group when resource group already exists."""
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: True)
    mock_run = MagicMock()
    monkeypatch.setattr(utils, 'run', mock_run)

    utils.create_resource_group('existing-rg', 'eastus')

    # Verify run was not called since RG already exists
    mock_run.assert_not_called()

def test_create_resource_group_tags_with_special_chars(monkeypatch):
    """Test create_resource_group with tags containing special characters."""
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: False)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', MagicMock())

    tags = {'description': 'This is a test environment', 'owner': 'john@company.com'}
    utils.create_resource_group('test-rg', 'eastus', tags)

    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    # Check that quotes are properly escaped
    assert 'description="This is a test environment"' in actual_cmd
    assert 'owner="john@company.com"' in actual_cmd

def test_create_resource_group_tags_with_numeric_values(monkeypatch):
    """Test create_resource_group with tags containing numeric values."""
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: False)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', MagicMock())

    tags = {'cost-center': 12345, 'version': 1.0}
    utils.create_resource_group('test-rg', 'eastus', tags)

    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    # Numeric values should be converted to strings
    assert 'cost-center="12345"' in actual_cmd
    assert 'version="1.0"' in actual_cmd


# ------------------------------
#    create_bicep_deployment_group
# ------------------------------

def test_create_bicep_deployment_group_with_enum(monkeypatch):
    """Test create_bicep_deployment_group with INFRASTRUCTURE enum."""
    mock_create_rg = MagicMock()
    monkeypatch.setattr(utils, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    mock_open_func = mock_open()
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(builtins, 'print', MagicMock())
    # Mock os functions for file path operations
    monkeypatch.setattr('os.getcwd', MagicMock(return_value='/test/dir'))
    monkeypatch.setattr('os.path.exists', MagicMock(return_value=True))
    monkeypatch.setattr('os.path.basename', MagicMock(return_value='test-dir'))

    bicep_params = {'param1': {'value': 'test'}}
    rg_tags = {'infrastructure': 'simple-apim'}

    _result = utils.create_bicep_deployment_group(
        'test-rg', 'eastus', INFRASTRUCTURE.SIMPLE_APIM, bicep_params, 'params.json', rg_tags
    )

    # Verify create_resource_group was called with correct parameters
    mock_create_rg.assert_called_once_with('test-rg', 'eastus', rg_tags)

    # Verify deployment command was called with enum value
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    assert 'az deployment group create' in actual_cmd
    assert '--name simple-apim' in actual_cmd
    assert '--resource-group test-rg' in actual_cmd

def test_create_bicep_deployment_group_with_string(monkeypatch):
    """Test create_bicep_deployment_group with string deployment name."""
    mock_create_rg = MagicMock()
    monkeypatch.setattr(utils, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    mock_open_func = mock_open()
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(builtins, 'print', MagicMock())
    # Mock os functions for file path operations
    monkeypatch.setattr('os.getcwd', MagicMock(return_value='/test/dir'))
    monkeypatch.setattr('os.path.exists', MagicMock(return_value=True))
    monkeypatch.setattr('os.path.basename', MagicMock(return_value='test-dir'))

    bicep_params = {'param1': {'value': 'test'}}

    _result = utils.create_bicep_deployment_group(
        'test-rg', 'eastus', 'custom-deployment', bicep_params
    )

    # Verify create_resource_group was called without tags
    mock_create_rg.assert_called_once_with('test-rg', 'eastus', None)

    # Verify deployment command uses string deployment name
    mock_run.assert_called_once()
    actual_cmd = mock_run.call_args[0][0]
    assert '--name custom-deployment' in actual_cmd

def test_create_bicep_deployment_group_params_file_written(monkeypatch):
    """Test that bicep parameters are correctly written to file."""
    mock_create_rg = MagicMock()
    monkeypatch.setattr(utils, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    mock_open_func = mock_open()
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(builtins, 'print', MagicMock())

    # Mock os functions for file path operations
    # For this test, we want to simulate being in an infrastructure directory
    monkeypatch.setattr('os.getcwd', MagicMock(return_value='/test/dir/infrastructure/apim-aca'))

    def mock_exists(path):
        # Only return True for the main.bicep in the infrastructure directory, not in current dir
        if path.endswith('main.bicep') and 'infrastructure' in path:
            return True
        return False

    monkeypatch.setattr('os.path.exists', mock_exists)
    monkeypatch.setattr('os.path.basename', MagicMock(return_value='apim-aca'))

    bicep_params = {
        'apiManagementName': {'value': 'test-apim'},
        'location': {'value': 'eastus'}
    }

    utils.create_bicep_deployment_group(
        'test-rg', 'eastus', INFRASTRUCTURE.APIM_ACA, bicep_params, 'custom-params.json'
    )

    # With our new logic, when current directory name matches infrastructure_dir,
    # it should use the current directory
    expected_path = os.path.join('/test/dir/infrastructure/apim-aca', 'custom-params.json')
    mock_open_func.assert_called_once_with(expected_path, 'w')

    # Verify the correct JSON structure was written
    written_content = ''.join(call.args[0] for call in mock_open_func().write.call_args_list)
    written_data = json.loads(written_content)

    assert written_data['$schema'] == 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'
    assert written_data['contentVersion'] == '1.0.0.0'
    assert written_data['parameters'] == bicep_params

def test_create_bicep_deployment_group_no_tags(monkeypatch):
    """Test create_bicep_deployment_group without tags."""
    mock_create_rg = MagicMock()
    monkeypatch.setattr(utils, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=True))
    monkeypatch.setattr(utils, 'run', mock_run)
    mock_open_func = mock_open()
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(builtins, 'print', MagicMock())
    # Mock os functions for file path operations
    monkeypatch.setattr('os.getcwd', MagicMock(return_value='/test/dir'))
    monkeypatch.setattr('os.path.exists', MagicMock(return_value=True))
    monkeypatch.setattr('os.path.basename', MagicMock(return_value='test-dir'))

    bicep_params = {'param1': {'value': 'test'}}

    utils.create_bicep_deployment_group('test-rg', 'eastus', 'test-deployment', bicep_params)

    # Verify create_resource_group was called with None tags
    mock_create_rg.assert_called_once_with('test-rg', 'eastus', None)

def test_create_bicep_deployment_group_deployment_failure(monkeypatch):
    """Test create_bicep_deployment_group when deployment fails."""
    mock_create_rg = MagicMock()
    monkeypatch.setattr(utils, 'create_resource_group', mock_create_rg)
    mock_run = MagicMock(return_value=MagicMock(success=False))
    monkeypatch.setattr(utils, 'run', mock_run)
    mock_open_func = mock_open()
    monkeypatch.setattr(builtins, 'open', mock_open_func)
    monkeypatch.setattr(builtins, 'print', MagicMock())
    # Mock os functions for file path operations
    monkeypatch.setattr('os.getcwd', MagicMock(return_value='/test/dir'))
    monkeypatch.setattr('os.path.exists', MagicMock(return_value=True))
    monkeypatch.setattr('os.path.basename', MagicMock(return_value='test-dir'))

    bicep_params = {'param1': {'value': 'test'}}

    result = utils.create_bicep_deployment_group('test-rg', 'eastus', 'test-deployment', bicep_params)

    # Should still create resource group
    mock_create_rg.assert_called_once()

    # Result should indicate failure
    assert result.success is False

# ------------------------------
#    ADDITIONAL COVERAGE TESTS
# ------------------------------

def test_print_functions_comprehensive():
    """Test all print utility functions for coverage."""
    import io
    import sys

    # Capture stdout
    captured_output = io.StringIO()
    sys.stdout = captured_output

    try:
        # Test all print functions
        utils.print_info('Test info message')
        utils.print_success('Test success message')
        utils.print_warning('Test warning message')
        utils.print_error('Test error message')
        utils.print_message('Test message')
        utils.print_val('Test key', 'Test value')

        output = captured_output.getvalue()
        assert 'Test info message' in output
        assert 'Test success message' in output
        assert 'Test warning message' in output
        assert 'Test error message' in output
        assert 'Test message' in output
        assert 'Test key' in output
        assert 'Test value' in output
    finally:
        sys.stdout = sys.__stdout__


def test_test_url_preflight_check_with_frontdoor(monkeypatch):
    """Test URL preflight check when Front Door is available."""
    monkeypatch.setattr(utils, 'get_frontdoor_url', lambda x, y: 'https://test.azurefd.net')
    monkeypatch.setattr(utils, 'print_message', lambda x, **kw: None)

    result = utils.test_url_preflight_check(INFRASTRUCTURE.AFD_APIM_PE, 'test-rg', 'https://apim.com')
    assert result == 'https://test.azurefd.net'


def test_test_url_preflight_check_no_frontdoor(monkeypatch):
    """Test URL preflight check when Front Door is not available."""
    monkeypatch.setattr(utils, 'get_frontdoor_url', lambda x, y: None)
    monkeypatch.setattr(utils, 'print_message', lambda x, **kw: None)

    result = utils.test_url_preflight_check(INFRASTRUCTURE.SIMPLE_APIM, 'test-rg', 'https://apim.com')
    assert result == 'https://apim.com'


def test_determine_policy_path_filename_mode(monkeypatch):
    """Test determine_policy_path with filename mode."""
    import inspect

    # Mock the project root
    mock_project_root = Path('/mock/project/root')
    monkeypatch.setattr('apimtypes._get_project_root', lambda: mock_project_root)

    # Mock current frame to simulate being in samples/test-sample
    class MockFrame:
        def __init__(self):
            self.f_globals = {'__file__': '/mock/project/root/samples/test-sample/create.ipynb'}

    def mock_currentframe():
        frame = MockFrame()
        frame.f_back = frame
        return frame

    monkeypatch.setattr(inspect, 'currentframe', mock_currentframe)

    result = utils.determine_policy_path('policy.xml', 'test-sample')
    expected = str(mock_project_root / 'samples' / 'test-sample' / 'policy.xml')
    assert result == expected


def test_determine_policy_path_full_path():
    """Test determine_policy_path with full path."""
    full_path = '/path/to/policy.xml'
    result = utils.determine_policy_path(full_path)
    assert result == full_path


def test_check_apim_blob_permissions_success(monkeypatch):
    """Test check_apim_blob_permissions with successful permissions."""
    def mock_run_success(cmd, **kwargs):
        if 'az apim show' in cmd and 'identity.principalId' in cmd:
            return utils.Output(success=True, text='12345678-1234-1234-1234-123456789012')
        elif 'az storage account show' in cmd and '--query id' in cmd:
            return utils.Output(success=True, text='/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/test-storage')
        elif 'az role assignment list' in cmd:
            return utils.Output(success=True, text='/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/test-rg/providers/Microsoft.Authorization/roleAssignments/test-assignment')
        elif 'az storage blob list' in cmd:
            return utils.Output(success=True, text='test-blob.txt')
        return utils.Output(success=True, text='{}')

    monkeypatch.setattr(utils, 'run', mock_run_success)
    monkeypatch.setattr(utils, 'print_info', lambda x: None)
    monkeypatch.setattr(utils, 'print_success', lambda x: None)

    result = utils.check_apim_blob_permissions('test-apim', 'test-storage', 'test-rg', 1)
    assert result is True


def test_check_apim_blob_permissions_failure(monkeypatch):
    """Test check_apim_blob_permissions with failed permissions."""
    def mock_run_failure(cmd, **kwargs):
        if 'az apim api operation' in cmd:
            return utils.Output(success=True, text='{"statusCode": 403}')
        return utils.Output(success=True, text='{}')

    monkeypatch.setattr(utils, 'run', mock_run_failure)
    monkeypatch.setattr(utils, 'print_info', lambda x: None)
    monkeypatch.setattr(utils, 'print_warning', lambda x: None)
    monkeypatch.setattr('time.sleep', lambda x: None)

    result = utils.check_apim_blob_permissions('test-apim', 'test-storage', 'test-rg', 1)
    assert result is False


def test_wait_for_apim_blob_permissions_success(monkeypatch):
    """Test wait_for_apim_blob_permissions with successful wait."""
    monkeypatch.setattr(utils, 'check_apim_blob_permissions', lambda *args: True)
    monkeypatch.setattr(utils, 'print_info', lambda x: None)
    monkeypatch.setattr(utils, 'print_success', lambda x: None)
    monkeypatch.setattr(utils, 'print_error', lambda x: None)

    result = utils.wait_for_apim_blob_permissions('test-apim', 'test-storage', 'test-rg', 1)
    assert result is True


def test_wait_for_apim_blob_permissions_failure(monkeypatch):
    """Test wait_for_apim_blob_permissions with failed wait."""
    monkeypatch.setattr(utils, 'check_apim_blob_permissions', lambda *args: False)
    monkeypatch.setattr(utils, 'print_info', lambda x: None)
    monkeypatch.setattr(utils, 'print_success', lambda x: None)
    monkeypatch.setattr(utils, 'print_error', lambda x: None)

    result = utils.wait_for_apim_blob_permissions('test-apim', 'test-storage', 'test-rg', 1)
    assert result is False


def test_read_policy_xml_with_sample_name_explicit(monkeypatch):
    """Test read_policy_xml with explicit sample name."""
    mock_project_root = Path('/mock/project/root')
    monkeypatch.setattr('apimtypes._get_project_root', lambda: mock_project_root)

    xml_content = '<policies><inbound><base /></inbound></policies>'
    m = mock_open(read_data=xml_content)
    monkeypatch.setattr(builtins, 'open', m)

    result = utils.read_policy_xml('policy.xml', sample_name='test-sample')
    assert result == xml_content


def test_read_policy_xml_with_named_values_formatting(monkeypatch):
    """Test read_policy_xml with named values formatting."""
    xml_content = '<policy><key>{jwt_key}</key></policy>'
    expected = '<policy><key>{{JwtSigningKey}}</key></policy>'
    m = mock_open(read_data=xml_content)
    monkeypatch.setattr(builtins, 'open', m)

    named_values = {'jwt_key': 'JwtSigningKey'}
    result = utils.read_policy_xml('/path/to/policy.xml', named_values)
    assert result == expected


@pytest.mark.parametrize(
    'infra_type,expected_suffix',
    [
        (INFRASTRUCTURE.SIMPLE_APIM, 'simple-apim'),
        (INFRASTRUCTURE.AFD_APIM_PE, 'afd-apim-pe'),
        (INFRASTRUCTURE.APIM_ACA, 'apim-aca'),
    ]
)
def test_get_infra_rg_name_different_types(infra_type, expected_suffix, monkeypatch):
    """Test get_infra_rg_name with different infrastructure types."""
    monkeypatch.setattr(utils, 'validate_infrastructure', lambda x: x)
    result = utils.get_infra_rg_name(infra_type)
    assert result == f'apim-infra-{expected_suffix}'


def test_create_bicep_deployment_group_for_sample_success(monkeypatch):
    """Test create_bicep_deployment_group_for_sample success case."""
    mock_output = utils.Output(success=True, text='{"outputs": {"test": "value"}}')

    def mock_create_bicep(rg_name, rg_location, deployment, bicep_parameters, bicep_parameters_file='params.json', rg_tags=None, is_debug=False):
        return mock_output

    # Mock file system checks
    def mock_exists(path):
        return True  # Pretend all paths exist

    def mock_chdir(path):
        pass  # Do nothing

    monkeypatch.setattr(utils, 'create_bicep_deployment_group', mock_create_bicep)
    monkeypatch.setattr(utils, 'build_infrastructure_tags', lambda x: [])
    monkeypatch.setattr(os.path, 'exists', mock_exists)
    monkeypatch.setattr(os, 'chdir', mock_chdir)

    result = utils.create_bicep_deployment_group_for_sample('test-sample', 'test-rg', 'eastus', {})
    assert result.success is True


def test_extract_json_invalid_input():
    """Test extract_json with various invalid inputs."""
    assert utils.extract_json(None) is None
    assert utils.extract_json(123) is None
    assert utils.extract_json([1, 2, 3]) is None
    assert utils.extract_json('not json at all') is None


def test_generate_signing_key_format():
    """Test that generate_signing_key returns properly formatted keys."""
    key, b64_key = utils.generate_signing_key()

    # Key should be a string of length 32-100
    assert isinstance(key, str)
    assert 32 <= len(key) <= 100  # Length should be between 32 and 100

    # Key should only contain alphanumeric characters
    assert key.isalnum()

    # Base64 key should be valid base64
    assert isinstance(b64_key, str)
    import base64
    try:
        decoded = base64.b64decode(b64_key)
        assert len(decoded) == len(key)  # Decoded should match original length
    except Exception:
        pytest.fail('Base64 key is not valid base64')


def test_output_class_functionality():
    """Test the Output class properties and methods."""
    # Test successful output with deployment structure
    output = utils.Output(success=True, text='{"properties": {"outputs": {"test": {"value": "value"}}}}')
    assert output.success is True
    assert output.get('test') == 'value'
    assert output.get('missing') is None  # Should return None for missing key without label

    # Test failed output
    output = utils.Output(success=False, text='error')
    assert output.success is False
    assert output.get('test') is None


def test_run_command_with_error_suppression(monkeypatch):
    """Test run command with error output suppression."""
    def mock_subprocess_check_output(cmd, **kwargs):
        # Simulate a CalledProcessError with bytes output
        import subprocess
        error = subprocess.CalledProcessError(1, cmd)
        error.output = b'test output'  # Return bytes, as subprocess would
        raise error

    monkeypatch.setattr('subprocess.check_output', mock_subprocess_check_output)

    output = utils.run('test command', print_errors=False, print_output=False)
    assert output.success is False
    assert output.text == 'test output'


def test_bicep_directory_determination_edge_cases(monkeypatch, tmp_path):
    """Test edge cases in Bicep directory determination."""
    # Test when no main.bicep exists anywhere
    empty_dir = tmp_path / 'empty'
    empty_dir.mkdir()
    monkeypatch.setattr(os, 'getcwd', lambda: str(empty_dir))

    # Should fall back to current directory + infrastructure/nonexistent
    result = utils._determine_bicep_directory('nonexistent')
    expected = os.path.join(str(empty_dir), 'infrastructure', 'nonexistent')
    assert result == expected


def test_create_resource_group_edge_cases(monkeypatch):
    """Test create resource group with edge cases."""
    # Test with empty tags
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda x: False)

    def mock_run_with_tags(*args, **kwargs):
        cmd = args[0]
        assert '--tags' in cmd  # Should include tags (with default source=apim-sample)
        return utils.Output(success=True, text='{}')

    monkeypatch.setattr(utils, 'run', mock_run_with_tags)

    utils.create_resource_group('test-rg', 'eastus', {})  # Empty dict, function doesn't return anything


# ------------------------------
#    ROLE AND PERMISSION TESTS
# ------------------------------

def test_get_azure_role_guid_comprehensive(monkeypatch):
    """Test get_azure_role_guid with comprehensive scenarios."""
    # Mock the azure-roles.json file content
    mock_roles = {
        'Storage Blob Data Reader': '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1',
        'Storage Account Contributor': '17d1049b-9a84-46fb-8f53-869881c3d3ab'
    }

    m = mock_open(read_data=json.dumps(mock_roles))
    monkeypatch.setattr(builtins, 'open', m)

    # Test valid role
    result = utils.get_azure_role_guid('Storage Blob Data Reader')
    assert result == '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'

    # Test case sensitivity - function is case sensitive, so this should return None
    result = utils.get_azure_role_guid('storage blob data reader')
    assert result is None

    # Test invalid role
    result = utils.get_azure_role_guid('Nonexistent Role')
    assert result is None


def test_cleanup_functions_comprehensive(monkeypatch):
    """Test cleanup functions with various scenarios."""
    run_commands = []

    def mock_run(command, ok_message='', error_message='', print_output=False, print_command_to_run=True, print_errors=True, print_warnings=True):
        run_commands.append(command)

        # Return appropriate mock responses
        if 'deployment group show' in command:
            return utils.Output(success=True, json_data={
                'properties': {'provisioningState': 'Succeeded'}
            })

        # Return empty lists for resource queries to avoid complex mocking
        if any(x in command for x in ['list -g', 'list']):
            return utils.Output(success=True, json_data=[])

        return utils.Output(success=True, text='{}')

    def mock_get_infra_rg_name(deployment, index):
        return f'test-rg-{deployment.value}-{index}' if index else f'test-rg-{deployment.value}'

    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_message', lambda *a, **kw: None)

    # Test _cleanup_resources (private function)
    utils._cleanup_resources('test-deployment', 'test-rg')  # Should not raise

    # Test cleanup_infra_deployments with INFRASTRUCTURE enum (correct function name and parameter type)

    # Test with all infrastructure types
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.APIM_ACA, 1)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.AFD_APIM_PE, [1, 2])

    # Verify commands were executed
    assert len(run_commands) > 0


def test_cleanup_edge_cases_comprehensive(monkeypatch):
    """Test cleanup functions with edge cases and error conditions."""

    # Test with different index types
    cleanup_calls = []

    def mock_cleanup_resources(deployment_name, rg_name):
        cleanup_calls.append((deployment_name, rg_name))
        return True, ""

    def mock_cleanup_resources_thread_safe(deployment_name, rg_name, thread_prefix, thread_color):
        cleanup_calls.append((deployment_name, rg_name))
        return True, ""

    def mock_get_infra_rg_name(deployment, index):
        return f'rg-{deployment.value}-{index}' if index is not None else f'rg-{deployment.value}'

    # Mock Azure CLI calls to avoid real execution
    def mock_run(*args, **kwargs):
        return utils.Output(success=True, text='{}')

    monkeypatch.setattr(utils, '_cleanup_resources', mock_cleanup_resources)
    monkeypatch.setattr(utils, '_cleanup_resources_thread_safe', mock_cleanup_resources_thread_safe)
    monkeypatch.setattr(utils, 'get_infra_rg_name', mock_get_infra_rg_name)
    monkeypatch.setattr(utils, 'run', mock_run)  # Mock Azure CLI calls
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_ok', lambda *a, **kw: None)

    # Test with zero index (single index, uses sequential path)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, 0)
    assert ('simple-apim', 'rg-simple-apim-0') in cleanup_calls

    # Test with negative index (single index, uses sequential path)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, -1)
    assert ('simple-apim', 'rg-simple-apim--1') in cleanup_calls

    # Test with large index (single index, uses sequential path)
    utils.cleanup_infra_deployments(INFRASTRUCTURE.SIMPLE_APIM, 9999)
    assert ('simple-apim', 'rg-simple-apim-9999') in cleanup_calls

    # Test with mixed positive and negative indexes in list (multiple indexes, uses parallel path)
    cleanup_calls.clear()
    utils.cleanup_infra_deployments(INFRASTRUCTURE.APIM_ACA, [-1, 0, 1])
    expected = [
        ('apim-aca', 'rg-apim-aca--1'),
        ('apim-aca', 'rg-apim-aca-0'),
        ('apim-aca', 'rg-apim-aca-1')
    ]
    for call in expected:
        assert call in cleanup_calls    # Test with single-item list
    cleanup_calls.clear()
    utils.cleanup_infra_deployments(INFRASTRUCTURE.AFD_APIM_PE, [42])
    assert ('afd-apim-pe', 'rg-afd-apim-pe-42') in cleanup_calls


def test_cleanup_resources_partial_failures(monkeypatch):
    """Test _cleanup_resources when some operations fail."""
    run_commands = []

    def mock_run(command, ok_message='', error_message='', print_command_to_run=True, print_errors=True, print_warnings=True):
        run_commands.append(command)

        # Mock deployment show response
        if 'deployment group show' in command:
            return utils.Output(success=True, text='{"properties": {"provisioningState": "Failed"}}')

        # Mock resources exist
        if 'cognitiveservices account list' in command:
            return utils.Output(success=True, text='[{"name": "cog-service-1", "location": "eastus"}]')

        if 'apim list' in command:
            return utils.Output(success=True, text='[{"name": "apim-service-1", "location": "eastus"}]')

        if 'keyvault list' in command:
            return utils.Output(success=True, text='[{"name": "kv-vault-1", "location": "eastus"}]')

        # Simulate failure for delete operations but success for purge
        if 'delete' in command and ('cognitiveservices' in command or 'apim delete' in command or 'keyvault delete' in command):
            return utils.Output(success=False, text='Delete failed')

        # Simulate failure for purge operations
        if 'purge' in command:
            return utils.Output(success=False, text='Purge failed')

        # Resource group deletion succeeds
        return utils.Output(success=True, text='Operation completed')

    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_message', lambda *a, **kw: None)

    # Should not raise exception even when individual operations fail
    utils._cleanup_resources('test-deployment', 'test-rg')

    # Verify all expected commands were attempted despite failures
    expected_patterns = [
        'deployment group show',
        'cognitiveservices account list',
        'cognitiveservices account delete',
        'cognitiveservices account purge',
        'apim list',
        'apim delete',
        'apim deletedservice purge',
        'keyvault list',
        'keyvault delete',
        'keyvault purge',
        'group delete'
    ]

    for pattern in expected_patterns:
        assert any(pattern in cmd for cmd in run_commands), f"Expected command pattern not found: {pattern}"


def test_cleanup_resources_malformed_responses(monkeypatch):
    """Test _cleanup_resources with malformed API responses."""

    def mock_run(command, ok_message='', error_message='', print_command_to_run=True, print_errors=True, print_warnings=True):

        # Mock deployment show with missing properties
        if 'deployment group show' in command:
            return utils.Output(success=True, text='{}')

        # Mock malformed resource responses (missing required fields)
        if 'cognitiveservices account list' in command:
            return utils.Output(success=True, text='[{"name": "cog-service-1"}, {"location": "eastus"}, {}]')

        if 'apim list' in command:
            return utils.Output(success=True, text='[{"name": "apim-service-1"}, {"location": "eastus"}]')

        if 'keyvault list' in command:
            return utils.Output(success=True, text='[{"name": "kv-vault-1"}]')

        # Default response for delete/purge operations
        return utils.Output(success=True, text='Operation completed')

    monkeypatch.setattr(utils, 'run', mock_run)
    monkeypatch.setattr(utils, 'print_info', lambda *a, **kw: None)
    monkeypatch.setattr(utils, 'print_message', lambda *a, **kw: None)

    # Should handle malformed responses gracefully without raising exceptions
    utils._cleanup_resources('test-deployment', 'test-rg')



# ------------------------------
#    INFRASTRUCTURE SELECTION TESTS
# ------------------------------

def test_find_infrastructure_instances_success(monkeypatch):
    """Test _find_infrastructure_instances with successful Azure query."""
    # Create a mock NotebookHelper instance
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    # Mock successful Azure CLI response
    mock_output = utils.Output(success=True, text='apim-infra-simple-apim-1\napim-infra-simple-apim-2\napim-infra-simple-apim')
    monkeypatch.setattr(utils, 'run', lambda *args, **kwargs: mock_output)

    result = nb_helper._find_infrastructure_instances(INFRASTRUCTURE.SIMPLE_APIM)

    expected = [
        (INFRASTRUCTURE.SIMPLE_APIM, None),
        (INFRASTRUCTURE.SIMPLE_APIM, 1),
        (INFRASTRUCTURE.SIMPLE_APIM, 2)
    ]
    # Check that we have the expected results regardless of order
    assert len(result) == len(expected)
    assert set(result) == set(expected)

def test_find_infrastructure_instances_no_results(monkeypatch):
    """Test _find_infrastructure_instances with no matching resource groups."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    # Mock empty Azure CLI response
    mock_output = utils.Output(success=True, text='')
    monkeypatch.setattr(utils, 'run', lambda *args, **kwargs: mock_output)

    result = nb_helper._find_infrastructure_instances(INFRASTRUCTURE.SIMPLE_APIM)
    assert result == []

def test_find_infrastructure_instances_failure(monkeypatch):
    """Test _find_infrastructure_instances when Azure CLI fails."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    # Mock failed Azure CLI response
    mock_output = utils.Output(success=False, text='Error: Authentication failed')
    monkeypatch.setattr(utils, 'run', lambda *args, **kwargs: mock_output)

    result = nb_helper._find_infrastructure_instances(INFRASTRUCTURE.SIMPLE_APIM)
    assert result == []

def test_find_infrastructure_instances_invalid_names(monkeypatch):
    """Test _find_infrastructure_instances with invalid resource group names."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    # Mock Azure CLI response with valid and invalid names
    mock_output = utils.Output(
        success=True,
        text='apim-infra-simple-apim-1\napim-infra-simple-apim-invalid\napim-infra-simple-apim-2\napim-infra-different'
    )
    monkeypatch.setattr(utils, 'run', lambda *args, **kwargs: mock_output)

    result = nb_helper._find_infrastructure_instances(INFRASTRUCTURE.SIMPLE_APIM)

    # Should only include valid names and skip invalid ones
    expected = [
        (INFRASTRUCTURE.SIMPLE_APIM, 1),
        (INFRASTRUCTURE.SIMPLE_APIM, 2)
    ]
    # Check that we have the expected results regardless of order
    assert len(result) == len(expected)
    assert set(result) == set(expected)

def test_find_infrastructure_instances_mixed_formats(monkeypatch):
    """Test _find_infrastructure_instances with mixed indexed and non-indexed names."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.APIM_ACA, [INFRASTRUCTURE.APIM_ACA]
    )

    # Mock Azure CLI response with mixed formats
    mock_output = utils.Output(
        success=True,
        text='apim-infra-apim-aca\napim-infra-apim-aca-1\napim-infra-apim-aca-5'
    )
    monkeypatch.setattr(utils, 'run', lambda *args, **kwargs: mock_output)

    result = nb_helper._find_infrastructure_instances(INFRASTRUCTURE.APIM_ACA)

    expected = [
        (INFRASTRUCTURE.APIM_ACA, None),
        (INFRASTRUCTURE.APIM_ACA, 1),
        (INFRASTRUCTURE.APIM_ACA, 5)
    ]
    # Check that we have the expected results regardless of order
    assert len(result) == len(expected)
    assert set(result) == set(expected)

def test_query_and_select_infrastructure_no_options(monkeypatch):
    """Test _query_and_select_infrastructure when no infrastructures are available."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA]
    )

    # Mock empty results for all infrastructure types
    monkeypatch.setattr(nb_helper, '_find_infrastructure_instances', lambda x: [])
    monkeypatch.setattr(utils, 'print_info', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'print_warning', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'print_success', lambda *args, **kwargs: None)

    # Mock the infrastructure creation to succeed
    def mock_infrastructure_creation(self, bypass_check=True):
        return True

    monkeypatch.setattr(utils.InfrastructureNotebookHelper, 'create_infrastructure', mock_infrastructure_creation)

    # When no infrastructures are available, it should automatically create new infrastructure
    result = nb_helper._query_and_select_infrastructure()

    # Expect it to return the desired infrastructure and None index (since 'test-rg' doesn't match the expected pattern)
    assert result == (INFRASTRUCTURE.SIMPLE_APIM, None)

def test_query_and_select_infrastructure_single_option(monkeypatch):
    """Test _query_and_select_infrastructure with a single available option."""
    # Set up nb_helper with a resource group name that doesn't match the desired pattern
    # This forces the method to show the selection menu instead of finding existing desired infrastructure
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA]
    )

    # Mock single result that doesn't match the desired infrastructure
    def mock_find_instances(infra):
        if infra == INFRASTRUCTURE.SIMPLE_APIM:
            return [(INFRASTRUCTURE.SIMPLE_APIM, 2)]  # Different index than expected
        return []

    # Mock the infrastructure creation to succeed
    def mock_infrastructure_creation(self, bypass_check=True):
        return True

    monkeypatch.setattr(nb_helper, '_find_infrastructure_instances', mock_find_instances)
    monkeypatch.setattr(utils, 'print_info', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'print_success', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'print_warning', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'get_infra_rg_name', lambda infra, idx: f'apim-infra-{infra.value}-{idx}')
    monkeypatch.setattr(utils, 'get_resource_group_location', lambda rg_name: 'eastus')
    monkeypatch.setattr(utils.InfrastructureNotebookHelper, 'create_infrastructure', mock_infrastructure_creation)
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Mock user input to select option 2 (the existing infrastructure, since option 1 is "create new")
    monkeypatch.setattr('builtins.input', lambda prompt: '2')

    result = nb_helper._query_and_select_infrastructure()
    assert result == (INFRASTRUCTURE.SIMPLE_APIM, 2)

def test_query_and_select_infrastructure_multiple_options(monkeypatch):
    """Test _query_and_select_infrastructure with multiple available options."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA]
    )

    # Mock multiple results
    def mock_find_instances(infra):
        if infra == INFRASTRUCTURE.SIMPLE_APIM:
            return [(INFRASTRUCTURE.SIMPLE_APIM, 1), (INFRASTRUCTURE.SIMPLE_APIM, 2)]
        elif infra == INFRASTRUCTURE.APIM_ACA:
            return [(INFRASTRUCTURE.APIM_ACA, None)]
        return []

    # Mock the infrastructure creation to succeed
    def mock_infrastructure_creation(self, bypass_check=True):
        return True

    monkeypatch.setattr(nb_helper, '_find_infrastructure_instances', mock_find_instances)
    monkeypatch.setattr(utils, 'print_info', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'print_success', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'get_infra_rg_name', lambda infra, idx: f'apim-infra-{infra.value}-{idx or ""}')
    monkeypatch.setattr(utils, 'get_resource_group_location', lambda rg_name: 'eastus')
    monkeypatch.setattr(utils.InfrastructureNotebookHelper, 'create_infrastructure', mock_infrastructure_creation)
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Options are sorted:
    # 1. Create new simple-apim (index: 1 since nb_helper._get_current_index() returns 1 for 'test-rg')
    # 2. apim-aca (no index) - sorted first alphabetically
    # 3. simple-apim (index: 1)
    # 4. simple-apim (index: 2)
    # Select option 2 (first existing infrastructure: APIM_ACA with no index)
    monkeypatch.setattr('builtins.input', lambda prompt: '2')

    result = nb_helper._query_and_select_infrastructure()
    assert result == (INFRASTRUCTURE.APIM_ACA, None)

def test_query_and_select_infrastructure_user_cancellation(monkeypatch):
    """Test _query_and_select_infrastructure when user cancels selection."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    # Mock single result
    def mock_find_instances(infra):
        return [(INFRASTRUCTURE.SIMPLE_APIM, 1)]

    monkeypatch.setattr(nb_helper, '_find_infrastructure_instances', mock_find_instances)
    monkeypatch.setattr(utils, 'print_info', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'print_warning', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'get_infra_rg_name', lambda infra, idx: f'apim-infra-{infra.value}-{idx}')
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Mock user input to press Enter (cancel)
    monkeypatch.setattr('builtins.input', lambda prompt: '')

    result = nb_helper._query_and_select_infrastructure()
    assert result == (None, None)

def test_query_and_select_infrastructure_invalid_input_then_valid(monkeypatch):
    """Test _query_and_select_infrastructure with invalid input followed by valid input."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    # Mock single result that doesn't match the desired infrastructure
    def mock_find_instances(infra):
        return [(INFRASTRUCTURE.SIMPLE_APIM, 2)]  # Different index

    # Mock the infrastructure creation to succeed
    def mock_infrastructure_creation(self, bypass_check=True):
        return True

    monkeypatch.setattr(nb_helper, '_find_infrastructure_instances', mock_find_instances)
    monkeypatch.setattr(utils, 'print_info', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'print_error', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'print_success', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'get_infra_rg_name', lambda infra, idx: f'apim-infra-{infra.value}-{idx}')
    monkeypatch.setattr(utils, 'get_resource_group_location', lambda rg_name: 'eastus')
    monkeypatch.setattr(utils.InfrastructureNotebookHelper, 'create_infrastructure', mock_infrastructure_creation)
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Mock user input sequence: invalid number, invalid text, then valid choice (option 2 = existing infrastructure)
    inputs = iter(['99', 'abc', '2'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))

    result = nb_helper._query_and_select_infrastructure()
    assert result == (INFRASTRUCTURE.SIMPLE_APIM, 2)


# ------------------------------
#    TESTS FOR _prompt_for_infrastructure_update
# ------------------------------

def test_prompt_for_infrastructure_update_option_1(monkeypatch):
    """Test _prompt_for_infrastructure_update when user selects option 1 (update)."""
    monkeypatch.setattr('builtins.input', lambda prompt: '1')

    result = utils._prompt_for_infrastructure_update('test-rg')
    assert result == (True, None)

def test_prompt_for_infrastructure_update_option_1_default(monkeypatch):
    """Test _prompt_for_infrastructure_update when user presses Enter (defaults to option 1)."""
    monkeypatch.setattr('builtins.input', lambda prompt: '')

    result = utils._prompt_for_infrastructure_update('test-rg')
    assert result == (True, None)

def test_prompt_for_infrastructure_update_option_2_valid_index(monkeypatch):
    """Test _prompt_for_infrastructure_update when user selects option 2 with valid index."""
    inputs = iter(['2', '5'])  # Option 2, then index 5
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))

    result = utils._prompt_for_infrastructure_update('test-rg')
    assert result == (False, 5)

def test_prompt_for_infrastructure_update_option_2_invalid_then_valid_index(monkeypatch):
    """Test _prompt_for_infrastructure_update when user provides invalid index then valid one."""
    inputs = iter(['2', '', '0', '-1', 'abc', '3'])  # Option 2, then empty, zero, negative, non-number, finally valid
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))

    result = utils._prompt_for_infrastructure_update('test-rg')
    assert result == (False, 3)

def test_prompt_for_infrastructure_update_option_3(monkeypatch):
    """Test _prompt_for_infrastructure_update when user selects option 3 (delete first)."""
    monkeypatch.setattr('builtins.input', lambda prompt: '3')

    result = utils._prompt_for_infrastructure_update('test-rg')
    assert result == (False, None)

def test_prompt_for_infrastructure_update_invalid_choice_then_valid(monkeypatch):
    """Test _prompt_for_infrastructure_update with invalid choice followed by valid choice."""
    inputs = iter(['4', '0', 'invalid', '1'])  # Invalid choices, then option 1
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))

    result = utils._prompt_for_infrastructure_update('test-rg')
    assert result == (True, None)


# ------------------------------
#    TESTS FOR InfrastructureNotebookHelper.create_infrastructure WITH INDEX RETRY
# ------------------------------

def test_infrastructure_notebook_helper_create_with_index_retry(monkeypatch):
    """Test InfrastructureNotebookHelper.create_infrastructure with option 2 (different index) retry."""

    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock resource group existence to return True initially
    call_count = 0
    def mock_rg_exists(rg_name):
        nonlocal call_count
        call_count += 1
        # First call (index 1) returns True, second call (index 3) returns False
        return call_count == 1

    # Mock the prompt to return option 2 with index 3
    monkeypatch.setattr(utils, '_prompt_for_infrastructure_update', lambda rg_name: (False, 3))
    monkeypatch.setattr(utils, 'does_resource_group_exist', mock_rg_exists)

    # Mock subprocess execution to succeed
    class MockProcess:
        def __init__(self, *args, **kwargs):
            self.returncode = 0
            self.stdout = iter(['Mock deployment output\n', 'Success!\n'])

        def wait(self):
            pass

    monkeypatch.setattr('subprocess.Popen', MockProcess)
    monkeypatch.setattr(utils, 'find_project_root', lambda: 'c:\\mock\\root')

    # Mock print functions to avoid output during testing
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Should succeed after retrying with index 3
    result = helper.create_infrastructure()
    assert result is True
    assert helper.index == 3  # Verify index was updated

def test_infrastructure_notebook_helper_create_with_recursive_retry(monkeypatch):
    """Test InfrastructureNotebookHelper.create_infrastructure with multiple recursive retries."""

    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock resource group existence for multiple indexes
    rg_checks = {}
    def mock_rg_exists(rg_name):
        # Parse index from resource group name
        if 'simple-apim-1' in rg_name:
            return True  # Index 1 exists
        elif 'simple-apim-2' in rg_name:
            return True  # Index 2 also exists
        else:
            return False  # Index 3 doesn't exist

    # Mock the prompt to first return index 2, then index 3
    prompt_calls = 0
    def mock_prompt(rg_name):
        nonlocal prompt_calls
        prompt_calls += 1
        if prompt_calls == 1:
            return (False, 2)  # First retry with index 2
        else:
            return (False, 3)  # Second retry with index 3

    monkeypatch.setattr(utils, '_prompt_for_infrastructure_update', mock_prompt)
    monkeypatch.setattr(utils, 'does_resource_group_exist', mock_rg_exists)

    # Mock subprocess execution to succeed
    class MockProcess:
        def __init__(self, *args, **kwargs):
            self.returncode = 0
            self.stdout = iter(['Mock deployment output\n'])

        def wait(self):
            pass

    monkeypatch.setattr('subprocess.Popen', MockProcess)
    monkeypatch.setattr(utils, 'find_project_root', lambda: 'c:\\mock\\root')
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Should succeed after retrying with index 3
    result = helper.create_infrastructure()
    assert result is True
    assert helper.index == 3  # Verify final index

def test_infrastructure_notebook_helper_create_user_cancellation(monkeypatch):
    """Test InfrastructureNotebookHelper.create_infrastructure when user cancels during retry."""

    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock resource group to exist (triggering prompt)
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda rg_name: True)

    # Mock the prompt to return cancellation (option 3)
    monkeypatch.setattr(utils, '_prompt_for_infrastructure_update', lambda rg_name: (False, None))
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Should raise SystemExit when user cancels
    with pytest.raises(SystemExit) as exc_info:
        helper.create_infrastructure()

    assert "User cancelled deployment" in str(exc_info.value)

def test_infrastructure_notebook_helper_create_keyboard_interrupt_during_prompt(monkeypatch):
    """Test InfrastructureNotebookHelper.create_infrastructure when KeyboardInterrupt occurs during prompt."""

    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock resource group to exist (triggering prompt)
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda rg_name: True)

    # Mock the prompt to raise KeyboardInterrupt
    def mock_prompt(rg_name):
        raise KeyboardInterrupt()

    monkeypatch.setattr(utils, '_prompt_for_infrastructure_update', mock_prompt)
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Should raise SystemExit when KeyboardInterrupt occurs
    with pytest.raises(SystemExit) as exc_info:
        helper.create_infrastructure()

    assert "User cancelled deployment" in str(exc_info.value)

def test_infrastructure_notebook_helper_create_eof_error_during_prompt(monkeypatch):
    """Test InfrastructureNotebookHelper.create_infrastructure when EOFError occurs during prompt."""

    helper = utils.InfrastructureNotebookHelper('eastus', INFRASTRUCTURE.SIMPLE_APIM, 1, APIM_SKU.BASICV2)

    # Mock resource group to exist (triggering prompt)
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda rg_name: True)

    # Mock the prompt to raise EOFError
    def mock_prompt(rg_name):
        raise EOFError()

    monkeypatch.setattr(utils, '_prompt_for_infrastructure_update', mock_prompt)
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Should raise SystemExit when EOFError occurs
    with pytest.raises(SystemExit) as exc_info:
        helper.create_infrastructure()

    assert "User cancelled deployment" in str(exc_info.value)

def test_deploy_sample_with_infrastructure_selection(monkeypatch):
    """Test deploy_sample method with infrastructure selection when original doesn't exist."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA]
    )

    # Mock does_resource_group_exist to return False for original, triggering selection
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda rg: False)

    # Mock infrastructure selection to return a valid infrastructure
    selected_infra = INFRASTRUCTURE.APIM_ACA
    selected_index = 2
    monkeypatch.setattr(nb_helper, '_query_and_select_infrastructure',
                       lambda: (selected_infra, selected_index))

    # Mock successful deployment
    mock_output = utils.Output(success=True, text='{"outputs": {"test": "value"}}')
    monkeypatch.setattr(utils, 'create_bicep_deployment_group_for_sample',
                       lambda *args, **kwargs: mock_output)

    # Mock utility functions
    monkeypatch.setattr(utils, 'get_infra_rg_name',
                       lambda infra, idx: f'apim-infra-{infra.value}-{idx}')
    monkeypatch.setattr(utils, 'print_error', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'print_success', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'print_val', lambda *args, **kwargs: None)

    # Test the deployment
    result = nb_helper.deploy_sample({'test': {'value': 'param'}})

    # Verify the helper was updated with selected infrastructure
    assert nb_helper.deployment == selected_infra
    assert nb_helper.rg_name == 'apim-infra-apim-aca-2'
    assert result.success is True

def test_deploy_sample_no_infrastructure_found(monkeypatch):
    """Test deploy_sample method when no suitable infrastructure is found."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    # Mock does_resource_group_exist to return False for original
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda rg: False)

    # Mock infrastructure selection to return None (no infrastructure found)
    monkeypatch.setattr(nb_helper, '_query_and_select_infrastructure',
                       lambda: (None, None))

    # Mock utility functions
    monkeypatch.setattr(utils, 'print_error', lambda *args, **kwargs: None)

    # Test should raise SystemExit
    with pytest.raises(SystemExit):
        nb_helper.deploy_sample({'test': {'value': 'param'}})

def test_deploy_sample_existing_infrastructure(monkeypatch):
    """Test deploy_sample method when the specified infrastructure already exists."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    # Mock does_resource_group_exist to return True (infrastructure exists)
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda rg: True)

    # Mock successful deployment
    mock_output = utils.Output(success=True, text='{"outputs": {"test": "value"}}')
    monkeypatch.setattr(utils, 'create_bicep_deployment_group_for_sample',
                       lambda *args, **kwargs: mock_output)

    # Mock utility functions
    monkeypatch.setattr(utils, 'print_success', lambda *args, **kwargs: None)

    # Test the deployment - should not call infrastructure selection
    result = nb_helper.deploy_sample({'test': {'value': 'param'}})

    # Verify the helper was not modified (still has original values)
    assert nb_helper.deployment == INFRASTRUCTURE.SIMPLE_APIM
    assert nb_helper.rg_name == 'test-rg'
    assert result.success is True

def test_deploy_sample_deployment_failure(monkeypatch):
    """Test deploy_sample method when Bicep deployment fails."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM]
    )

    # Mock does_resource_group_exist to return True
    monkeypatch.setattr(utils, 'does_resource_group_exist', lambda rg: True)

    # Mock failed deployment
    mock_output = utils.Output(success=False, text='Deployment failed')
    monkeypatch.setattr(utils, 'create_bicep_deployment_group_for_sample',
                       lambda *args, **kwargs: mock_output)

    # Test should raise SystemExit
    with pytest.raises(SystemExit):
        nb_helper.deploy_sample({'test': {'value': 'param'}})

def test_notebookhelper_initialization_with_supported_infrastructures():
    """Test NotebookHelper initialization with supported infrastructures list."""
    supported_infras = [INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA]

    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, supported_infras
    )

    assert nb_helper.deployment == INFRASTRUCTURE.SIMPLE_APIM
    assert nb_helper.supported_infrastructures == supported_infras
    assert nb_helper.sample_folder == 'test-sample'
    assert nb_helper.rg_name == 'test-rg'
    assert nb_helper.rg_location == 'eastus'
    assert nb_helper.use_jwt is False

def test_notebookhelper_initialization_with_jwt(monkeypatch):
    """Test NotebookHelper initialization with JWT enabled."""
    # Mock JWT-related functions
    monkeypatch.setattr(utils, 'generate_signing_key', lambda: ('test-key', 'test-key-b64'))
    monkeypatch.setattr(utils, 'print_val', lambda *args, **kwargs: None)
    monkeypatch.setattr('time.time', lambda: 1234567890)

    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM], use_jwt=True
    )

    assert nb_helper.use_jwt is True
    assert nb_helper.jwt_key_name == 'JwtSigningKey-test-sample-1234567890'
    assert nb_helper.jwt_key_value == 'test-key'
    assert nb_helper.jwt_key_value_bytes_b64 == 'test-key-b64'

def test_infrastructure_sorting_in_query_and_select(monkeypatch):
    """Test that infrastructure options are sorted correctly by type then index."""
    nb_helper = utils.NotebookHelper(
        'test-sample', 'test-rg', 'eastus',
        INFRASTRUCTURE.SIMPLE_APIM, [INFRASTRUCTURE.SIMPLE_APIM, INFRASTRUCTURE.APIM_ACA, INFRASTRUCTURE.AFD_APIM_PE]
    )

    # Mock mixed results in unsorted order
    def mock_find_instances(infra):
        if infra == INFRASTRUCTURE.SIMPLE_APIM:
            return [(INFRASTRUCTURE.SIMPLE_APIM, 3), (INFRASTRUCTURE.SIMPLE_APIM, 1)]
        elif infra == INFRASTRUCTURE.APIM_ACA:
            return [(INFRASTRUCTURE.APIM_ACA, None), (INFRASTRUCTURE.APIM_ACA, 2)]
        elif infra == INFRASTRUCTURE.AFD_APIM_PE:
            return [(INFRASTRUCTURE.AFD_APIM_PE, 1)]
        return []

    # Mock the infrastructure creation to succeed
    def mock_infrastructure_creation(self, bypass_check=True):
        return True

    monkeypatch.setattr(nb_helper, '_find_infrastructure_instances', mock_find_instances)
    monkeypatch.setattr(utils, 'print_info', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'print_success', lambda *args, **kwargs: None)
    monkeypatch.setattr(utils, 'get_infra_rg_name', lambda infra, idx: f'apim-infra-{infra.value}-{idx or ""}')
    monkeypatch.setattr(utils, 'get_resource_group_location', lambda rg_name: 'eastus')
    monkeypatch.setattr(utils.InfrastructureNotebookHelper, 'create_infrastructure', mock_infrastructure_creation)
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

    # Test sorting by selecting different options:
    # Options should be sorted: AFD_APIM_PE(1), APIM_ACA(None), APIM_ACA(2), SIMPLE_APIM(1), SIMPLE_APIM(3)
    # 1 = Create new simple-apim
    # 2 = afd-apim-pe (index: 1) - alphabetically first
    # 3 = apim-aca (no index) - None treated as 0
    # 4 = apim-aca (index: 2)
    # 5 = simple-apim (index: 1)
    # 6 = simple-apim (index: 3)

    # Test selecting the first existing infrastructure (afd-apim-pe with index 1)
    monkeypatch.setattr('builtins.input', lambda prompt: '2')
    result = nb_helper._query_and_select_infrastructure()
    assert result == (INFRASTRUCTURE.AFD_APIM_PE, 1)
