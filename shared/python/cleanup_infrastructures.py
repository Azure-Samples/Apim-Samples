"""Interactively start cleanup for deployed APIM Samples infrastructures."""

from collections.abc import Callable
from dataclasses import dataclass

# APIM Samples imports
import azure_resources as az
import infrastructures
from apimtypes import INFRASTRUCTURE
from console import BOLD_G, DIM, RESET

InputReader = Callable[[str], str]
OutputWriter = Callable[[str], None]
CleanupRunner = Callable[[INFRASTRUCTURE, int | list[int | None] | None], None]
INFRASTRUCTURE_NAME_WIDTH = max(len(infrastructure.value) for infrastructure in INFRASTRUCTURE)


@dataclass(frozen=True)
class InfrastructureDeployment:
    """Identify one deployed infrastructure instance."""

    infrastructure: INFRASTRUCTURE
    index: int | None
    resource_group: str


def gather_deployments() -> list[InfrastructureDeployment]:
    """Return all tagged infrastructure deployments in display order."""

    deployments = [InfrastructureDeployment(infrastructure, index, az.get_infra_rg_name(infrastructure, index)) for infrastructure in INFRASTRUCTURE for _, index in az.find_infrastructure_instances(infrastructure)]

    return sorted(deployments, key=lambda deployment: (deployment.infrastructure.value, deployment.index or 0))


def _display_pending(pending: list[InfrastructureDeployment], write: OutputWriter) -> None:
    """Display cleanup operations started during this session."""

    if not pending:
        return

    write('\nPending deletion:')
    for deployment in pending:
        write(f'  [PENDING] {deployment.resource_group}')


def _select_infrastructure_type(
    deployments: list[InfrastructureDeployment],
    pending: list[InfrastructureDeployment],
    read: InputReader,
    write: OutputWriter,
) -> INFRASTRUCTURE | None:
    """Prompt for one infrastructure type, or return None to exit."""

    while True:
        available = [deployment for deployment in deployments if deployment not in pending]
        write('\nDeployed infrastructure types')
        write('-----------------------------')
        for number, infrastructure in enumerate(INFRASTRUCTURE, 1):
            count = sum(deployment.infrastructure == infrastructure for deployment in available)
            emphasis = BOLD_G if count else DIM
            write(f'{emphasis}  {number}) {infrastructure.value:<{INFRASTRUCTURE_NAME_WIDTH}} ({count} deployed){RESET}')
        write('')
        write('  0) Return to the Developer CLI')
        _display_pending(pending, write)

        choice = read('\nSelect an infrastructure type or return: ').strip()
        if choice == '0':
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(INFRASTRUCTURE):
            selected = list(INFRASTRUCTURE)[int(choice) - 1]
            if any(deployment.infrastructure == selected for deployment in available):
                return selected
            write('\nNo selectable deployments exist for that infrastructure type.')
            continue
        write('\nInvalid selection.')


def _select_deployments(
    infrastructure: INFRASTRUCTURE,
    deployments: list[InfrastructureDeployment],
    pending: list[InfrastructureDeployment],
    read: InputReader,
    write: OutputWriter,
) -> list[InfrastructureDeployment] | None:
    """Prompt for one or all deployments of an infrastructure type."""

    available = [deployment for deployment in deployments if deployment.infrastructure == infrastructure and deployment not in pending]
    write('')
    write(f'Deployed {infrastructure.value} infrastructures')
    write('-' * (len(infrastructure.value) + 25))
    write('  a) Delete all listed infrastructures')
    write('')
    for number, deployment in enumerate(available, 1):
        write(f'  {number}) {deployment.resource_group}')
    write('')
    write('  0) Return to the list of infrastructure types')
    _display_pending(pending, write)

    choice = read('\nSelect an infrastructure to delete: ').strip().lower()
    if choice == '0':
        return None
    if choice == 'a':
        return available
    if choice.isdigit() and 1 <= int(choice) <= len(available):
        return [available[int(choice) - 1]]

    write('\nInvalid selection.')
    return []


def run_cleanup_menu(
    read: InputReader = input,
    write: OutputWriter = print,
    cleanup: CleanupRunner = infrastructures.cleanup_infra_deployments,
) -> list[InfrastructureDeployment]:
    """Run the cleanup menu and return deployments marked pending."""

    write('\nQuerying deployed infrastructures...')
    deployments = gather_deployments()
    pending: list[InfrastructureDeployment] = []
    if not deployments:
        write('\nNo deployed infrastructures found with the infrastructure tag.')
        return pending

    while True:
        selected_type = _select_infrastructure_type(deployments, pending, read, write)
        if selected_type is None:
            return pending

        while True:
            selected_deployments = _select_deployments(selected_type, deployments, pending, read, write)
            if selected_deployments is None:
                break
            if not selected_deployments:
                continue

            for deployment in selected_deployments:
                pending.append(deployment)
                write(f'\n[PENDING] Starting deletion of {deployment.resource_group}')

            indexes = [deployment.index for deployment in selected_deployments]
            cleanup(selected_type, indexes if len(indexes) > 1 else indexes[0])
            break


def main() -> int:
    """Run the interactive cleanup menu."""

    run_cleanup_menu()
    return 0


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
