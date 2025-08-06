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

    def __init__(self, infra: INFRASTRUCTURE, index: int, rg_location: str, apim_sku: APIM_SKU = APIM_SKU.BASICV2, networkMode: APIMNetworkMode = APIMNetworkMode.PUBLIC, 
                 infra_pfs: List[PolicyFragment] | None = None, infra_apis: List[API] | None = None):
        self.infra = infra
        self.index = index
        self.rg_location = rg_location
        self.apim_sku = apim_sku
        self.networkMode = networkMode
        self.infra_apis = infra_apis
        self.infra_pfs = infra_pfs

        self.rg_name = utils.get_infra_rg_name(infra, index)
        self.rg_tags = utils.build_infrastructure_tags(infra)


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
    

    def _define_policy_fragments(self) -> List[PolicyFragment]:
        """
        Define policy fragments for the infrastructure.
        """

        # The base policy fragments common to all infrastructures
        self.base_pfs = [
            PolicyFragment('AuthZ-Match-All', utils.read_policy_xml(utils.determine_shared_policy_path('pf-authz-match-all.xml')), 'Authorizes if all of the specified roles match the JWT role claims.'),
            PolicyFragment('AuthZ-Match-Any', utils.read_policy_xml(utils.determine_shared_policy_path('pf-authz-match-any.xml')), 'Authorizes if any of the specified roles match the JWT role claims.'),
            PolicyFragment('Http-Response-200', utils.read_policy_xml(utils.determine_shared_policy_path('pf-http-response-200.xml')), 'Returns a 200 OK response for the current HTTP method.'),
            PolicyFragment('Product-Match-Any', utils.read_policy_xml(utils.determine_shared_policy_path('pf-product-match-any.xml')), 'Proceeds if any of the specified products match the context product name.'),
            PolicyFragment('Remove-Request-Headers', utils.read_policy_xml(utils.determine_shared_policy_path('pf-remove-request-headers.xml')), 'Removes request headers from the incoming request.')
        ]

        # Combine base policy fragments with infrastructure-specific ones
        self.pfs = self.base_pfs + self.infra_pfs if self.infra_pfs else self.base_pfs

        return self.pfs

    def _define_apis(self) -> List[API]:
        """
        Define APIs for the infrastructure.
        """

        # The base APIs common to all infrastructures 
        # Hello World API
        pol_hello_world = utils.read_policy_xml(HELLO_WORLD_XML_POLICY_PATH)
        api_hwroot_get = GET_APIOperation('Gets a Hello World message', pol_hello_world)
        api_hwroot = API('hello-world', 'Hello World', '', 'This is the root API for Hello World', operations = [api_hwroot_get])
        self.base_apis = [api_hwroot]

        # Combine base APIs with infrastructure-specific ones
        self.apis = self.base_apis + self.infra_apis if self.infra_apis else self.base_apis

        return self.apis

    def _verify_infrastructure(self, rg_name: str) -> bool:
        """
        Verify that the infrastructure was created successfully.
        
        Args:
            rg_name (str): Resource group name.
            
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
            output = utils.run(f'az apim list -g {rg_name} --query "[0]" -o json', print_command_to_run = False, print_errors = False)
            
            if output.success and output.json_data:
                apim_name = output.json_data.get('name')
                
                print(f'✅ APIM Service verified: {apim_name}')
                
                # Get API count
                api_output = utils.run(f'az apim api list --service-name {apim_name} -g {rg_name} --query "length(@)"', 
                                    print_command_to_run = False, print_errors = False)
                
                if api_output.success:
                    api_count = int(api_output.text.strip())
                    print(f'✅ APIs verified: {api_count} API(s) created')
                    
                    # Test basic connectivity (optional)
                    if api_count > 0:
                        try:
                            # Get subscription key for testing
                            sub_output = utils.run(f'az apim subscription list --service-name {apim_name} -g {rg_name} --query "[0].primaryKey" -o tsv', 
                                                print_command_to_run = False, print_errors = False)
                            
                            if sub_output.success and sub_output.text.strip():
                                print('✅ Subscription key available for API testing')
                        except:
                            pass
                
                # Call infrastructure-specific verification
                if self._verify_infrastructure_specific(rg_name):
                    print('\n🎉 Infrastructure verification completed successfully!')
                    return True
                else:
                    print('\n❌ Infrastructure-specific verification failed!')
                    return False
                
            else:
                print('\n❌ APIM service not found!')
                return False
                
        except Exception as e:
            print(f'\n⚠️  Verification failed with error: {str(e)}')
            return False

    def _verify_infrastructure_specific(self, rg_name: str) -> bool:
        """
        Verify infrastructure-specific components.
        This is a virtual method that can be overridden by subclasses for specific verification logic.
        
        Args:
            rg_name (str): Resource group name.
            
        Returns:
            bool: True if verification passed, False otherwise.
        """
        # Base implementation - no additional verification required
        return True

    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------   

    def deploy_infrastructure(self) -> 'utils.Output':
        """
        Deploy the infrastructure using the defined Bicep parameters.
        This method should be implemented in subclasses to handle specific deployment logic.
        """
        
        print(f'\n🚀 Creating infrastructure...\n')
        print(f'   Infrastructure : {self.infra.value}')
        print(f'   Index          : {self.index}')
        print(f'   Resource group : {self.rg_name}')
        print(f'   Location       : {self.rg_location}')
        print(f'   APIM SKU       : {self.apim_sku.value}\n')

        self._define_policy_fragments()
        self._define_apis() 
        self._define_bicep_parameters()

        # Determine the correct infrastructure directory based on the infrastructure type
        original_cwd = os.getcwd()
        
        # Map infrastructure types to their directory names
        infra_dir_map = {
            INFRASTRUCTURE.SIMPLE_APIM: 'simple-apim',
            INFRASTRUCTURE.APIM_ACA: 'apim-aca', 
            INFRASTRUCTURE.AFD_APIM_PE: 'afd-apim-pe'
        }
        
        # Get the infrastructure directory
        infra_dir_name = infra_dir_map.get(self.infra)
        if not infra_dir_name:
            raise ValueError(f"Unknown infrastructure type: {self.infra}")
            
        # Navigate to the correct infrastructure directory
        # From shared/python -> ../../infrastructure/{infra_type}/
        shared_dir = Path(__file__).parent
        infra_dir = shared_dir.parent.parent / 'infrastructure' / infra_dir_name

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
                    self._verify_infrastructure(self.rg_name)
            else:
                print('❌ Infrastructure creation failed!')
                
            return output
            
        finally:
            # Always restore the original working directory
            os.chdir(original_cwd)
            print(f'📁 Restored working directory to: {original_cwd}')


class SimpleApimInfrastructure(Infrastructure):
    """
    Represents a simple API Management infrastructure.
    """

    def __init__(self, rg_location: str, index: int, apim_sku: APIM_SKU = APIM_SKU.BASICV2, infra_pfs: List[PolicyFragment] | None = None, infra_apis: List[API] | None = None):
        super().__init__(INFRASTRUCTURE.SIMPLE_APIM, index, rg_location, apim_sku, APIMNetworkMode.PUBLIC, infra_pfs, infra_apis)


class ApimAcaInfrastructure(Infrastructure):
    """
    Represents an API Management with Azure Container Apps infrastructure.
    """

    def __init__(self, rg_location: str, index: int, apim_sku: APIM_SKU = APIM_SKU.BASICV2, infra_pfs: List[PolicyFragment] | None = None, infra_apis: List[API] | None = None):
        super().__init__(INFRASTRUCTURE.APIM_ACA, index, rg_location, apim_sku, APIMNetworkMode.PUBLIC, infra_pfs, infra_apis)

    def _verify_infrastructure_specific(self, rg_name: str) -> bool:
        """
        Verify APIM-ACA specific components.
        
        Args:
            rg_name (str): Resource group name.
            
        Returns:
            bool: True if verification passed, False otherwise.
        """
        try:
            # Get Container Apps count
            aca_output = utils.run(f'az containerapp list -g {rg_name} --query "length(@)"', print_command_to_run = False, print_errors = False)
            
            if aca_output.success:
                aca_count = int(aca_output.text.strip())
                print(f'✅ Container Apps verified: {aca_count} app(s) created')
                return True
            else:
                print('❌ Container Apps verification failed!')
                return False
                
        except Exception as e:
            print(f'⚠️  Container Apps verification failed with error: {str(e)}')
            return False


class AfdApimAcaInfrastructure(Infrastructure):
    """
    Represents an Azure Front Door with API Management and Azure Container Apps infrastructure.
    """

    def __init__(self, rg_location: str, index: int, apim_sku: APIM_SKU = APIM_SKU.BASICV2, infra_pfs: List[PolicyFragment] | None = None, infra_apis: List[API] | None = None):
        super().__init__(INFRASTRUCTURE.AFD_APIM_PE, index, rg_location, apim_sku, APIMNetworkMode.PUBLIC, infra_pfs, infra_apis)

    def _define_bicep_parameters(self) -> dict:
        """
        Define AFD-APIM-PE specific Bicep parameters.
        """
        # Get base parameters
        base_params = super()._define_bicep_parameters()
        
        # Add AFD-specific parameters
        afd_params = {
            'apimPublicAccess': {'value': True},  # Initially true for private link approval
            'useACA': {'value': len(self.infra_apis) > 0 if self.infra_apis else False}  # Enable ACA if custom APIs are provided
        }
        
        # Merge with base parameters
        base_params.update(afd_params)
        return base_params

    def _verify_infrastructure_specific(self, rg_name: str) -> bool:
        """
        Verify AFD-APIM-PE specific components.
        
        Args:
            rg_name (str): Resource group name.
            
        Returns:
            bool: True if verification passed, False otherwise.
        """
        try:
            # Check Front Door
            afd_output = utils.run(f'az afd profile list -g {rg_name} --query "[0]" -o json', print_command_to_run = False, print_errors = False)
            
            if afd_output.success and afd_output.json_data:
                afd_name = afd_output.json_data.get('name')
                print(f'✅ Azure Front Door verified: {afd_name}')
                
                # Check Container Apps if they exist (optional for this infrastructure)
                aca_output = utils.run(f'az containerapp list -g {rg_name} --query "length(@)"', print_command_to_run = False, print_errors = False)
                
                if aca_output.success:
                    aca_count = int(aca_output.text.strip())
                    if aca_count > 0:
                        print(f'✅ Container Apps verified: {aca_count} app(s) created')
                
                return True
            else:
                print('❌ Azure Front Door verification failed!')
                return False
                
        except Exception as e:
            print(f'⚠️  AFD-APIM-PE verification failed with error: {str(e)}')
            return False
