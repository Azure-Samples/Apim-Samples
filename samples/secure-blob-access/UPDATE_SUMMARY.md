# Sample File Upload via Bicep Deployment Script

This approach uses Azure Bicep deployment scripts to automatically create sample files in blob storage as part of the Infrastructure as Code (IaC) deployment process.

## Overview

Instead of manually uploading files from the notebook, we use a **Bicep deployment script** that:

1. Creates a user-assigned managed identity
2. Grants the identity **Storage Blob Data Contributor** permissions
3. Runs a PowerShell script that uploads sample files to the storage container

## Benefits

✅ **Secure**: Uses managed identity authentication (no keys or secrets)  
✅ **Consistent**: Same files created across all environments  
✅ **Automated**: No manual intervention required  
✅ **Reliable**: Part of the infrastructure deployment process  
✅ **Clean**: No authentication issues in the notebook  

## Files Created

The deployment script creates these sample files:

- **`sample.txt`** - A text file with sample content demonstrating secure access patterns

## Implementation

### Main Bicep File (`main.bicep`)

The main Bicep file now includes a reference to the upload module:

```bicep
// Upload sample files to blob storage using deployment script
module uploadSampleFilesModule 'upload-sample-files.bicep' = {
  name: 'upload-sample-files'
  params: {
    location: location
    resourceSuffix: resourceSuffix
    storageAccountName: storageAccount.name
    containerName: containerName
  }
  dependsOn: [
    blobContainer
  ]
}
```

### Upload Module (`upload-sample-files.bicep`)

The upload module:
- Creates a user-assigned managed identity
- Assigns Storage Blob Data Contributor role to the identity
- Runs a deployment script using PowerShell to upload files
- Uses managed identity authentication for secure access

### Notebook Changes

The notebook has been updated to:
- Remove the manual upload section
- Add explanation of the IaC-based approach
- Focus on testing the valet key pattern with the sample text file

## Security Considerations

- **Managed Identity**: Uses Azure managed identity for authentication
- **Least Privilege**: Deployment identity only has blob contributor access to the specific storage account
- **Temporary**: Deployment script identity is only used during deployment
- **No Secrets**: No storage account keys or connection strings in code

## Azure Best Practices Followed

- Infrastructure as Code (IaC) for file provisioning
- Managed identity for authentication
- Role-based access control (RBAC)
- Secure credential management
- Automated deployment processes

This approach aligns with Azure best practices for secure, scalable cloud deployments.
