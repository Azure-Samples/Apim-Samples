"""
Infrastructure creation module for Simple APIM.

This module provides a reusable way to create Simple APIM infrastructure
that can be called from notebooks or other scripts.
"""

import sys
import os
import argparse
from pathlib import Path
import utils
from apimtypes import *
import json

def _create_simple_apim_infrastructure(
    rg_location: str = 'eastus2',
    index: int | None = None,
    apim_sku: APIM_SKU = APIM_SKU.BASICV2,
    custom_apis: list[API] | None = None,
    custom_policy_fragments: list[PolicyFragment] | None = None
) -> utils.Output:
    """
    Create Simple APIM infrastructure with the specified parameters.
    
    Args:
        rg_location (str): Azure region for deployment. Defaults to 'eastus2'.
        index (int | None): Index for the infrastructure. Defaults to None (no index).
        apim_sku (APIM_SKU): SKU for API Management. Defaults to BASICV2.
        custom_apis (list[API] | None): Custom APIs to deploy. If None, uses default Hello World API.
        custom_policy_fragments (list[PolicyFragment] | None): Custom policy fragments. If None, uses defaults.
        
    Returns:
        utils.Output: The deployment result.
    """
    
    print(f"\n🚀 Creating Simple APIM infrastructure...")
    print(f"   Location       : {rg_location}")
    print(f"   Index          : {index}")
    print(f"   APIM SKU       : {apim_sku.value}")
    
    # 1) Setup deployment parameters
    deployment = INFRASTRUCTURE.SIMPLE_APIM
    rg_name = utils.get_infra_rg_name(deployment, index)
    rg_tags = utils.build_infrastructure_tags(deployment)
    
    print(f"   Resource Group : {rg_name}\n")
    
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
    else:
        apis = custom_apis
    
    # 4) Define the Bicep parameters with serialized APIs
    bicep_parameters = {
        'apimSku'               : {'value': apim_sku.value},
        'apis'                  : {'value': [api.to_dict() for api in apis]},
        'policyFragments'       : {'value': [pf.to_dict() for pf in pfs]}
    }
    
    # 5) Change to the infrastructure directory to ensure bicep files are found
    original_cwd = os.getcwd()
    infra_dir = Path(__file__).parent
    
    try:
        os.chdir(infra_dir)
        print(f"📁 Changed working directory to: {infra_dir}")
        
        # 6) Prepare deployment parameters and run directly to avoid path detection issues
        bicep_parameters_format = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
            "contentVersion": "1.0.0.0",
            "parameters": bicep_parameters
        }
        
        # Write the parameters file
        params_file_path = infra_dir / 'params.json'

        with open(params_file_path, 'w') as file:            
            file.write(json.dumps(bicep_parameters_format))
        
        print(f"📝 Updated the policy XML in the bicep parameters file 'params.json'")
        
        # Create the resource group if it doesn't exist
        utils.create_resource_group(rg_name, rg_location, rg_tags)
        
        # Run the deployment directly
        main_bicep_path = infra_dir / 'main.bicep'
        output = utils.run(
            f'az deployment group create --name {deployment.value} --resource-group {rg_name} --template-file "{main_bicep_path}" --parameters "{params_file_path}" --query "properties.outputs"',
            f"Deployment '{deployment.value}' succeeded", 
            f"Deployment '{deployment.value}' failed."
        )
        
        # 7) Check the deployment results and perform verification
        if output.success:
            print("\n✅ Infrastructure creation completed successfully!")
            if output.json_data:
                apim_gateway_url = output.get('apimResourceGatewayURL', 'APIM API Gateway URL', suppress_logging = True)
                apim_apis = output.getJson('apiOutputs', 'APIs', suppress_logging = True)
                
                print(f"\n📋 Infrastructure Details:")
                print(f"   Resource Group : {rg_name}")
                print(f"   Location       : {rg_location}")
                print(f"   APIM SKU       : {apim_sku.value}")
                print(f"   Gateway URL    : {apim_gateway_url}")
                print(f"   APIs Created   : {len(apim_apis)}")
                
                # Perform basic verification
                _verify_infrastructure(rg_name, apim_gateway_url)
        else:
            print("❌ Infrastructure creation failed!")
            
        return output
        
    finally:
        # Always restore the original working directory
        os.chdir(original_cwd)
        print(f"📁 Restored working directory to: {original_cwd}")

def _verify_infrastructure(rg_name: str, apim_gateway_url: str) -> bool:
    """
    Verify that the infrastructure was created successfully.
    
    Args:
        rg_name (str): Resource group name.
        apim_gateway_url (str): API Management gateway Url.
        
    Returns:
        bool: True if verification passed, False otherwise.
    """
    
    print("\n🔍 Verifying infrastructure...")
    
    try:
        # Check if the resource group exists
        if not utils.does_resource_group_exist(rg_name):
            print("❌ Resource group does not exist!")
            return False
        
        print("✅ Resource group verified")
        
        # Get APIM service details
        output = utils.run(f'az apim list -g {rg_name} --query "[0]" -o json', print_command_to_run = False, print_errors = False)
        
        if output.success and output.json_data:
            apim_name = output.json_data.get('name')
            apim_gateway_url = output.json_data.get('gatewayUrl')
            
            print(f"✅ APIM Service verified: {apim_name}")
            
            # Get API count
            api_output = utils.run(f'az apim api list --service-name {apim_name} -g {rg_name} --query "length(@)"', 
                                  print_command_to_run = False, print_errors = False)
            
            if api_output.success:
                api_count = int(api_output.text.strip())
                print(f"✅ APIs verified: {api_count} API(s) created")
                
                # Test basic connectivity (optional)
                if api_count > 0:
                    try:
                        # Get subscription key for testing
                        sub_output = utils.run(f'az apim subscription list --service-name {apim_name} -g {rg_name} --query "[0].primaryKey" -o tsv', 
                                             print_command_to_run = False, print_errors = False)
                        
                        if sub_output.success and sub_output.text.strip():
                            print("✅ Subscription key available for API testing")
                    except:
                        pass
            
            print("\n🎉 Infrastructure verification completed successfully!")
            return True
            
        else:
            print("\n❌ APIM service not found!")
            return False
            
    except Exception as e:
        print(f"\n⚠️  Verification failed with error: {str(e)}")
        return False

def main():
    """
    Main entry point for command-line usage.
    """
        
    parser = argparse.ArgumentParser(description='Create Simple APIM infrastructure')
    parser.add_argument('--location', default='eastus2', help='Azure region (default: eastus2)')
    parser.add_argument('--index', type=int, help='Infrastructure index')
    parser.add_argument('--sku', choices=['Basicv2', 'Standardv2', 'Premiumv2'], default='Basicv2', help='APIM SKU (default: Basicv2)')
    
    args = parser.parse_args()
    
    # Convert SKU string to enum
    sku_map = {
        'Basicv2': APIM_SKU.BASICV2,
        'Standardv2': APIM_SKU.STANDARDV2,
        'Premiumv2': APIM_SKU.PREMIUMV2
    }
    
    try:
        result = _create_simple_apim_infrastructure(rg_location = args.location, index = args.index, apim_sku = sku_map[args.sku])
        
        if result.success:
            print("\n🎉 Infrastructure creation completed successfully!")
            sys.exit(0)
        else:
            print("\n💥 Infrastructure creation failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
