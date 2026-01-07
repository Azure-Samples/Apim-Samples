"""
List all deployed APIM infrastructures in the current Azure subscription.
Results are based on resource groups tagged with the standard 'infrastructure' tag
used by APIM Samples deployments.
"""

import argparse
from typing import Any

# APIM Samples imports
import azure_resources as az
from apimtypes import INFRASTRUCTURE


def _format_index(index: int | None) -> str:
    return str(index) if index is not None else 'N/A'


def _format_location(location: str | None) -> str:
    return location if location else 'Unknown'


def _sort_key(entry: dict[str, Any]) -> tuple[str, int]:
    index_value = entry.get('index')
    return entry.get('infrastructure', ''), index_value if index_value is not None else 0


def gather_infrastructures(include_location: bool = True) -> list[dict[str, str | int | None]]:
    """Collect deployed infrastructures by scanning for known infrastructure tags."""

    discovered: list[dict[str, str | int | None]] = []

    for infra in INFRASTRUCTURE:
        instances = az.find_infrastructure_instances(infra)
        if not instances:
            continue

        for infra_type, index in instances:
            rg_name = az.get_infra_rg_name(infra_type, index)
            location = az.get_resource_group_location(rg_name) if include_location else None

            discovered.append(
                {
                    'infrastructure': infra_type.value,
                    'index': index,
                    'resource_group': rg_name,
                    'location': location,
                }
            )

    discovered.sort(key=_sort_key)
    return discovered


def display_infrastructures(infrastructures: list[dict[str, str | int | None]], include_location: bool = True) -> None:
    """Render a simple table summarizing deployed infrastructures."""

    print('Deployed infrastructures')
    print('------------------------')

    if not infrastructures:
        print('\nNo deployed infrastructures found with the infrastructure tag.\n')
        return

    headers = ['#', 'Infrastructure', 'Index', 'Resource Group']
    if include_location:
        headers.append('Location')

    rows: list[list[str]] = []
    for idx, entry in enumerate(infrastructures, 1):
        row = [
            str(idx),
            entry.get('infrastructure', ''),
            _format_index(entry.get('index')),
            entry.get('resource_group', ''),
        ]

        if include_location:
            row.append(_format_location(entry.get('location')))

        rows.append(row)

    widths = [max(len(str(value)) for value in column) for column in zip(headers, *rows)]

    header_line = '  '.join(str(value).ljust(widths[i]) for i, value in enumerate(headers))
    separator_line = '  '.join('-' * width for width in widths)

    print('\n' + header_line)
    print(separator_line)

    # Index column (column 2) is right-aligned; others are left-aligned
    for row in rows:
        formatted_row = []
        for i, value in enumerate(row):
            if i == 2:  # Index column
                formatted_row.append(str(value).rjust(widths[i]))
            else:
                formatted_row.append(str(value).ljust(widths[i]))
        print('  '.join(formatted_row))

    infra_totals: dict[str, int] = {}
    for entry in infrastructures:
        infra_name = entry.get('infrastructure', '')
        infra_totals[infra_name] = infra_totals.get(infra_name, 0) + 1

    print('\nSummary:')
    print(f"  Resource groups found : {len(infrastructures)}")
    print(f"  Infrastructure types  : {len(infra_totals)}")
    print('\n')


def show_subscription() -> None:
    """Display the current Azure subscription information."""

    account_output = az.run('az account show -o json')

    print('Current subscription')
    print('---------------------')

    if account_output.success and account_output.json_data:
        name = account_output.json_data.get('name', 'Unknown')
        subscription_id = account_output.json_data.get('id', 'Unknown')

        print(f'Name : {name}')
        print(f'ID   : {subscription_id}\n')
    else:
        print('Unable to read subscription details. Ensure Azure CLI is logged in.\n')


def main() -> int:
    parser = argparse.ArgumentParser(
        description='List all deployed APIM infrastructures in the current Azure subscription'
    )
    parser.add_argument(
        '--no-location',
        action='store_true',
        help='Skip resource group location lookup for faster execution.',
    )

    args = parser.parse_args()
    include_location = not args.no_location

    print('\nListing infrastructures based on the "infrastructure" tag.\n')

    show_subscription()

    infrastructures = gather_infrastructures(include_location=include_location)
    display_infrastructures(infrastructures, include_location=include_location)

    return 0


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
