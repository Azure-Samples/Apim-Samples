"""
This module provides a reusable way to create Simple APIM infrastructure that can be called from notebooks or other scripts.
"""

import sys
import argparse
from apimtypes import APIM_SKU
from infrastructures import SimpleApimInfrastructure

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
    
    try:
        infra = SimpleApimInfrastructure(args.location, args.index, apim_sku)
        result = infra.deploy_infrastructure()
        
        if result.success:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except Exception as e:
        print(f'\n💥 Error: {str(e)}')
        sys.exit(1)

if __name__ == '__main__':
    main()