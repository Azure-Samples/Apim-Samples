"""
This module deploys the AG_APIM_VNET infrastructure (App Gateway in front of APIM in External VNet mode).
"""

import sys
import argparse
from apimtypes import APIM_SKU, INFRASTRUCTURE
from infrastructures import AgApimVnetInfrastructure
import utils


def create_infrastructure(location: str, index: int, apim_sku: APIM_SKU) -> None:
    try:
        infrastructure_exists = utils.does_resource_group_exist(utils.get_infra_rg_name(INFRASTRUCTURE.AG_APIM_VNET, index))
        result = AgApimVnetInfrastructure(location, index, apim_sku).deploy_infrastructure(infrastructure_exists)
        sys.exit(0 if result.success else 1)
    except Exception as e:
        print(f'\n💥 Error: {str(e)}')
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description = 'Create AG_APIM_VNET infrastructure')
    parser.add_argument('--location', default = 'eastus2', help = 'Azure region (default: eastus2)')
    parser.add_argument('--index', type = int, help = 'Infrastructure index')
    parser.add_argument('--sku', choices = ['Developer', 'Basicv2', 'Standardv2', 'Premiumv2'], default = 'Developer', help = 'APIM SKU (default: Developer)')
    args = parser.parse_args()

    try:
        apim_sku = APIM_SKU(args.sku)
    except ValueError:
        print(f"Error: Invalid SKU '{args.sku}'. Valid options are: {', '.join([sku.value for sku in APIM_SKU])}")
        sys.exit(1)

    create_infrastructure(args.location, args.index, apim_sku)


if __name__ == '__main__':
    main()
