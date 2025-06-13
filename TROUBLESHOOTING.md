# Troubleshooting Guide

This guide helps you resolve common issues when working with the Azure API Management samples.

## Table of Contents

- [Deployment Errors](#deployment-errors)
- [Authentication Issues](#authentication-issues)
- [Notebook and Development Environment Issues](#notebook-and-development-environment-issues)
- [Azure CLI Issues](#azure-cli-issues)
- [Resource Management Issues](#resource-management-issues)
- [Getting Additional Help](#getting-additional-help)

## Deployment Errors

### "The content for this response was already consumed"

**Error Message:**
```
ERROR: The content for this response was already consumed
```

**Root Cause:** This misleading error message often indicates a Bicep template validation error, typically caused by parameter mismatches between the notebook and the Bicep template.

**Solution:**
1. Run the Azure CLI command with `--debug` to see the actual error:
   ```bash
   az deployment group validate --resource-group <rg-name> --template-file "main.bicep" --parameters "params.json" --debug
   ```

2. Look for the real error in the debug output, often something like:
   ```
   The following parameters were supplied, but do not correspond to any parameters defined in the template: 'parameterName'
   ```

3. Check that all parameters in your notebook's `bicep_parameters` dictionary match the parameters defined in the `main.bicep` file. 

**Example Fix:**
If the error mentions `apimSku` parameter not found:
```python
# ❌ Incorrect - includes undefined/unexpected apimSku parameter
bicep_parameters = {
    'apis': { 'value': [api.to_dict() for api in apis] },
    'apimSku': { 'value': 'Developer' }  # This parameter doesn't exist
}

# ✅ Correct - only includes defined parameters  
bicep_parameters = {
    'apis': { 'value': [api.to_dict() for api in apis] }
}
```

### "Resource already exists" Conflicts

**Error Message:**
```
The resource already exists and conflicts with...
```

**Solution:**
1. Use unique deployment names with timestamps:
   ```bash
   az deployment group create --name "sample-$(date +%Y%m%d-%H%M%S)" ...
   ```

2. Or delete existing conflicting resources:
   ```bash
   az resource delete --ids /subscriptions/.../resourceGroups/.../providers/...
   ```

### Module Path Resolution Errors

**Error Message:**
```
Unable to download the module...
```

**Solution:**
1. Ensure you're running deployments from the correct directory (sample directory, not project root)
2. Verify relative paths to shared modules are correct
3. The utility function `create_bicep_deployment_group_for_sample()` handles this automatically

## Authentication Issues

### Azure CLI Not Authenticated

**Error Message:**
```
Please run 'az login' to setup account
```

**Solution:**
```bash
az login
az account set --subscription "your-subscription-name-or-id"
```

You may also need to log into specific tenants:

```bash
az login --tenant "your-tenant-name-or-id"
az account set --subscription "your-subscription-name-or-id"
```

### Insufficient Permissions

**Error Message:**
```
The client does not have authorization to perform action...
```

**Solution:**
1. Ensure you have the necessary role assignments:
   - **Contributor** or **Owner** on the resource group/subscription
   - **API Management Service Contributor** for APIM-specific operations

2. Check your current permissions:
   ```bash
   az role assignment list --assignee $(az account show --query user.name -o tsv)
   ```

## Notebook and Development Environment Issues

### Module Import Errors

These can be a bit nebulous. When making changes to imported modules, they are not automatically picked up.

**Error Message:**
```
AttributeError: module 'utils' has no attribute 'function_name'
```

**Solution:**
Reload the utils module in your notebook by pressing `Restart` in the notebook to load updated files. You will need to re-run all cells from the beginning then as any variable assignments will have been lost.

**Anti-pattern:**

Avoid introducing a programmatic reload.

```python
import importlib
importlib.reload(utils)
```

### Python Path Issues

**Error Message:**
```
ModuleNotFoundError: No module named 'utils'
```

**Solution:**
Use the provided setup script:
```bash
python setup/setup_python_path.py --generate-env
```

### Working Directory Issues

**Error Message:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'main.bicep'
```

**Solution:**
Use the utility function that handles working directory management:
```python
# ✅ Use this instead of manual directory management
output = utils.create_bicep_deployment_group_for_sample('sample-name', rg_name, rg_location, bicep_parameters)
```

## Azure CLI Issues

### Rate Limiting

**Error Message:**
```
Rate limit exceeded
```

**Solution:**
1. Wait a few minutes before retrying
2. Reduce the frequency of API calls
3. Use `--verbose` to see retry information

### API Version Compatibility

**Error Message:**
```
The api-version '...' is invalid
```

**Solution:**
1. Update Azure CLI to the latest version:
   ```bash
   az upgrade
   ```

2. Check for newer API versions in the Bicep templates

## Resource Management Issues

### Resource Group Does Not Exist

**Error Message:**
```
Resource group 'name' could not be found
```

**Solution:**
1. Create the infrastructure first by running the appropriate infrastructure deployment from the `/infrastructure/` folder
2. Verify the resource group name matches the expected pattern:
   ```python
   rg_name = utils.get_infra_rg_name(deployment, index)
   ```

### APIM Service Not Found

**Error Message:**
```
API Management service 'name' not found
```

**Solution:**
1. Ensure the infrastructure deployment completed successfully
2. Check that the APIM service exists:
   ```bash
   az apim list --resource-group <rg-name>
   ```

3. Verify the naming pattern matches:
   ```bash
   az resource list --resource-group <rg-name> --resource-type Microsoft.ApiManagement/service
   ```

### Permission Propagation Delays

**Error Message:**
```
403 Forbidden / Access denied errors when accessing storage
```

**Solution:**
1. Azure role assignments can take 5-10 minutes to propagate
2. Use the built-in permission verification utility:
   ```python
   permissions_ready = utils.wait_for_apim_blob_permissions(
       apim_name=apim_name,
       storage_account_name=storage_account_name,
       resource_group_name=rg_name,
       max_wait_minutes=5
   )
   ```

## Getting Additional Help

### Enable Verbose Logging

For more detailed error information:

1. **Azure CLI:**
   ```bash
   az deployment group create ... --verbose --debug
   ```

2. **Python/Notebook:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

### Check Azure Activity Logs

1. In the Azure Portal, navigate to your resource group
2. Go to **Activity log** to see recent operations and any failures
3. Look for failed deployments and click for detailed error messages

### Validate Templates Before Deployment

```bash
az deployment group validate --resource-group <rg-name> --template-file "main.bicep" --parameters "params.json"
```

### Common Diagnostic Commands

```bash
# Check Azure CLI version and authentication
az version
az account show

# List available resource groups
az group list --output table

# Check resource group contents
az resource list --resource-group <rg-name> --output table

# Validate Bicep template
az deployment group validate --resource-group <rg-name> --template-file main.bicep --parameters params.json
```

### Report Issues

If you encounter issues not covered in this guide:

1. **Check existing issues:** [GitHub Issues](https://github.com/Azure-Samples/Apim-Samples/issues)
2. **Create a new issue** with:
   - Full error message
   - Steps to reproduce
   - Azure CLI version (`az version`)
   - Python version
   - Operating system

### Additional Resources

- [Azure CLI Troubleshooting](https://docs.microsoft.com/cli/azure/troubleshooting)
- [Azure Resource Manager Template Troubleshooting](https://docs.microsoft.com/azure/azure-resource-manager/troubleshooting)
- [API Management Documentation](https://docs.microsoft.com/azure/api-management/)
- [Bicep Troubleshooting](https://docs.microsoft.com/azure/azure-resource-manager/bicep/troubleshoot)
