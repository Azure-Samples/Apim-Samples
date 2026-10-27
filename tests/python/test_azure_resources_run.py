"""Focused tests for azure_resources.run behavior.

These tests validate the command-runner semantics (debug flag injection, stdout/stderr
handling, and Azure CLI locking) without requiring live Azure.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

# APIM Samples imports
import azure_resources as az
import pytest
from test_helpers import mock_module_functions


class _FakeLock:
    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0

    def __enter__(self) -> None:
        self.entered += 1

    def __exit__(self, exc_type, exc, tb) -> None:
        self.exited += 1


@pytest.fixture
def _quiet_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """Silence console facade functions used by az.run."""

    mock_module_functions(monkeypatch, az, ['print_command', 'print_plain', 'print_ok', 'print_error'])


def test_run_adds_az_debug_flag_and_keeps_stdout_clean_when_success(_quiet_console: None) -> None:
    completed = SimpleNamespace(stdout='{"ok": true}', stderr='DEBUG: noisy stderr', returncode=0)

    with (
        patch.object(az, 'is_debug_enabled', return_value=True),
        patch.object(az.subprocess, 'run', return_value=completed) as sp_run,
        patch.object(az, 'print_plain') as mock_print_plain,
    ):
        output = az.run('az group list -o json')

    assert output.success is True
    assert output.text == '{"ok": true}'

    called_command = sp_run.call_args.args[0]
    assert called_command.startswith('az group list')
    assert '--debug' in called_command

    assert sp_run.call_args.kwargs['check'] is False
    assert sp_run.call_args.kwargs['capture_output'] is True
    assert sp_run.call_args.kwargs['text'] is True

    # stderr debug noise should still be logged at DEBUG.
    assert any(call.kwargs.get('level') == logging.DEBUG for call in mock_print_plain.call_args_list)


def test_run_does_not_add_debug_flag_when_not_debug_enabled(_quiet_console: None) -> None:
    completed = SimpleNamespace(stdout='[]', stderr='', returncode=0)

    with patch.object(az, 'is_debug_enabled', return_value=False), patch.object(az.subprocess, 'run', return_value=completed) as sp_run:
        output = az.run('az group list -o json')

    assert output.success is True
    assert output.text == '[]'
    assert '--debug' not in sp_run.call_args.args[0]


def test_run_inserts_debug_flag_before_pipe_operator(_quiet_console: None) -> None:
    completed = SimpleNamespace(stdout='[]', stderr='debug', returncode=0)

    with patch.object(az, 'is_debug_enabled', return_value=True), patch.object(az.subprocess, 'run', return_value=completed) as sp_run:
        az.run('az group list -o json | jq .')

    assert sp_run.call_args.args[0] == 'az group list -o json --debug | jq .'


def test_run_combines_stdout_and_stderr_on_failure(_quiet_console: None) -> None:
    completed = SimpleNamespace(stdout='partial', stderr='ERROR: failed', returncode=1)

    with patch.object(az, 'is_debug_enabled', return_value=False), patch.object(az.subprocess, 'run', return_value=completed):
        output = az.run('az group list -o json', error_message='failed')

    assert output.success is False
    assert 'partial' in output.text
    assert 'ERROR: failed' in output.text


def test_extract_group_deployment_context_parses_name_and_resource_group() -> None:
    context = az._extract_group_deployment_context(
        'az deployment group create --name appgw-apim --resource-group apim-infra-appgw-apim-1 --template-file "main.bicep"'
    )

    assert context == ('appgw-apim', 'apim-infra-appgw-apim-1')


def test_tokenize_command_handles_empty_and_quoted_values() -> None:
    assert az._tokenize_command('') == []
    assert az._tokenize_command('az group show --name "my rg" --tag \'two words\'') == [
        'az',
        'group',
        'show',
        '--name',
        'my rg',
        '--tag',
        'two words',
    ]


def test_extract_group_deployment_context_supports_short_group_flag() -> None:
    context = az._extract_group_deployment_context('az deployment group create --name appgw-apim -g my-rg')

    assert context == ('appgw-apim', 'my-rg')


def test_extract_group_deployment_context_returns_none_for_non_matching_commands() -> None:
    assert az._extract_group_deployment_context('az group create --name my-rg') is None
    assert az._extract_group_deployment_context('az deployment group create --name only-name') is None


def test_extract_arm_error_details_prefers_nested_detail_message() -> None:
    payload = {
        'code': 'TopLevel',
        'message': 'One or more fields contain incorrect values:',
        'details': [
            {
                'code': 'NestedCode',
                'message': 'Nested message',
            }
        ],
    }

    assert az._extract_arm_error_details(payload) == ('NestedCode', 'Nested message')


def test_extract_arm_error_details_skips_empty_detail_until_it_finds_a_message() -> None:
    payload = {
        'code': 'TopLevel',
        'details': [
            {'code': 'EmptyNested'},
            {'code': 'SecondNested', 'message': 'Second nested message'},
        ],
    }

    assert az._extract_arm_error_details(payload) == ('SecondNested', 'Second nested message')


def test_extract_arm_error_details_prefers_innererror_when_needed() -> None:
    payload = {
        'code': 'TopLevel',
        'innererror': {
            'code': 'InnerCode',
            'message': 'Inner message',
        },
    }

    assert az._extract_arm_error_details(payload) == ('InnerCode', 'Inner message')


def test_extract_arm_error_details_handles_non_dict() -> None:
    assert az._extract_arm_error_details('bad payload') == ('', '')


def test_extract_arm_error_details_returns_fallback_when_innererror_has_no_message() -> None:
    payload = {
        'code': 'TopLevel',
        'innererror': {
            'code': 'InnerOnly',
        },
    }

    assert az._extract_arm_error_details(payload) == ('TopLevel', '')


def test_extract_arm_error_details_returns_fallback_when_details_have_no_message() -> None:
    payload = {
        'code': 'TopLevel',
        'details': [
            {
                'code': 'DetailOnly',
            }
        ],
    }

    assert az._extract_arm_error_details(payload) == ('TopLevel', '')


def test_extract_operation_status_details_covers_string_and_non_dict_paths() -> None:
    assert az._extract_operation_status_details('{bad json') == ('', '{bad json')
    assert az._extract_operation_status_details(['not', 'a', 'dict']) == ('', '')
    assert az._extract_operation_status_details({'code': 'PlainCode', 'message': 'Plain message'}) == ('PlainCode', 'Plain message')


def test_summarize_failed_group_deployment_operations_handles_empty_and_fallback_labels() -> None:
    assert az._summarize_failed_group_deployment_operations([], 'test-rg') == ''

    operations = [
        {
            'operationId': 'op-fallback',
            'properties': {
                'provisioningState': 'Failed',
                'statusMessage': 'Plain failure text',
            },
        },
        {
            'operationId': 'op-success',
            'properties': {
                'provisioningState': 'Succeeded',
                'statusMessage': 'Ignored',
            },
        },
    ]

    summary = az._summarize_failed_group_deployment_operations(operations, 'test-rg')
    assert 'Failed deployment operations (1):' in summary
    assert '- op-fallback: Plain failure text' in summary


def test_summarize_failed_group_deployment_operations_limits_displayed_entries() -> None:
    operations = [
        {
            'operationId': f'op-{index}',
            'properties': {
                'provisioningState': 'Failed',
                'statusMessage': {'message': f'failure-{index}'},
            },
        }
        for index in range(6)
    ]

    summary = az._summarize_failed_group_deployment_operations(operations, 'test-rg')
    assert 'Failed deployment operations (6):' in summary
    assert '- ... and 1 more failed operation(s)' in summary


def test_summarize_failed_group_deployment_operations_recurses_into_nested_deployments(monkeypatch: pytest.MonkeyPatch) -> None:
    operations = [
        {
            'operationId': 'op-parent',
            'properties': {
                'provisioningState': 'Failed',
                'targetResource': {
                    'resourceType': 'Microsoft.Resources/deployments',
                    'resourceName': 'apimModule',
                },
                'statusMessage': {
                    'error': {
                        'code': 'DeploymentFailed',
                        'message': 'Parent deployment failed.',
                    }
                },
            },
        },
        {
            'operationId': 'op-sibling',
            'properties': {
                'provisioningState': 'Failed',
                'targetResource': {
                    'resourceType': 'Microsoft.Network/applicationGateways',
                    'resourceName': 'appgw-sibling',
                },
                'statusMessage': 'Sibling failure',
            },
        },
    ]
    nested_operations = [
        {
            'operationId': 'op-child',
            'properties': {
                'provisioningState': 'Failed',
                'targetResource': {
                    'resourceType': 'Microsoft.ApiManagement/service',
                    'resourceName': 'apim-demo',
                },
                'statusMessage': {
                    'error': {
                        'code': 'ServiceActivationFailed',
                        'message': 'The managed service identity could not access Key Vault.',
                    }
                },
            },
        }
    ]

    monkeypatch.setattr(az, '_fetch_group_deployment_operations', lambda deployment_name, resource_group_name: nested_operations)

    summary = az._summarize_failed_group_deployment_operations(operations, 'test-rg')

    assert '- Microsoft.Resources/deployments / apimModule: DeploymentFailed: Parent deployment failed.' in summary
    assert '>>> Nested deployment apimModule failed operations:' in summary
    assert (
        '  - Microsoft.ApiManagement/service / apim-demo: ServiceActivationFailed: The managed service identity could not access Key Vault.'
        in summary
    )
    assert '- Microsoft.Network/applicationGateways / appgw-sibling: Sibling failure' in summary


def test_summarize_failed_group_deployment_operations_avoids_infinite_recursion(monkeypatch: pytest.MonkeyPatch) -> None:
    operations = [
        {
            'operationId': 'op-parent',
            'properties': {
                'provisioningState': 'Failed',
                'targetResource': {
                    'resourceType': 'Microsoft.Resources/deployments',
                    'resourceName': 'apimModule',
                },
                'statusMessage': 'Deployment failed',
            },
        }
    ]

    monkeypatch.setattr(az, '_fetch_group_deployment_operations', lambda deployment_name, resource_group_name: operations)

    summary = az._summarize_failed_group_deployment_operations(operations, 'test-rg')
    assert summary.count('>>> Nested deployment apimModule failed operations:') == 1


def test_summarize_failed_group_deployment_operations_skips_empty_nested_results(monkeypatch: pytest.MonkeyPatch) -> None:
    operations = [
        {
            'operationId': 'op-parent',
            'properties': {
                'provisioningState': 'Failed',
                'targetResource': {
                    'resourceType': 'Microsoft.Resources/deployments',
                    'resourceName': 'apimModule',
                },
                'statusMessage': 'Deployment failed',
            },
        }
    ]

    monkeypatch.setattr(az, '_fetch_group_deployment_operations', lambda deployment_name, resource_group_name: [])

    summary = az._summarize_failed_group_deployment_operations(operations, 'test-rg')
    assert '>>> Nested deployment apimModule failed operations:' not in summary


def test_collect_failed_group_deployment_operation_lines_continues_when_child_operations_have_no_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = [
        {
            'operationId': 'op-parent',
            'properties': {
                'provisioningState': 'Failed',
                'targetResource': {
                    'resourceType': 'Microsoft.Resources/deployments',
                    'resourceName': 'apimModule',
                },
                'statusMessage': 'Deployment failed',
            },
        },
        {
            'operationId': 'op-sibling',
            'properties': {
                'provisioningState': 'Failed',
                'targetResource': {
                    'resourceType': 'Microsoft.Network/applicationGateways',
                    'resourceName': 'appgw-sibling',
                },
                'statusMessage': 'Sibling failure',
            },
        },
    ]
    child_operations = [
        {
            'operationId': 'child-ok',
            'properties': {
                'provisioningState': 'Succeeded',
                'statusMessage': 'ok',
            },
        }
    ]

    monkeypatch.setattr(az, '_fetch_group_deployment_operations', lambda deployment_name, resource_group_name: child_operations)

    lines = az._collect_failed_group_deployment_operation_lines(operations, 'test-rg')

    assert '>>> Nested deployment apimModule failed operations:' not in '\n'.join(lines)
    assert lines[-1] == '- Microsoft.Network/applicationGateways / appgw-sibling: Sibling failure'


def test_collect_failed_group_deployment_operation_lines_handles_non_failed_and_missing_target_resource() -> None:
    operations = [
        {
            'operationId': 'ignored',
            'properties': {
                'provisioningState': 'Succeeded',
                'statusMessage': 'ok',
            },
        },
        {
            'operationId': 'fallback-op',
            'properties': {
                'provisioningState': 'Failed',
                'targetResource': 'not-a-dict',
                'statusMessage': {'code': 'OnlyCode'},
            },
        },
    ]

    lines = az._collect_failed_group_deployment_operation_lines(operations, 'test-rg')
    assert lines == ['- fallback-op: OnlyCode']


def test_collect_failed_group_deployment_operation_lines_highlights_deeply_nested_errors() -> None:
    """Verify that deeply nested errors (depth >= 2) are highlighted in red."""
    RED = '\033[91m'
    RESET = '\033[0m'

    operations = [
        {
            'operationId': 'top-level',
            'properties': {
                'provisioningState': 'Failed',
                'targetResource': {
                    'resourceType': 'Microsoft.Network/virtualNetworks',
                    'resourceName': 'vnet-test',
                },
                'statusMessage': {
                    'error': {
                        'code': 'TopLevelError',
                        'message': 'Top level failure',
                    },
                },
            },
        },
    ]

    # Depth 0 should not have red coloring
    lines_depth_0 = az._collect_failed_group_deployment_operation_lines(operations, 'test-rg', depth=0)
    assert lines_depth_0 == ['- Microsoft.Network/virtualNetworks / vnet-test: TopLevelError: Top level failure']
    assert RED not in lines_depth_0[0]

    # Depth 1 should not have red coloring
    lines_depth_1 = az._collect_failed_group_deployment_operation_lines(operations, 'test-rg', depth=1)
    assert lines_depth_1[0].startswith('  - ')  # 2-space indent
    assert RED not in lines_depth_1[0]

    # Depth 2 should have red coloring
    lines_depth_2 = az._collect_failed_group_deployment_operation_lines(operations, 'test-rg', depth=2)
    assert lines_depth_2[0].startswith('    - ')  # 4-space indent
    assert RED in lines_depth_2[0]
    assert RESET in lines_depth_2[0]
    assert f'{RED}TopLevelError: Top level failure{RESET}' in lines_depth_2[0]

    # Depth 3 should also have red coloring
    lines_depth_3 = az._collect_failed_group_deployment_operation_lines(operations, 'test-rg', depth=3)
    assert lines_depth_3[0].startswith('      - ')  # 6-space indent
    assert RED in lines_depth_3[0]
    assert RESET in lines_depth_3[0]


def test_collect_failed_group_deployment_operation_lines_formats_nested_deployment_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that nested deployment headers are highlighted in bold red with visual marker."""
    RED = '\033[91m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    operations = [
        {
            'operationId': 'parent-op',
            'properties': {
                'provisioningState': 'Failed',
                'targetResource': {
                    'resourceType': 'Microsoft.Resources/deployments',
                    'resourceName': 'parentModule',
                },
                'statusMessage': {
                    'error': {
                        'code': 'ParentError',
                        'message': 'Parent deployment failed',
                    },
                },
            },
        },
    ]

    child_operations = [
        {
            'operationId': 'child-op',
            'properties': {
                'provisioningState': 'Failed',
                'targetResource': {
                    'resourceType': 'Microsoft.Network/networkSecurityGroups',
                    'resourceName': 'nsg-child',
                },
                'statusMessage': {
                    'error': {
                        'code': 'ChildError',
                        'message': 'Child resource failed',
                    },
                },
            },
        },
    ]

    def mock_fetch(deployment_name, resource_group_name):
        if deployment_name == 'parentModule':
            return child_operations
        return None

    monkeypatch.setattr(az, '_fetch_group_deployment_operations', mock_fetch)

    lines = az._collect_failed_group_deployment_operation_lines(operations, 'test-rg')

    # Should have 3 lines: parent error, nested header, child error
    assert len(lines) >= 3

    # Check that the nested deployment header has the visual marker and red/bold formatting
    nested_header_line = lines[1]
    assert '>>>' in nested_header_line
    assert 'Nested deployment parentModule failed operations:' in nested_header_line
    assert RED in nested_header_line
    assert BOLD in nested_header_line
    assert RESET in nested_header_line


def test_get_group_deployment_failure_summary_returns_empty_for_non_deployment_commands() -> None:
    assert az._get_group_deployment_failure_summary('az group list') == ''


def test_get_group_deployment_failure_summary_handles_subprocess_edge_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    command = 'az deployment group create --name appgw-apim --resource-group my-rg'

    monkeypatch.setattr(az, '_fetch_group_deployment_operations', lambda deployment_name, resource_group_name: None)
    assert az._get_group_deployment_failure_summary(command) == ''

    monkeypatch.setattr(az, '_fetch_group_deployment_operations', lambda deployment_name, resource_group_name: [])
    assert az._get_group_deployment_failure_summary(command) == ''


def test_fetch_group_deployment_operations_handles_subprocess_edge_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_error(*args, **kwargs):
        raise OSError('boom')

    monkeypatch.setattr(az.subprocess, 'run', raise_error)
    assert az._fetch_group_deployment_operations('appgw-apim', 'my-rg') is None

    monkeypatch.setattr(az.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stdout='', stderr='', returncode=1))
    assert az._fetch_group_deployment_operations('appgw-apim', 'my-rg') is None

    monkeypatch.setattr(az.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stdout='{bad json', stderr='', returncode=0))
    assert az._fetch_group_deployment_operations('appgw-apim', 'my-rg') is None

    monkeypatch.setattr(az.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stdout='{}', stderr='', returncode=0))
    assert az._fetch_group_deployment_operations('appgw-apim', 'my-rg') is None


def test_fetch_group_deployment_operations_returns_list(monkeypatch: pytest.MonkeyPatch) -> None:
    operations = [{'operationId': 'op-1', 'properties': {'provisioningState': 'Failed'}}]

    monkeypatch.setattr(
        az.subprocess,
        'run',
        lambda *args, **kwargs: SimpleNamespace(stdout=az.json.dumps(operations), stderr='', returncode=0),
    )

    result = az._fetch_group_deployment_operations('appgw-apim', 'my-rg')
    assert result == operations


def test_get_group_deployment_failure_summary_uses_fetched_operations(monkeypatch: pytest.MonkeyPatch) -> None:
    command = 'az deployment group create --name appgw-apim --resource-group my-rg'
    operations = [
        {
            'operationId': 'op-1',
            'properties': {
                'provisioningState': 'Failed',
                'statusMessage': 'failure',
            },
        }
    ]

    monkeypatch.setattr(az, '_fetch_group_deployment_operations', lambda deployment_name, resource_group_name: operations)

    summary = az._get_group_deployment_failure_summary(command)
    assert 'Failed deployment operations (1):' in summary


def test_run_failure_appends_failed_group_deployment_operations(_quiet_console: None) -> None:
    failed_deployment = SimpleNamespace(
        stdout='',
        stderr='ERROR: At least one resource deployment operation failed. Please list deployment operations for details.',
        returncode=1,
    )
    deployment_operations = [
        {
            'operationId': 'op-1',
            'properties': {
                'provisioningState': 'Failed',
                'targetResource': {
                    'resourceType': 'Microsoft.Network/applicationGateways',
                    'resourceName': 'appgw-demo',
                },
                'statusMessage': {
                    'error': {
                        'code': 'ApplicationGatewaySubnetCannotHaveDelegations',
                        'message': 'Subnet appgw-subnet cannot have delegations configured.',
                    }
                },
            },
        }
    ]
    with (
        patch.object(az, 'is_debug_enabled', return_value=False),
        patch.object(az.subprocess, 'run', return_value=failed_deployment),
        patch.object(az, '_fetch_group_deployment_operations', return_value=deployment_operations),
        patch.object(az, 'print_error') as mock_print_error,
    ):
        output = az.run(
            'az deployment group create --name appgw-apim --resource-group apim-infra-appgw-apim-1 --template-file "main.bicep"',
            error_message='Deployment failed',
        )

    assert output.success is False
    rendered_detail = mock_print_error.call_args.args[1]
    assert 'At least one resource deployment operation failed' in rendered_detail
    assert 'Failed deployment operations (1):' in rendered_detail
    assert 'Microsoft.Network/applicationGateways / appgw-demo' in rendered_detail
    assert 'ApplicationGatewaySubnetCannotHaveDelegations' in rendered_detail


def test_run_uses_az_cli_lock_only_for_az_commands(_quiet_console: None, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_lock = _FakeLock()
    monkeypatch.setattr(az, '_AZ_CLI_LOCK', fake_lock)

    completed = SimpleNamespace(stdout='ok', stderr='', returncode=0)

    with patch.object(az, 'is_debug_enabled', return_value=False), patch.object(az.subprocess, 'run', return_value=completed):
        az.run('az group list')

    assert fake_lock.entered == 1
    assert fake_lock.exited == 1

    # Non-az command should not use the lock.
    fake_lock.entered = 0
    fake_lock.exited = 0

    with patch.object(az, 'is_debug_enabled', return_value=False), patch.object(az.subprocess, 'run', return_value=completed):
        az.run('echo hello')

    assert not fake_lock.entered
    assert not fake_lock.exited


# ------------------------------
#    TIMEOUT TESTS
# ------------------------------


def test_run_passes_default_timeout_to_subprocess(_quiet_console: None) -> None:
    """Default timeout of 240 seconds is forwarded to subprocess.run."""
    completed = SimpleNamespace(stdout='ok', stderr='', returncode=0)

    with patch.object(az, 'is_debug_enabled', return_value=False), patch.object(az.subprocess, 'run', return_value=completed) as sp_run:
        az.run('echo hello')

    assert sp_run.call_args.kwargs['timeout'] == 240


def test_run_passes_custom_timeout_to_subprocess(_quiet_console: None) -> None:
    """A caller-provided timeout overrides the default."""
    completed = SimpleNamespace(stdout='ok', stderr='', returncode=0)

    with patch.object(az, 'is_debug_enabled', return_value=False), patch.object(az.subprocess, 'run', return_value=completed) as sp_run:
        az.run('echo hello', timeout=60)

    assert sp_run.call_args.kwargs['timeout'] == 60


def test_run_timeout_expired_returns_failure(_quiet_console: None) -> None:
    """When the command times out, run() returns a failed Output."""
    with (
        patch.object(az, 'is_debug_enabled', return_value=False),
        patch.object(az.subprocess, 'run', side_effect=subprocess.TimeoutExpired('cmd', 10)),
    ):
        output = az.run('az group list', timeout=10, retries=0)

    assert output.success is False
    assert 'timed out' in output.text


def test_run_timeout_expired_with_az_lock(_quiet_console: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Timeout while holding the az CLI lock still marks the result as failed."""
    fake_lock = _FakeLock()
    monkeypatch.setattr(az, '_AZ_CLI_LOCK', fake_lock)

    with (
        patch.object(az, 'is_debug_enabled', return_value=False),
        patch.object(az.subprocess, 'run', side_effect=subprocess.TimeoutExpired('cmd', 10)),
    ):
        output = az.run('az group list', timeout=10, retries=0)

    assert output.success is False
    assert 'timed out' in output.text
    assert fake_lock.entered == 1
    assert fake_lock.exited == 1


# ------------------------------
#    RETRY TESTS
# ------------------------------


def test_run_default_retries_do_not_repeat_permanent_failure(_quiet_console: None) -> None:
    """A permanent failure is never retried by the default transient policy."""
    failed = SimpleNamespace(stdout='', stderr='error', returncode=1)

    with (
        patch.object(az, 'is_debug_enabled', return_value=False),
        patch.object(az.subprocess, 'run', return_value=failed) as sp_run,
        patch.object(az, 'print_warning'),
    ):
        output = az.run('echo fail')

    assert output.success is False
    assert sp_run.call_count == 1


def test_run_retries_zero_no_retry_on_failure(_quiet_console: None) -> None:
    """With retries=0, subprocess.run is called only once."""
    failed = SimpleNamespace(stdout='', stderr='error', returncode=1)

    with (
        patch.object(az, 'is_debug_enabled', return_value=False),
        patch.object(az.subprocess, 'run', return_value=failed) as sp_run,
    ):
        output = az.run('echo fail', retries=0)

    assert output.success is False
    assert sp_run.call_count == 1


def test_run_retries_custom_value(_quiet_console: None) -> None:
    """With retries=3, subprocess.run is called four times on persistent failure."""
    failed = SimpleNamespace(stdout='', stderr='error', returncode=1)

    with (
        patch.object(az, 'is_debug_enabled', return_value=False),
        patch.object(az.subprocess, 'run', return_value=failed) as sp_run,
        patch.object(az, 'print_warning'),
    ):
        output = az.run('echo fail', retries=3, retry_policy = 'always')

    assert output.success is False
    assert sp_run.call_count == 4


def test_run_retry_succeeds_on_second_attempt(_quiet_console: None) -> None:
    """When the first attempt fails and the retry succeeds, run() returns success."""
    failed = SimpleNamespace(stdout='', stderr='ERROR: (ServiceUnavailable) Try again later', returncode=1)
    succeeded = SimpleNamespace(stdout='ok', stderr='', returncode=0)

    with (
        patch.object(az, 'is_debug_enabled', return_value=False),
        patch.object(az.subprocess, 'run', side_effect=[failed, succeeded]) as sp_run,
        patch.object(az, 'print_warning'),
    ):
        output = az.run('echo hello')

    assert output.success is True
    assert output.text == 'ok'
    assert sp_run.call_count == 2


def test_run_no_retry_on_success(_quiet_console: None) -> None:
    """When the first attempt succeeds, no retry is attempted."""
    completed = SimpleNamespace(stdout='ok', stderr='', returncode=0)

    with (
        patch.object(az, 'is_debug_enabled', return_value=False),
        patch.object(az.subprocess, 'run', return_value=completed) as sp_run,
    ):
        output = az.run('echo hello', retries=3)

    assert output.success is True
    assert sp_run.call_count == 1


def test_run_retry_after_timeout_succeeds(_quiet_console: None) -> None:
    """A timeout on the first attempt followed by success on retry."""
    succeeded = SimpleNamespace(stdout='ok', stderr='', returncode=0)

    with (
        patch.object(az, 'is_debug_enabled', return_value=False),
        patch.object(az.subprocess, 'run', side_effect=[subprocess.TimeoutExpired('cmd', 10), succeeded]) as sp_run,
        patch.object(az, 'print_warning'),
    ):
        output = az.run('echo hello', timeout=10, retry_policy = 'always')

    assert output.success is True
    assert output.text == 'ok'
    assert sp_run.call_count == 2


def test_run_retry_prints_warning_on_failure(_quiet_console: None) -> None:
    """A warning is printed between retry attempts."""
    failed = SimpleNamespace(stdout='', stderr='error', returncode=1)

    with (
        patch.object(az, 'is_debug_enabled', return_value=False),
        patch.object(az.subprocess, 'run', return_value=failed),
        patch.object(az, 'print_warning') as mock_warn,
    ):
        az.run('echo fail', retries=2, retry_policy = 'always')

    assert mock_warn.call_count == 2
    assert 'attempt 1/3' in mock_warn.call_args_list[0].args[0]
    assert 'attempt 2/3' in mock_warn.call_args_list[1].args[0]


def test_run_negative_retries_treated_as_zero(_quiet_console: None) -> None:
    """Negative retries value is clamped to zero (single attempt)."""
    failed = SimpleNamespace(stdout='', stderr='error', returncode=1)

    with (
        patch.object(az, 'is_debug_enabled', return_value=False),
        patch.object(az.subprocess, 'run', return_value=failed) as sp_run,
    ):
        output = az.run('echo fail', retries=-5)

    assert output.success is False
    assert sp_run.call_count == 1


@pytest.mark.parametrize('returncode', [0, 7])
def test_command_result_retains_streams_exit_code_and_attempts(monkeypatch, _quiet_console, returncode):
    completed = SimpleNamespace(stdout='{"value": 42}', stderr='diagnostic', returncode=returncode)
    monkeypatch.setattr(az.subprocess, 'run', Mock(return_value = completed))
    monkeypatch.setattr(az, 'is_debug_enabled', lambda: False)
    output = az.run(['program', 'argument'])

    assert output.success is (returncode == 0)
    assert output.returncode == returncode
    assert output.stdout == '{"value": 42}'
    assert output.stderr == 'diagnostic'
    assert output.attempts == 1
    assert output.elapsed_seconds >= 0
    assert not output.timed_out
    assert output.execution_error is None
    assert output.text == ('{"value": 42}' if returncode == 0 else '{"value": 42}\ndiagnostic')
    assert output.json_data == {'value': 42}
    assert az.subprocess.run.call_args.kwargs['shell'] is False


def test_manually_constructed_output_retains_legacy_contract():
    output = az.Output(True, '{"name": {"value": "demo"}}')

    assert output.get('name', suppress_logging = True) == 'demo'
    assert output.stdout == output.stderr == ''
    assert output.returncode is None
    assert not output.timed_out
    assert output.attempts == 0
    assert output.elapsed_seconds == 0
    assert output.execution_error is None


def test_successful_retry_reports_final_streams_and_total_elapsed_time(monkeypatch, _quiet_console):
    monkeypatch.setattr(az.time, 'monotonic', Mock(side_effect = [10.0, 10.1, 15.2]))
    process = Mock(side_effect = [
        SimpleNamespace(stdout='partial', stderr='HTTP 503 Unavailable', returncode=1),
        SimpleNamespace(stdout='{}', stderr='', returncode=0),
    ])
    monkeypatch.setattr(az.subprocess, 'run', process)

    output = az.run(['program'])

    assert output.success
    assert output.attempts == 2
    assert output.elapsed_seconds == pytest.approx(5.2)
    assert output.returncode == 0
    assert output.stdout == '{}'
    assert output.stderr == ''
    assert output.execution_error is None
    assert not output.timed_out


def test_argument_execution_preserves_shell_metacharacters_without_side_effects(tmp_path):
    """Exercise the real subprocess boundary, not a mock proxy for quoting."""
    marker = tmp_path / 'should-not-exist'
    arguments = [
        'two words', '"quotes"', "'apostrophes'", 'a&b|c>d<e', '%PATH%', '$HOME',
        f'& echo injected > "{marker}"', 'trailing\\', '', 'caf\u00e9',
    ]
    output = az.run([sys.executable, '-c', 'import json,sys; print(json.dumps(sys.argv[1:]))', *arguments])

    assert output.success
    assert output.returncode == 0
    assert output.json_data == arguments
    assert not marker.exists()


@pytest.mark.parametrize('platform', ['linux', 'darwin'])
def test_non_windows_native_arguments_are_preserved(monkeypatch: pytest.MonkeyPatch, platform: str) -> None:
    """Non-Azure commands bypass Windows launcher resolution on Linux and macOS."""
    monkeypatch.setattr(az.sys, 'platform', platform)
    which = Mock()
    monkeypatch.setattr(az.shutil, 'which', which)
    arguments = ['program', 'two words', 'a&b|c>d<e']

    resolved, environment = az._resolve_command_arguments(arguments)

    assert resolved == arguments
    assert environment is None
    which.assert_not_called()


@pytest.mark.parametrize('platform, extension', [('win32', '.exe'), ('linux', ''), ('darwin', '')])
def test_azure_argument_execution_resolves_native_launcher_and_locks(monkeypatch, _quiet_console, tmp_path, platform, extension):
    launcher = str(tmp_path / f'az{extension}')
    monkeypatch.setattr(az.sys, 'platform', platform)
    monkeypatch.setattr(az.shutil, 'which', lambda name: launcher)
    monkeypatch.setattr(az, 'is_debug_enabled', lambda: True)
    lock = _FakeLock()
    monkeypatch.setattr(az, '_AZ_CLI_LOCK', lock)
    process = Mock(return_value = SimpleNamespace(stdout='[]', stderr='debug', returncode=0))
    monkeypatch.setattr(az.subprocess, 'run', process)
    arguments = ['az', 'group', 'list', '--query', "[?name == 'a|b'].name"]

    output = az.run(arguments)

    assert output.success
    assert arguments[-1] == "[?name == 'a|b'].name"
    assert process.call_args.args[0] == [launcher, *arguments[1:], '--debug']
    assert process.call_args.kwargs['shell'] is False
    assert lock.entered == lock.exited == 1
    assert process.call_args.kwargs['env'] is None


@pytest.mark.parametrize('extension', ['.cmd', '.bat'])
def test_windows_azure_batch_launcher_uses_bundled_python_without_shell(monkeypatch, _quiet_console, tmp_path, extension):
    install = tmp_path / 'CLI with spaces'
    (install / 'wbin').mkdir(parents = True)
    python = install / 'python.exe'
    python.touch()
    launcher = str(install / 'wbin' / f'az{extension}')
    monkeypatch.setattr(az.sys, 'platform', 'win32')
    monkeypatch.setattr(az.shutil, 'which', lambda name: launcher)
    monkeypatch.setattr(az, 'is_debug_enabled', lambda: False)
    process = Mock(return_value = SimpleNamespace(stdout='{}', stderr='', returncode=0))
    monkeypatch.setattr(az.subprocess, 'run', process)
    arguments = ['az', 'group', 'show', '--name', 'value & echo not-a-command']

    assert az.run(arguments).success

    assert process.call_args.args[0] == [str(python), '-IBm', 'azure.cli', *arguments[1:]]
    assert process.call_args.kwargs['shell'] is False
    assert process.call_args.kwargs['env']['AZ_INSTALLER'] == 'MSI'


@pytest.mark.parametrize('extension', ['.cmd', '.bat'])
def test_other_windows_batch_launchers_cannot_silently_invoke_a_shell(monkeypatch, _quiet_console, tmp_path, extension):
    monkeypatch.setattr(az.sys, 'platform', 'win32')
    monkeypatch.setattr(az.shutil, 'which', lambda name: str(tmp_path / f'custom{extension}'))
    process = Mock()
    monkeypatch.setattr(az.subprocess, 'run', process)

    output = az.run(['custom', 'a&b'])

    assert not output.success
    assert 'native executable' in output.execution_error
    process.assert_not_called()


@pytest.mark.parametrize('launcher_found', [True, False])
def test_windows_native_argument_execution_preserves_arguments(monkeypatch: pytest.MonkeyPatch, _quiet_console: None, tmp_path, launcher_found: bool) -> None:
    """Native commands remain shell-free whether PATH lookup succeeds or not."""
    monkeypatch.setattr(az.sys, 'platform', 'win32')
    launcher = str(tmp_path / 'Tools with spaces' / 'custom.EXE') if launcher_found else None
    which = Mock(return_value = launcher)
    monkeypatch.setattr(az.shutil, 'which', which)
    process = Mock(return_value = SimpleNamespace(stdout = '{}', stderr = '', returncode = 0))
    monkeypatch.setattr(az.subprocess, 'run', process)
    arguments = ['custom', 'two words', 'a&b|c>d<e', '%PATH%', '']

    output = az.run(arguments)

    assert output.success
    assert output.execution_error is None
    which.assert_called_once_with('custom')
    process.assert_called_once()
    assert process.call_args.args[0] == arguments
    assert process.call_args.kwargs['shell'] is False
    assert process.call_args.kwargs['env'] is None


@pytest.mark.parametrize('missing_launcher', [True, False])
def test_azure_launcher_failures_are_explicit_and_not_retried(monkeypatch, _quiet_console, tmp_path, missing_launcher):
    monkeypatch.setattr(az.sys, 'platform', 'win32')
    monkeypatch.setattr(az.shutil, 'which', lambda name: None if missing_launcher else str(tmp_path / 'wbin' / 'az.cmd'))
    process = Mock()
    monkeypatch.setattr(az.subprocess, 'run', process)
    output = az.run(['az', 'group', 'list'], retries = 3)

    assert not output.success
    assert output.returncode is None
    assert output.execution_error
    assert output.attempts == 1
    assert not output.timed_out
    assert ('not found on PATH' if missing_launcher else 'no bundled Python') in output.text
    process.assert_not_called()


@pytest.mark.parametrize('as_bytes', [False, True])
def test_timeout_preserves_partial_streams_and_never_retries_by_default(monkeypatch, _quiet_console, as_bytes):
    stdout = b'partial' if as_bytes else 'partial'
    stderr = b'diagnostic' if as_bytes else 'diagnostic'
    process = Mock(side_effect = subprocess.TimeoutExpired('program', 10, output = stdout, stderr = stderr))
    monkeypatch.setattr(az.subprocess, 'run', process)

    output = az.run(['program'], timeout = 10, retries = 3)

    assert not output.success
    assert output.timed_out
    assert output.stdout == 'partial'
    assert output.stderr == 'diagnostic'
    assert output.returncode is None
    assert output.execution_error == 'Command timed out after 10 seconds'
    assert output.text == 'partial\ndiagnostic\nCommand timed out after 10 seconds'
    assert output.attempts == 1
    process.assert_called_once()


@pytest.mark.parametrize(
    'message, transient',
    [
        ('{"error": {"code": "TooManyRequests", "message": "Wait"}}', True),
        ('{"code": "ServiceUnavailable"}', True),
        ('{"code": 503}', True),
        ('ERROR: (ServerBusy) Try later', True),
        ('HTTP/1.1 429 Too many requests', True),
        ('status code: 502 Bad Gateway', True),
        ('ERROR: HTTP 504 Gateway timeout', True),
        ('{"error": {"code": "AuthorizationFailed"}}', False),
        ('{"error": {"code": "InvalidTemplate"}}', False),
        ('{"error": "Service is unavailable"}', False),
        ('ERROR: resource does not exist', False),
        ('resource-503 not found', False),
        ('{bad json', False),
        ('unknown error', False),
    ],
)
def test_default_retries_only_recognized_transient_failures(monkeypatch, _quiet_console, message, transient):
    failed = SimpleNamespace(stdout='', stderr=message, returncode=1)
    succeeded = SimpleNamespace(stdout='{}', stderr='', returncode=0)
    process = Mock(side_effect = [failed, succeeded])
    monkeypatch.setattr(az.subprocess, 'run', process)

    output = az.run(['program'])

    assert output.success is transient
    assert output.attempts == (2 if transient else 1)
    assert process.call_count == output.attempts


def test_never_policy_disables_transient_retries(monkeypatch, _quiet_console):
    process = Mock(return_value = SimpleNamespace(stdout='', stderr='HTTP 503 Unavailable', returncode=1))
    monkeypatch.setattr(az.subprocess, 'run', process)

    output = az.run(['program'], retries = 3, retry_policy = 'never')

    assert not output.success
    assert output.attempts == 1
    process.assert_called_once()


@pytest.mark.parametrize('invalid_command', [[], ['program', 3]])
def test_argument_validation_happens_before_execution(monkeypatch, invalid_command):
    process = Mock()
    monkeypatch.setattr(az.subprocess, 'run', process)
    with pytest.raises(ValueError, match = 'non-empty sequence of strings'):
        az.run(invalid_command)
    process.assert_not_called()


def test_invalid_retry_policy_rejected_before_execution(monkeypatch):
    process = Mock()
    monkeypatch.setattr(az.subprocess, 'run', process)
    with pytest.raises(ValueError, match = 'Unknown retry policy'):
        az.run(['program'], retry_policy = 'invalid')
    process.assert_not_called()


def test_programming_errors_are_not_hidden_or_retried(monkeypatch, _quiet_console):
    process = Mock(side_effect = TypeError('Programming error'))
    monkeypatch.setattr(az.subprocess, 'run', process)
    with pytest.raises(TypeError, match = 'Programming error'):
        az.run(['program'])
    process.assert_called_once()


def test_sensitive_arguments_and_streams_never_reach_logging(monkeypatch, _quiet_console):
    secret = 'test-sensitive-value'
    monkeypatch.setattr(az, 'is_debug_enabled', lambda: True)
    process = Mock(return_value = SimpleNamespace(stdout=secret, stderr=secret, returncode=1))
    monkeypatch.setattr(az.subprocess, 'run', process)
    output = az.run(['program', '--secret', secret], sensitive_output = True, error_message = 'Failed')

    assert output.stdout == output.stderr == secret
    assert process.call_args.args[0] == ['program', '--secret', secret]
    assert '--debug' not in process.call_args.args[0]
    assert az.print_command.call_args.args == ('Command arguments withheld (sensitive operation).',)
    assert az.print_error.call_args.args[1] == 'Command failed; sensitive output was withheld.'
    az.print_plain.assert_not_called()


def test_argument_deployment_failure_keeps_context_and_diagnostics(monkeypatch, _quiet_console):
    monkeypatch.setattr(az.shutil, 'which', lambda name: sys.executable)
    process = Mock(return_value = SimpleNamespace(stdout='', stderr='ERROR: InvalidTemplate', returncode=1))
    monkeypatch.setattr(az.subprocess, 'run', process)
    fetch = Mock(return_value = [{'properties': {'provisioningState': 'Failed', 'statusMessage': 'Bad template'}}])
    monkeypatch.setattr(az, '_fetch_group_deployment_operations', fetch)

    output = az.run(['az', 'deployment', 'group', 'create', '--name', 'demo & name', '-g', 'rg with spaces'], error_message = 'Failed')

    assert not output.success
    fetch.assert_called_once_with('demo & name', 'rg with spaces')
    assert 'Bad template' in az.print_error.call_args.args[1]
