"""
Infrastructure creation module for AFD-APIM-PE.

This module provides a reusable way to create Azure Front Door with API Management 
(Private Endpoint) infrastructure that can be called from notebooks or other scripts.
"""

import sys
import os
import argparse
from pathlib import Path
import utils
from apimtypes import *
import json

def _create_afd_apim_pe_infrastructure(
    rg_location: str = 'eastus2',
    index: int | None = None,
    apim_sku: APIM_SKU = APIM_SKU.STANDARDV2,
    use_aca: bool = True,
    custom_apis: list[API] | None = None,
    custom_policy_fragments: list[PolicyFragment] | None = None
) -> utils.Output:
    """
    Create AFD-APIM-PE infrastructure with the specified parameters.
    
    Args:
        rg_location (str): Azure region for deployment. Defaults to 'eastus2'.
        index (int | None): Index for the infrastructure. Defaults to None (no index).
        apim_sku (APIM_SKU): SKU for API Management. Defaults to STANDARDV2.
        use_aca (bool): Whether to include Azure Container Apps. Defaults to True.
        custom_apis (list[API] | None): Custom APIs to deploy. If None, uses default Hello World API.
        custom_policy_fragments (list[PolicyFragment] | None): Custom policy fragments. If None, uses defaults.
        
    Returns:
        utils.Output: The deployment result.
    """
    
    # 1) Setup deployment parameters
    deployment = INFRASTRUCTURE.AFD_APIM_PE
    rg_name = utils.get_infra_rg_name(deployment, index)
    rg_tags = utils.build_infrastructure_tags(deployment)
    apim_network_mode = APIMNetworkMode.EXTERNAL_VNET

    print(f'\n🚀 Creating AFD-APIM-PE infrastructure...')
    print(f'    Location       : {rg_location}')
    print(f'    Index          : {index}')
    print(f'    Infrastructure : {deployment.value}')
    print(f'    APIM SKU       : {apim_sku.value}')
    print(f'    Use ACA        : {use_aca}')
    print(f'    Resource Group : {rg_name}\n')
    
    # 2) Set up the policy fragments
    if custom_policy_fragments is None:
        pfs: List[PolicyFragment] = [
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
        os.chdir(infra_dir)
        print(f'📁 Changed working directory to: {infra_dir}')
        
        # 6) Create the resource group if it doesn't exist
        utils.create_resource_group(rg_name, rg_location, rg_tags)
        
        # 7) First deployment with public access enabled
        print('\n🚀 Phase 1: Creating infrastructure with public access enabled...')
        output = utils.create_bicep_deployment_group(rg_name, rg_location, deployment, bicep_parameters)
        
        if not output.success:
            print('❌ Phase 1 deployment failed!')
            return output
            
        # Extract service details for private link approval
        if output.json_data:
            apim_service_id = output.get('apimServiceId', 'APIM Service Id', suppress_logging = True)
            
            print('✅ Phase 1 deployment completed successfully!')
            
            # 8) Approve private link connections
            print('\n🔗 Approving Front Door private link connections...')
            _approve_private_link_connections(apim_service_id)
            
            # 9) Second deployment to disable public access
            print('\n🔒 Phase 2: Disabling APIM public access...')
            bicep_parameters['apimPublicAccess']['value'] = False
            
            output = utils.create_bicep_deployment_group(rg_name, rg_location, deployment, bicep_parameters)
            
            if output.success:
                print('\n✅ Infrastructure creation completed successfully!')
                if output.json_data:
                    apim_gateway_url = output.get('apimResourceGatewayURL', 'APIM API Gateway URL', suppress_logging = True)
                    afd_endpoint_url = output.get('fdeSecureUrl', 'Front Door Endpoint URL', suppress_logging = True)
                    apim_apis = output.getJson('apiOutputs', 'APIs', suppress_logging = True)
                    
                    print(f'\n📋 Infrastructure Details:')
                    print(f'   Resource Group     : {rg_name}')
                    print(f'   Location           : {rg_location}')
                    print(f'   APIM SKU           : {apim_sku.value}')
                    print(f'   Use ACA            : {use_aca}')
                    print(f'   Gateway URL        : {apim_gateway_url}')
                    print(f'   Front Door URL     : {afd_endpoint_url}')
                    print(f'   APIs Created       : {len(apim_apis)}')
                    
                    # Perform basic verification
                    _verify_infrastructure(rg_name, use_aca)
            else:
                print('❌ Phase 2 deployment failed!')
                
        return output
        
    finally:
        # Always restore the original working directory
        os.chdir(original_cwd)
        print(f'📁 Restored working directory to: {original_cwd}')

def _approve_private_link_connections(apim_service_id: str) -> None:
    """
    Approve pending private link connections for the APIM service.
    
    Args:
        apim_service_id (str): The resource ID of the APIM service.
    """
    
    # Get all pending private endpoint connections as JSON
    output = utils.run(f"az network private-endpoint-connection list --id {apim_service_id} --query \"[?contains(properties.privateLinkServiceConnectionState.status, 'Pending')]\' -o json', print_command_to_run = False)

    # Handle both a single object and a list of objects
    pending_connections = output.json_data if output.success and output.is_json else []

    if isinstance(pending_connections, dict):
        pending_connections = [pending_connections]

    total = len(pending_connections)
    print(f'Found {total} pending private link service connection(s).')

    if total > 0:
        for i, conn in enumerate(pending_connections, 1):
            conn_id = conn.get('id')
            conn_name = conn.get('name', '<unknown>')
            print(f'  {i}/{total}: Approving {conn_name}')

            approve_result = utils.run(
                f"az network private-endpoint-connection approve --id {conn_id} --description 'Approved'",
                f'Private Link Connection approved: {conn_name}',
                f'Failed to approve Private Link Connection: {conn_name}',
                print_command_to_run = False
            )

        print('✅ Private link approvals completed')
    else:
        print('No pending private link service connections found. Nothing to approve.')

def _verify_infrastructure(rg_name: str, use_aca: bool) -> bool:
    """
    Verify that the infrastructure was created successfully.
    
    Args:
        rg_name (str): Resource group name.
        use_aca (bool): Whether Container Apps were included.
        
    Returns:
        bool: True if verification passed, False otherwise.
    """
    
    print('\n🔍 Verifying infrastructure...')
    
    try:
        # Check if the resource group exists
        if not utils.does_resource_group_exist(rg_name):
            print('❌ Resource group does not exist!')
            return False
        
        print('✅ Resource group verified')
        
        # Get APIM service details
        output = utils.run(f'az apim list -g {rg_name} --query '[0]' -o json', print_command_to_run = False, print_errors = False)
        
        if output.success and output.json_data:
            apim_name = output.json_data.get('name')
            print(f'✅ APIM Service verified: {apim_name}')
            
            # Check Front Door
            afd_output = utils.run(f'az afd profile list -g {rg_name} --query '[0]' -o json', print_command_to_run = False, print_errors = False)
            
            if afd_output.success and afd_output.json_data:
                afd_name = afd_output.json_data.get('name')
                print(f'✅ Azure Front Door verified: {afd_name}')
                
                # Check Container Apps if enabled
                if use_aca:
                    aca_output = utils.run(f'az containerapp list -g {rg_name} --query 'length(@)'', print_command_to_run = False, print_errors = False)
                    
                    if aca_output.success:
                        aca_count = int(aca_output.text.strip())
                        print(f'✅ Container Apps verified: {aca_count} app(s) created')
            
            print('\n🎉 Infrastructure verification completed successfully!')
            return True
            
        else:
            print('\n❌ APIM service not found!')
            return False
            
    except Exception as e:
        print(f'\n⚠️  Verification failed with error: {str(e)}')
        return False

def main():
    """
    Main entry point for command-line usage.
    """
        
    parser = argparse.ArgumentParser(description='Create AFD-APIM-PE infrastructure')
    parser.add_argument('--location', default='eastus2', help='Azure region (default: eastus2)')
    parser.add_argument('--index', type=int, help='Infrastructure index')
    parser.add_argument('--sku', choices=['Standardv2', 'Premiumv2'], default='Standardv2', help='APIM SKU (default: Standardv2)')
    parser.add_argument('--no-aca', action='store_true', help='Disable Azure Container Apps')
    
    args = parser.parse_args()
    
    # Convert SKU string to enum
    sku_map = {
        'Standardv2': APIM_SKU.STANDARDV2,
        'Premiumv2': APIM_SKU.PREMIUMV2
    }
    
    try:
        result = _create_afd_apim_pe_infrastructure(
            rg_location = args.location, 
            index = args.index, 
            apim_sku = sku_map[args.sku],
            use_aca = not args.no_aca
        )
        
        if result.success:
            print('\n🎉 Infrastructure creation completed successfully!')
            sys.exit(0)
        else:
            print('\n💥 Infrastructure creation failed!')
            sys.exit(1)
            
    except Exception as e:
        print(f'\n💥 Error: {str(e)}')
        sys.exit(1)


if __name__ == '__main__':
    main()
