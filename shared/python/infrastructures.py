"""
Infrastructure Types and Cleanup Utilities
"""

import json
import os
import time
import traceback
from pathlib import Path
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# APIM Samples imports
from apimtypes import API, APIM_SKU, APIMNetworkMode, GET_APIOperation, HELLO_WORLD_XML_POLICY_PATH, INFRASTRUCTURE, PolicyFragment
from console import BOLD_R, BOLD_Y, RESET, THREAD_COLORS, _print_lock, _print_log, print_command, print_error, print_info, print_message, print_ok, print_plain, print_warning, print_val
from logging_config import should_print_traceback
import azure_resources as az
import utils


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

        # Define and create the resource group
        self.rg_name = az.get_infra_rg_name(infra, index)
        self.rg_tags = utils.build_infrastructure_tags(infra)
        az.create_resource_group(self.rg_name, self.rg_location, self.rg_tags)

        # Some infrastructure deployments require knowing the resource suffix that bicep will use prior to the main deployment.
        # Uses subscription ID and resource group name hashing to generate the suffix.
        self.resource_suffix = az.get_unique_suffix_for_resource_group(self.rg_name)

        self.current_user, self.current_user_id, self.tenant_id, self.subscription_id = az.get_account_info()

    # ------------------------------
    #    PRIVATE METHODS
    # ------------------------------

    def _approve_private_link_connections(self, apim_service_id: str) -> bool:
        """
        Approve pending private link connections from AFD to APIM.

        Args:
            apim_service_id (str): APIM service resource ID.

        Returns:
            bool: True if all connections were approved successfully, False otherwise.
        """
        print_plain('\n🔗 Step 3: Approving private link connection to APIM...')

        try:
            # Get all pending private endpoint connections
            output = az.run(
                f'az network private-endpoint-connection list --id {apim_service_id} --query "[?contains(properties.privateLinkServiceConnectionState.status, \'Pending\')]" -o json'
            )

            if not output.success:
                print_error('Failed to retrieve private endpoint connections')
                return False

            pending_connections = output.json_data if output.is_json else []

            # Handle both single object and list
            if isinstance(pending_connections, dict):
                pending_connections = [pending_connections]

            total = len(pending_connections)
            print_plain(f'Found {total} pending private link service connection(s)')

            if not total:
                print_ok('No pending connections found. They may already be approved. This is also normal for some VNet scenarios.')
                return True

            # Approve each pending connection
            for i, conn in enumerate(pending_connections, 1):
                conn_id = conn.get('id')
                conn_name = conn.get('name', '<unknown>')
                print_plain(f'Approving {i}/{total}: {conn_name}')

                approve_result = az.run(
                    f'az network private-endpoint-connection approve --id {conn_id} --description "Approved by infrastructure deployment"',
                    f'Private Link Connection approved: {conn_name}',
                    f'Failed to approve Private Link Connection: {conn_name}'
                )

                if not approve_result.success:
                    return False

            print_ok('All private link connections approved successfully')
            return True

        except Exception as e:
            print_error(f'Error during private link approval: {str(e)}')
            return False

    def _create_keyvault(self, key_vault_name: str) -> bool:
        # Check if Key Vault already exists
        check_kv = az.run(
            f'az keyvault show --name {key_vault_name} --resource-group {self.rg_name} -o json'
        )

        if not check_kv.success:
            # Create Key Vault via Azure CLI with RBAC authorization (consistent with Bicep module)
            print_plain(f'Creating Key Vault: {key_vault_name}')
            create_kv = az.run(
                f'az keyvault create --name {key_vault_name} --resource-group {self.rg_name} --location {self.rg_location} --enable-rbac-authorization true'
            )

            if not create_kv.success:
                print_error(f'Failed to create Key Vault: {key_vault_name}')
                print_plain('This may be caused by a soft-deleted Key Vault with the same name.')
                print_plain('Check for soft-deleted resources: python shared/python/show_soft_deleted_resources.py\n')
                return False

            print_ok(f'Key Vault created: {key_vault_name}')

            #Assign Key Vault Certificates Officer role to current user for certificate creation

            # Key Vault Certificates Officer role
            assign_kv_role = az.run(
                f'az role assignment create --role "Key Vault Certificates Officer" --assignee {self.current_user_id} --scope /subscriptions/{self.subscription_id}/resourceGroups/{self.rg_name}/providers/Microsoft.KeyVault/vaults/{key_vault_name}'
            )
            if not assign_kv_role.success:
                print_error('Failed to assign Key Vault Certificates Officer role to current user.\nThis is an RBAC permission issue - verify your account has sufficient permissions.')
                return False

            print_ok('Assigned Key Vault Certificates Officer role to current user')

            # Brief wait for role assignment propagation
            print_plain('⏳ Waiting for role assignment propagation (15 seconds)...')
            time.sleep(15)

        return True

    def _define_bicep_parameters(self) -> dict:
        # Define the Bicep parameters with serialized APIs
        self.bicep_parameters = {
            'resourceSuffix'  : {'value': self.resource_suffix},
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
            PolicyFragment('Api-Id', utils.read_policy_xml(utils.determine_shared_policy_path('pf-api-id.xml')), 'Extracts a specific API identifier for tracing.'),
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

    def _disable_apim_public_access(self) -> bool:
        """
        Disable public network access to APIM by redeploying with updated parameters.

        Returns:
            bool: True if deployment succeeded, False otherwise.
        """
        print_plain('🔒 Disabling API Management public network access...')

        try:
            # Update parameters to disable public access
            self.bicep_parameters['apimPublicAccess']['value'] = False

            # Write updated parameters file
            original_cwd = os.getcwd()
            shared_dir = Path(__file__).parent
            infra_dir = shared_dir.parent.parent / 'infrastructure' / self.infra.value

            try:
                os.chdir(infra_dir)

                bicep_parameters_format = {
                    '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#',
                    'contentVersion': '1.0.0.0',
                    'parameters': self.bicep_parameters
                }

                params_file_path = infra_dir / 'params.json'
                with open(params_file_path, 'w', encoding='utf-8') as file:
                    file.write(json.dumps(bicep_parameters_format))

                print_plain('📝 Updated parameters to disable public access')

                # Run the second deployment
                main_bicep_path = infra_dir / 'main.bicep'
                output = az.run(
                    f'az deployment group create --name {self.infra.value}-lockdown --resource-group {self.rg_name} --template-file "{main_bicep_path}" --parameters "{params_file_path}" --query "properties.outputs"',
                    'Public access disabled successfully',
                    'Failed to disable public access'
                )

                return output.success

            finally:
                os.chdir(original_cwd)

        except Exception as e:
            print_error(f'Error during public access disable: {str(e)}')
            return False

    def _verify_apim_connectivity(self, apim_gateway_url: str) -> bool:
        """
        Verify APIM connectivity before disabling public access using the health check endpoint.

        Args:
            apim_gateway_url (str): APIM gateway URL.

        Returns:
            bool: True if connectivity test passed, False otherwise.
        """
        print_plain('Verifying API request success via API Management...')

        try:
            # Use the health check endpoint which doesn't require a subscription key
            healthcheck_url = f'{apim_gateway_url}/status-0123456789abcdef'
            print_plain(f'Testing connectivity to health check endpoint: {healthcheck_url}')

            response = requests.get(healthcheck_url, timeout=30)

            if response.status_code == 200:
                print_ok('APIM connectivity verified - Health check returned 200')
                return True
            else:
                print_warning(f'APIM health check returned status code {response.status_code} (expected 200)')
                return True  # Continue anyway as this might be expected during deployment

        except Exception as e:
            print_warning(f'APIM connectivity test failed: {str(e)}')
            print_info('Continuing deployment - this may be expected during infrastructure setup')
            return True  # Continue anyway

    def _verify_infrastructure(self, rg_name: str) -> bool:
        """
        Verify that the infrastructure was created successfully.

        Args:
            rg_name (str): Resource group name.

        Returns:
            bool: True if verification passed, False otherwise.
        """

        print_plain('\n🔍 Verifying infrastructure...')

        try:
            # Check if the resource group exists
            if not az.does_resource_group_exist(rg_name):
                print_error('Resource group does not exist!')
                return False

            print_ok('Resource group verified')

            # Get APIM service details
            output = az.run(f'az apim list -g {rg_name} --query "[0]" -o json')

            if output.success and output.json_data:
                apim_name = output.json_data.get('name')

                print_ok(f'APIM Service verified: {apim_name}')

                # Get API count
                api_output = az.run(f'az apim api list --service-name {apim_name} -g {rg_name} --query "length(@)"')

                if api_output.success:
                    api_count = int(api_output.text.strip())
                    print_ok(f'APIs verified: {api_count} API(s) created')

                    # Test basic connectivity (optional)
                    if api_count > 0:
                        try:
                            # Get subscription key for testing
                            subscription_key = az.get_apim_subscription_key(apim_name, rg_name)
                            if subscription_key:
                                print_ok('Subscription key available for API testing')
                        except:
                            pass

                # Call infrastructure-specific verification
                if self._verify_infrastructure_specific(rg_name):
                    print_plain('\n🎉 Infrastructure verification completed successfully!')
                    return True

                print_error('Infrastructure-specific verification failed!')
                return False

            print_error('APIM service not found!')
            return False

        except Exception as e:
            print_warning(f'Verification failed with error: {str(e)}')
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

    def deploy_infrastructure(self, is_update: bool = False) -> utils.Output:
        """
        Deploy the infrastructure using the defined Bicep parameters.
        This method should be implemented in subclasses to handle specific deployment logic.

        Args:
            is_update (bool): Whether this is an update to existing infrastructure or a new deployment.
        """

        action_verb = "Updating" if is_update else "Creating"
        print_plain(f'🚀 {action_verb} infrastructure...\n')
        print_val('Infrastructure', self.infra.value)
        print_val('Index', self.index)
        print_val('Resource group', self.rg_name)
        print_val('Location', self.rg_location)
        print_val('APIM SKU', self.apim_sku.value)

        self._define_policy_fragments()
        self._define_apis()
        self._define_bicep_parameters()

        # Determine the correct infrastructure directory based on the infrastructure type
        original_cwd = os.getcwd()

        # Map infrastructure types to their directory names
        infra_dir_map = {
            INFRASTRUCTURE.SIMPLE_APIM: 'simple-apim',
            INFRASTRUCTURE.APIM_ACA: 'apim-aca',
            INFRASTRUCTURE.AFD_APIM_PE: 'afd-apim-pe',
            INFRASTRUCTURE.APPGW_APIM_PE: 'appgw-apim-pe',
            INFRASTRUCTURE.APPGW_APIM: 'appgw-apim'
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
            print_plain(f'📁 Changed working directory to: {infra_dir}', blank_above = True)

            # Prepare deployment parameters and run directly to avoid path detection issues
            bicep_parameters_format = {
                '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#',
                'contentVersion': '1.0.0.0',
                'parameters': self.bicep_parameters
            }

            # Write the parameters file
            params_file_path = infra_dir / 'params.json'

            with open(params_file_path, 'w', encoding='utf-8') as file:
                file.write(json.dumps(bicep_parameters_format))

            print_plain("📝 Updated the policy XML in the bicep parameters file 'params.json'")

            # ------------------------------
            #    EXECUTE DEPLOYMENT
            # ------------------------------

            # Run the deployment directly
            main_bicep_path = infra_dir / 'main.bicep'
            output = az.run(
                f'az deployment group create --name {self.infra.value} --resource-group {self.rg_name} --template-file "{main_bicep_path}" --parameters "{params_file_path}" --query "properties.outputs"',
                f"Deployment '{self.infra.value}' succeeded",
                utils.get_deployment_failure_message(self.infra.value)
            )

            # ------------------------------
            #    VERIFY DEPLOYMENT RESULTS
            # ------------------------------

            if output.success:
                print_ok('Infrastructure creation completed successfully!')
                if output.json_data:
                    apim_gateway_url = output.get('apimResourceGatewayURL', 'APIM API Gateway URL', suppress_logging = True)
                    apim_apis = output.getJson('apiOutputs', 'APIs', suppress_logging = True)

                    print_plain('\n📋 Infrastructure Details:')
                    print_val('Resource Group', self.rg_name)
                    print_val('Location', self.rg_location)
                    print_val('APIM SKU', self.apim_sku.value)
                    print_val('Gateway URL', apim_gateway_url)
                    print_val('APIs Created', len(apim_apis))

                    # TODO: Perform basic verification
                    self._verify_infrastructure(self.rg_name)
            else:
                print_error('Infrastructure creation failed!')

            return output

        finally:
            # Always restore the original working directory
            os.chdir(original_cwd)
            print_plain(f'📁 Restored working directory to: {original_cwd}')

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
            aca_output = az.run(f'az containerapp list -g {rg_name} --query "length(@)"')

            if aca_output.success:
                aca_count = int(aca_output.text.strip())
                print_ok(f'Container Apps verified: {aca_count} app(s) created')
                return True
            else:
                print_error('Container Apps verification failed!')
                return False

        except Exception as e:
            print_warning(f'Container Apps verification failed with error: {str(e)}')
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

    def deploy_infrastructure(self, is_update: bool = False) -> utils.Output:
        """
        Deploy the AFD-APIM-PE infrastructure with the required multi-step process.

        Args:
            is_update (bool): Whether this is an update to existing infrastructure or a new deployment.

        Returns:
            utils.Output: The deployment result.
        """
        action_verb = "Updating" if is_update else "Starting"
        print_plain(f'🚀 {action_verb} AFD-APIM-PE infrastructure deployment...\n')
        print_plain('   This deployment requires multiple steps:\n')
        print_plain('   1. Initial deployment with public access enabled')
        print_plain('   2. Approve private link connections')
        print_plain('   3. Verify connectivity')
        print_plain('   4. Disable public access to APIM')
        print_plain('   5. Final verification\n')

        # Step 1 & 2: Initial deployment using base class method
        output = super().deploy_infrastructure(is_update)

        if not output.success:
            print_error('Initial deployment failed!')
            return output

        print_ok('Step 1 & 2: Initial infrastructure deployment completed')

        # Extract required values from deployment output
        if not output.json_data:
            print_error('No deployment output data available')
            return output

        apim_service_id = output.get('apimServiceId', 'APIM Service ID', suppress_logging = True)
        apim_gateway_url = output.get('apimResourceGatewayURL', 'APIM Gateway URL', suppress_logging = True)

        if not apim_service_id or not apim_gateway_url:
            print_error('Required APIM information not found in deployment output')
            return output

        # Step 3: Approve private link connections
        if not self._approve_private_link_connections(apim_service_id):
            print_error('Private link approval failed!')
            return utils.Output(False, 'Private link approval failed')

        # Step 4: Verify connectivity (optional - continues on failure)
        self._verify_apim_connectivity(apim_gateway_url)

        # Step 5: Disable public access
        if not self._disable_apim_public_access():
            print_error('Failed to disable public access!')
            return utils.Output(False, 'Failed to disable public access')

        print_plain('\n🎉 AFD-APIM-PE infrastructure deployment completed successfully!\n')
        print_plain('\n📋 Final Configuration:\n')
        print_ok('Azure Front Door deployed')
        print_ok('API Management deployed with private endpoints')
        print_ok('Private link connections approved')
        print_ok('Public access to APIM disabled')
        print_info('Traffic now flows: Internet → AFD → Private Endpoint → APIM')

        return output

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
            afd_output = az.run(f'az afd profile list -g {rg_name} --query "[0]" -o json')

            if afd_output.success and afd_output.json_data:
                afd_name = afd_output.json_data.get('name')
                print_ok(f'Azure Front Door verified: {afd_name}')

                # Check Container Apps if they exist (optional for this infrastructure)
                aca_output = az.run(f'az containerapp list -g {rg_name} --query "length(@)"')

                if aca_output.success:
                    aca_count = int(aca_output.text.strip())
                    if aca_count > 0:
                        print_ok(f'Container Apps verified: {aca_count} app(s) created')

                # Verify private endpoint connections (optional - don't fail if it errors)
                try:
                    apim_output = az.run(f'az apim list -g {rg_name} --query "[0].id" -o tsv')
                    if apim_output.success and apim_output.text.strip():
                        apim_id = apim_output.text.strip()
                        pe_output = az.run(f'az network private-endpoint-connection list --id {apim_id} --query "length(@)"')
                        if pe_output.success:
                            pe_count = int(pe_output.text.strip())
                            print_ok(f'Private endpoint connections: {pe_count}')
                except:
                    # Don't fail verification if private endpoint check fails
                    pass

                return True
            else:
                print_error('Azure Front Door verification failed!')
                return False

        except Exception as e:
            print_warning(f'AFD-APIM-PE verification failed with error: {str(e)}')
            return False

class AppGwApimPeInfrastructure(Infrastructure):
    """
    Represents an Application Gateway with API Management and Azure Container Apps infrastructure.
    """

    # Class constants for certificate configuration
    CERT_NAME = 'appgw-cert'
    DOMAIN_NAME = 'api.apim-samples.contoso.com'

    def __init__(self, rg_location: str, index: int, apim_sku: APIM_SKU = APIM_SKU.BASICV2, infra_pfs: List[PolicyFragment] | None = None, infra_apis: List[API] | None = None):
        super().__init__(INFRASTRUCTURE.APPGW_APIM_PE, index, rg_location, apim_sku, APIMNetworkMode.PUBLIC, infra_pfs, infra_apis)

    def _create_keyvault_certificate(self, key_vault_name: str) -> bool:
        """
        Create a self-signed certificate in Key Vault for Application Gateway TLS.
        This is done via Azure CLI because deployment scripts require storage accounts with
        shared key access enabled, which may be blocked by Azure Policy.

        Args:
            key_vault_name (str): Name of the Key Vault.

        Returns:
            bool: True if certificate was created or already exists, False on failure.
        """
        print_plain('\n🔐 Creating self-signed certificate in Key Vault...\n')
        print_val('Key Vault', key_vault_name)
        print_val('Certificate', self.CERT_NAME)
        print_val('Domain', self.DOMAIN_NAME)

        # Check if certificate already exists
        check_output = az.run(
            f'az keyvault certificate show --vault-name {key_vault_name} --name {self.CERT_NAME} -o json'
        )

        if check_output.success:
            print_ok('Certificate already exists in Key Vault')
            return True

        # Build the certificate policy JSON for Azure CLI
        cert_policy = json.dumps({
            "issuerParameters": {
                "name": "Self"
            },
            "keyProperties": {
                "exportable": True,
                "keySize": 2048,
                "keyType": "RSA",
                "reuseKey": True
            },
            "secretProperties": {
                "contentType": "application/x-pkcs12"
            },
            "x509CertificateProperties": {
                "keyUsage": [
                    "digitalSignature",
                    "keyEncipherment"
                ],
                "subject": f"CN={self.DOMAIN_NAME}",
                "validityInMonths": 12
            }
        })

        # Create the certificate using Azure CLI
        # Use escaped double quotes for Windows PowerShell compatibility
        escaped_policy = cert_policy.replace('"', '\\"')
        create_output = az.run(
            f'az keyvault certificate create --vault-name {key_vault_name} --name {self.CERT_NAME} --policy "{escaped_policy}"',
            'Certificate created successfully in Key Vault',
            'Failed to create certificate in Key Vault'
        )

        return create_output.success

    def _define_bicep_parameters(self) -> dict:
        """
        Define APPGW-APIM-PE specific Bicep parameters.
        """
        # Get base parameters
        base_params = super()._define_bicep_parameters()

        # Add AppGw-specific parameters
        appgw_params = {
            'apimPublicAccess': {'value': True},  # Initially true for private link approval
            'useACA': {'value': len(self.infra_apis) > 0 if self.infra_apis else False},  # Enable ACA if custom APIs are provided
            'setCurrentUserAsKeyVaultAdmin': {'value': True},
            'currentUserId': {'value': self.current_user_id}
        }

        # Merge with base parameters
        base_params.update(appgw_params)
        return base_params

    def deploy_infrastructure(self, is_update: bool = False) -> utils.Output:
        """
        Deploy the APPGW-APIM-PE infrastructure with the required multi-step process.

        Args:
            is_update (bool): Whether this is an update to existing infrastructure or a new deployment.

        Returns:
            utils.Output: The deployment result.
        """
        action_verb = "Updating" if is_update else "Starting"
        print_plain(f'🚀 {action_verb} APPGW-APIM-PE infrastructure deployment...\n')
        print_plain('   This deployment requires multiple steps:\n')
        print_plain('   1. Create Key Vault and self-signed certificate')
        print_plain('   2. Initial deployment with public access enabled')
        print_plain('   3. Approve private link connections')
        print_plain('   4. Verify connectivity')
        print_plain('   5. Disable public access to APIM')

        # Step 1: Create Key Vault and certificate before main deployment
        print_plain('\n📋 Step 1: Creating Key Vault and certificate...')
        key_vault_name = f'kv-{self.resource_suffix}'

        # Create the Key Vault
        if not self._create_keyvault(key_vault_name):
            return utils.Output(False, 'Failed to create Key Vault')

        # Create the certificate
        if not self._create_keyvault_certificate(key_vault_name):
            return utils.Output(False, 'Failed to create certificate in Key Vault')

        print_ok('Step 1: Key Vault and certificate creation completed', blank_above = True)

        # Step 2: Initial deployment using base class method
        print_plain('\n📋 Step 2: Deploying initial infrastructure...\n')

        output = super().deploy_infrastructure(is_update)

        if not output.success:
            print_error('Initial deployment failed!')
            return output

        print_ok('Step 2: Initial infrastructure deployment completed', blank_above = True)

        # Extract required values from deployment output
        if not output.json_data:
            print_error('No deployment output data available')
            return output

        apim_service_id = output.get('apimServiceId', 'APIM Service ID', suppress_logging = True)
        apim_gateway_url = output.get('apimResourceGatewayURL', 'APIM Gateway URL', suppress_logging = True)
        self.appgw_domain_name = output.get('appGatewayDomainName', 'App Gateway Domain Name', suppress_logging = True)
        self.appgw_public_ip = output.get('appgwPublicIpAddress', 'App Gateway Public IP', suppress_logging = True)

        if not apim_service_id or not apim_gateway_url:
            print_error('Required APIM information not found in deployment output')
            return output

        # Step 3: Approve private link connections
        print_plain('\n📋 Step 3: Approving private link connection...\n')
        if not self._approve_private_link_connections(apim_service_id):
            print_error('Private link approval failed!')
            return utils.Output(False, 'Private link approval failed')

        print_ok('Step 3: Private link connection approval completed', blank_above = True)

        # Step 4: Verify connectivity (optional - continues on failure)
        print_plain('\n📋 Step 4: Verifying API Management connectivity...\n')
        self._verify_apim_connectivity(apim_gateway_url)

        print_ok('Step 4: API Management connectivity verification completed', blank_above = True)

        # Step 5: Disable public access
        print_plain('\n📋 Step 5: Disabling public access...\n')
        if not self._disable_apim_public_access():
            print_error('Failed to disable public access!')
            return utils.Output(False, 'Failed to disable public access')

        print_ok('Step 5: Public access disabling completed', blank_above = True)

        print_plain('\n🎉 APPGW-APIM-PE infrastructure deployment completed successfully!\n')
        print_plain('\n📋 Final Configuration:\n')
        print_ok('Application Gateway deployed')
        print_ok('API Management deployed with private endpoints')
        print_ok('Private link connections approved')
        print_ok('Public access to APIM disabled')
        print_info('Traffic now flows: Internet → Application Gateway → Private Endpoint → APIM')

        print_plain('\n\n🧪 TESTING\n')
        print_plain('As we are using a self-signed certificate (please see README.md for details), we need to test differently.\n' +
              'A curl command using flags for verbose (v), ignoring cert issues (k), and supplying a host header (h) works to verify connectivity.\n' +
              'This tests ingress through App Gateway and a response from API Management\'s health endpoint. An "HTTP 200 Service Operational" response indicates success.\n')
        print_command(f'curl -v -k -H "Host: {self.appgw_domain_name}" https://{self.appgw_public_ip}/status-0123456789abcdef')

        return output

    def _verify_infrastructure_specific(self, rg_name: str) -> bool:
        """
        Verify APPGW-APIM-PE specific components.

        Args:
            rg_name (str): Resource group name.

        Returns:
            bool: True if verification passed, False otherwise.
        """
        try:
            # Check Application Gateway
            appgw_output = az.run(f'az network application-gateway list -g {rg_name} --query "[0]" -o json')

            if appgw_output.success and appgw_output.json_data:
                appgw_name = appgw_output.json_data.get('name')
                print_ok(f'Application Gateway verified: {appgw_name}')

                # Check Container Apps if they exist (optional for this infrastructure)
                aca_output = az.run(f'az containerapp list -g {rg_name} --query "length(@)"')

                if aca_output.success:
                    aca_count = int(aca_output.text.strip())
                    if aca_count > 0:
                        print_ok(f'Container Apps verified: {aca_count} app(s) created')

                # Verify private endpoint connections (optional - don't fail if it errors)
                try:
                    apim_output = az.run(f'az apim list -g {rg_name} --query "[0].id" -o tsv')
                    if apim_output.success and apim_output.text.strip():
                        apim_id = apim_output.text.strip()
                        pe_output = az.run(f'az network private-endpoint-connection list --id {apim_id} --query "length(@)"')
                        if pe_output.success:
                            pe_count = int(pe_output.text.strip())
                            print_ok(f'Private endpoint connections: {pe_count}')
                except:
                    # Don't fail verification if private endpoint check fails
                    pass

                return True
            else:
                print_error('Application Gateway verification failed!')
                return False

        except Exception as e:
            print_warning(f'APPGW-APIM-PE verification failed with error: {str(e)}')
            return False

class AppGwApimInfrastructure(Infrastructure):
    """
    Represents an Application Gateway with API Management (Developer SKU) using VNet Internal mode.
    No Private Endpoints are used; App Gateway routes directly to APIM's private IP.
    """

    CERT_NAME = 'appgw-cert'
    DOMAIN_NAME = 'api.apim-samples.contoso.com'

    def __init__(self, rg_location: str, index: int, apim_sku: APIM_SKU = APIM_SKU.DEVELOPER, infra_pfs: List[PolicyFragment] | None = None, infra_apis: List[API] | None = None):
        super().__init__(INFRASTRUCTURE.APPGW_APIM, index, rg_location, apim_sku, APIMNetworkMode.INTERNAL_VNET, infra_pfs, infra_apis)

    def _create_keyvault_certificate(self, key_vault_name: str) -> bool:
        print_plain('\n🔐 Creating self-signed certificate in Key Vault...\n')
        print_val('Key Vault', key_vault_name)
        print_val('Certificate', self.CERT_NAME)
        print_val('Domain', self.DOMAIN_NAME)

        check_output = az.run(
            f'az keyvault certificate show --vault-name {key_vault_name} --name {self.CERT_NAME} -o json'
        )

        if check_output.success:
            print_ok('Certificate already exists in Key Vault')
            return True

        cert_policy = json.dumps({
            "issuerParameters": {"name": "Self"},
            "keyProperties": {"exportable": True, "keySize": 2048, "keyType": "RSA", "reuseKey": True},
            "secretProperties": {"contentType": "application/x-pkcs12"},
            "x509CertificateProperties": {
                "keyUsage": ["digitalSignature", "keyEncipherment"],
                "subject": f"CN={self.DOMAIN_NAME}",
                "validityInMonths": 12
            }
        })

        escaped_policy = cert_policy.replace('"', '\\"')
        create_output = az.run(
            f'az keyvault certificate create --vault-name {key_vault_name} --name {self.CERT_NAME} --policy "{escaped_policy}"',
            'Certificate created successfully in Key Vault',
            'Failed to create certificate in Key Vault'
        )

        return create_output.success

    def _define_bicep_parameters(self) -> dict:
        base_params = super()._define_bicep_parameters()

        appgw_params = {
            'useACA': {'value': len(self.infra_apis) > 0 if self.infra_apis else False},
            'setCurrentUserAsKeyVaultAdmin': {'value': True},
            'currentUserId': {'value': self.current_user_id}
        }

        base_params.update(appgw_params)
        return base_params

    def deploy_infrastructure(self, is_update: bool = False) -> utils.Output:
        """
        Deploy the APPGW-APIM infrastructure with the required multi-step process.

        Args:
            is_update (bool): Whether this is an update to existing infrastructure or a new deployment.

        Returns:
            utils.Output: The deployment result.
        """
        action_verb = "Updating" if is_update else "Starting"
        print_plain(f'🚀 {action_verb} APPGW-APIM infrastructure deployment...\n')
        print_plain('   This deployment requires multiple steps:\n')
        print_plain('   1. Create Key Vault and self-signed certificate')
        print_plain('   2. Deploy infrastructure (APIM in VNet Internal mode)')

        # Step 1: Create Key Vault and certificate
        print_plain('\n📋 Step 1: Creating Key Vault and certificate...\n')
        key_vault_name = f'kv-{self.resource_suffix}'

        if not self._create_keyvault(key_vault_name):
            return utils.Output(False, 'Failed to create Key Vault')

        if not self._create_keyvault_certificate(key_vault_name):
            return utils.Output(False, 'Failed to create certificate in Key Vault')

        print_ok('Step 1: Key Vault and certificate creation completed', blank_above = True)

        # Step 2: Main deployment
        print_plain('\n📋 Step 2: Deploying infrastructure...\n')
        output = super().deploy_infrastructure(is_update)

        if not output.success:
            print_error('Deployment failed!')
            return output

        print_ok('Step 2: Deployment completed', blank_above = True)

        # Extract required values from deployment output
        if not output.json_data:
            print_error('No deployment output data available')
            return output

        self.appgw_domain_name = output.get('appGatewayDomainName', 'App Gateway Domain Name', suppress_logging = True)
        self.appgw_public_ip = output.get('appgwPublicIpAddress', 'App Gateway Public IP', suppress_logging = True)

        print_plain('\n📋 Final Configuration:\n')
        print_ok('Application Gateway deployed')
        print_ok('API Management deployed in VNet (Internal)')
        print_ok('No Private Endpoints used')
        print_info('Traffic flow: Internet → Application Gateway → APIM (VNet Internal)')

        print_plain('\n\n🧪 TESTING\n')
        print_plain('Using a self-signed certificate; test using curl with Host header against the App Gateway public IP. A 200 from the APIM health endpoint indicates success.')
        print_command(f'curl -v -k -H "Host: {self.appgw_domain_name}" https://{self.appgw_public_ip}/status-0123456789abcdef')

        return output


# ------------------------------
#    INFRASTRUCTURE CLEANUP FUNCTIONS
# ------------------------------

def _cleanup_single_resource(resource: dict) -> tuple[bool, str]:
    """
    Delete and purge a single Azure resource (worker function for parallel cleanup).

    This is the atomic unit of work that deletes and purges one resource.
    Called by _cleanup_resources_parallel() which manages multiple resources concurrently.

    Args:
        resource (dict): Resource information with keys: type, name, location, rg_name

    Returns:
        tuple[bool, str]: (success, error_message)
    """
    try:
        resource_type = resource['type']
        resource_name = resource['name']
        rg_name = resource['rg_name']
        location = resource['location']

        print_info(f"Deleting and purging {resource_type} '{resource_name}'...")

        # Delete the resource
        if resource_type == 'cognitiveservices':
            delete_cmd = f"az cognitiveservices account delete -g {rg_name} -n {resource_name}"
            purge_cmd = f"az cognitiveservices account purge -g {rg_name} -n {resource_name} --location \"{location}\""
        elif resource_type == 'apim':
            delete_cmd = f"az apim delete -n {resource_name} -g {rg_name} -y"
            purge_cmd = f"az apim deletedservice purge --service-name {resource_name} --location \"{location}\""
        elif resource_type == 'keyvault':
            delete_cmd = f"az keyvault delete -n {resource_name} -g {rg_name}"
            purge_cmd = f"az keyvault purge -n {resource_name} --location \"{location}\" --no-wait"
        else:
            return False, f"Unknown resource type: {resource_type}"

        # Execute delete
        output = az.run(delete_cmd, f"{resource_type} '{resource_name}' deleted", f"Failed to delete {resource_type} '{resource_name}'")
        if not output.success:
            return False, f"Delete failed for {resource_name}"

        # Execute purge
        output = az.run(purge_cmd, f"{resource_type} '{resource_name}' purged", f"Failed to purge {resource_type} '{resource_name}'")
        if not output.success:
            return False, f"Purge failed for {resource_name}"

        return True, ""

    except Exception as e:
        return False, str(e)

def _cleanup_resources_parallel(resources: list[dict], thread_prefix: str = '', thread_color: str = '') -> None:
    """
    Clean up multiple resources in parallel using ThreadPoolExecutor (orchestrator function).

    This function manages concurrent deletion and purging of Azure resources within a single resource group.
    Can operate in two modes: regular printing or thread-safe printing (for when multiple RGs are being cleaned in parallel).

    Args:
        resources (list[dict]): List of resources to clean up, each with keys: type, name, location, rg_name
        thread_prefix (str, optional): Prefix for thread-safe logging (empty = regular printing)
        thread_color (str, optional): ANSI color code for thread-safe logging
    """
    if not resources:
        return

    # Limit concurrent operations to avoid overwhelming Azure APIs
    max_workers = min(len(resources), 5)

    # Determine if we need thread-safe printing
    use_thread_safe_printing = bool(thread_prefix)

    # Helper function for thread-safe or regular printing
    def log_info(msg):
        if use_thread_safe_printing:
            with _print_lock:
                _print_log(f"{thread_prefix}{msg}", '👉 ', thread_color)
        else:
            print_info(msg)

    def log_success(msg):
        if use_thread_safe_printing:
            with _print_lock:
                _print_log(f"{thread_prefix}{msg}", '✅ ', thread_color, show_time=True)
        else:
            print_ok(msg)

    def log_error(msg):
        if use_thread_safe_printing:
            with _print_lock:
                _print_log(f"{thread_prefix}{msg}", '❌ ', BOLD_R)
        else:
            print_error(msg)

    def log_ok(msg):
        if use_thread_safe_printing:
            with _print_lock:
                _print_log(f"{thread_prefix}{msg}", '✅ ', thread_color)
        else:
            print_ok(msg)

    def log_warning(msg):
        if use_thread_safe_printing:
            with _print_lock:
                _print_log(f"{thread_prefix}{msg}", '⚠️ ', BOLD_Y)
        else:
            print_warning(msg)

    log_info(f'Starting parallel cleanup of {len(resources)} resource(s) with {max_workers} worker(s)...')

    completed_count = 0
    failed_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all cleanup tasks
        future_to_resource = {
            executor.submit(_cleanup_single_resource, resource): resource
            for resource in resources
        }

        # Wait for completion and track results
        for future in as_completed(future_to_resource):
            resource = future_to_resource[future]
            try:
                success, error_msg = future.result()
                completed_count += 1

                if success:
                    log_success(f"✓ Cleaned up {resource['type']} '{resource['name']}' ({completed_count}/{len(resources)})")
                else:
                    failed_count += 1
                    log_error(f"✗ Failed to clean up {resource['type']} '{resource['name']}': {error_msg}")

            except Exception as e:
                failed_count += 1
                log_error(f"✗ Exception cleaning up {resource['type']} '{resource['name']}': {str(e)}")

    # Summary
    if not failed_count:
        log_ok(f'All {len(resources)} resource(s) cleaned up successfully!')
    else:
        log_warning(f'Completed with {failed_count} failure(s) out of {len(resources)} total resources.')
        if completed_count - failed_count > 0:
            log_info(f'{completed_count - failed_count} resource(s) cleaned up successfully.')

def _cleanup_resources_parallel_thread_safe(resources: list[dict], thread_prefix: str, thread_color: str) -> None:
    """
    Convenience wrapper for parallel cleanup with thread-safe printing.

    Args:
        resources (list[dict]): List of resources to clean up
        thread_prefix (str): Thread prefix for output formatting
        thread_color (str): ANSI color code for this thread
    """
    _cleanup_resources_parallel(resources, thread_prefix, thread_color)

def _delete_resource_group_best_effort(
    rg_name: str,
    *,
    thread_prefix: str = '',
    thread_color: str = ''
) -> None:
    if not rg_name:
        return

    delete_cmd = f'az group delete --name {rg_name} -y --no-wait'

    if thread_prefix:
        with _print_lock:
            _print_log(f"{thread_prefix}Deleting resource group '{rg_name}'...", 'ℹ️ ', thread_color, show_time=True)
        try:
            az.run(
                delete_cmd,
                f"Initiated deletion of resource group '{rg_name}'",
                f"Failed to initiate deletion of resource group '{rg_name}'"
            )
        except Exception as e:  # pragma: no cover
            with _print_lock:
                _print_log(f"{thread_prefix}Failed to initiate deletion of resource group '{rg_name}': {e}", '❌ ', BOLD_R, show_time=True)
                if should_print_traceback():  # pragma: no cover
                    traceback.print_exc()
        return

    print_message(f"Deleting resource group '{rg_name}'...")
    try:
        az.run(
            delete_cmd,
            f"Initiated deletion of resource group '{rg_name}'",
            f"Failed to initiate deletion of resource group '{rg_name}'"
        )
    except Exception as e:
        print_plain(f"Failed to initiate deletion of resource group '{rg_name}': {e}")
        if should_print_traceback():  # pragma: no cover
            traceback.print_exc()

def _cleanup_resources(deployment_name: str, rg_name: str) -> None:
    """
    Clean up resources in a single resource group (main cleanup entry point for sequential mode).

    Lists all Azure resources (APIM, Key Vault, Cognitive Services) in a resource group,
    then deletes and purges them in parallel before removing the resource group itself.

    Args:
        deployment_name (str): The deployment name (string).
        rg_name (str): The resource group name.

    Returns:
        None

    Raises:
        Exception: If an error occurs during cleanup.
    """
    if not deployment_name:
        print_error('Missing deployment name parameter.')
        return

    if not rg_name:
        print_error('Missing resource group name parameter.')
        return

    rg_delete_attempted = False

    try:
        print_info(f'Resource group : {rg_name}')

        # Show the deployment details (if it exists)
        output = az.run(
            f'az deployment group show --name {deployment_name} -g {rg_name} -o json',
            'Deployment retrieved',
            'Deployment not found (may be empty resource group)'
        )

        # Collect all resources that need to be deleted and purged
        resources_to_cleanup = []

        # List CognitiveService accounts
        output = az.run(
            f'az cognitiveservices account list -g {rg_name}',
            'Listed CognitiveService accounts',
            'Failed to list CognitiveService accounts'
        )

        if output.success and output.json_data:
            for resource in output.json_data:
                resources_to_cleanup.append({
                    'type': 'cognitiveservices',
                    'name': resource['name'],
                    'location': resource['location'],
                    'rg_name': rg_name
                })

        # List APIM resources
        output = az.run(
            f'az apim list -g {rg_name}',
            'Listed APIM resources',
            'Failed to list APIM resources'
        )

        if output.success and output.json_data:
            for resource in output.json_data:
                resources_to_cleanup.append({
                    'type': 'apim',
                    'name': resource['name'],
                    'location': resource['location'],
                    'rg_name': rg_name
                })

        # List Key Vault resources
        output = az.run(
            f'az keyvault list -g {rg_name}',
            'Listed Key Vault resources',
            'Failed to list Key Vault resources'
        )

        if output.success and output.json_data:
            for resource in output.json_data:
                resources_to_cleanup.append({
                    'type': 'keyvault',
                    'name': resource['name'],
                    'location': resource['location'],
                    'rg_name': rg_name
                })

        # Delete and purge resources in parallel if there are any
        if resources_to_cleanup:
            print_info(f'Found {len(resources_to_cleanup)} resource(s) to clean up. Processing in parallel...')
            _cleanup_resources_parallel(resources_to_cleanup)
        else:
            print_info('No resources found to clean up.')

        # Delete the resource group last
        rg_delete_attempted = True
        _delete_resource_group_best_effort(rg_name)

        print_message('Cleanup completed.')

    except Exception as e:
        print_plain(f'An error occurred during cleanup: {e}')
        if should_print_traceback():  # pragma: no cover
            traceback.print_exc()

    finally:
        # Best-effort: always attempt RG deletion for the specified RG.
        # This ensures we don't leave orphaned RGs when earlier steps fail.
        if not rg_delete_attempted:
            _delete_resource_group_best_effort(rg_name)

def _cleanup_resources_thread_safe(deployment_name: str, rg_name: str, thread_prefix: str, thread_color: str) -> tuple[bool, str]:
    """
    Thread-safe wrapper for _cleanup_resources with formatted output.

    Args:
        deployment_name (str): The deployment name (string).
        rg_name (str): The resource group name.
        thread_prefix (str): The thread prefix for output formatting.
        thread_color (str): ANSI color code for this thread.

    Returns:
        tuple[bool, str]: (success, error_message)
    """
    try:
        with _print_lock:
            _print_log(f"{thread_prefix}Starting cleanup for resource group: {rg_name}", '👉 ', thread_color)

        # Create a modified version of _cleanup_resources that uses thread-safe printing
        _cleanup_resources_with_thread_safe_printing(deployment_name, rg_name, thread_prefix, thread_color)

        with _print_lock:
            _print_log(f"{thread_prefix}Completed cleanup for resource group: {rg_name}", '👉 ', thread_color)

        return True, ""

    except Exception as e:
        error_msg = f'An error occurred during cleanup of {rg_name}: {str(e)}'
        with _print_lock:
            _print_log(f"{thread_prefix}{error_msg}", '❌ ', BOLD_R, show_time=True)
            if should_print_traceback():  # pragma: no cover
                traceback.print_exc()
        return False, error_msg

def _cleanup_resources_with_thread_safe_printing(deployment_name: str, rg_name: str, thread_prefix: str, thread_color: str) -> None:
    """
    Clean up resources with thread-safe printing (internal implementation for parallel execution).
    This is a modified version of _cleanup_resources that uses thread-safe output and parallel resource cleanup.
    """
    if not deployment_name:
        with _print_lock:
            _print_log(f"{thread_prefix}Missing deployment name parameter.", '❌ ', BOLD_R)
        return

    if not rg_name:
        with _print_lock:
            _print_log(f"{thread_prefix}Missing resource group name parameter.", '❌ ', BOLD_R)
        return

    rg_delete_attempted = False

    try:
        with _print_lock:
            _print_log(f"{thread_prefix}Resource group : {rg_name}", '👉 ', thread_color)

        # Show the deployment details
        output = az.run(
            f'az deployment group show --name {deployment_name} -g {rg_name} -o json',
            'Deployment retrieved',
            'Failed to retrieve the deployment'
        )

        # Collect all resources that need to be deleted and purged
        resources_to_cleanup = []

        # List CognitiveService accounts
        output = az.run(
            f'az cognitiveservices account list -g {rg_name}',
            'Listed CognitiveService accounts',
            'Failed to list CognitiveService accounts'
        )

        if output.success and output.json_data:
            for resource in output.json_data:
                resources_to_cleanup.append({
                    'type': 'cognitiveservices',
                    'name': resource['name'],
                    'location': resource['location'],
                    'rg_name': rg_name
                })

        # List APIM resources
        output = az.run(
            f'az apim list -g {rg_name}',
            'Listed APIM resources',
            'Failed to list APIM resources'
        )

        if output.success and output.json_data:
            for resource in output.json_data:
                resources_to_cleanup.append({
                    'type': 'apim',
                    'name': resource['name'],
                    'location': resource['location'],
                    'rg_name': rg_name
                })

        # List Key Vault resources
        output = az.run(
            f'az keyvault list -g {rg_name}',
            'Listed Key Vault resources',
            'Failed to list Key Vault resources'
        )

        if output.success and output.json_data:
            for resource in output.json_data:
                resources_to_cleanup.append({
                    'type': 'keyvault',
                    'name': resource['name'],
                    'location': resource['location'],
                    'rg_name': rg_name
                })

        # Delete and purge resources in parallel if there are any
        if resources_to_cleanup:
            with _print_lock:
                _print_log(
                    f"{thread_prefix}Found {len(resources_to_cleanup)} resource(s) to clean up. Processing in parallel...",
                    '👉 ',
                    thread_color
                )
            _cleanup_resources_parallel_thread_safe(resources_to_cleanup, thread_prefix, thread_color)
        else:
            with _print_lock:
                _print_log(f"{thread_prefix}No resources found to clean up.", '👉 ', thread_color)

        # Delete the resource group last
        rg_delete_attempted = True
        _delete_resource_group_best_effort(rg_name, thread_prefix=thread_prefix, thread_color=thread_color)

        with _print_lock:
            _print_log(f"{thread_prefix}Cleanup completed.", 'ℹ️ ', thread_color, show_time=True)

    except Exception as e:
        with _print_lock:
            _print_log(f"{thread_prefix}An error occurred during cleanup: {e}", '❌ ', BOLD_R)
            if should_print_traceback():  # pragma: no cover
                traceback.print_exc()

    finally:
        # Best-effort: always attempt RG deletion for the specified RG.
        if not rg_delete_attempted:
            _delete_resource_group_best_effort(rg_name, thread_prefix=thread_prefix, thread_color=thread_color)

def cleanup_infra_deployments(deployment: INFRASTRUCTURE, indexes: int | list[int] | None = None) -> None:
    """
    Clean up infrastructure deployments by deployment enum and index/indexes.
    Obtains the infra resource group name for each index and calls the private cleanup method.
    For multiple indexes, runs cleanup operations in parallel for better performance.

    Args:
        deployment (INFRASTRUCTURE): The infrastructure deployment enum value.
        indexes (int | list[int] | None): A single index, a list of indexes, or None for no index.
    """

    if indexes is None:
        indexes_list = [None]
    elif isinstance(indexes, (list, tuple)):
        indexes_list = list(indexes)
    else:
        indexes_list = [indexes]

    # If only one index, run sequentially (no need for threading overhead)
    if len(indexes_list) <= 1:
        idx = indexes_list[0] if indexes_list else None
        print_info(f'Cleaning up resources for {deployment.value} - {idx}', True)
        rg_name = az.get_infra_rg_name(deployment, idx)
        _cleanup_resources(deployment.value, rg_name)
        return

    # For multiple indexes, run in parallel
    print_info(f'Starting parallel cleanup for {len(indexes_list)} infrastructure instances', True)
    print_val('Infrastructure', deployment.value)
    print_val('Indexes', indexes_list)
    print_plain('')

    # Determine max workers (reasonable limit to avoid overwhelming the system)
    max_workers = min(len(indexes_list), 4)  # Cap at 4 concurrent threads

    cleanup_tasks = []
    for i, idx in enumerate(indexes_list):
        rg_name = az.get_infra_rg_name(deployment, idx)
        thread_color = THREAD_COLORS[i % len(THREAD_COLORS)]
        thread_prefix = f"{thread_color}[{deployment.value}-{idx}]{RESET}: "

        cleanup_tasks.append({
            'deployment_name': deployment.value,
            'rg_name': rg_name,
            'thread_prefix': thread_prefix,
            'thread_color': thread_color,
            'index': idx
        })

    # Execute cleanup tasks in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(
                _cleanup_resources_thread_safe,
                task['deployment_name'],
                task['rg_name'],
                task['thread_prefix'],
                task['thread_color']
            ): task for task in cleanup_tasks
        }

        # Track results
        completed_count = 0
        failed_count = 0

        # Wait for completion and handle results
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                success, error_msg = future.result()
                completed_count += 1

                if success:
                    with _print_lock:
                        print_ok(f"Completed cleanup for {deployment.value}-{task['index']} ({completed_count}/{len(indexes_list)})")
                else:
                    failed_count += 1
                    with _print_lock:
                        print_error(f"Failed cleanup for {deployment.value}-{task['index']}: {error_msg}")

            except Exception as e:  # pragma: no cover
                failed_count += 1
                with _print_lock:
                    print_error(f"Exception during cleanup for {deployment.value}-{task['index']}: {str(e)}")

    # Final summary
    if not failed_count:
        print_ok(f'All {len(indexes_list)} infrastructure cleanups completed successfully!')
    else:
        print_warning(f'Completed with {failed_count} failures out of {len(indexes_list)} total cleanups.')
        if completed_count > 0:
            print_info(f'{completed_count} cleanups succeeded.')

    print_ok('All done!')
