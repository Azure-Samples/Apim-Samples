"""
This module provides a reusable way to create Simple APIM infrastructure that can be called from notebooks or other scripts.
"""

import sys
import argparse
from apimtypes import APIM_SKU
from infrastructures import SimpleApimInfrastructure
import utils


def create_infrastructure(location: str, index: int, apim_sku: APIM_SKU) -> None:    
    try:
        # Check if infrastructure already exists to determine messaging
        infrastructure_exists = utils.does_resource_group_exist(utils.get_infra_rg_name(utils.INFRASTRUCTURE.SIMPLE_APIM, index))
        
        result = SimpleApimInfrastructure(location, index, apim_sku).deploy_infrastructure(infrastructure_exists)
        sys.exit(0 if result.success else 1)
            
    except Exception as e:
        print(f'\n💥 Error: {str(e)}')
        sys.exit(1)

def main():
    """
    Main entry point for command-line usage.
    """
        
    parser = argparse.ArgumentParser(description = 'Create Simple APIM infrastructure')
    parser.add_argument('--location', default = 'eastus2', help = 'Azure region (default: eastus2)')
    parser.add_argument('--index', type = int, help = 'Infrastructure index')
    parser.add_argument('--sku', choices = ['Basicv2', 'Standardv2', 'Premiumv2'], default = 'Basicv2', help = 'APIM SKU (default: Basicv2)')    
    args = parser.parse_args()

    # Convert SKU string to enum using the enum's built-in functionality
    try:
        apim_sku = APIM_SKU(args.sku)
    except ValueError:
        print(f"Error: Invalid SKU '{args.sku}'. Valid options are: {', '.join([sku.value for sku in APIM_SKU])}")
        sys.exit(1)

    create_infrastructure(args.location, args.index, apim_sku)

if __name__ == '__main__':
    main()