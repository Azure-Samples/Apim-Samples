"""
This module provides a reusable way to create Azure Front Door with API Management (Private Endpoint) infrastructure that can be called from notebooks or other scripts.
"""

import sys
import argparse
from apimtypes import APIM_SKU, API, GET_APIOperation, BACKEND_XML_POLICY_PATH
from infrastructures import AfdApimAcaInfrastructure
import utils


def create_infrastructure(location: str, index: int, apim_sku: APIM_SKU, no_aca: bool = False) -> None:
    try:
        # Check if infrastructure already exists to determine messaging
        infrastructure_exists = utils.does_resource_group_exist(utils.get_infra_rg_name(utils.INFRASTRUCTURE.AFD_APIM_PE, index))
        
        # Create custom APIs for AFD-APIM-PE with optional Container Apps backends
        custom_apis = _create_afd_specific_apis(not no_aca)
        
        infra = AfdApimAcaInfrastructure(location, index, apim_sku, infra_apis = custom_apis)
        result = infra.deploy_infrastructure(infrastructure_exists)
        
        sys.exit(0 if result.success else 1)
            
    except Exception as e:
        print(f'\n💥 Error: {str(e)}')
        sys.exit(1)


def _create_afd_specific_apis(use_aca: bool = True) -> list[API]:
    """
    Create AFD-APIM-PE specific APIs with optional Container Apps backends.
    
    Args:
        use_aca (bool): Whether to include Azure Container Apps backends. Defaults to true.
        
    Returns:
        list[API]: List of AFD-specific APIs.
    """
    
    # If Container Apps is enabled, create the ACA APIs in APIM
    if use_aca:
        pol_backend          = utils.read_policy_xml(BACKEND_XML_POLICY_PATH)
        pol_aca_backend_1    = pol_backend.format(backend_id = 'aca-backend-1')
        pol_aca_backend_2    = pol_backend.format(backend_id = 'aca-backend-2')
        pol_aca_backend_pool = pol_backend.format(backend_id = 'aca-backend-pool')

        # API 1: Hello World (ACA Backend 1)
        api_hwaca_1_get      = GET_APIOperation('This is a GET for Hello World on ACA Backend 1')
        api_hwaca_1          = API('hello-world-aca-1', 'Hello World (ACA 1)', '/aca-1', 'This is the ACA API for Backend 1', pol_aca_backend_1, [api_hwaca_1_get])

        # API 2: Hello World (ACA Backend 2)
        api_hwaca_2_get      = GET_APIOperation('This is a GET for Hello World on ACA Backend 2')
        api_hwaca_2          = API('hello-world-aca-2', 'Hello World (ACA 2)', '/aca-2', 'This is the ACA API for Backend 2', pol_aca_backend_2, [api_hwaca_2_get])

        # API 3: Hello World (ACA Backend Pool)
        api_hwaca_pool_get   = GET_APIOperation('This is a GET for Hello World on ACA Backend Pool')
        api_hwaca_pool       = API('hello-world-aca-pool', 'Hello World (ACA Pool)', '/aca-pool', 'This is the ACA API for Backend Pool', pol_aca_backend_pool, [api_hwaca_pool_get])

        return [api_hwaca_1, api_hwaca_2, api_hwaca_pool]
    
    return []
def main():
    """
    Main entry point for command-line usage.
    """
        
    parser = argparse.ArgumentParser(description = 'Create AFD-APIM-PE infrastructure')
    parser.add_argument('--location', default = 'eastus2', help = 'Azure region (default: eastus2)')
    parser.add_argument('--index', type = int, help = 'Infrastructure index')
    parser.add_argument('--sku', choices = ['Standardv2', 'Premiumv2'], default = 'Standardv2', help = 'APIM SKU (default: Standardv2)')
    parser.add_argument('--no-aca', action = 'store_true', help = 'Disable Azure Container Apps')
    args = parser.parse_args()

    # Convert SKU string to enum using the enum's built-in functionality
    try:
        apim_sku = APIM_SKU(args.sku)
    except ValueError:
        print(f"Error: Invalid SKU '{args.sku}'. Valid options are: {', '.join([sku.value for sku in APIM_SKU])}")
        sys.exit(1)

    create_infrastructure(args.location, args.index, apim_sku, args.no_aca)

if __name__ == '__main__':
    main()
