"""Run existing Bicep resource-group deployment workflows."""

import json
import os

# APIM Samples imports
import azure_resources as az
import logging_config
from apimtypes import INFRASTRUCTURE, Output, find_project_root, get_project_root
from console import print_plain


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
        return f'{base_message} Enable DEBUG logging in workspace root .env file, then rerun to see details.'

    return base_message


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


def create_bicep_deployment_group(
    rg_name: str,
    rg_location: str,
    deployment: str | INFRASTRUCTURE,
    bicep_parameters: dict,
    bicep_parameters_file: str = 'params.json',
    rg_tags: dict | None = None,
    is_debug: bool = False,
) -> Output:
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
        'parameters': bicep_parameters,
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
    if not os.path.exists(main_bicep_path):  # pragma: no cover
        raise FileNotFoundError(f'main.bicep file not found in expected infrastructure directory: {bicep_dir}')

    cmd = f'az deployment group create --name {deployment_name} --resource-group {rg_name} --template-file "{main_bicep_path}" --parameters "{params_file_path}" --query "properties.outputs"'

    if is_debug:
        cmd += ' --debug'

    print_plain('\nDeploying bicep...\n')
    # Bicep deployments routinely run longer than the default 240s subprocess timeout
    # (APIM provisioning alone can take 30+ minutes). Use a 30-minute cap so a long-running
    # but successful deployment is not reported as a transient "Command failed" / retry.
    return az.run(cmd, f"Deployment '{deployment_name}' succeeded", get_deployment_failure_message(deployment_name), timeout=1800)


def create_bicep_deployment_group_for_sample(
    sample_name: str,
    rg_name: str,
    rg_location: str,
    bicep_parameters: dict,
    bicep_parameters_file: str = 'params.json',
    rg_tags: dict | None = None,
    is_debug: bool = False,
) -> Output:
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
        print_plain(f'📁 Changed working directory to: {sample_dir}', blank_above=True)

        # Call the original deployment function
        return create_bicep_deployment_group(rg_name, rg_location, sample_name, bicep_parameters, bicep_parameters_file, rg_tags, is_debug)

    finally:
        # Always restore the original working directory
        os.chdir(original_cwd)
        print_plain(f'📁 Restored working directory to: {original_cwd}')
