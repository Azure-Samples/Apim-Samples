"""
Infrastructure Types 
"""

import json
import os
from pathlib import Path
from apimtypes import *
import utils
# from abc import ABC, abstractmethod


# ------------------------------
#    INFRASTRUCTURE CLASSES
# ------------------------------

class Infrastructure:
    """
    Represents the base Infrastructure class
    """

    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, infra: INFRASTRUCTURE, index: int, location: str, apim_sku: APIM_SKU = APIM_SKU.BASICV2, networkMode: APIMNetworkMode = APIMNetworkMode.PUBLIC, 
                 infra_pfs: List[PolicyFragment] | None = None, infra_apis: List[API] | None = None):
        self.infra = infra
        self.index = index
        self.rg_location = location
        self.apim_sku = apim_sku
        self.networkMode = networkMode
        self.infra_apis = infra_apis
        self.infra_pfs = infra_pfs

        self.rg_name = utils.get_infra_rg_name(infra, index)
        self.rg_tags = utils.build_infrastructure_tags(infra)

        print(f'\n🚀 Initializing infrastructure...\n')
        print(f'   Infrastructure : {self.infra.value}')
        print(f'   Index          : {self.index}')
        print(f'   Resource group : {self.rg_name}')
        print(f'   Location       : {self.rg_location}')
        print(f'   APIM SKU       : {self.apim_sku.value}\n')

        self._define_policy_fragments(self.infra_pfs)
        self._define_apis(self.infra_apis)        

    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------   

    def deploy_infrastructure(self) -> None:
        """
        Deploy the infrastructure using the defined Bicep parameters.
        This method should be implemented in subclasses to handle specific deployment logic.
        """
        
        self._define_bicep_parameters()

        # Change to the infrastructure directory to ensure bicep files are found
        original_cwd = os.getcwd()
        infra_dir = Path(__file__).parent

        try:
            os.chdir(infra_dir)
            print(f'📁 Changed working directory to: {infra_dir}')
            
            # Prepare deployment parameters and run directly to avoid path detection issues
            bicep_parameters_format = {
                '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#',
                'contentVersion': '1.0.0.0',
                'parameters': self.bicep_parameters
            }
            
            # Write the parameters file
            params_file_path = infra_dir / 'params.json'

            with open(params_file_path, 'w') as file:            
                file.write(json.dumps(bicep_parameters_format))
            
            print(f"📝 Updated the policy XML in the bicep parameters file 'params.json'")
            
            # ------------------------------
            #    EXECUTE DEPLOYMENT
            # ------------------------------
            
            # Create the resource group if it doesn't exist
            utils.create_resource_group(self.rg_name, self.rg_location, self.rg_tags)
            
            # Run the deployment directly
            main_bicep_path = infra_dir / 'main.bicep'
            output = utils.run(
                f'az deployment group create --name {self.infra.value} --resource-group {self.rg_name} --template-file "{main_bicep_path}" --parameters "{params_file_path}" --query "properties.outputs"',
                f"Deployment '{self.infra.value}' succeeded", 
                f"Deployment '{self.infra.value}' failed.",
                print_command_to_run = False
            )
            
            # ------------------------------
            #    VERIFY DEPLOYMENT RESULTS
            # ------------------------------
            
            if output.success:
                print('\n✅ Infrastructure creation completed successfully!')
                if output.json_data:
                    apim_gateway_url = output.get('apimResourceGatewayURL', 'APIM API Gateway URL', suppress_logging = True)
                    apim_apis = output.getJson('apiOutputs', 'APIs', suppress_logging = True)
                    
                    print(f'\n📋 Infrastructure Details:')
                    print(f'   Resource Group : {self.rg_name}')
                    print(f'   Location       : {self.rg_location}')
                    print(f'   APIM SKU       : {self.apim_sku.value}')
                    print(f'   Gateway URL    : {apim_gateway_url}')
                    print(f'   APIs Created   : {len(apim_apis)}')
                    
                    # TODO: Perform basic verification
                    # utils.verify_infrastructure(self.rg_name)
            else:
                print('❌ Infrastructure creation failed!')
                
            return output
            
        finally:
            # Always restore the original working directory
            os.chdir(original_cwd)
            print(f'📁 Restored working directory to: {original_cwd}')

    # @abstractmethod
    # def verify_infrastructure(self) -> bool:
    #     """
    #     Verify the infrastructure deployment.
    #     This method should be implemented in subclasses to handle specific verification logic.
    #     """
    #     pass

    # ------------------------------
    #    PRIVATE METHODS
    # ------------------------------  

    def _define_bicep_parameters(self) -> dict:
        # Define the Bicep parameters with serialized APIs
        self.bicep_parameters = {
            'apimSku'         : {'value': self.apim_sku.value},
            'apis'            : {'value': [api.to_dict() for api in self.apis]},
            'policyFragments' : {'value': [pf.to_dict() for pf in self.pfs]}
        }

        return self.bicep_parameters
    

    def _define_policy_fragments(self, infra_pfs: List[PolicyFragment] | None) -> List[PolicyFragment]:
        """
        Define policy fragments for the infrastructure.
        """

        # The base policy fragments common to all infrastructures
        self.base_pfs = [
            PolicyFragment('AuthZ-Match-All', utils.read_policy_xmll(utils.determine_shared_policy_path('pf-authz-match-all.xml')), 'Authorizes if all of the specified roles match the JWT role claims.'),
            PolicyFragment('AuthZ-Match-Any', utils.read_policy_xmll(utils.determine_shared_policy_path('pf-authz-match-any.xml')), 'Authorizes if any of the specified roles match the JWT role claims.'),
            PolicyFragment('Http-Response-200', utils.read_policy_xmll(utils.determine_shared_policy_path('pf-http-response-200.xml')), 'Returns a 200 OK response for the current HTTP method.'),
            PolicyFragment('Product-Match-Any', utils.read_policy_xmll(utils.determine_shared_policy_path('pf-product-match-any.xml')), 'Proceeds if any of the specified products match the context product name.'),
            PolicyFragment('Remove-Request-Headers', utils.read_policy_xmll(utils.determine_shared_policy_path('pf-remove-request-headers.xml')), 'Removes request headers from the incoming request.')
        ]

        # Combine base policy fragments with infrastructure-specific ones
        self.pfs = self.base_pfs + infra_pfs if infra_pfs else self.base_pfs

        return self.pfs

    def _define_apis(self, infra_apis: List[API] | None) -> List[API]:
        """
        Define APIs for the infrastructure.
        """

        # The base APIs common to all infrastructures 
        # Hello World API
        pol_hello_world = utils.read_policy_xmll(HELLO_WORLD_XML_POLICY_PATH)
        api_hwroot_get = GET_APIOperation('Gets a Hello World message', pol_hello_world)
        api_hwroot = API('hello-world', 'Hello World', '', 'This is the root API for Hello World', operations = [api_hwroot_get])
        self.base_apis = [api_hwroot]

        # Combine base APIs with infrastructure-specific ones
        self.apis = self.base_apis + infra_apis if infra_apis else self.base_apis

        return self.apis


class SimpleApimInfrastructure(Infrastructure):
    """
    Represents a simple API Management infrastructure.
    """

    def __init__(self, location: str, index: int, apim_sku: APIM_SKU = APIM_SKU.BASICV2):
        super().__init__(INFRASTRUCTURE.SIMPLE_APIM, index, location, apim_sku, APIMNetworkMode.PUBLIC)


class ApimAcaInfrastructure(Infrastructure):
    """
    Represents an API Management with Azure Container Apps infrastructure.
    """

    def __init__(self, location: str, index: int, apim_sku: APIM_SKU = APIM_SKU.BASICV2):
        super().__init__(INFRASTRUCTURE.APIM_ACA, index, location, apim_sku, APIMNetworkMode.PUBLIC)


class AfdApimAcaInfrastructure(Infrastructure):
    """
    Represents an Azure Front Door with API Management and Azure Container Apps infrastructure.
    """

    def __init__(self, location: str, index: int, apim_sku: APIM_SKU = APIM_SKU.BASICV2):
        super().__init__(INFRASTRUCTURE.AFD_APIM_PE, index, location, apim_sku, APIMNetworkMode.PUBLIC)
