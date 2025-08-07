"""
This module provides a reusable way to create Simple APIM infrastructure that can be called from notebooks or other scripts.
"""

import sys
import argparse
from apimtypes import APIM_SKU
from infrastructures import SimpleApimInfrastructure


    print(f'\n🚀 Creating Simple APIM infrastructure...\n')
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
    else:
        apis = custom_apis
    
    # 4) Define the Bicep parameters with serialized APIs
    # Define the Bicep parameters with serialized APIs
    bicep_parameters = {
        'apimSku'         : {'value': apim_sku.value},
        'apis'            : {'value': [api.to_dict() for api in apis]},
        'policyFragments' : {'value': [pf.to_dict() for pf in pfs]}
    }
    
    # Change to the infrastructure directory to ensure bicep files are found
    original_cwd = os.getcwd()
    infra_dir = Path(__file__).parent
    
    try:
        result = SimpleApimInfrastructure(location, index, apim_sku).deploy_infrastructure()
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