"""
Module providing Azure resource management functions, often wrapped with additional functionality.

This module contains functions for interacting with Azure resources,
including resource groups, deployments, and various Azure services.
"""

import json
import time
import tempfile
import os
import re
import subprocess
import traceback
from typing import Tuple, Optional

# APIM Samples imports
from apimtypes import INFRASTRUCTURE, Endpoints, Output
from console import print_ok, print_warning, print_error, print_val, print_message, print_info, print_command, print_success

# Explicitly define what is exported with 'from azure_resources import *'
__all__ = [
    # Public functions
    'cleanup_old_jwt_signing_keys',
    'check_apim_blob_permissions',
    'find_infrastructure_instances',
    'create_resource_group',
    'get_azure_role_guid',
    'does_resource_group_exist',
    'get_resource_group_location',
    'get_account_info',
    'get_deployment_name',
    'get_frontdoor_url',
    'get_apim_url',
    'get_appgw_endpoint',
    'get_infra_rg_name',
    'get_unique_suffix_for_resource_group',
    'get_rg_name',
    'get_endpoints',
    # Private functions (exported for backward compatibility)
    '_run',
]


# ------------------------------
#    PRIVATE FUNCTIONS
# ------------------------------

def _run(command: str, ok_message: str = '', error_message: str = '', print_output: bool = False, print_command_to_run: bool = True, print_errors: bool = True, print_warnings: bool = True) -> Output:
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
        Output: An Output object containing success status, text, and parsed JSON data.
    """

    if print_command_to_run:
        print_command(command)

    start_time = time.time()

    # Execute the command and capture the output
    try:
        output_text = subprocess.check_output(command, shell = True, stderr = subprocess.STDOUT).decode('utf-8')
        success = True
    except subprocess.CalledProcessError as e:
        output_bytes = e.output if isinstance(e.output, (bytes, bytearray)) else b''
        output_text = output_bytes.decode('utf-8')
        success = False
    except Exception as e:
        # Covers unexpected errors (and test mocks) without assuming an 'output' attribute exists.
        output_text = str(e)
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

            if l.lower().startswith('error'):
                if l and print_errors:
                    print_error(l)
                continue

        print_message = print_ok if success else print_error

        if (ok_message or error_message):
            print_message(ok_message if success else error_message, output_text if not success or print_output else '', f'[{int(minutes)}m:{int(seconds)}s]')

    return Output(success, output_text)


# ------------------------------
#    PUBLIC FUNCTIONS
# ------------------------------

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

        output = _run(
            f'az apim nv list --service-name "{apim_name}" --resource-group "{resource_group_name}" --query "[?contains(name, \'JwtSigningKey\')].name" -o tsv',
            'Retrieved JWT signing keys',
            'Failed to retrieve JWT signing keys'
        )

        if not output.success:
            print_error('Failed to retrieve JWT signing keys from APIM.')
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
                delete_output = _run(
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
    apim_identity_output = _run(
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
    storage_account_output = _run(
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
        role_assignment_output = _run(
            f"az role assignment list --assignee {principal_id} --scope {storage_account_id} --role {blob_reader_role_id} --query '[0].id' -o tsv",
            error_message='Failed to check role assignment',
            print_command_to_run=True,
            print_errors=False
        )

        if role_assignment_output.success and role_assignment_output.text.strip():
            print_success('Role assignment found! APIM managed identity has Storage Blob Data Reader permissions.')

            # Additional check: try to test blob access using the managed identity
            print_info('Testing actual blob access...')
            test_access_output = _run(
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

        if not elapsed_time:
            print_info('Role assignment not found yet. Waiting for Azure AD propagation...')
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

def find_infrastructure_instances(infrastructure: INFRASTRUCTURE) -> list[tuple[INFRASTRUCTURE, int | None]]:
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
    output = _run(query_cmd, print_command_to_run = False, print_errors = False)

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
        # Build the tags string for the Azure CLI command
        tag_string = 'source=apim-sample'
        if tags:
            for key, value in tags.items():
                # Escape values that contain spaces or special characters
                escaped_value = value.replace('"', '\\"') if isinstance(value, str) else str(value)
                tag_string += f' {key}=\"{escaped_value}\"'

        _run(f'az group create --name {rg_name} --location {resource_group_location} --tags {tag_string}',
            f"Resource group '{rg_name}' created",
            f"Failed to create the resource group '{rg_name}'",
            False, False, False, False)

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

def does_resource_group_exist(resource_group_name: str) -> bool:
    """
    Check if a resource group exists in the current Azure subscription.

    Args:
        resource_group_name (str): The name of the resource group to check.

    Returns:
        bool: True if the resource group exists, False otherwise.
    """

    output = _run(f'az group show --name {resource_group_name} -o json', print_command_to_run = False, print_errors = False)

    return output.success

def get_resource_group_location(resource_group_name: str) -> str | None:
    """
    Get the location of an existing resource group.

    Args:
        resource_group_name (str): The name of the resource group.

    Returns:
        str | None: The location of the resource group if found, otherwise None.
    """

    output = _run(f'az group show --name {resource_group_name} --query "location" -o tsv', print_command_to_run = False, print_errors = False)

    if output.success and output.text.strip():
        return output.text.strip()

    return None

def get_account_info() -> Tuple[str, str, str, str]:
    """
    Retrieve the current Azure account information using the Azure CLI.

    Returns:
        tuple: (current_user, current_user_id, tenant_id, subscription_id)

    Raises:
        Exception: If account information cannot be retrieved.
    """

    account_show_output = _run('az account show', 'Retrieved az account', 'Failed to get the current az account', print_command_to_run = False)
    ad_user_show_output = _run('az ad signed-in-user show', 'Retrieved az ad signed-in-user', 'Failed to get the current az ad signed-in-user', print_command_to_run = False)

    if account_show_output.success and account_show_output.json_data and ad_user_show_output.success and ad_user_show_output.json_data:
        current_user = account_show_output.json_data['user']['name']
        tenant_id = account_show_output.json_data['tenantId']
        subscription_id = account_show_output.json_data['id']
        current_user_id = ad_user_show_output.json_data['id']

        print_val('Current user', current_user)
        print_val('Current user ID', current_user_id)
        print_val('Tenant ID', tenant_id)
        print_val('Subscription ID', subscription_id)

        return current_user, current_user_id, tenant_id, subscription_id
    else:
        error = 'Failed to retrieve account information. Please ensure the Azure CLI is installed, you are logged in, and the subscription is set correctly.'
        print_error(error)
        raise Exception(error)

def get_deployment_name(directory_name: str | None = None) -> str:
    """
    Get a standardized deployment name based on the working directory.

    Args:
        directory_name (str | None): Optional directory name. If None, uses current working directory.

    Returns:
        str: The deployment name based on the directory.
    """

    if directory_name is None:
        directory_name = os.path.basename(os.getcwd())

    deployment_name = f'deploy-{directory_name}-{int(time.time())}'

    print_val('Deployment name', deployment_name)
    return deployment_name

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
        output = _run(f'az afd profile list -g {rg_name} -o json')

        if output.success and output.json_data:
            afd_profile_name = output.json_data[0]['name']
            print_ok(f'Front Door Profile Name: {afd_profile_name}', blank_above = False)

            if afd_profile_name:
                output = _run(f'az afd endpoint list -g {rg_name} --profile-name {afd_profile_name} -o json')

                if output.success and output.json_data:
                    afd_hostname = output.json_data[0]['hostName']

                    if afd_hostname:
                        afd_endpoint_url = f'https://{afd_hostname}'

    if afd_endpoint_url:
        print_ok(f'Front Door Endpoint URL: {afd_endpoint_url}', blank_above = False)
    else:
        print_warning('No Front Door endpoint URL found.')

    return afd_endpoint_url

def get_apim_url(rg_name: str) -> str | None:
    """
    Retrieve the gateway URL for the API Management service in the specified resource group.

    Args:
        rg_name (str): The name of the resource group containing the APIM service.

    Returns:
        str | None: The gateway URL (https) of the APIM service if found, otherwise None.
    """

    apim_endpoint_url: str | None = None

    output = _run(f'az apim list -g {rg_name} -o json', print_command_to_run = False)

    if output.success and output.json_data:
        apim_gateway_url = output.json_data[0]['gatewayUrl']
        print_ok(f'APIM Service Name: {output.json_data[0]["name"]}', blank_above = False)

        if apim_gateway_url:
            apim_endpoint_url = apim_gateway_url

    if apim_endpoint_url:
        print_ok(f'APIM Gateway URL: {apim_endpoint_url}', blank_above = False)
    else:
        print_warning('No APIM gateway URL found.')

    return apim_endpoint_url

def get_appgw_endpoint(rg_name: str) -> Tuple[str | None, str | None]:
    """
    Retrieve the hostname and public IP address for the Application Gateway in the specified resource group.

    Args:
        rg_name (str): The name of the resource group containing the Application Gateway.

    Returns:
        Tuple[str | None, str | None]: A tuple containing (hostname, public_ip) if found, otherwise (None, None).
    """

    hostname: str | None = None
    public_ip: str | None = None

    # Get Application Gateway details
    output = _run(f'az network application-gateway list -g {rg_name} -o json', print_command_to_run = False)

    if output.success and output.json_data:
        appgw_name = output.json_data[0]['name']
        print_ok(f'Application Gateway Name: {appgw_name}', blank_above = False)

        # Get hostname
        http_listeners = output.json_data[0].get('httpListeners', [])

        for listener in http_listeners:
            # Assume that only a single hostname is used, not the hostnames array
            if listener.get('hostName'):
                hostname = listener['hostName']

        # Get frontend IP configuration to find public IP reference
        frontend_ip_configs = output.json_data[0].get('frontendIPConfigurations', [])
        public_ip_id = None

        for config in frontend_ip_configs:
            if config.get('publicIPAddress'):
                public_ip_id = config['publicIPAddress']['id']
                break

        if public_ip_id:
            # Extract public IP name from the resource ID
            public_ip_name = public_ip_id.split('/')[-1]

            # Get public IP details
            ip_output = _run(f'az network public-ip show -g {rg_name} -n {public_ip_name} -o json', print_command_to_run = False)

            if ip_output.success and ip_output.json_data:
                public_ip = ip_output.json_data.get('ipAddress')

    return hostname, public_ip

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

def get_unique_suffix_for_resource_group(rg_name: str) -> str:
    """
    Get the exact uniqueString value that Bicep/ARM generates for a resource group.

    Uses a minimal ARM deployment to ensure the value matches exactly what
    Bicep's uniqueString(subscription().id, resourceGroup().id) produces.

    Args:
        rg_name (str): The resource group name (must already exist).

    Returns:
        str: The 13-character unique string matching Bicep's uniqueString output.
    """

    # Minimal ARM template that just outputs the uniqueString
    template = json.dumps({
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "resources": [],
        "outputs": {
            "suffix": {
                "type": "string",
                "value": "[uniqueString(subscription().id, resourceGroup().id)]"
            }
        }
    })

    # Write template to temp file
    with tempfile.NamedTemporaryFile(mode = 'w', suffix = '.json', delete = False) as f:
        f.write(template)
        template_path = f.name

    try:
        deployment_name = f'get-suffix-{int(time.time())}'
        output = _run(
            f'az deployment group create --name {deployment_name} --resource-group {rg_name} --template-file "{template_path}" --query "properties.outputs.suffix.value" -o tsv',
            print_command_to_run = False,
            print_errors = False
        )

        if output.success and output.text.strip():
            return output.text.strip()

        print_error('Could not get uniqueString from Azure.')
        return ''
    finally:
        try:
            os.unlink(template_path)
        except Exception:
            pass

def get_rg_name(deployment_name: str, index: int | None = None) -> str:
    """
    Generate a resource group name for a sample deployment, optionally with an index.

    Args:
        deployment_name (str): The base name for the deployment.
        index (int | None): An optional index to append to the name.

    Returns:
        str: The generated resource group name.
    """

    rg_name = f'apim-sample-{deployment_name}'

    if index is not None:
        rg_name = f'{rg_name}-{str(index)}'

    print_val('Resource group name', rg_name)
    return rg_name

def get_endpoints(deployment: INFRASTRUCTURE, rg_name: str) -> Endpoints:
    """
    Retrieve all possible endpoints for a given infrastructure deployment.

    Args:
        deployment (INFRASTRUCTURE): The infrastructure deployment enum value.
        rg_name (str): The name of the resource group.

    Returns:
        Endpoints: An object containing all discovered endpoints.
    """

    print_message(f'Identifying possible endpoints for infrastructure {deployment}...')

    endpoints = Endpoints(deployment)

    endpoints.afd_endpoint_url = get_frontdoor_url(deployment, rg_name)
    endpoints.apim_endpoint_url = get_apim_url(rg_name)
    endpoints.appgw_hostname, endpoints.appgw_public_ip = get_appgw_endpoint(rg_name)

    return endpoints
