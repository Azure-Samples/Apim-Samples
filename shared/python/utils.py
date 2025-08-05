"""
Module providing utility functions.
"""

import ast
import datetime
import json
import os
import re
import subprocess
import textwrap
import time
import traceback
import string
import secrets
import base64
import inspect
from pathlib import Path

from typing import Any, Optional, Tuple
from apimtypes import APIM_SKU, HTTP_VERB, INFRASTRUCTURE


# ------------------------------
#    DECLARATIONS
# ------------------------------


# Define ANSI escape code constants for clarity in the print commands below
BOLD_B = '\x1b[1;34m'   # blue
BOLD_G = '\x1b[1;32m'   # green
BOLD_R = '\x1b[1;31m'   # red
BOLD_Y = '\x1b[1;33m'   # yellow
RESET  = '\x1b[0m'

CONSOLE_WIDTH = 175


# ------------------------------
#    HELPER FUNCTIONS
# ------------------------------

def build_infrastructure_tags(infrastructure: str | INFRASTRUCTURE, custom_tags: dict | None = None) -> dict:
    """
    Build standard tags for infrastructure resource groups, including required 'infrastructure' and infrastructure name tags.
    
    Args:
        infrastructure (str | INFRASTRUCTURE): The infrastructure type/name.
        custom_tags (dict, optional): Additional custom tags to include.
    
    Returns:
        dict: Combined tags dictionary with standard and custom tags.
    """
    
    # Convert infrastructure enum to string value if needed
    if hasattr(infrastructure, 'value'):
        infra_name = infrastructure.value
    else:
        infra_name = str(infrastructure)
    
    # Build standard tags
    standard_tags = {
        'infrastructure': infra_name
    }
    
    # Add custom tags if provided
    if custom_tags:
        standard_tags.update(custom_tags)
    
    return standard_tags


# ------------------------------
#    CLASSES
# ------------------------------

class Output(object):
    """
    Represents the output of a command or deployment, including success status, raw text, and parsed JSON data.
    """

    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, success: bool, text: str):
        """
        Initialize the Output object with command success status and output text.
        Attempts to parse JSON from the output text.
        """

        self.success = success
        self.text = text
        self.jsonParseException = None

        # Check if the exact string is JSON. 
        if (is_string_json(text)):
            try:
                self.json_data = json.loads(text)
            except json.JSONDecodeError as e:
                self.jsonParseException = e
                self.json_data = extract_json(text)
        else:
            # Check if a substring in the string is JSON.
            self.json_data = extract_json(text)

        self.is_json = self.json_data is not None

    def get(self, key: str, label: str = '', secure: bool = False, suppress_logging: bool = False) -> str | None:
        """
        Retrieve a deployment output property by key, with optional label and secure masking.

        Args:
            key (str): The output key to retrieve.
            label (str, optional): Optional label for logging.
            secure (bool, optional): If True, masks the value in logs.

        Returns:
            str | None: The value as a string, or None if not found.
        """

        try:
            if not isinstance(self.json_data, dict):
                raise KeyError('json_data is not a dict')

            if 'properties' in self.json_data:
                properties = self.json_data.get('properties')
                if not isinstance(properties, dict):
                    raise KeyError("'properties' is not a dict in deployment result")

                outputs = properties.get('outputs')
                if not isinstance(outputs, dict):
                    raise KeyError("'outputs' is missing or not a dict in deployment result")

                output_entry = outputs.get(key)
                if not isinstance(output_entry, dict) or 'value' not in output_entry:
                    raise KeyError(f"Output key '{key}' not found in deployment outputs")

                deployment_output = output_entry['value']
            elif key in self.json_data:
                deployment_output = self.json_data[key]['value']

            if not suppress_logging and label:
                if secure and isinstance(deployment_output, str) and len(deployment_output) >= 4:
                    print_val(label, f'****{deployment_output[-4:]}')
                else:
                    print_val(label, deployment_output)

            return str(deployment_output)

        except Exception as e:
            error = f"Failed to retrieve output property: '{key}'\nError: {e}"
            print_error(error)

            if label:
                raise Exception(error)

            return None

    def getJson(self, key: str, label: str = '', secure: bool = False, suppress_logging: bool = False) -> Any:
        """
        Retrieve a deployment output property by key and return it as a JSON object.
        This method is independent from get() and retrieves the raw deployment output value.

        Args:
            key (str): The output key to retrieve.
            label (str, optional): Optional label for logging.
            secure (bool, optional): If True, masks the value in logs.

        Returns:
            Any: The value as a JSON object (dict, list, etc.), or the original value if not JSON, or None if not found.
        """

        try:
            if not isinstance(self.json_data, dict):
                raise KeyError('json_data is not a dict')

            if 'properties' in self.json_data:
                properties = self.json_data.get('properties')
                if not isinstance(properties, dict):
                    raise KeyError("'properties' is not a dict in deployment result")

                outputs = properties.get('outputs')
                if not isinstance(outputs, dict):
                    raise KeyError("'outputs' is missing or not a dict in deployment result")

                output_entry = outputs.get(key)
                if not isinstance(output_entry, dict) or 'value' not in output_entry:
                    raise KeyError(f"Output key '{key}' not found in deployment outputs")

                deployment_output = output_entry['value']
            elif key in self.json_data:
                deployment_output = self.json_data[key]['value']

            if not suppress_logging and label:
                if secure and isinstance(deployment_output, str) and len(deployment_output) >= 4:
                    print_val(label, f'****{deployment_output[-4:]}')
                else:
                    print_val(label, deployment_output)

            # If the result is a string, try to parse it as JSON
            if isinstance(deployment_output, str):
                # First try JSON parsing (handles double quotes)
                try:
                    return json.loads(deployment_output)
                except json.JSONDecodeError:
                    pass

                # If JSON fails, try Python literal evaluation (handles single quotes)
                try:
                    return ast.literal_eval(deployment_output)
                except (ValueError, SyntaxError) as e:
                    print_error(f'Failed to parse deployment output as Python literal. Error: {e}')
                    pass

            # Return the original result if it's not a string or can't be parsed
            return deployment_output

        except Exception as e:
            error = f"Failed to retrieve output property: '{key}'\nError: {e}"
            print_error(error)

            if label:
                raise Exception(error)

            return None

class InfrastructureNotebookHelper:
    """
    Helper class for managing infrastructure notebooks.
    Provides methods to execute infrastructure creation notebooks and handle outputs.
    """

    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, rg_location: str, deployment: INFRASTRUCTURE, index: int, apim_sku: APIM_SKU):
        """
        Initialize the InfrastructureNotebookHelper.
        
        Args:
            rg_location (str): Azure region for deployment.
            deployment (INFRASTRUCTURE): Infrastructure type to deploy.
            index (int): Index for multi-instance deployments.
            apim_sku (APIM_SKU): SKU for API Management service.
        """

        self.rg_location = rg_location
        self.deployment = deployment
        self.index = index
        self.apim_sku = apim_sku

    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def create_infrastructure(self, bypass_infrastructure_check: bool = False) -> bool:
        """
        Create infrastructure by executing the appropriate creation script.
        
        Args:
            bypass_infrastructure_check (bool): Skip infrastructure existence check. Defaults to False.
            
        Returns:
            bool: True if infrastructure creation succeeded, False otherwise.
        """

        import sys 

        if bypass_infrastructure_check or not does_infrastructure_exist(self.deployment, self.index):
            # Map infrastructure types to their folder names
            infra_folder_map = {
                INFRASTRUCTURE.SIMPLE_APIM: 'simple-apim',
                INFRASTRUCTURE.AFD_APIM_PE: 'afd-apim-pe', 
                INFRASTRUCTURE.APIM_ACA: 'apim-aca'
            }
            
            infra_folder = infra_folder_map.get(self.deployment)
            if not infra_folder:
                print(f'❌ Unsupported infrastructure type: {self.deployment.value}')
                return False
            
            # Build the command to call the infrastructure creation script
            cmd_args = [
                sys.executable, 
                os.path.join(find_project_root(), 'infrastructure', infra_folder, 'create_infrastructure.py'),
                '--location', self.rg_location,
                '--sku', str(self.apim_sku.value),
                '--index', str(self.index)
            ]

            # Execute the infrastructure creation script with real-time output streaming and UTF-8 encoding to handle Unicode characters properly
            process = subprocess.Popen(cmd_args, stdout = subprocess.PIPE, stderr = subprocess.STDOUT, text = True, 
                                    bufsize = 1, universal_newlines = True, encoding = 'utf-8', errors = 'replace')

            try:
                # Stream output in real-time
                for line in process.stdout:
                    print(line.rstrip())
            except Exception as e:
                print(f'Error reading subprocess output: {e}')
                
            # Wait for process to complete
            process.wait()

            return process.returncode == 0

        return True
        
class NotebookHelper:
    """
    Helper class for managing sample notebook deployments and infrastructure interaction.
    """

    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, sample_folder: str, rg_name: str, rg_location: str, deployment: INFRASTRUCTURE, supported_infrastructures = list[INFRASTRUCTURE], use_jwt: bool = False, index: int = 1, is_debug = False):
        """
        Initialize the NotebookHelper with sample configuration and infrastructure details.
        
        Args:
            sample_folder (str): The name of the sample folder.
            rg_name (str): The name of the resource group associated with the notebook.
            rg_location (str): The Azure region for deployment.
            deployment (INFRASTRUCTURE): The infrastructure type to use.
            supported_infrastructures (list[INFRASTRUCTURE]): List of supported infrastructure types.
            use_jwt (bool): Whether to generate JWT tokens. Defaults to False.
            index (int): Index for multi-instance deployments. Defaults to 1.
            is_debug (bool): Whether to enable debug mode. Defaults to False.
        """

        self.sample_folder = sample_folder
        self.rg_name = rg_name
        self.rg_location = rg_location
        self.deployment = deployment
        self.supported_infrastructures = supported_infrastructures
        self.use_jwt = use_jwt
        self.index = index
        self.is_debug = is_debug

        validate_infrastructure(deployment, supported_infrastructures)

        if use_jwt:
            self._create_jwt()

    # ------------------------------
    #    PRIVATE METHODS
    # ------------------------------

    def _create_jwt(self) -> None:
        """Create JWT signing key and values for the sample."""

        # Set up the signing key for the JWT policy
        self.jwt_key_name = f'JwtSigningKey-{self.sample_folder}-{int(time.time())}'
        self.jwt_key_value, self.jwt_key_value_bytes_b64 = generate_signing_key()
        print_val('JWT key value', self.jwt_key_value)                    # this value is used to create the signed JWT token for requests to APIM
        print_val('JWT key value (base64)', self.jwt_key_value_bytes_b64) # this value is used in the APIM validate-jwt policy's issuer-signing-key attribute  

    def _get_current_index(self) -> int | None:
        """
        Extract the index from the current resource group name.
        
        Returns:
            int | None: The index if it exists, None otherwise.
        """

        prefix = f'apim-infra-{self.deployment.value}'
        
        if self.rg_name == prefix:
            return None
        elif self.rg_name.startswith(f'{prefix}-'):
            try:
                index_str = self.rg_name[len(f'{prefix}-'):]
                return int(index_str)
            except ValueError:
                return None

        return None

    def _clean_up_jwt(self, apim_name: str) -> None:
        """Clean up old JWT signing keys after successful deployment."""

        # Clean up old JWT signing keys after successful deployment
        if not cleanup_old_jwt_signing_keys(apim_name, self.rg_name, self.jwt_key_name):
            print_warning('JWT key cleanup failed, but deployment was successful. Old keys may need manual cleanup.')

    def _query_and_select_infrastructure(self) -> tuple[INFRASTRUCTURE | None, int | None]:
        """
        Query for available infrastructures and allow user to select one or create new infrastructure.
        
        Returns:
            tuple: (selected_infrastructure, selected_index) or (None, None) if no valid option
        """
        
        # SJK: Querying the resource group location is inefficient at this time as it's done sequentially. 
        # I'm leaving the code here, but may revisit it later.
        QUERY_RG_LOCATION = False

        print('Querying for available infrastructures...\n')
        
        # Get all resource groups that match the infrastructure pattern
        available_options = []
        
        for infra in self.supported_infrastructures:
            infra_options = self._find_infrastructure_instances(infra)
            available_options.extend(infra_options)
        
        # Check if the desired infrastructure/index combination exists
        desired_rg_name = get_infra_rg_name(self.deployment, self._get_current_index())
        desired_exists = any(
            get_infra_rg_name(infra, idx) == desired_rg_name 
            for infra, idx in available_options
        )
        
        if desired_exists:
            # Scenario 1: Desired infrastructure exists, use it directly
            print_success(f'Found desired infrastructure: {self.deployment.value} with resource group {desired_rg_name}')
            return self.deployment, self._get_current_index()
        
        # Sort available options by infrastructure type, then by index
        available_options.sort(key = lambda x: (x[0].value, x[1] if x[1] is not None else 0))
        
        # Prepare display options
        display_options = []
        option_counter = 1
        
        # Add existing infrastructure options
        if available_options:
            print_info(f'Found {len(available_options)} existing infrastructure(s). You can either create a new one or select an existing one.')
            
            # ALWAYS make "Create a NEW infrastructure" the first option for consistency
            desired_index_str = self._get_current_index() if self._get_current_index() is not None else 'N/A'
            desired_location = self.rg_location
            
            print(f'\n   Create a NEW infrastructure:\n')
            # Column headers
            if QUERY_RG_LOCATION:
                print(f'     {'#':>3} {'Infrastructure':<20} {'Index':>8} {'Resource Group':<35} {'Location':<15}')
                print(f'     {'-'*3:>3} {'-'*20:<20} {'-'*8:>8} {'-'*35:<35} {'-'*15:<15}')
                print(f'     {option_counter:>3} {self.deployment.value:<20} {desired_index_str:>8} {desired_rg_name:<35} {desired_location:<15}')
            else: 
                print(f'     {'#':>3} {'Infrastructure':<20} {'Index':>8} {'Resource Group':<35}')
                print(f'     {'-'*3:>3} {'-'*20:<20} {'-'*8:>8} {'-'*35:<35}')
                print(f'     {option_counter:>3} {self.deployment.value:<20} {desired_index_str:>8} {desired_rg_name:<35}')

            display_options.append(('create_new', self.deployment, self._get_current_index()))
            option_counter += 1
            
            print(f'\n   Or select an EXISTING infrastructure:\n')
            # Column headers
            if QUERY_RG_LOCATION:
                print(f'     {'#':>3} {'Infrastructure':<20} {'Index':>8} {'Resource Group':<35} {'Location':<15}')
                print(f'     {'-'*3:>3} {'-'*20:<20} {'-'*8:>8} {'-'*35:<35} {'-'*15:<15}')
            else:
                print(f'     {'#':>3} {'Infrastructure':<20} {'Index':>8} {'Resource Group':<35}')
                print(f'     {'-'*3:>3} {'-'*20:<20} {'-'*8:>8} {'-'*35:<35}')
            
            for infra, index in available_options:
                index_str = index if index is not None else 'N/A'
                rg_name = get_infra_rg_name(infra, index)
                
                if QUERY_RG_LOCATION:
                    rg_location = get_resource_group_location(rg_name)
                    print(f'     {option_counter:>3} {infra.value:<20} {index_str:>8} {rg_name:<35} {rg_location:<15}')
                else:
                    print(f'     {option_counter:>3} {infra.value:<20} {index_str:>8} {rg_name:<35}')

                display_options.append(('existing', infra, index))
                option_counter += 1
        else:
            print_warning('No existing supported infrastructures found.')
            print_info(f'Automatically proceeding to create new infrastructure: {self.deployment.value}')
            
            # Automatically create the desired infrastructure without user confirmation
            selected_index = self._get_current_index()
            print_info(f'Creating new infrastructure: {self.deployment.value}{' (index: ' + str(selected_index) + ')' if selected_index is not None else ''}')
            
            # Execute the infrastructure creation
            inb_helper = InfrastructureNotebookHelper(self.rg_location, self.deployment, selected_index, APIM_SKU.BASICV2)
            success = inb_helper.create_infrastructure(True)  # Bypass infrastructure check to force creation

            if success:
                print_success(f'Successfully created infrastructure: {self.deployment.value}{' (index: ' + str(selected_index) + ')' if selected_index is not None else ''}')
                return self.deployment, selected_index
            else:
                print_error('Failed to create infrastructure.')
                return None, None
        
        print('')
        
        # Get user selection
        while True:
            try:
                choice = input(f'Select infrastructure (1-{len(display_options)}) or press Enter to exit: ').strip()
                
                if not choice:
                    print_warning('No infrastructure selected. Exiting.')
                    return None, None
                
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(display_options):
                    option_type, selected_infra, selected_index = display_options[choice_idx]
                    
                    if option_type == 'existing':
                        print_success(f'Selected existing: {selected_infra.value}{' (index: ' + str(selected_index) + ')' if selected_index is not None else ''}')
                        return selected_infra, selected_index
                    elif option_type == 'create_new':
                        print_info(f'Creating new infrastructure: {selected_infra.value}{' (index: ' + str(selected_index) + ')' if selected_index is not None else ''}')
                        
                        # Execute the infrastructure creation
                        inb_helper = InfrastructureNotebookHelper(self.rg_location, self.deployment, selected_index, APIM_SKU.BASICV2)
                        success = inb_helper.create_infrastructure(True)  # Bypass infrastructure check to force creation

                        if success:
                            print_success(f'Successfully created infrastructure: {selected_infra.value}{' (index: ' + str(selected_index) + ')' if selected_index is not None else ''}')
                            return selected_infra, selected_index
                        else:
                            print_error('Failed to create infrastructure.')
                            return None, None
                else:
                    print_error(f'Invalid choice. Please enter a number between 1 and {len(display_options)}.')
                    
            except ValueError:
                print_error('Invalid input. Please enter a number.')
            except KeyboardInterrupt:
                print_warning('\nOperation cancelled by user.')
                return None, None

    def _find_infrastructure_instances(self, infrastructure: INFRASTRUCTURE) -> list[tuple[INFRASTRUCTURE, int | None]]:
        """
        Find all instances of a specific infrastructure type by querying Azure resource groups.
        
        Args:
            infrastructure (INFRASTRUCTURE): The infrastructure type to search for.
            
        Returns:
            list: List of tuples (infrastructure, index) for found instances.
        """
        
        instances = []
        
        # Query Azure for resource groups with the infrastructure tag
        query_cmd = f'az group list --tag infrastructure={infrastructure.value} --query "[].name" -o tsv'
        output = run(query_cmd, print_command_to_run = False, print_errors = False)
        
        if output.success and output.text.strip():
            rg_names = [name.strip() for name in output.text.strip().split('\n') if name.strip()]
            
            for rg_name in rg_names:
                # Parse the resource group name to extract the index
                # Expected format: apim-infra-{infrastructure}-{index} or apim-infra-{infrastructure}
                prefix = f'apim-infra-{infrastructure.value}'
                
                if rg_name == prefix:
                    # No index
                    instances.append((infrastructure, None))
                elif rg_name.startswith(prefix + '-'):
                    # Has index
                    try:
                        index_str = rg_name[len(prefix + '-'):]
                        index = int(index_str)
                        instances.append((infrastructure, index))
                    except ValueError:
                        # Invalid index format, skip
                        continue
        
        return instances

    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def deploy_sample(self, bicep_parameters: dict) -> Output:
        """
        Deploy a sample with infrastructure auto-detection and selection.
        
        Args:
            bicep_parameters (dict): Parameters for the Bicep template deployment.
            
        Returns:
            Output: The deployment result.
        """

        # Check infrastructure availability and let user select or create
        print(f'Checking desired infrastructure availability...\n')
        print(f'   Infrastructure : {self.deployment.value}')
        print(f'   Index          : {self.index}')
        print(f'   Resource group : {self.rg_name}\n')

        # Call the resource group existence check only once
        rg_exists = does_resource_group_exist(self.rg_name)

        # If the desired infrastructure doesn't exist, use the interactive selection process
        if not rg_exists:
            print_info('Desired infrastructure does not exist.\n')
            
            # Check if we've already done infrastructure selection (prevent double execution)
            if 'infrastructure_selection_completed' not in globals():
                # Use the NotebookHelper's infrastructure selection process
                selected_deployment, selected_index = self._query_and_select_infrastructure()
                
                if selected_deployment is None:
                    raise SystemExit(1)
                
                # Update the notebook helper with the selected infrastructure
                self.deployment = selected_deployment
                self.index = selected_index
                self.rg_name = get_infra_rg_name(self.deployment, self.index)
                
                # Verify the updates were applied correctly
                print(f'📝 Updated infrastructure variables')
            else:
                print('✅ Infrastructure selection already completed in this session')
        else:
            print('✅ Desired infrastructure already exists, proceeding with sample deployment')

        # Deploy the sample APIs to the selected infrastructure
        print(f'\nDeploying sample to:\n')
        print(f'   Infrastructure : {self.deployment.value}')
        print(f'   Index          : {self.index}')
        print(f'   Resource group : {self.rg_name}\n')

        # Execute the deployment using the utility function that handles working directory management
        output = create_bicep_deployment_group_for_sample(self.sample_folder, self.rg_name, self.rg_location, bicep_parameters, is_debug = self.is_debug)

        # Print a deployment summary, if successful; otherwise, exit with an error
        if output.success:
            if self.use_jwt:
                apim_name = output.get('apimServiceName')
                self._clean_up_jwt(apim_name)
                    
            print_success('Deployment succeeded', blank_above = True)
        else:
            raise SystemExit('Deployment failed')

        return output



# ------------------------------
#    PRIVATE METHODS
# ------------------------------

def _cleanup_resources(deployment_name: str, rg_name: str) -> None:
    """
    Clean up resources associated with a deployment in a resource group.
    Deletes and purges Cognitive Services, API Management, and Key Vault resources, then deletes the resource group itself.

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

    try:
        print_info(f'Resource group : {rg_name}')

        # Show the deployment details
        output = run(f'az deployment group show --name {deployment_name} -g {rg_name} -o json', 'Deployment retrieved', 'Failed to retrieve the deployment', print_command_to_run = False)

        if output.success and output.json_data:
            # provisioning_state = output.json_data.get('properties').get('provisioningState')
            # print_info(f'Deployment provisioning state: {provisioning_state}')

            # Delete and purge CognitiveService accounts
            output = run(f' az cognitiveservices account list -g {rg_name}', f'Listed CognitiveService accounts', f'Failed to list CognitiveService accounts', print_command_to_run = False)

            if output.success and output.json_data:
                for resource in output.json_data:
                    print_info(f"Deleting and purging Cognitive Service Account '{resource['name']}'...")
                    output = run(f"az cognitiveservices account delete -g {rg_name} -n {resource['name']}", f"Cognitive Services '{resource['name']}' deleted", f"Failed to delete Cognitive Services '{resource['name']}'", print_command_to_run = False)
                    output = run(f"az cognitiveservices account purge -g {rg_name} -n {resource['name']} --location \"{resource['location']}\"", f"Cognitive Services '{resource['name']}' purged", f"Failed to purge Cognitive Services '{resource['name']}'", print_command_to_run = False)

            # Delete and purge APIM resources
            output = run(f' az apim list -g {rg_name}', f'Listed APIM resources', f'Failed to list APIM resources', print_command_to_run = False)

            if output.success and output.json_data:
                for resource in output.json_data:
                    print_info(f"Deleting and purging API Management '{resource['name']}'...")
                    output = run(f"az apim delete -n {resource['name']} -g {rg_name} -y", f"API Management '{resource['name']}' deleted", f"Failed to delete API Management '{resource['name']}'", print_command_to_run = False)
                    output = run(f"az apim deletedservice purge --service-name {resource['name']} --location \"{resource['location']}\"", f"API Management '{resource['name']}' purged", f"Failed to purge API Management '{resource['name']}'", print_command_to_run = False)

            # Delete and purge Key Vault resources
            output = run(f' az keyvault list -g {rg_name}', f'Listed Key Vault resources', f'Failed to list Key Vault resources', print_command_to_run = False)
            
            if output.success and output.json_data:
                for resource in output.json_data:
                    print_info(f"Deleting and purging Key Vault '{resource['name']}'...")
                    output = run(f"az keyvault delete -n {resource['name']} -g {rg_name}", f"Key Vault '{resource['name']}' deleted", f"Failed to delete Key Vault '{resource['name']}'", print_command_to_run = False)
                    output = run(f"az keyvault purge -n {resource['name']} --location \"{resource['location']}\"", f"Key Vault '{resource['name']}' purged", f"Failed to purge Key Vault '{resource['name']}'", print_command_to_run = False)

            # Delete the resource group last
            print_message(f"Deleting resource group '{rg_name}'...")
            output = run(f'az group delete --name {rg_name} -y', f"Resource group '{rg_name}' deleted', f'Failed to delete resource group '{rg_name}'", print_command_to_run = False)

            print_message('Cleanup completed.')

    except Exception as e:
        print(f'An error occurred during cleanup: {e}')
        traceback.print_exc()

def _print_log(message: str, prefix: str = '', color: str = '', output: str = '', duration: str = '', show_time: bool = False, blank_above: bool = False, blank_below: bool = False, wrap_lines: bool = False) -> None:
    """
    Print a formatted log message with optional prefix, color, output, duration, and time.
    Handles blank lines above and below the message for readability.

    Args:
        message (str): The message to print.
        prefix (str, optional): Prefix for the message.
        color (str, optional): ANSI color code.
        output (str, optional): Additional output to append.
        duration (str, optional): Duration string to append.
        show_time (bool, optional): Whether to show the current time.
        blank_above (bool, optional): Whether to print a blank line above.
        blank_below (bool, optional): Whether to print a blank line below.
        wrap_lines (bool, optional): Whether to wrap lines to fit console width.
    """
    time_str    = f' ⌚ {datetime.datetime.now().time()}' if show_time else ''
    output_str  = f' {output}' if output else ''

    if blank_above:
        print()

    # To preserve explicit newlines in the message (e.g., from print_val with val_below=True),
    # split the message on actual newlines and wrap each line separately, preserving blank lines and indentation.
    full_message = f'{prefix}{color}{message}{RESET}{time_str} {duration}{output_str}'
    lines = full_message.splitlines(keepends = False)

    for line in lines:
        if (wrap_lines):
            wrapped = textwrap.fill(line, width = CONSOLE_WIDTH)
            print(wrapped)
        else:
            print(line)

    if blank_below:
        print()


def _determine_bicep_directory(infrastructure_dir: str) -> str:
    """
    Determine the correct Bicep directory based on the current working directory and infrastructure directory name.
    
    This function implements the following logic:
    1. If current directory contains main.bicep, use current directory (for samples)
    2. If current directory name matches infrastructure_dir, use current directory (for infrastructure)
    3. Look for infrastructure/{infrastructure_dir} relative to current directory
    4. Look for infrastructure/{infrastructure_dir} relative to parent directory
    5. Try to find project root and construct path from there
    6. Fall back to current directory + infrastructure/{infrastructure_dir}
    
    Args:
        infrastructure_dir (str): The name of the infrastructure directory to find.
        
    Returns:
        str: The path to the directory containing the main.bicep file.
    """
    current_dir = os.getcwd()
    
    # First, check if there's a main.bicep file in the current directory (for samples)
    if os.path.exists(os.path.join(current_dir, 'main.bicep')):
        return current_dir
    
    # Check if we're already in the correct infrastructure directory
    if os.path.basename(current_dir) == infrastructure_dir:
        return current_dir
    
    # Look for the infrastructure directory from the current location
    bicep_dir = os.path.join(current_dir, 'infrastructure', infrastructure_dir)
    if os.path.exists(bicep_dir):
        return bicep_dir
    
    # If that doesn't exist, try going up one level and looking again
    parent_dir = os.path.dirname(current_dir)
    bicep_dir = os.path.join(parent_dir, 'infrastructure', infrastructure_dir)
    if os.path.exists(bicep_dir):
        return bicep_dir
    
    # Try to find the project root and construct the path from there
    try:
        from apimtypes import _get_project_root
        project_root = _get_project_root()
        bicep_dir = os.path.join(str(project_root), 'infrastructure', infrastructure_dir)
        if os.path.exists(bicep_dir):
            return bicep_dir
    except Exception:
        pass
    
    # Fall back to current directory + infrastructure/{infrastructure_dir}
    return os.path.join(current_dir, 'infrastructure', infrastructure_dir)


# ------------------------------
#    PUBLIC METHODS
# ------------------------------

print_command   = lambda cmd = ''                                               : _print_log(cmd, '⚙️ ', BOLD_B)
print_error     = lambda msg, output = '', duration = ''                        : _print_log(msg, '⛔ ', BOLD_R, output, duration, True)
print_info      = lambda msg, blank_above = False                               : _print_log(msg, '👉🏽 ', BOLD_B, blank_above = blank_above)
print_message   = lambda msg, output = '', duration = '', blank_above = False   : _print_log(msg, 'ℹ️ ', BOLD_G, output, duration, True, blank_above)
print_ok        = lambda msg, output = '', duration = '', blank_above = True    : _print_log(msg, '✅ ', BOLD_G, output, duration, True, blank_above)
print_success   = lambda msg, output = '', duration = '', blank_above = False   : _print_log(msg, '✅ ', BOLD_G, output, duration, True, blank_above)
print_warning   = lambda msg, output = '', duration = ''                        : _print_log(msg, '⚠️ ', BOLD_Y, output, duration, True)
print_val       = lambda name, value, val_below = False                         : _print_log(f"{name:<25}:{'\n' if val_below else ' '}{value}", '👉🏽 ', BOLD_B)
print_header    = lambda msg                                                    : _print_log(f"\n{'=' * len(msg)}\n{msg}\n{'=' * len(msg)}", '', BOLD_G, blank_above=True, blank_below=True)


def get_azure_role_guid(role_name: str) -> Optional[str]:
    """
    Load the Azure roles JSON file and return the GUID for the specified role name.
    
    Args:
        role_name (str): The name of the Azure role (e.g., 'StorageBlobDataReader').
        
    Returns:
        Optional[str]: The GUID of the role if found, None if not found or file cannot be loaded.
    """
    try:
        # Get the directory of the current script to build the path to azure-roles.json
        current_dir = os.path.dirname(os.path.abspath(__file__))
        roles_file_path = os.path.join(current_dir, '..', 'azure-roles.json')
        
        # Normalize the path for cross-platform compatibility
        roles_file_path = os.path.normpath(roles_file_path)
        
        # Load the JSON file
        with open(roles_file_path, 'r', encoding='utf-8') as file:
            roles_data: dict[str, str] = json.load(file)
        
        # Return the GUID for the specified role name
        return roles_data.get(role_name)
        
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        print_error(f'Failed to load Azure roles from {roles_file_path}: {str(e)}')
        
        return None


def create_bicep_deployment_group(rg_name: str, rg_location: str, deployment: str | INFRASTRUCTURE, bicep_parameters: dict, bicep_parameters_file: str = 'params.json', rg_tags: dict | None = None, is_debug: bool = False) -> Output:
    """
    Create a Bicep deployment in a resource group, writing parameters to a file and running the deployment.
    Creates the resource group if it does not exist.

    Args:
        rg_name (str): Name of the resource group.
        rg_location (str): Azure region for the resource group.
        deployment (str | INFRASTRUCTURE): Deployment name or enum value.
        bicep_parameters: Parameters for the Bicep template.
        bicep_parameters_file (str, optional): File to write parameters to.
        rg_tags (dict, optional): Additional tags to apply to the resource group.
        is_debug (bool, optional): Whether to enable debug mode. Defaults to False.

    Returns:
        Output: The result of the deployment command.
    """

    # Create the resource group if doesn't exist
    create_resource_group(rg_name, rg_location, rg_tags)

    if hasattr(deployment, 'value'):
        deployment_name = deployment.value
    else:
        deployment_name = deployment

    bicep_parameters_format = {
        '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#',
        'contentVersion': '1.0.0.0',
        'parameters': bicep_parameters
    }

    # Determine the correct deployment name and find the Bicep directory
    if hasattr(deployment, 'value'):
        deployment_name = deployment.value
        infrastructure_dir = deployment.value
    else:
        deployment_name = deployment
        infrastructure_dir = deployment
    
    # Use helper function to determine the correct Bicep directory
    bicep_dir = _determine_bicep_directory(infrastructure_dir)
    
    main_bicep_path = os.path.join(bicep_dir, 'main.bicep')
    params_file_path = os.path.join(bicep_dir, bicep_parameters_file)

    # Write the updated bicep parameters to the specified parameters file
    with open(params_file_path, 'w') as file:
        file.write(json.dumps(bicep_parameters_format))

    print(f'📝 Updated the policy XML in the bicep parameters file {bicep_parameters_file}')
    
    # Verify that main.bicep exists in the infrastructure directory
    if not os.path.exists(main_bicep_path):
        raise FileNotFoundError(f'main.bicep file not found in expected infrastructure directory: {bicep_dir}')

    cmd = f'az deployment group create --name {deployment_name} --resource-group {rg_name} --template-file "{main_bicep_path}" --parameters "{params_file_path}" --query "properties.outputs"'

    if is_debug:
        cmd += ' --debug'

    print('\nDeploying bicep...\n')
    return run(cmd, f"Deployment '{deployment_name}' succeeded", f"Deployment '{deployment_name}' failed.", print_command_to_run = False)


# TODO: Reconcile this with apimtypes.py _get_project_root
def find_project_root() -> str:
    """
    Find the project root directory by looking for specific marker files.
    
    Returns:
        str: Path to the project root directory.
        
    Raises:
        FileNotFoundError: If project root cannot be determined.
    """
    current_dir = os.getcwd()
    
    # Look for marker files that indicate the project root
    marker_files = ['requirements.txt', 'README.md', 'bicepconfig.json']
    
    while current_dir != os.path.dirname(current_dir):  # Stop at filesystem root
        if any(os.path.exists(os.path.join(current_dir, marker)) for marker in marker_files):
            # Additional check: verify this looks like our project by checking for samples directory
            if os.path.exists(os.path.join(current_dir, 'samples')):
                return current_dir
        current_dir = os.path.dirname(current_dir)
    
    # If we can't find the project root, raise an error
    raise FileNotFoundError('Could not determine project root directory')


def create_bicep_deployment_group_for_sample(sample_name: str, rg_name: str, rg_location: str, bicep_parameters: dict, bicep_parameters_file: str = 'params.json', rg_tags: dict | None = None, is_debug: bool = False) -> Output:
    """
    Create a Bicep deployment for a sample, handling the working directory change automatically.
    This function ensures that the params.json file is written to the correct sample directory
    regardless of the current working directory (e.g., when running from VS Code).

    Args:
        sample_name (str): Name of the sample (used for deployment name and directory).
        rg_name (str): Name of the resource group.
        rg_location (str): Azure region for the resource group.
        bicep_parameters: Parameters for the Bicep template.
        bicep_parameters_file (str, optional): File to write parameters to.
        rg_tags (dict, optional): Additional tags to apply to the resource group.
        is_debug (bool, optional): Whether to enable debug mode. Defaults to False.

    Returns:
        Output: The result of the deployment command.
    """
    import os
    
    # Get the current working directory
    original_cwd = os.getcwd()
    
    try:
        # Determine the sample directory path
        # This handles both cases: running from project root or from sample directory
        if os.path.basename(original_cwd) == sample_name:
            # Already in the sample directory
            sample_dir = original_cwd
        else:
            # Assume we're in project root or elsewhere, navigate to sample directory
            project_root = find_project_root()
            sample_dir = os.path.join(project_root, 'samples', sample_name)
        
        # Verify the sample directory exists and has main.bicep
        if not os.path.exists(sample_dir):
            raise FileNotFoundError(f'Sample directory not found: {sample_dir}')
        
        main_bicep_path = os.path.join(sample_dir, 'main.bicep')
        if not os.path.exists(main_bicep_path):
            raise FileNotFoundError(f'main.bicep not found in sample directory: {sample_dir}')
        
        # Change to the sample directory to ensure params.json is written there
        os.chdir(sample_dir)
        print(f'📁 Changed working directory to: {sample_dir}')
        
        # Call the original deployment function
        return create_bicep_deployment_group(rg_name, rg_location, sample_name, bicep_parameters, bicep_parameters_file, rg_tags, is_debug)
        
    finally:
        # Always restore the original working directory
        os.chdir(original_cwd)
        print(f'📁 Restored working directory to: {original_cwd}')


def create_resource_group(rg_name: str, resource_group_location: str | None = None, tags: dict | None = None) -> None:
    """
    Create a resource group in Azure if it does not already exist.

    Args:
        rg_name (str): Name of the resource group.
        resource_group_location (str, optional): Azure region for the resource group.
        tags (dict, optional): Additional tags to apply to the resource group.

    Returns:
        None
    """

    if not does_resource_group_exist(rg_name):
        print_info(f'Creating the resource group now...')

        # Build the tags string for the Azure CLI command
        tag_string = 'source=apim-sample'
        if tags:
            for key, value in tags.items():
                # Escape values that contain spaces or special characters
                escaped_value = value.replace('"', '\\"') if isinstance(value, str) else str(value)
                tag_string += f' {key}=\"{escaped_value}\"'

        run(f'az group create --name {rg_name} --location {resource_group_location} --tags {tag_string}',
            f"Resource group '{rg_name}' created",
            f"Failed to create the resource group '{rg_name}'", 
            False, False, False, False)

def does_infrastructure_exist(infrastructure: INFRASTRUCTURE, index: int) -> bool:
    """
    Check if a specific infrastructure exists by querying the resource group.

    Args:
        infrastructure (INFRASTRUCTURE): The infrastructure type to check.
        index (int): index for multi-instance infrastructures.

    Returns:
        bool: True if the infrastructure exists, False otherwise.
    """
    
    print(f'🔍 Checking if infrastructure already exists...')

    rg_name = get_infra_rg_name(infrastructure, index)

    if does_resource_group_exist(rg_name):
        print(f'✅ Infrastructure already exists!\n')
        print('ℹ️  To redeploy, either:')
        print('     1. Use a different index number, or')
        print('     2. Delete the existing resource group first using the clean-up notebook')
        return True
    else:
        print('   Infrastructure does not yet exist.')    
        return False

def does_resource_group_exist(rg_name: str) -> bool:
    """
    Check if a resource group exists in Azure.

    Args:
        rg_name (str): Name of the resource group.

    Returns:
        bool: True if the resource group exists, False otherwise.
    """

    output = run(f'az group show --name {rg_name}', print_command_to_run = False, print_output = False, print_errors = False)
    return output.success

def get_resource_group_location(rg_name: str) -> str:
    """
    Get the location of a resource group.

    Args:
        rg_name (str): Name of the resource group.

    Returns:
        str: The location of the resource group, or 'Unknown' if not found.
    """

    output = run(f'az group show --name {rg_name} --query location -o tsv', print_command_to_run = False, print_output = False, print_errors = False)
    return output.text.strip() if output.success and output.text.strip() else 'Unknown'

def read_and_modify_policy_xml(policy_xml_filepath: str, replacements: dict[str, str], sample_name: str = None) -> str:
    """
    Read and return the contents of a policy XML file, then modifies it by replacing placeholders with provided values.

    Args:
        policy_xml_filepath (str): Path to the policy XML file.

    Returns:
        str: Contents of the policy XML file.
    """

    policy_xml_filepath = determine_policy_path(policy_xml_filepath, sample_name)
    # print(f'📄 Reading policy XML from : {policy_xml_filepath}')  # debug

    # Read the specified policy XML file
    with open(policy_xml_filepath, 'r', encoding='utf-8') as policy_xml_file:
        policy_template_xml = policy_xml_file.read()

    if replacements is not None and isinstance(replacements, dict):
        # Replace placeholders in the policy XML with provided values
        for placeholder, value in replacements.items():
            placeholder = '{' + placeholder + '}'

            if placeholder in policy_template_xml:
                policy_template_xml = policy_template_xml.replace(placeholder, value)
            else:
                print_warning(f"Placeholder '{placeholder}' not found in the policy XML file.")

    return policy_template_xml

def determine_shared_policy_path(policy_xml_filename: str) -> str:
    return str(Path(find_project_root()) / 'shared' / 'apim-policies' / 'fragments' / policy_xml_filename)

def determine_policy_path(policy_xml_filepath_or_filename: str, sample_name: str = None) -> str:
    # Determine if this is a full path or just a filename
    path_obj = Path(policy_xml_filepath_or_filename)
    
    # Legacy mode check: if named_values is None, always treat as legacy (backwards compatibility)
    # OR if it looks like a path (contains separators or is absolute)
    if (path_obj.is_absolute() or 
        '/' in policy_xml_filepath_or_filename or 
        '\\' in policy_xml_filepath_or_filename):
        # Legacy mode: treat as full path
        policy_xml_filepath = policy_xml_filepath_or_filename
    else:
        # Smart mode: auto-detect sample directory
        if sample_name is None:
            try:
                # Get the current frame's filename (the notebook or script calling this function)
                frame = inspect.currentframe()
                caller_frame = frame.f_back
                
                # Try to get the filename from the caller's frame
                if hasattr(caller_frame, 'f_globals') and '__file__' in caller_frame.f_globals:
                    caller_file = caller_frame.f_globals['__file__']
                    caller_path = Path(caller_file).resolve()
                else:
                    # Fallback for Jupyter notebooks: use current working directory
                    caller_path = Path(os.getcwd()).resolve()
                
                # Walk up the directory tree to find the samples directory structure
                current_path = caller_path.parent if caller_path.is_file() else caller_path
                
                # Look for samples directory in the path
                path_parts = current_path.parts
                if 'samples' in path_parts:
                    samples_index = path_parts.index('samples')
                    if samples_index + 1 < len(path_parts):
                        sample_name = path_parts[samples_index + 1]
                    else:
                        raise ValueError('Could not detect sample name from path')
                else:
                    raise ValueError('Not running from within a samples directory')
                    
            except Exception as e:
                raise ValueError(f'Could not auto-detect sample name. Please provide sample_name parameter explicitly. Error: {e}')
        
        # Construct the full path
        from apimtypes import _get_project_root
        project_root = _get_project_root()
        policy_xml_filepath = str(project_root / 'samples' / sample_name / policy_xml_filepath_or_filename)

    return policy_xml_filepath

def read_policy_xml(policy_xml_filepath_or_filename: str, named_values: dict[str, str] = None, sample_name: str = None) -> str:
    """
    Read and return the contents of a policy XML file, with optional named value formatting.
    
    Can work in two modes:
    1. Legacy mode: Pass a full file path (backwards compatible)
    2. Smart mode: Pass just a filename and auto-detect sample directory
    
    Args:
        policy_xml_filepath_or_filename (str): Full path to policy XML file OR just filename for auto-detection.
        named_values (dict[str, str], optional): Dictionary of named values to format in the policy XML.
        sample_name (str, optional): Override the auto-detected sample name if needed.

    Returns:
        str: Contents of the policy XML file with optional named values formatted.

    Examples:
        # Legacy usage - full path
        policy_xml = read_policy_xml('/path/to/policy.xml')
        
        # Smart usage - auto-detects sample directory
        policy_xml = read_policy_xml('hr_all_operations.xml', {
            'jwt_signing_key': jwt_key_name,
            'hr_member_role_id': 'HRMemberRoleId'
        })
    """
    
    policy_xml_filepath = determine_policy_path(policy_xml_filepath_or_filename, sample_name)
    # print(f'📄 Reading policy XML from : {policy_xml_filepath}')  # debug

    # Read the specified policy XML file
    with open(policy_xml_filepath, 'r', encoding='utf-8') as policy_xml_file:
        policy_template_xml = policy_xml_file.read()

    # Apply named values formatting if provided
    if named_values is not None and isinstance(named_values, dict):
        # Format the policy XML with named values (double braces for APIM named value syntax)
        formatted_replacements = {}
        for placeholder, named_value in named_values.items():
            formatted_replacements[placeholder] = '{{' + named_value + '}}'
        
        # Apply the replacements
        policy_template_xml = policy_template_xml.format(**formatted_replacements)

    return policy_template_xml


def cleanup_infra_deployments(deployment: INFRASTRUCTURE, indexes: int | list[int] | None = None) -> None:
    """
    Clean up infrastructure deployments by deployment enum and index/indexes.
    Obtains the infra resource group name for each index and calls the private cleanup method.

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

    i = 1
    for idx in indexes_list:
        print_info(f'{i}/{len(indexes_list)}: Cleaning up resources for {deployment} - {idx}', True)
        rg_name = get_infra_rg_name(deployment, idx)
        _cleanup_resources(deployment.value, rg_name)
        i += 1

def extract_json(text: str) -> Any:
    """
    Extract the first valid JSON object or array from a string and return it as a Python object.

    This function searches the input string for the first occurrence of a JSON object or array (delimited by '{' or '['),
    and attempts to decode it using json.JSONDecoder().raw_decode. If the input is already valid JSON, it is returned as a Python object.
    If no valid JSON is found, None is returned.

    Args:
        text (str): The string to search for a JSON object or array.

    Returns:
        Any | None: The extracted JSON as a Python object (dict or list), or None if not found or not valid.
    """

    if not isinstance(text, str):
        return None

    # If the string is already valid JSON, parse and return it as a Python object.
    if is_string_json(text):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # If JSON parsing fails despite is_string_json returning True, 
            # fall through to substring search
            pass

    decoder = json.JSONDecoder()

    for start in range(len(text)):
        if text[start] in ('{', '['):
            try:
                obj, _ = decoder.raw_decode(text[start:])
                return obj
            except Exception:
                continue

    return None

def is_string_json(text: str) -> bool:
    """
    Check if the provided string is a valid JSON object or array.

    Args:
        text (str): The string to check.

    Returns:
        bool: True if the string is valid JSON, False otherwise.
    """

    # Accept only str, bytes, or bytearray as valid input for JSON parsing.
    if not isinstance(text, (str, bytes, bytearray)):
        return False

    # Skip empty or whitespace-only strings
    if not text or not text.strip():
        return False

    # First try JSON parsing (handles double quotes)
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        pass

    # If JSON fails, try Python literal evaluation (handles single quotes)
    try:
        ast.literal_eval(text)
        return True
    except (ValueError, SyntaxError):
        pass

    return False

def get_account_info() -> Tuple[str, str, str]:
    """
    Retrieve the current Azure account information using the Azure CLI.

    Returns:
        tuple: (current_user, tenant_id, subscription_id)

    Raises:
        Exception: If account information cannot be retrieved.
    """

    output = run('az account show', 'Retrieved az account', 'Failed to get the current az account')

    if output.success and output.json_data:
        current_user = output.json_data['user']['name']
        tenant_id = output.json_data['tenantId']
        subscription_id = output.json_data['id']

        print_val('Current user', current_user)
        print_val('Tenant ID', tenant_id)
        print_val('Subscription ID', subscription_id)

        return current_user, tenant_id, subscription_id
    else:
        error = 'Failed to retrieve account information. Please ensure the Azure CLI is installed, you are logged in, and the subscription is set correctly.'
        print_error(error)
        raise Exception(error)

def get_deployment_name() -> str:

    """
    Get the deployment name based on the directory of the currently running Jupyter notebook.

    Returns:
        str: The deployment name, derived from the current working directory.
    """

    notebook_path = os.path.basename(os.getcwd())

    if not notebook_path:
        raise RuntimeError('Notebook path could not be determined.')
    
    print_val('Deployment name', notebook_path)

    return notebook_path

def get_frontdoor_url(deployment_name: INFRASTRUCTURE, rg_name: str) -> str | None:
    """
    Retrieve the secure URL for the first endpoint in the first Azure Front Door Standard/Premium profile in the specified resource group.

    Args:
        deployment_name (INFRASTRUCTURE): The infrastructure deployment enum value. Should be INFRASTRUCTURE.AFD_APIM_PE for AFD scenarios.
        rg_name (str): The name of the resource group containing the Front Door profile.

    Returns:
        str | None: The secure URL (https) of the first endpoint if found, otherwise None.
    """

    afd_endpoint_url: str | None = None

    if deployment_name == INFRASTRUCTURE.AFD_APIM_PE:
        output = run(f'az afd profile list -g {rg_name} -o json')

        if output.success and output.json_data:
            afd_profile_name = output.json_data[0]['name']
            print_ok(f'Front Door Profile Name: {afd_profile_name}', blank_above = False)

            if afd_profile_name:
                output = run(f'az afd endpoint list -g {rg_name} --profile-name {afd_profile_name} -o json')

                if output.success and output.json_data:
                    afd_hostname = output.json_data[0]['hostName']

                    if afd_hostname:
                        afd_endpoint_url = f'https://{afd_hostname}'

    if afd_endpoint_url:
        print_ok(f'Front Door Endpoint URL: {afd_endpoint_url}', blank_above = False)
    else:
        print_warning('No Front Door endpoint URL found.')

    return afd_endpoint_url

def get_infra_rg_name(deployment_name: INFRASTRUCTURE, index: int | None = None) -> str:
    """
    Generate a resource group name for infrastructure deployments, optionally with an index.

    Args:
        deployment_name (INFRASTRUCTURE): The infrastructure deployment enum value.
        index (int | None): An optional index to append to the name. Defaults to None.

    Returns:
        str: The generated resource group name.
    """

    rg_name = f'apim-infra-{deployment_name.value}'

    if index is not None:
        rg_name = f'{rg_name}-{index}'

    return rg_name

def get_rg_name(deployment_name: str, index: int | None = None) -> str:
    """
    Generate a resource group name for a sample deployment, optionally with an index.

    Args:
        deployment_name (str): The base name for the deployment.
        index (int, optional): An optional index to append to the name.

    Returns:
        str: The generated resource group name.
    """

    rg_name = f'apim-sample-{deployment_name}'

    if index is not None:
        rg_name = f'{rg_name}-{str(index)}'

    print_val('Resource group name', rg_name)
    return rg_name

def run(command: str, ok_message: str = '', error_message: str = '', print_output: bool = False, print_command_to_run: bool = True, print_errors: bool = True, print_warnings: bool = True) -> Output:
    """
    Execute a shell command, log the command and its output, and attempt to extract JSON from the output.

    Args:
        command (str): The shell command to execute.
        ok_message (str, optional): Message to print if the command succeeds. Defaults to ''.
        error_message (str, optional): Message to print if the command fails. Defaults to ''.
        print_output (bool, optional): Whether to print the command output on failure. Defaults to False.
        print_command_to_run (bool, optional): Whether to print the command before running it. Defaults to True.
        print_errors (bool, optional): Whether to log error lines from the output. Defaults to True.
        print_warnings (bool, optional): Whether to log warning lines from the output. Defaults to True.

    Returns:
        Output: An Output object containing:
            - success (bool): True if the command succeeded, False otherwise.
            - text (str): The raw output from the command.
            - json_data (any, optional): Parsed JSON object or array if found in the output, else None.
    """

    if print_command_to_run:
        print_command(command)

    start_time = time.time()

    # Execute the command and capture the output

    try:
        output_text = subprocess.check_output(command, shell = True, stderr = subprocess.STDOUT).decode('utf-8')
        success = True
    except Exception as e:
        # Handles both CalledProcessError and any custom/other exceptions (for test mocks)
        output_text = getattr(e, 'output', b'').decode('utf-8') if hasattr(e, 'output') and isinstance(e.output, (bytes, bytearray)) else str(e)
        success = False
        
        if print_errors:
            print_error(f'Command failed with error: {output_text}', duration = f'[{int((time.time() - start_time) // 60)}m:{int((time.time() - start_time) % 60)}s]')
            traceback.print_exc()

    if print_output:
        print(f'Command output:\n{output_text}')

    minutes, seconds = divmod(time.time() - start_time, 60)

    # Only print failures, warnings, or errors if print_output is True
    if print_output:
        for line in output_text.splitlines():
            l = line.strip()

            # Only log and skip lines that start with 'warning' or 'error' (case-insensitive)
            if l.lower().startswith('warning'):
                if l and print_warnings:
                    print_warning(l)
                continue
            elif l.lower().startswith('error'):
                if l and print_errors:
                    print_error(l)
                continue

        print_message = print_ok if success else print_error

        if (ok_message or error_message):
            print_message(ok_message if success else error_message, output_text if not success or print_output else '', f'[{int(minutes)}m:{int(seconds)}s]')

    return Output(success, output_text)

# Validation functions will raise ValueError if the value is not valid

validate_http_verb      = lambda val: HTTP_VERB(val)
validate_sku            = lambda val: APIM_SKU(val)

def validate_infrastructure(infra: INFRASTRUCTURE, supported_infras: list[INFRASTRUCTURE]) -> None:
    """
    Validate that the provided infrastructure is supported.

    Args:
        infra (INFRASTRUCTURE): The infrastructure deployment enum value.
        supported_infras (list[INFRASTRUCTURE]): List of supported infrastructure types.

    Raises:
        ValueError: If the infrastructure is not supported.
    """

    if infra not in supported_infras:
        supported_names = ', '.join([i.value for i in supported_infras])
        raise ValueError(f'Unsupported infrastructure: {infra}. Supported infrastructures are: {supported_names}')
    
def generate_signing_key() -> tuple[str, str]:
    """
    Generate a random signing key string of length 32–100 using [A-Za-z0-9], and return:

    1. The generated ASCII string.
    2. The base64-encoded string of the ASCII bytes.

    Returns:
        tuple[str, str]:
            - random_string (str): The generated random ASCII string.
            - b64 (str): The base64-encoded string of the ASCII bytes.
    """

    # 1) Generate a random length string based on [A-Za-z0-9]
    length = secrets.choice(range(32, 101))
    alphabet = string.ascii_letters + string.digits
    random_string = ''.join(secrets.choice(alphabet) for _ in range(length))

    # 2) Convert the string to an ASCII byte array
    string_in_bytes = random_string.encode('ascii')

    # 3) Base64-encode the ASCII byte array
    b64 = base64.b64encode(string_in_bytes).decode('utf-8')

    return random_string, b64

def check_apim_blob_permissions(apim_name: str, storage_account_name: str, resource_group_name: str, max_wait_minutes: int = 10) -> bool:
    """
    Check if APIM's managed identity has Storage Blob Data Reader permissions on the storage account.
    Waits for role assignments to propagate across Azure AD, which can take several minutes.
    
    Args:
        apim_name (str): The name of the API Management service.
        storage_account_name (str): The name of the storage account.
        resource_group_name (str): The name of the resource group.
        max_wait_minutes (int, optional): Maximum time to wait for permissions to propagate. Defaults to 10.
    
    Returns:
        bool: True if APIM has the required permissions, False otherwise.
    """
    
    print_info(f"🔍 Checking if APIM '{apim_name}' has Storage Blob Data Reader permissions on '{storage_account_name}' in resource group '{resource_group_name}'...")
    
    # Storage Blob Data Reader role definition ID
    blob_reader_role_id = get_azure_role_guid('StorageBlobDataReader')
    
    # Get APIM's managed identity principal ID
    print_info('Getting APIM managed identity...')
    apim_identity_output = run(
        f'az apim show --name {apim_name} --resource-group {resource_group_name} --query identity.principalId -o tsv',
        error_message='Failed to get APIM managed identity',
        print_command_to_run=True
    )
    
    if not apim_identity_output.success or not apim_identity_output.text.strip():
        print_error('Could not retrieve APIM managed identity principal ID')
        return False
    
    principal_id = apim_identity_output.text.strip()
    print_info(f'APIM managed identity principal ID: {principal_id}')    # Get storage account resource ID
    # Remove suppression flags to get raw output, then extract resource ID with regex
    storage_account_output = run(
        f'az storage account show --name {storage_account_name} --resource-group {resource_group_name} --query id -o tsv',
        error_message='Failed to get storage account resource ID',
        print_command_to_run=True
    )
    
    if not storage_account_output.success:
        print_error('Could not retrieve storage account resource ID')
        return False
    
    # Extract resource ID using regex pattern, ignoring any warning text
    resource_id_pattern = r'/subscriptions/[a-f0-9-]+/resourceGroups/[^/]+/providers/Microsoft\.Storage/storageAccounts/[^/\s]+'
    match = re.search(resource_id_pattern, storage_account_output.text)
    
    if not match:
        print_error('Could not parse storage account resource ID from output')
        return False
    
    storage_account_id = match.group(0)
    
    # Check for role assignment with retry logic for propagation
    max_wait_seconds = max_wait_minutes * 60
    wait_interval = 30  # Check every 30 seconds
    elapsed_time = 0
    
    print_info(f'Checking role assignment (will wait up to {max_wait_minutes} minute(s) for propagation)...')
    
    while elapsed_time < max_wait_seconds:
        # Check if role assignment exists
        role_assignment_output = run(
            f"az role assignment list --assignee {principal_id} --scope {storage_account_id} --role {blob_reader_role_id} --query '[0].id' -o tsv",
            error_message='Failed to check role assignment',
            print_command_to_run=True,
            print_errors=False
        )
        
        if role_assignment_output.success and role_assignment_output.text.strip():
            print_success(f'Role assignment found! APIM managed identity has Storage Blob Data Reader permissions.')
            
            # Additional check: try to test blob access using the managed identity
            print_info('Testing actual blob access...')
            test_access_output = run(
                f"az storage blob list --account-name {storage_account_name} --container-name samples --auth-mode login --only-show-errors --query '[0].name' -o tsv 2>/dev/null || echo 'access-test-failed'",
                error_message='',
                print_command_to_run=True,
                print_errors=False
            )
            
            if test_access_output.success and test_access_output.text.strip() != 'access-test-failed':
                print_success('Blob access test successful!')
                return True
            else:
                print_warning('Role assignment exists but blob access test failed. Permissions may still be propagating...')
        
        if elapsed_time == 0:
            print_info(f'Role assignment not found yet. Waiting for Azure AD propagation...')
        else:
            print_info(f'Still waiting... ({elapsed_time // 60}m {elapsed_time % 60}s elapsed)')
        
        if elapsed_time + wait_interval >= max_wait_seconds:
            break
            
        time.sleep(wait_interval)
        elapsed_time += wait_interval
    
    print_error(f'Timeout: Role assignment not found after {max_wait_minutes} minutes.')
    print_info('This is likely due to Azure AD propagation delays. You can:')
    print_info('1. Wait a few more minutes and try again')
    print_info('2. Manually verify the role assignment in the Azure portal')
    print_info('3. Check the deployment logs for any errors')
    
    return False

def wait_for_apim_blob_permissions(apim_name: str, storage_account_name: str, resource_group_name: str, max_wait_minutes: int = 15) -> bool:
    """
    Wait for APIM's managed identity to have Storage Blob Data Reader permissions on the storage account.
    This is a user-friendly wrapper that provides clear feedback during the wait process.
    
    Args:
        apim_name (str): The name of the API Management service.
        storage_account_name (str): The name of the storage account.
        resource_group_name (str): The name of the resource group.
        max_wait_minutes (int, optional): Maximum time to wait for permissions. Defaults to 15.
    
    Returns:
        bool: True if permissions are available, False if timeout or error occurred.
    """
    
    print_info('Azure role assignments can take several minutes to propagate across Azure AD. This check will verify that APIM can access the blob storage before proceeding with tests.\n')
    
    success = check_apim_blob_permissions(apim_name, storage_account_name, resource_group_name, max_wait_minutes)
    
    if success:
        print_success('Permission check passed! Ready to proceed with secure blob access tests.')
    else:
        print_error('Permission check failed. Please check the deployment and try again later.')
        print_info('Tip: You can also run the verify-permissions.ps1 script to manually check role assignments.')
    
    print('')

    return success

def test_url_preflight_check(deployment: INFRASTRUCTURE, rg_name: str, apim_gateway_url: str) -> str:
    # Preflight: Check if the infrastructure architecture deployment uses Azure Front Door. If so, assume that APIM is not directly accessible and use the Front Door URL instead.

    print_message('Checking if the infrastructure architecture deployment uses Azure Front Door.', blank_above = True)

    afd_endpoint_url = get_frontdoor_url(deployment, rg_name)

    if afd_endpoint_url:
        endpoint_url = afd_endpoint_url
        print_message(f'Using Azure Front Door URL: {afd_endpoint_url}', blank_above = True)
    else:
        endpoint_url = apim_gateway_url
        print_message(f'Using APIM Gateway URL: {apim_gateway_url}', blank_above = True)

    return endpoint_url

def cleanup_old_jwt_signing_keys(apim_name: str, resource_group_name: str, current_jwt_key_name: str) -> bool:
    """
    Clean up old JWT signing keys from APIM named values for the same sample folder, keeping only the current key.
    Uses regex matching to identify keys that belong to the same sample folder by extracting the sample folder
    name from the current key and matching against the pattern 'JwtSigningKey-{sample_folder}-{timestamp}'.
    
    Args:
        apim_name (str): Name of the APIM service
        resource_group_name (str): Name of the resource group containing APIM
        current_jwt_key_name (str): Name of the current JWT key to preserve (format: JwtSigningKey-{sample_folder}-{timestamp})
        
    Returns:
        bool: True if cleanup was successful, False otherwise
    """
    
    try:
        import re
        
        print_message('🧹 Cleaning up old JWT signing keys for the same sample folder...', blank_above = True)
        
        # Extract sample folder name from current JWT key using regex
        # Pattern: JwtSigningKey-{sample_folder}-{timestamp}
        current_key_pattern = r'^JwtSigningKey-(.+)-\d+$'
        current_key_match = re.match(current_key_pattern, current_jwt_key_name)
        
        if not current_key_match:
            print_error(f"Current JWT key name '{current_jwt_key_name}' does not match expected pattern 'JwtSigningKey-{{sample_folder}}-{{timestamp}}'")
            return False
        
        sample_folder = current_key_match.group(1)
        print_info(f"Identified sample folder: '{sample_folder}'")
        
        # Get all named values that start with 'JwtSigningKey'
        print_info(f"Getting all JWT signing key named values from APIM '{apim_name}'...")
        
        output = run(
            f'az apim nv list --service-name "{apim_name}" --resource-group "{resource_group_name}" --query "[?contains(name, \'JwtSigningKey\')].name" -o tsv',
            'Retrieved JWT signing keys',
            'Failed to retrieve JWT signing keys'
        )
        
        if not output.success:
            print_error('Failed to retrieve JWT signing keys from APIM')
            return False
            
        if not output.text.strip():
            print_info('No JWT signing keys found. Nothing to clean up.')
            return True
            
        # Parse the list of JWT keys
        jwt_keys = [key.strip() for key in output.text.strip().split('\n') if key.strip()]
        
        # print_info(f'Found {len(jwt_keys)} total JWT signing keys.')
        
        # Filter keys that belong to the same sample folder using regex
        sample_key_pattern = rf'^JwtSigningKey-{re.escape(sample_folder)}-\d+$'
        sample_folder_keys = [key for key in jwt_keys if re.match(sample_key_pattern, key)]
        
        print_info(f"Found {len(sample_folder_keys)} JWT signing keys for sample folder '{sample_folder}'.")
        
        # Process each JWT key for this sample folder
        deleted_count = 0
        kept_count = 0
        
        for jwt_key in sample_folder_keys:
            if jwt_key == current_jwt_key_name:
                print_info(f'Keeping current JWT key: {jwt_key}')
                kept_count += 1
            else:
                print_info(f'Deleting old JWT key: {jwt_key}')
                delete_output = run(
                    f'az apim nv delete --service-name "{apim_name}" --resource-group "{resource_group_name}" --named-value-id "{jwt_key}" --yes',
                    f'Deleted old JWT key: {jwt_key}',
                    f'Failed to delete JWT key: {jwt_key}',
                    print_errors = False
                )
                
                if delete_output.success:
                    deleted_count += 1
        
        # Summary
        print_success(f"JWT signing key cleanup completed for sample '{sample_folder}'. Deleted {deleted_count} old key(s), kept {kept_count}.", blank_above = True)
        return True
        
    except Exception as e:
        print_error(f'Error during JWT key cleanup: {str(e)}')
        return False
    
def get_json(input: str) -> Any:
    """
    Safely parse a JSON string or file content into a Python object.
    
    Args:
        input (str): The JSON string or file content to parse.
        
    Returns:
        Any: The parsed JSON object, or None if parsing fails.
    """
    
    # If the result is a string, try to parse it as JSON
    if isinstance(input, str):
        # First try JSON parsing (handles double quotes)
        try:
            return json.loads(input)
        except json.JSONDecodeError:
            pass

        # If JSON fails, try Python literal evaluation (handles single quotes)
        try:
            return ast.literal_eval(input)
        except (ValueError, SyntaxError) as e:
            print_error(f'Failed to parse deployment output as Python literal. Error: {e}')
            pass

    # Return the original result if it's not a string or can't be parsed
    return input