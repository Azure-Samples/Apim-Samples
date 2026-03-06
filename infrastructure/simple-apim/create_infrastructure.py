"""
This module provides a reusable way to create Simple APIM infrastructure that can be called from notebooks or other scripts.
"""

import argparse
import sys

# APIM Samples imports
import azure_resources as az
from apimtypes import APIM_SKU, INFRASTRUCTURE, Region
from console import print_plain
from infrastructures import SimpleApimInfrastructure


def create_infrastructure(location: str, index: int, apim_sku: APIM_SKU, rg_exists: bool | None = None) -> None:
    """Create the simple APIM infrastructure."""
    if rg_exists is None:
        infrastructure_exists = az.does_resource_group_exist(az.get_infra_rg_name(INFRASTRUCTURE.SIMPLE_APIM, index))
    else:
        infrastructure_exists = rg_exists

    result = SimpleApimInfrastructure(location, index, apim_sku, rg_exists=rg_exists).deploy_infrastructure(infrastructure_exists)
    raise SystemExit(0 if result.success else 1)


def main():
    """
    Main entry point for command-line usage.
    """

    parser = argparse.ArgumentParser(description='Create Simple APIM infrastructure')
    parser.add_argument('--location', default=Region.EAST_US_2, help=f'Azure region (default: {Region.EAST_US_2})')
    parser.add_argument('--index', type=int, help='Infrastructure index')
    parser.add_argument('--sku', choices=['Basicv2', 'Standardv2', 'Premiumv2'], default='Basicv2', help='APIM SKU (default: Basicv2)')
    parser.add_argument('--rg-exists', action=argparse.BooleanOptionalAction, default=None, help='Pre-checked resource group existence state')
    args = parser.parse_args()

    # Convert SKU string to enum using the enum's built-in functionality
    try:
        apim_sku = APIM_SKU(args.sku)
    except ValueError:
        print_plain(f"Error: Invalid SKU '{args.sku}'. Valid options are: {', '.join([sku.value for sku in APIM_SKU])}")
        sys.exit(1)

    create_infrastructure(args.location, args.index, apim_sku, rg_exists=args.rg_exists)


if __name__ == '__main__':  # pragma: no cover
    main()
