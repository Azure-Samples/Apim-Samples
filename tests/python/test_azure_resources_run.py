"""Focused tests for azure_resources.run behavior.

These tests validate the command-runner semantics (debug flag injection, stdout/stderr
handling, and Azure CLI locking) without requiring live Azure.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

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
    """Silence console facade functions so tests don't emit output."""

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
        raise RuntimeError('boom')

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
