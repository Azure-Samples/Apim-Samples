"""Run existing Bicep resource-group deployment workflows.

Autoreload: reload_safe
Functions reload between cells. Changed templates still require an explicit deployment.
"""

import json
import os
import tempfile
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path

# APIM Samples imports
import azure_resources as az
import logging_config
from apimtypes import INFRASTRUCTURE, Output, find_project_root, get_project_root
from console import print_debug, print_plain


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
    except (OSError, RuntimeError, ValueError) as exc:
        print_debug(f'Project-root lookup failed while resolving Bicep directory {infrastructure_dir!r}: {exc}. Falling back to the current directory.')

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
    *,
    template_path: str | Path | None = None,
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
        template_path: Explicit template path; omitted for legacy directory discovery.

    Returns:
        Output: The result of the deployment command.
    """

    deployment_name = deployment.value if isinstance(deployment, INFRASTRUCTURE) else deployment
    if template_path is None:
        template_path = os.path.join(_determine_bicep_directory(deployment_name), 'main.bicep')
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f'Bicep template not found: {template_path}')

    az.create_resource_group(rg_name, rg_location, rg_tags)

    return deploy_bicep_template(
        rg_name,
        deployment_name,
        template_path,
        bicep_parameters,
        parameters_path = os.path.join(os.path.dirname(template_path), bicep_parameters_file),
        is_debug = is_debug,
    )


def deploy_bicep_template(
    rg_name: str,
    deployment_name: str,
    template_path: str | Path,
    bicep_parameters: dict,
    *,
    parameters_path: str | Path | None = None,
    sensitive_output: bool = False,
    is_debug: bool = False,
    ok_message: str | None = None,
    error_message: str | None = None,
    recover: Callable[[], bool] | None = None,
    runner: Callable[..., Output] | None = None,
) -> Output:
    """Deploy an explicit template without changing cwd or creating a resource group.

    Omit parameters_path to use an owned temporary directory. Sensitive deployments
    always use temporary parameters and suppress CLI debug. A recovery callback may
    authorize one retry; the same command and parameter file are used for both attempts.
    """
    template_path = os.path.abspath(template_path)
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f'Bicep template not found: {template_path}')

    temporary_parameters = sensitive_output or parameters_path is None
    directory = tempfile.TemporaryDirectory(prefix = 'apim-deployment-') if temporary_parameters else nullcontext()
    with directory as temporary_directory:
        if temporary_directory is not None:
            params_path = os.path.join(temporary_directory, 'params.json')
        else:
            assert parameters_path is not None
            params_path = os.path.abspath(parameters_path)
        document = {
            '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#',
            'contentVersion': '1.0.0.0',
            'parameters': bicep_parameters,
        }
        with open(params_path, 'w', encoding = 'utf-8', newline = '\n') as file:
            file.write(json.dumps(document))

        command = [
            'az', 'deployment', 'group', 'create',
            '--name', deployment_name, '--resource-group', rg_name,
            '--template-file', template_path, '--parameters', params_path,
            '--query', 'properties.outputs',
        ]
        if is_debug and not sensitive_output:
            command.append('--debug')

        print_plain('\nDeploying bicep...\n')
        run = runner if runner is not None else az.run
        recovery_attempted = False
        while True:
            output = run(
                command,
                ok_message if ok_message is not None else f"Deployment '{deployment_name}' succeeded",
                error_message if error_message is not None else get_deployment_failure_message(deployment_name),
                sensitive_output = sensitive_output,
                timeout = 1800,
                retries = 0,
            )
            if output.success or recovery_attempted or recover is None or not recover():
                return output
            recovery_attempted = True


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
    Create a Bicep deployment for a sample without changing the working directory.
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

    current_dir = os.getcwd()
    sample_dir = current_dir if os.path.basename(current_dir) == sample_name else os.path.join(find_project_root(), 'samples', sample_name)
    main_bicep_path = os.path.join(sample_dir, 'main.bicep')
    if not os.path.isfile(main_bicep_path):
        raise FileNotFoundError(f'main.bicep not found in sample directory: {sample_dir}')

    return create_bicep_deployment_group(
        rg_name, rg_location, sample_name, bicep_parameters, bicep_parameters_file, rg_tags, is_debug,
        template_path = main_bicep_path,
    )
