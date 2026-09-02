"""Tests for the interactive infrastructure cleanup menu."""

# APIM Samples imports
import cleanup_infrastructures as cleanup_menu
from apimtypes import INFRASTRUCTURE
from console import BOLD_G, DIM, RESET


def _deployment(infrastructure: INFRASTRUCTURE, index: int) -> cleanup_menu.InfrastructureDeployment:
    return cleanup_menu.InfrastructureDeployment(infrastructure, index, f'apim-infra-{infrastructure.value}-{index}')


def test_gather_deployments(monkeypatch):
    """Gather tagged deployments across all five infrastructure types."""

    monkeypatch.setattr(
        cleanup_menu.az,
        'find_infrastructure_instances',
        lambda infrastructure: [(infrastructure, 2)] if infrastructure == INFRASTRUCTURE.APIM_ACA else [],
    )
    monkeypatch.setattr(cleanup_menu.az, 'get_infra_rg_name', lambda infrastructure, index: f'rg-{infrastructure.value}-{index}')

    assert cleanup_menu.gather_deployments() == [cleanup_menu.InfrastructureDeployment(INFRASTRUCTURE.APIM_ACA, 2, 'rg-apim-aca-2')]


def test_run_cleanup_menu_selects_one_and_tracks_pending(monkeypatch):
    """Delete one instance and retain its pending status until exit."""

    deployments = [_deployment(INFRASTRUCTURE.APIM_ACA, 1), _deployment(INFRASTRUCTURE.APIM_ACA, 2)]
    answers = iter(['2', '1', '0'])
    output: list[str] = []
    cleanup_calls: list[tuple[INFRASTRUCTURE, int | list[int] | None]] = []
    monkeypatch.setattr(cleanup_menu, 'gather_deployments', lambda: deployments)

    pending = cleanup_menu.run_cleanup_menu(
        read=lambda prompt: next(answers),
        write=output.append,
        cleanup=lambda infrastructure, index: cleanup_calls.append((infrastructure, index)),
    )

    assert cleanup_calls == [(INFRASTRUCTURE.APIM_ACA, 1)]
    assert pending == [deployments[0]]
    assert any('[PENDING] apim-infra-apim-aca-1' in line for line in output)
    assert output.index('') + 1 == output.index('  0) Return to the Developer CLI')
    submenu_start = output.index('Deployed apim-aca infrastructures')
    assert output[submenu_start - 1] == ''
    assert output[submenu_start + 2 : submenu_start + 8] == [
        '  a) Delete all listed infrastructures',
        '',
        '  1) apim-infra-apim-aca-1',
        '  2) apim-infra-apim-aca-2',
        '',
        '  0) Return to the list of infrastructure types',
    ]


def test_run_cleanup_menu_queries_and_emphasizes_deployed_types(monkeypatch):
    """Report the query and emphasize only selectable infrastructure types."""

    deployment = _deployment(INFRASTRUCTURE.SIMPLE_APIM, 1)
    output: list[str] = []
    monkeypatch.setattr(cleanup_menu, 'gather_deployments', lambda: [deployment])

    cleanup_menu.run_cleanup_menu(read=lambda prompt: '0', write=output.append)

    assert output[0] == '\nQuerying deployed infrastructures...'
    assert f'{BOLD_G}  1) simple-apim   (1 deployed){RESET}' in output
    assert f'{DIM}  2) apim-aca      (0 deployed){RESET}' in output

    menu_rows = [line for line in output if 'deployed)' in line]
    visible_rows = [line.removeprefix(BOLD_G).removeprefix(DIM) for line in menu_rows]
    assert len({line.index('(') for line in visible_rows}) == 1


def test_run_cleanup_menu_deletes_all_and_returns_to_type_list(monkeypatch):
    """Delete all instances in a subset and allow navigation between type lists."""

    deployments = [_deployment(INFRASTRUCTURE.SIMPLE_APIM, 1), _deployment(INFRASTRUCTURE.SIMPLE_APIM, 2)]
    answers = iter(['1', '0', '1', 'a', '0'])
    cleanup_calls: list[tuple[INFRASTRUCTURE, int | list[int] | None]] = []
    monkeypatch.setattr(cleanup_menu, 'gather_deployments', lambda: deployments)

    pending = cleanup_menu.run_cleanup_menu(
        read=lambda prompt: next(answers),
        write=lambda message: None,
        cleanup=lambda infrastructure, index: cleanup_calls.append((infrastructure, index)),
    )

    assert cleanup_calls == [(INFRASTRUCTURE.SIMPLE_APIM, [1, 2])]
    assert pending == deployments


def test_run_cleanup_menu_splits_non_indexed_and_indexed_deployments(monkeypatch):
    """Delete non-indexed and indexed instances without passing None in a list."""

    deployments = [
        cleanup_menu.InfrastructureDeployment(INFRASTRUCTURE.SIMPLE_APIM, None, 'apim-infra-simple-apim'),
        _deployment(INFRASTRUCTURE.SIMPLE_APIM, 1),
    ]
    answers = iter(['1', 'a', '0'])
    cleanup_calls: list[tuple[INFRASTRUCTURE, int | list[int] | None]] = []
    monkeypatch.setattr(cleanup_menu, 'gather_deployments', lambda: deployments)

    pending = cleanup_menu.run_cleanup_menu(
        read=lambda prompt: next(answers),
        write=lambda message: None,
        cleanup=lambda infrastructure, index: cleanup_calls.append((infrastructure, index)),
    )

    assert cleanup_calls == [
        (INFRASTRUCTURE.SIMPLE_APIM, None),
        (INFRASTRUCTURE.SIMPLE_APIM, 1),
    ]
    assert pending == deployments


def test_run_cleanup_menu_deletes_non_indexed_deployment(monkeypatch):
    """Delete a legacy deployment that has no index."""

    deployment = cleanup_menu.InfrastructureDeployment(INFRASTRUCTURE.SIMPLE_APIM, None, 'apim-infra-simple-apim')
    answers = iter(['1', '1', '0'])
    cleanup_calls: list[tuple[INFRASTRUCTURE, int | list[int] | None]] = []
    monkeypatch.setattr(cleanup_menu, 'gather_deployments', lambda: [deployment])

    pending = cleanup_menu.run_cleanup_menu(
        read=lambda prompt: next(answers),
        write=lambda message: None,
        cleanup=lambda infrastructure, index: cleanup_calls.append((infrastructure, index)),
    )

    assert cleanup_calls == [(INFRASTRUCTURE.SIMPLE_APIM, None)]
    assert pending == [deployment]


def test_run_cleanup_menu_handles_empty_and_invalid_choices(monkeypatch):
    """Handle no deployments and reject unavailable or malformed selections."""

    output: list[str] = []
    monkeypatch.setattr(cleanup_menu, 'gather_deployments', lambda: [])
    assert not cleanup_menu.run_cleanup_menu(write=output.append)
    assert any('No deployed infrastructures' in line for line in output)

    deployment = _deployment(INFRASTRUCTURE.SIMPLE_APIM, 1)
    answers = iter(['2', 'x', '1', 'x', '0', '0'])
    output.clear()
    monkeypatch.setattr(cleanup_menu, 'gather_deployments', lambda: [deployment])

    pending = cleanup_menu.run_cleanup_menu(read=lambda prompt: next(answers), write=output.append)

    assert not pending
    assert sum('Invalid selection' in line for line in output) == 2
    assert any('No selectable deployments' in line for line in output)


def test_main_runs_cleanup_menu(monkeypatch):
    """Run the cleanup menu from the script entry function."""

    cleanup_calls = 0

    def run_cleanup_menu():
        nonlocal cleanup_calls
        cleanup_calls += 1

    monkeypatch.setattr(cleanup_menu, 'run_cleanup_menu', run_cleanup_menu)

    assert cleanup_menu.main() == 0
    assert cleanup_calls == 1
