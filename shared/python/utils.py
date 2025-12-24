"""
Module providing utility functions.
"""

import ast
import json
import sys
import os
import subprocess
import time
import string
import secrets
import base64
import inspect
import warnings
from pathlib import Path
from typing import Any

# APIM Samples imports
import azure_resources as az
from apimtypes import APIM_SKU, HTTP_VERB, INFRASTRUCTURE, Endpoints, Output, get_project_root
from console import print_error, print_info, print_message, print_ok, print_plain, print_warning, print_val
import logging_config

# Configure warning filter to suppress IPython exit warnings
warnings.filterwarnings(
    'ignore',
    message = r"To exit: use 'exit', 'quit', or Ctrl-D\.",
    category = UserWarning,
    module = r'IPython\.core\.interactiveshell',
)


# ------------------------------
#    HELPER FUNCTIONS
# ------------------------------

def get_deployment_failure_message(deployment_name: str) -> str:
    """
    Generate a deployment failure message that conditionally includes debug instruction.

    Args:
        deployment_name (str): The name of the failed deployment.

    Returns:
        str: Appropriate failure message based on current logging level.
    """
    base_message = f"Deployment '{deployment_name}' failed. View deployment details in Azure Portal."

    # Only suggest enabling DEBUG logging if it's not already enabled
    current_level = logging_config.get_configured_level_name()
    if current_level != 'DEBUG':
        return f"{base_message} Enable DEBUG logging in workspace root .env file, then rerun to see details."

    return base_message

def build_infrastructure_tags(infrastructure: str | INFRASTRUCTURE, custom_tags: dict | None = None) -> dict:
    """
    Build standard tags for infrastructure resource groups, including required 'infrastructure' tag.

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

    # Build standard tags - only include infrastructure tag
    tags = {'infrastructure': infra_name}

    # Add custom tags if provided
    if custom_tags:
        tags.update(custom_tags)

    return tags


# ------------------------------
#    CLASSES
# ------------------------------

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

        print_message('Initializing Infrastructure Notebook Helper with the following parameters:', blank_above = True, blank_below = True)
        print_val('Location', self.rg_location)
        print_val('Infrastructure', self.deployment.value)
        print_val('Index', self.index)
        print_val('APIM SKU', self.apim_sku.value)
        print_plain('')

    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def create_infrastructure(self, bypass_infrastructure_check: bool = False, allow_update: bool = True) -> None:
        """
        Create infrastructure by executing the appropriate creation script.

        Args:
            bypass_infrastructure_check (bool): Skip infrastructure existence check. Defaults to False.
            allow_update (bool): Allow infrastructure updates when infrastructure already exists. Defaults to True.

        Returns:
            None: Method either succeeds or exits the program with SystemExit.
        """

        try:
            # For infrastructure notebooks, check if update is allowed and handle user choice
            if allow_update:
                rg_name = az.get_infra_rg_name(self.deployment, self.index)
                if az.does_resource_group_exist(rg_name):
                    # Infrastructure exists, show update dialog
                    try:
                        should_proceed, new_index = _prompt_for_infrastructure_update(rg_name)
                        if new_index is not None:
                            # User selected option 2: Use a different index
                            print_plain(f'🔄 Retrying infrastructure creation with index {new_index}...')
                            self.index = new_index
                            # Recursively call create_infrastructure with the new index
                            return self.create_infrastructure(bypass_infrastructure_check, allow_update)
                        elif not should_proceed:
                            print_error('Infrastructure deployment cancelled by user.')
                            raise SystemExit("User cancelled deployment")
                    except (KeyboardInterrupt, EOFError) as exc:
                        print_error('Infrastructure deployment cancelled by user (Escape/Ctrl+C pressed).')
                        raise SystemExit("User cancelled deployment") from exc

            # Check infrastructure existence for the normal flow
            infrastructure_exists = az.does_resource_group_exist(az.get_infra_rg_name(self.deployment, self.index)) if not allow_update else False

            if bypass_infrastructure_check or not infrastructure_exists:
                # Map infrastructure types to their folder names
                infra_folder_map = {
                    INFRASTRUCTURE.SIMPLE_APIM: 'simple-apim',
                    INFRASTRUCTURE.AFD_APIM_PE: 'afd-apim-pe',
                    INFRASTRUCTURE.APIM_ACA: 'apim-aca',
                    INFRASTRUCTURE.APPGW_APIM_PE: 'appgw-apim-pe',
                    INFRASTRUCTURE.APPGW_APIM: 'appgw-apim'
                }

                infra_folder = infra_folder_map.get(self.deployment)
                if not infra_folder:
                    print_error(f'Unsupported infrastructure type: {self.deployment.value}')
                    raise SystemExit(1)

                # Build the command to call the infrastructure creation script
                cmd_args = [
                    sys.executable,
                    os.path.join(find_project_root(), 'infrastructure', infra_folder, 'create_infrastructure.py'),
                    '--location', self.rg_location,
                    '--index', str(self.index),
                    '--sku', str(self.apim_sku.value)
                ]

                # Execute the infrastructure creation script with real-time output streaming and UTF-8 encoding to handle Unicode characters properly
                project_root = find_project_root()

                with subprocess.Popen(
                    cmd_args,
                    cwd = project_root,
                    stdout = subprocess.PIPE,
                    stderr = subprocess.STDOUT,
                    text = True,
                    bufsize = 1,
                    universal_newlines = True,
                    encoding = 'utf-8',
                    errors = 'replace'
                ) as process:
                    try:
                        # Stream output in real-time
                        for line in process.stdout:
                            print_plain(line.rstrip())
                    except Exception as e:
                        print_plain(f'Error reading subprocess output: {e}')

                    # Wait for process to complete
                    process.wait()

                    if process.returncode:
                        raise SystemExit(1)

                return True

            return True

        except KeyboardInterrupt as exc:
            print_error('\nInfrastructure deployment cancelled by user.')
            raise SystemExit("User cancelled deployment") from exc
        except Exception as e:
            print_error(f'Infrastructure deployment failed with error: {e}')
            raise SystemExit(1) from e

class NotebookHelper:
    """
    Helper class for managing sample notebook deployments and infrastructure interaction.
    """

    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, sample_folder: str, rg_name: str, rg_location: str, deployment: INFRASTRUCTURE, supported_infrastructures = list[INFRASTRUCTURE], use_jwt: bool = False, index: int = 1, is_debug = False, apim_sku: APIM_SKU = APIM_SKU.BASICV2):
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
        self.apim_sku = apim_sku

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
        if not az.cleanup_old_jwt_signing_keys(apim_name, self.rg_name, self.jwt_key_name):
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

        print_plain('Querying for available infrastructures...\n')

        # Get all resource groups that match the infrastructure pattern
        available_options = []

        for infra in self.supported_infrastructures:
            infra_options = az.find_infrastructure_instances(infra)
            available_options.extend(infra_options)

        # Check if the desired infrastructure/index combination exists
        desired_rg_name = az.get_infra_rg_name(self.deployment, self._get_current_index())
        desired_exists = any(
            az.get_infra_rg_name(infra, idx) == desired_rg_name
            for infra, idx in available_options
        )

        if desired_exists:
            # Scenario 1: Desired infrastructure exists, use it directly
            print_ok(f'Found desired infrastructure: {self.deployment.value} with resource group {desired_rg_name}')
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

            print_plain('\n   Create a NEW infrastructure:\n')
            # Column headers
            if QUERY_RG_LOCATION:
                print_plain(f'     {'#':>3} {'Infrastructure':<20} {'Index':>8} {'Resource Group':<35} {'Location':<15}')
                print_plain(f'     {'-'*3:>3} {'-'*20:<20} {'-'*8:>8} {'-'*35:<35} {'-'*15:<15}')
                print_plain(f'     {option_counter:>3} {self.deployment.value:<20} {desired_index_str:>8} {desired_rg_name:<35} {desired_location:<15}')
            else:
                print_plain(f'     {'#':>3} {'Infrastructure':<20} {'Index':>8} {'Resource Group':<35}')
                print_plain(f'     {'-'*3:>3} {'-'*20:<20} {'-'*8:>8} {'-'*35:<35}')
                print_plain(f'     {option_counter:>3} {self.deployment.value:<20} {desired_index_str:>8} {desired_rg_name:<35}')

            display_options.append(('create_new', self.deployment, self._get_current_index()))
            option_counter += 1

            print_plain('\n   Or select an EXISTING infrastructure:\n')
            # Column headers
            if QUERY_RG_LOCATION:
                print_plain(f'     {'#':>3} {'Infrastructure':<20} {'Index':>8} {'Resource Group':<35} {'Location':<15}')
                print_plain(f'     {'-'*3:>3} {'-'*20:<20} {'-'*8:>8} {'-'*35:<35} {'-'*15:<15}')
            else:
                print_plain(f'     {'#':>3} {'Infrastructure':<20} {'Index':>8} {'Resource Group':<35}')
                print_plain(f'     {'-'*3:>3} {'-'*20:<20} {'-'*8:>8} {'-'*35:<35}')

            for infra, index in available_options:
                index_str = index if index is not None else 'N/A'
                rg_name = az.get_infra_rg_name(infra, index)

                if QUERY_RG_LOCATION:
                    rg_location = az.get_resource_group_location(rg_name)
                    print_plain(f'     {option_counter:>3} {infra.value:<20} {index_str:>8} {rg_name:<35} {rg_location:<15}')
                else:
                    print_plain(f'     {option_counter:>3} {infra.value:<20} {index_str:>8} {rg_name:<35}')

                display_options.append(('existing', infra, index))
                option_counter += 1
        else:
            print_warning('No existing supported infrastructures found.')
            print_info(f'Automatically proceeding to create new infrastructure: {self.deployment.value}')

            # Automatically create the desired infrastructure without user confirmation
            selected_index = self._get_current_index()
            print_info(f'Creating new infrastructure: {self.deployment.value}{' (index: ' + str(selected_index) + ')' if selected_index is not None else ''}')

            # Execute the infrastructure creation
            inb_helper = InfrastructureNotebookHelper(self.rg_location, self.deployment, selected_index, self.apim_sku)
            success = inb_helper.create_infrastructure(True)  # Bypass infrastructure check to force creation

            if success:
                print_ok(f'Successfully created infrastructure: {self.deployment.value}{' (index: ' + str(selected_index) + ')' if selected_index is not None else ''}')
                return self.deployment, selected_index
            else:
                print_error('Failed to create infrastructure.')
                return None, None

        print_plain('')

        # Get user selection
        while True:
            try:
                choice = input(f'Select infrastructure (1-{len(display_options)}): ').strip()

                if not choice:
                    print_warning('No infrastructure selected. Exiting.')
                    return None, None

                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(display_options):
                    option_type, selected_infra, selected_index = display_options[choice_idx]

                    if option_type == 'existing':
                        print_ok(f'Selected existing: {selected_infra.value}{' (index: ' + str(selected_index) + ')' if selected_index is not None else ''}')
                        return selected_infra, selected_index
                    elif option_type == 'create_new':
                        print_info(f'Creating new infrastructure: {selected_infra.value}{' (index: ' + str(selected_index) + ')' if selected_index is not None else ''}')

                        # Execute the infrastructure creation
                        inb_helper = InfrastructureNotebookHelper(self.rg_location, self.deployment, selected_index, self.apim_sku)
                        success = inb_helper.create_infrastructure(True)  # Bypass infrastructure check to force creation

                        if success:
                            print_ok(f'Successfully created infrastructure: {selected_infra.value}{' (index: ' + str(selected_index) + ')' if selected_index is not None else ''}')
                            return selected_infra, selected_index
                        else:
                            print_error('Failed to create infrastructure.')
                            return None, None
                else:
                    print_error(f'Invalid choice. Please enter a number between 1 and {len(display_options)}.')

            except ValueError:
                print_error('Invalid input. Please enter a number.')


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
        print_plain('Checking desired infrastructure availability...\n')
        print_plain(f'   Infrastructure : {self.deployment.value}')
        print_plain(f'   Index          : {self.index}')
        print_plain(f'   Resource group : {self.rg_name}\n')

        # Call the resource group existence check only once
        rg_exists = az.does_resource_group_exist(self.rg_name)

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
                self.rg_name = az.get_infra_rg_name(self.deployment, self.index)

                # Verify the updates were applied correctly
                print_plain('📝 Updated infrastructure variables')
            else:
                print_ok('Infrastructure selection already completed in this session')
        else:
            print_ok('Desired infrastructure already exists, proceeding with sample deployment')

        # Deploy the sample APIs to the selected infrastructure
        print_plain('\n------------------------------------------------')
        print_plain('\nSAMPLE DEPLOYMENT')
        print_plain('\nDeploying sample to:\n')
        print_plain(f'   Infrastructure : {self.deployment.value}')
        print_plain(f'   Index          : {self.index}')
        print_plain(f'   Resource group : {self.rg_name}\n')

        # Execute the deployment using the utility function that handles working directory management
        output = create_bicep_deployment_group_for_sample(self.sample_folder, self.rg_name, self.rg_location, bicep_parameters, is_debug = self.is_debug)

        # Print a deployment summary, if successful; otherwise, exit with an error
        if output.success:
            if self.use_jwt:
                apim_name = output.get('apimServiceName')
                self._clean_up_jwt(apim_name)

            print_ok('Deployment succeeded', blank_above = True)
        else:
            raise SystemExit('Deployment failed')

        return output



# ------------------------------
#    PRIVATE METHODS
# ------------------------------

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
        project_root = get_project_root()
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
    az.create_resource_group(rg_name, rg_location, rg_tags)

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
    with open(params_file_path, 'w', encoding='utf-8') as file:
        file.write(json.dumps(bicep_parameters_format))

    print_plain(f'📝 Updated the policy XML in the bicep parameters file {bicep_parameters_file}')

    # Verify that main.bicep exists in the infrastructure directory
    if not os.path.exists(main_bicep_path):
        raise FileNotFoundError(f'main.bicep file not found in expected infrastructure directory: {bicep_dir}')

    cmd = f'az deployment group create --name {deployment_name} --resource-group {rg_name} --template-file "{main_bicep_path}" --parameters "{params_file_path}" --query "properties.outputs"'

    if is_debug:
        cmd += ' --debug'

    print_plain('\nDeploying bicep...\n')
    return az.run(cmd, f"Deployment '{deployment_name}' succeeded", get_deployment_failure_message(deployment_name))

# TODO: Reconcile this with apimtypes.py get_project_root
def find_project_root() -> str:
    """
    Find the project root directory by looking for specific marker files.

    Returns:
        str: Path to the project root directory.

    Raises:
        FileNotFoundError: If project root cannot be determined.
    """
    current_dir = os.getcwd()

    # Look for marker files that indicate the project root.
    # Require all markers to avoid incorrectly treating notebook folders
    # (which often contain their own README.md) as the repo root.
    marker_files = ['requirements.txt', 'README.md', 'bicepconfig.json']

    while current_dir != os.path.dirname(current_dir):  # Stop at filesystem root
        if all(os.path.exists(os.path.join(current_dir, marker)) for marker in marker_files):
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
        print_plain(f'📁 Changed working directory to: {sample_dir}', blank_above = True)

        # Call the original deployment function
        return create_bicep_deployment_group(rg_name, rg_location, sample_name, bicep_parameters, bicep_parameters_file, rg_tags, is_debug)

    finally:
        # Always restore the original working directory
        os.chdir(original_cwd)
        print_plain(f'📁 Restored working directory to: {original_cwd}')

def _prompt_for_infrastructure_update(rg_name: str) -> tuple[bool, int | None]:
    """
    Prompt the user for infrastructure update confirmation.

    Args:
        rg_name (str): The resource group name.

    Returns:
        tuple: (proceed_with_update, new_index) where:
            - proceed_with_update: True if user wants to proceed with update, False to cancel
            - new_index: None if no index change, integer if user selected option 2
    """
    print_ok(f'Infrastructure already exists: {rg_name}')
    print_plain('🔄 Infrastructure Update Options:\n', blank_above = True)
    print_plain('   This infrastructure notebook can update the existing infrastructure.')
    print_plain('   Updates are additive and will:')
    print_plain('   • Add new APIs and policy fragments defined in the infrastructure')
    print_plain('   • Update existing infrastructure components to match the template')
    print_plain('   • Preserve manually added samples and configurations\n')

    print_plain('ℹ️ Choose an option (input box at the top of the screen):')
    print_plain('     1. Update the existing infrastructure (recommended)')
    print_plain('     2. Use a different index')
    print_plain('     3. Delete the existing resource group first using the clean-up notebook\n')

    while True:
        choice = input('\nEnter your choice (1, 2, or 3): ').strip()

        # Default to option 1 if user just presses Enter
        if choice == '1' or not choice:
            return True, None
        elif choice == '2':
            # Option 2: Prompt for a different index
            while True:
                try:
                    new_index_str = input('\nEnter the desired index for the infrastructure: ').strip()
                    if not new_index_str:
                        print_plain('❌ Please enter a valid index number.')
                        continue

                    new_index = int(new_index_str)
                    if new_index <= 0:
                        print_plain('❌ Index must be a positive integer.')
                        continue

                    return False, new_index
                except ValueError:
                    print_plain('❌ Please enter a valid integer for the index.')
        elif choice == '3':
            return False, None
        else:
            print_plain('❌ Invalid choice. Please enter 1, 2, or 3.')

def does_infrastructure_exist(infrastructure: INFRASTRUCTURE, index: int, allow_update_option: bool = False) -> bool:
    """
    Check if a specific infrastructure exists by querying the resource group.

    Args:
        infrastructure (INFRASTRUCTURE): The infrastructure type to check.
        index (int): index for multi-instance infrastructures.
        allow_update_option (bool): If True, provides option to proceed with infrastructure update when infrastructure exists.

    Returns:
        bool: True if the infrastructure exists and no update is desired, False if infrastructure doesn't exist or update is confirmed.
    """

    print_plain(f'� Debug: does_infrastructure_exist called with allow_update_option={allow_update_option}')
    print_plain('�🔍 Checking if infrastructure already exists...')

    rg_name = az.get_infra_rg_name(infrastructure, index)

    if az.does_resource_group_exist(rg_name):
        print_ok(f'Infrastructure already exists: {rg_name}')

        if allow_update_option:
            print_plain('🔄 Infrastructure Update Options:\n', blank_above = True)
            print_plain('   This infrastructure notebook can update the existing infrastructure. Updates are additive and will:\n')
            print_plain('   • Add new APIs and policy fragments defined in the infrastructure')
            print_plain('   • Update existing infrastructure components to match the template')
            print_plain('   • Preserve manually added samples and configurations\n')

            print_info('Choose an option (input box at the top of the screen):')
            print_plain('     1. Update the existing infrastructure (recommended and not destructive if samples already exist)')
            print_plain('     2. Use a different index')
            print_plain('     3. Exit, then delete the existing resource group separately via the clean-up notebook\n')

            while True:
                choice = input('\nEnter your choice (1, 2, or 3): ').strip()

                # Default to option 1 if user just presses Enter
                if choice == '1':
                    return False  # Allow deployment to proceed
                elif not choice or choice in('2', '3'):
                    return True  # Block deployment
                else:
                    print_plain('❌ Invalid choice. Please enter 1, 2, or 3.')
        else:
            print_plain('ℹ️  To redeploy, either:')
            print_plain('     1. Use a different index, or')
            print_plain('     2. Exit, then delete the existing resource group separately via the clean-up notebook\n')

        return True
    else:
        print_plain('   Infrastructure does not yet exist.')
        return False

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
    # Note: Check for leading slash to handle POSIX paths on Windows
    if (path_obj.is_absolute() or
        policy_xml_filepath_or_filename.startswith('/') or
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
                raise ValueError(f'Could not auto-detect sample name. Please provide sample_name parameter explicitly. Error: {e}') from e

        # Construct the full path
        project_root = get_project_root()
        policy_xml_filepath = str(Path(project_root) / 'samples' / sample_name / policy_xml_filepath_or_filename)

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

# Validation functions will raise ValueError if the value is not valid

def validate_http_verb(val):
    """Validate HTTP verb value."""
    return HTTP_VERB(val)

def validate_sku(val):
    """Validate APIM SKU value."""
    return APIM_SKU(val)

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

    success = az.check_apim_blob_permissions(apim_name, storage_account_name, resource_group_name, max_wait_minutes)

    if success:
        print_ok('Permission check passed! Ready to proceed with secure blob access tests.')
    else:
        print_error('Permission check failed. Please check the deployment and try again later.')
        print_info('Tip: You can also run the verify-permissions.ps1 script to manually check role assignments.')

    print_plain('')

    return success

def test_url_preflight_check(deployment: INFRASTRUCTURE, rg_name: str, apim_gateway_url: str) -> str:
    # Preflight: Check if the infrastructure architecture deployment uses Azure Front Door. If so, assume that APIM is not directly accessible and use the Front Door URL instead.

    print_message('Checking if the infrastructure architecture deployment uses Azure Front Door.', blank_above = True)

    afd_endpoint_url = az.get_frontdoor_url(deployment, rg_name)

    if afd_endpoint_url:
        endpoint_url = afd_endpoint_url
        print_message(f'Using Azure Front Door URL: {afd_endpoint_url}', blank_above = True)
    else:
        endpoint_url = apim_gateway_url
        print_message(f'Using APIM Gateway URL: {apim_gateway_url}', blank_above = True)

    return endpoint_url

def get_endpoints(deployment: INFRASTRUCTURE, rg_name: str) -> Endpoints:
    print_message(f'Identifying possible endpoints for infrastructure {deployment}...')

    endpoints = Endpoints(deployment)

    endpoints.afd_endpoint_url = az.get_frontdoor_url(deployment, rg_name)
    endpoints.apim_endpoint_url = az.get_apim_url(rg_name)
    endpoints.appgw_hostname, endpoints.appgw_public_ip = az.get_appgw_endpoint(rg_name)

    return endpoints

def get_json(json_str: str) -> Any:
    """
    Safely parse a JSON string or file content into a Python object.

    Args:
        json_str (str): The JSON string or file content to parse.

    Returns:
        Any: The parsed JSON object, or None if parsing fails.
    """

    # If the result is a string, try to parse it as JSON
    if isinstance(json_str, str):
        # First try JSON parsing (handles double quotes)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # If JSON fails, try Python literal evaluation (handles single quotes)
        try:
            return ast.literal_eval(json_str)
        except (ValueError, SyntaxError) as e:
            print_error(f'Failed to parse deployment output as Python literal. Error: {e}')

    # Return the original result if it's not a string or can't be parsed
    return json_str
