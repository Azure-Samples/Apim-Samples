"""
This module provides a reusable way to create Azure Front Door with API Management (Private Endpoint) infrastructure that can be called from notebooks or other scripts.
"""

import sys
import argparse
from apimtypes import APIM_SKU, API, GET_APIOperation, BACKEND_XML_POLICY_PATH
from infrastructures import AfdApimAcaInfrastructure
import utils


    print(f'\n🚀 Creating AFD-APIM-PE infrastructure...\n')
    print(f'   Infrastructure : {deployment.value}')
    print(f'   Index          : {index}')
    print(f'   Resource group : {rg_name}')
    print(f'   Location       : {rg_location}')
    print(f'   APIM SKU       : {apim_sku.value}\n')
    
    # 2) Set up the policy fragments
    if custom_policy_fragments is None:
        pfs: List[PolicyFragment] = [
            PolicyFragment('Api-Id', utils.read_policy_xml(utils.determine_shared_policy_path('pf-api-id.xml')), 'Extracts a specific API identifier for tracing.'),
            PolicyFragment('AuthZ-Match-All', utils.read_policy_xml(utils.determine_shared_policy_path('pf-authz-match-all.xml')), 'Authorizes if all of the specified roles match the JWT role claims.'),
            PolicyFragment('AuthZ-Match-Any', utils.read_policy_xml(utils.determine_shared_policy_path('pf-authz-match-any.xml')), 'Authorizes if any of the specified roles match the JWT role claims.'),
            PolicyFragment('Http-Response-200', utils.read_policy_xml(utils.determine_shared_policy_path('pf-http-response-200.xml')), 'Returns a 200 OK response for the current HTTP method.'),
            PolicyFragment('Product-Match-Any', utils.read_policy_xml(utils.determine_shared_policy_path('pf-product-match-any.xml')), 'Proceeds if any of the specified products match the context product name.'),
            PolicyFragment('Remove-Request-Headers', utils.read_policy_xml(utils.determine_shared_policy_path('pf-remove-request-headers.xml')), 'Removes request headers from the incoming request.')
        ]
    else:
        pfs = custom_policy_fragments
    
    # 3) Define the APIs
    if custom_apis is None:
        # Default Hello World API
        pol_hello_world = utils.read_policy_xml(HELLO_WORLD_XML_POLICY_PATH)
        api_hwroot_get = GET_APIOperation('This is a GET for API 1', pol_hello_world)
        api_hwroot = API('hello-world', 'Hello World', '', 'This is the root API for Hello World', operations = [api_hwroot_get])
        apis: List[API] = [api_hwroot]
        
        # If Container Apps is enabled, create the ACA APIs in APIM
        if use_aca:
            pol_backend          = utils.read_policy_xml(BACKEND_XML_POLICY_PATH)
            pol_aca_backend_1    = pol_backend.format(backend_id = 'aca-backend-1')
            pol_aca_backend_2    = pol_backend.format(backend_id = 'aca-backend-2')
            pol_aca_backend_pool = pol_backend.format(backend_id = 'aca-backend-pool')

            # API 1: Hello World (ACA Backend 1)
            api_hwaca_1_get = GET_APIOperation('This is a GET for Hello World on ACA Backend 1')
            api_hwaca_1     = API('hello-world-aca-1', 'Hello World (ACA 1)', '/aca-1', 'This is the ACA API for Backend 1', pol_aca_backend_1, [api_hwaca_1_get])

            # API 2: Hello World (ACA Backend 2)
            api_hwaca_2_get = GET_APIOperation('This is a GET for Hello World on ACA Backend 2')
            api_hwaca_2     = API('hello-world-aca-2', 'Hello World (ACA 2)', '/aca-2', 'This is the ACA API for Backend 2', pol_aca_backend_2, [api_hwaca_2_get])

            # API 3: Hello World (ACA Backend Pool)
            api_hwaca_pool_get = GET_APIOperation('This is a GET for Hello World on ACA Backend Pool')
            api_hwaca_pool     = API('hello-world-aca-pool', 'Hello World (ACA Pool)', '/aca-pool', 'This is the ACA API for Backend Pool', pol_aca_backend_pool, [api_hwaca_pool_get])

            # Add ACA APIs to the existing apis array
            apis += [api_hwaca_1, api_hwaca_2, api_hwaca_pool]
    else:
        apis = custom_apis
    
    # 4) Define the Bicep parameters with serialized APIs
    bicep_parameters = {
        'apimSku'          : {'value': apim_sku.value},
        'apis'             : {'value': [api.to_dict() for api in apis]},
        'policyFragments'  : {'value': [pf.to_dict() for pf in pfs]},
        'apimPublicAccess' : {'value': apim_network_mode in [APIMNetworkMode.PUBLIC, APIMNetworkMode.EXTERNAL_VNET]},
        'useACA'           : {'value': use_aca}
    }
    
    # 5) Change to the infrastructure directory to ensure bicep files are found
    original_cwd = os.getcwd()
    infra_dir = Path(__file__).parent
    
    try:
        # Create custom APIs for AFD-APIM-PE with optional Container Apps backends
        custom_apis = _create_afd_specific_apis(not no_aca)
        
        infra = AfdApimAcaInfrastructure(location, index, apim_sku, infra_apis = custom_apis)
        result = infra.deploy_infrastructure()
        
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
