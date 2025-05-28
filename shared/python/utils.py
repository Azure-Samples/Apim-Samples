"""
Module providing utility functions.
"""

import datetime
import json
import os
import subprocess
import textwrap
import time
import traceback

from typing import Any, Tuple
from apimtypes import APIM_SKU, HTTP_VERB, INFRASTRUCTURE


# ------------------------------
#    DECLARATIONS
# ------------------------------


# Define ANSI escape code constants for clarity in the print commands below
RESET   = "\x1b[0m"
BOLD_B  = "\x1b[1;34m"   # blue
BOLD_R  = "\x1b[1;31m"   # red
BOLD_G  = "\x1b[1;32m"   # green
BOLD_Y  = "\x1b[1;33m"   # yellow

CONSOLE_WIDTH = 175


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
            self.json_data = json.loads(text)
        else:
            # Check if a substring in the string is JSON.
            self.json_data = extract_json(text)

        self.is_json = self.json_data is not None

    def get(self, key: str, label: str = '', secure: bool = False) -> str | None:
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
                raise KeyError("json_data is not a dict")

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

            if label:
                if secure and isinstance(deployment_output, str) and len(deployment_output) >= 4:
                    print_val(label, f"****{deployment_output[-4:]}")
                else:
                    print_val(label, deployment_output)

            return str(deployment_output)

        except Exception as e:
            error = f"Failed to retrieve output property: '{key}'\nError: {e}"
            print_error(error)

            if label:
                raise Exception(error)

            return None


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
        print_error("Missing deployment name parameter.")
        return

    if not rg_name:
        print_error("Missing resource group name parameter.")
        return

    try:
        print_info(f"🧹 Cleaning up resource group '{rg_name}'...")

        # Show the deployment details
        output = run(f"az deployment group show --name {deployment_name} -g {rg_name} -o json", "Deployment retrieved", "Failed to retrieve the deployment")

        if output.success and output.json_data:
            provisioning_state = output.json_data.get("properties").get("provisioningState")
            print_info(f"Deployment provisioning state: {provisioning_state}")

            # Delete and purge CognitiveService accounts
            output = run(f" az cognitiveservices account list -g {rg_name}", f"Listed CognitiveService accounts", f"Failed to list CognitiveService accounts")
            if output.success and output.json_data:
                for resource in output.json_data:
                    print_info(f"Deleting and purging Cognitive Service Account '{resource['name']}' in resource group '{rg_name}'...")
                    output = run(f"az cognitiveservices account delete -g {rg_name} -n {resource['name']}", f"Cognitive Services '{resource['name']}' deleted", f"Failed to delete Cognitive Services '{resource['name']}'")
                    output = run(f"az cognitiveservices account purge -g {rg_name} -n {resource['name']} -l \"{resource['location']}\"", f"Cognitive Services '{resource['name']}' purged", f"Failed to purge Cognitive Services '{resource['name']}'")

            # Delete and purge APIM resources
            output = run(f" az apim list -g {rg_name}", f"Listed APIM resources", f"Failed to list APIM resources")
            if output.success and output.json_data:
                for resource in output.json_data:
                    print_info(f"Deleting and purging API Management '{resource['name']}' in resource group '{rg_name}'...")
                    output = run(f"az apim delete -n {resource['name']} -g {rg_name} -y", f"API Management '{resource['name']}' deleted", f"Failed to delete API Management '{resource['name']}'")
                    output = run(f"az apim deletedservice purge --service-name {resource['name']} --location \"{resource['location']}\"", f"API Management '{resource['name']}' purged", f"Failed to purge API Management '{resource['name']}'")

            # Delete and purge Key Vault resources
            output = run(f" az keyvault list -g {rg_name}", f"Listed Key Vault resources", f"Failed to list Key Vault resources")
            if output.success and output.json_data:
                for resource in output.json_data:
                    print_info(f"Deleting and purging Key Vault '{resource['name']}' in resource group '{rg_name}'...")
                    output = run(f"az keyvault delete -n {resource['name']} -g {rg_name}", f"Key Vault '{resource['name']}' deleted", f"Failed to delete Key Vault '{resource['name']}'")
                    output = run(f"az keyvault purge -n {resource['name']} --location \"{resource['location']}\"", f"Key Vault '{resource['name']}' purged", f"Failed to purge Key Vault '{resource['name']}'")

            # Delete the resource group last
            print_message(f"🧹 Deleting resource group '{rg_name}'...")
            output = run(f"az group delete --name {rg_name} -y", f"Resource group '{rg_name}' deleted", f"Failed to delete resource group '{rg_name}'")

            print_message("🧹 Cleanup completed.")

    except Exception as e:
        print(f"An error occurred during cleanup: {e}")
        traceback.print_exc()

def _print_log(message: str, prefix: str = '', color: str = '', output: str = '', duration: str = '', show_time: bool = False, blank_above: bool = False, blank_below: bool = False) -> None:
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
    """
    time_str    = f" ⌚ {datetime.datetime.now().time()}" if show_time else ""
    output_str  = f" {output}" if output else ""

    if blank_above:
        print()

    # To preserve explicit newlines in the message (e.g., from print_val with val_below=True),
    # split the message on actual newlines and wrap each line separately, preserving blank lines and indentation.
    full_message = f"{prefix}{color}{message}{RESET}{time_str} {duration}{output_str}"
    lines = full_message.splitlines(keepends = False)

    for line in lines:
        wrapped = textwrap.fill(line, width = CONSOLE_WIDTH)
        print(wrapped)

    if blank_below:
        print()


# ------------------------------
#    PUBLIC METHODS
# ------------------------------

print_command   = lambda cmd = ''                                               : _print_log(cmd, '⚙️ ', BOLD_B)
print_error     = lambda msg, output = '', duration = ''                        : _print_log(msg, '⛔ ', BOLD_R, output, duration, True)
print_info      = lambda msg, blank_above = False                               : _print_log(msg, '👉🏽 ', BOLD_B, blank_above = blank_above)
print_message   = lambda msg, output = '', duration = '', blank_above = False   : _print_log(msg, '👉🏽 ', BOLD_G, output, duration, True, blank_above)
print_ok        = lambda msg, output = '', duration = '', blank_above = True    : _print_log(msg, '✅ ', BOLD_G, output, duration, True, blank_above)
print_warning   = lambda msg, output = '', duration = ''                        : _print_log(msg, '⚠️ ', BOLD_Y, output, duration, True)
print_val       = lambda name, value, val_below = False                         : _print_log(f"{name:<25}:{'\n' if val_below else ' '}{value}", '👉🏽 ', BOLD_B)

def create_bicep_deployment_group(rg_name: str, rg_location: str, deployment: str | INFRASTRUCTURE, bicep_parameters: dict, bicep_parameters_file: str = 'params.json') -> Output:
    """
    Create a Bicep deployment in a resource group, writing parameters to a file and running the deployment.
    Creates the resource group if it does not exist.

    Args:
        rg_name (str): Name of the resource group.
        rg_location (str): Azure region for the resource group.
        deployment (str | INFRASTRUCTURE): Deployment name or enum value.
        bicep_parameters: Parameters for the Bicep template.
        bicep_parameters_file (str, optional): File to write parameters to.

    Returns:
        Output: The result of the deployment command.
    """

    # Create the resource group if doesn't exist
    create_resource_group(rg_name, rg_location)

    if hasattr(deployment, 'value'):
        deployment_name = deployment.value
    else:
        deployment_name = deployment

    bicep_parameters_format = {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
        "contentVersion": "1.0.0.0",
        "parameters": bicep_parameters
    }

    # Write the updated bicep parameters to the specified parameters file
    with open(bicep_parameters_file, 'w') as file:
        file.write(json.dumps(bicep_parameters_format))

    print(f"📝 Updated the policy XML in the bicep parameters file '{bicep_parameters_file}'")

    return run(f"az deployment group create --name {deployment_name} --resource-group {rg_name} --template-file main.bicep --parameters {bicep_parameters_file} --query \"properties.outputs\"",
        f"Deployment '{deployment_name}' succeeded", f"Deployment '{deployment_name}' failed.")

def create_resource_group(rg_name: str, resource_group_location: str | None = None) -> None:
    """
    Create a resource group in Azure if it does not already exist.

    Args:
        rg_name (str): Name of the resource group.
        resource_group_location (str, optional): Azure region for the resource group.

    Returns:
        None
    """

    if not does_resource_group_exist(rg_name):
        print_info(f"Creating the resource group now...")

        run(f"az group create --name {rg_name} --location {resource_group_location} --tags source=apim-sample",
            f"Resource group '{rg_name}' created",
            f"Failed to create the resource group '{rg_name}'", 
            False, True, False, False)

def does_resource_group_exist(rg_name: str) -> bool:
    """
    Check if a resource group exists in Azure.

    Args:
        rg_name (str): Name of the resource group.

    Returns:
        bool: True if the resource group exists, False otherwise.
    """

    output = run(f"az group show --name {rg_name}", print_output = False, print_errors = False)
    return output.success

def policy_xml_replacement(policy_xml_filepath: str) -> str:
    """
    Read and return the contents of a policy XML file.

    Args:
        policy_xml_filepath (str): Path to the policy XML file.

    Returns:
        str: Contents of the policy XML file.
    """

    # Read the specified policy XML file
    with open(policy_xml_filepath, 'r') as policy_xml_file:
        policy_template_xml = policy_xml_file.read()

    # TODO: Perform any replacements here

    # Convert the XML to JSON format
    return policy_template_xml

def read_policy_xml(policy_xml_filepath: str) -> str:
    """
    Read and return the contents of a policy XML file.

    Args:
        policy_xml_filepath (str): Path to the policy XML file.

    Returns:
        str: Contents of the policy XML file.
    """

    # Read the specified policy XML file
    with open(policy_xml_filepath, 'r') as policy_xml_file:
        policy_template_xml = policy_xml_file.read()

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

    for idx in indexes_list:
        print_info(f"Cleaning up resources for {deployment} - {idx}", True)
        rg_name = get_infra_rg_name(deployment, idx)
        _cleanup_resources(deployment.value, rg_name)

def cleanup_deployment(deployment: str, indexes: int | list[int] | None = None) -> None:
    """
    Clean up sample deployments by deployment name and index/indexes.
    Obtains the resource group name for each index and calls the private cleanup method.

    Args:
        deployment (str): The deployment name (string).
        indexes (int | list[int] | None): A single index, a list of indexes, or None for no index.
    """
    if not isinstance(deployment, str):
        raise ValueError("deployment must be a string")
    if indexes is None:
        indexes_list = [None]
    elif isinstance(indexes, (list, tuple)):
        indexes_list = list(indexes)
    else:
        indexes_list = [indexes]
    for idx in indexes_list:
        rg_name = get_rg_name(deployment, idx)
        _cleanup_resources(deployment, rg_name)

def extract_json(text: str) -> any:
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
        return json.loads(text)

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

    try:
        json.loads(text)
        return True
    except (ValueError, TypeError):
        return False

def get_account_info() -> Tuple[str, str, str]:
    """
    Retrieve the current Azure account information using the Azure CLI.

    Returns:
        tuple: (current_user, tenant_id, subscription_id)

    Raises:
        Exception: If account information cannot be retrieved.
    """

    output = run("az account show", "Retrieved az account", "Failed to get the current az account")

    if output.success and output.json_data:
        current_user = output.json_data['user']['name']
        tenant_id = output.json_data['tenantId']
        subscription_id = output.json_data['id']

        print_val("Current user", current_user)
        print_val("Tenant ID", tenant_id)
        print_val("Subscription ID", subscription_id)

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
        raise RuntimeError("Notebook path could not be determined.")
    
    print_val("Deployment name", notebook_path)

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
        output = run(f"az afd profile list -g {rg_name} -o json")

        if output.success and output.json_data:
            afd_profile_name = output.json_data[0]['name']
            print_ok(f"Front Door Profile Name: {afd_profile_name}", blank_above = False)

            if afd_profile_name:
                output = run(f"az afd endpoint list -g {rg_name} --profile-name {afd_profile_name} -o json")

                if output.success and output.json_data:
                    afd_hostname = output.json_data[0]['hostName']

                    if afd_hostname:
                        afd_endpoint_url = f"https://{afd_hostname}"

    if afd_endpoint_url:
        print_ok(f"Front Door Endpoint URL: {afd_endpoint_url}", blank_above = False)
    else:
        print_error("No Front Door endpoint URL found. Please check the deployment and ensure that Azure Front Door is configured correctly.")

    return afd_endpoint_url

def get_infra_rg_name(deployment_name: INFRASTRUCTURE, index: int | None = None) -> str:
    """
    Generate a resource group name for infrastructure deployments, optionally with an index.

    Args:
        deployment_name (INFRASTRUCTURE): The infrastructure deployment enum value.
        index (int, optional): An optional index to append to the name.

    Returns:
        str: The generated resource group name.
    """

    rg_name = f"apim-infra-{deployment_name.value}"

    if index is not None:
        rg_name = f"{rg_name}-{str(index)}"

    print_val("Resource group name", rg_name)

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

    rg_name = f"apim-sample-{deployment_name}"

    if index is not None:
        rg_name = f"{rg_name}-{str(index)}"

    print_val("Resource group name", rg_name)
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
        output_text = subprocess.check_output(command, shell = True, stderr = subprocess.STDOUT).decode("utf-8")
        success = True
    except Exception as e:
        # Handles both CalledProcessError and any custom/other exceptions (for test mocks)
        output_text = getattr(e, 'output', b'').decode("utf-8") if hasattr(e, 'output') and isinstance(e.output, (bytes, bytearray)) else str(e)
        success = False

    if print_output:
        print(f"Command output:\n{output_text}")

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
            print_message(ok_message if success else error_message, output_text if not success or print_output else "", f"[{int(minutes)}m:{int(seconds)}s]")

    return Output(success, output_text)

# Validation functions will raise ValueError if the value is not valid

validate_http_verb      = lambda val: HTTP_VERB(val)
validate_sku            = lambda val: APIM_SKU(val)

def validate_infrastructure(infra: INFRASTRUCTURE, supported_infras: list[INFRASTRUCTURE]) -> bool:
    """
    Validate that the provided infrastructure is a supported infrastructure.

    Args:
        infra (INFRASTRUCTURE): The infrastructure deployment enum value.
        supported_infras (list[INFRASTRUCTURE]): List of supported infrastructures.

    Raises:
        ValueError: If the infrastructure is not supported.
    """

    if infra not in supported_infras:
        raise ValueError(f"Unsupported infrastructure: {infra}. Supported infrastructures are: {', '.join([i.value for i in supported_infras])}")