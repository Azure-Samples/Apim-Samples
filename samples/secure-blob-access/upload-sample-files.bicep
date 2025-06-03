@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('Storage account name where files will be uploaded')
param storageAccountName string

@description('Container name where files will be uploaded')
param containerName string

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)


// ------------------------------
//    VARIABLES
// ------------------------------

var sampleTextContent = '''Hello from Azure Blob Storage!

This is a sample text file that was created as part of the Infrastructure as Code (IaC) deployment.

The valet key pattern allows secure access to this file through API Management without:
- Exposing storage account keys
- Requiring the API to stream large files
- Compromising security

This file demonstrates how APIM can generate time-limited, secure URLs for direct blob access.

Created on: ${utcNow()}
'''

var deploymentScriptName = 'upload-sample-files-${resourceSuffix}'
var managedIdentityName = 'mi-upload-files-${resourceSuffix}'


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.managedidentity/userassignedidentities
resource uploadManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: managedIdentityName
  location: location
}

// https://learn.microsoft.com/azure/templates/microsoft.storage/storageaccounts
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

// Grant the managed identity Storage Blob Data Contributor role
// https://learn.microsoft.com/azure/templates/microsoft.authorization/roleassignments
resource uploadIdentityBlobContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, uploadManagedIdentity.id, 'Storage Blob Data Contributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
    principalId: uploadManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.resources/deploymentscripts
resource uploadFilesScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: deploymentScriptName
  location: location
  kind: 'AzurePowerShell'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uploadManagedIdentity.id}': {}
    }
  }
  properties: {
    azPowerShellVersion: '11.0'
    timeout: 'PT10M'
    retentionInterval: 'PT1H'
    environmentVariables: [      {
        name: 'STORAGE_ACCOUNT_NAME'
        value: storageAccountName
      }
      {
        name: 'CONTAINER_NAME'
        value: containerName
      }
      {
        name: 'SAMPLE_TEXT_CONTENT'
        value: sampleTextContent
      }
    ]
    scriptContent: '''
      # Install required module
      Install-Module -Name Az.Storage -Force -AllowClobber

      # Get storage context using managed identity
      $ctx = New-AzStorageContext -StorageAccountName $env:STORAGE_ACCOUNT_NAME -UseConnectedAccount

      # Create sample.txt file
      $textBlob = @{
        File = 'sample.txt'
        Container = $env:CONTAINER_NAME
        Context = $ctx
        StandardBlobTier = 'Hot'
        Force = $true
      }

      # Write content to a temporary file and upload
      $tempFile = New-TemporaryFile
      $env:SAMPLE_TEXT_CONTENT | Out-File -FilePath $tempFile.FullName -Encoding utf8
      Set-AzStorageBlobContent @textBlob -File $tempFile.FullName
      Remove-Item $tempFile.FullName

      Write-Output "Successfully uploaded sample file:"
      Write-Output "- sample.txt ($(([Text.Encoding]::UTF8.GetBytes($env:SAMPLE_TEXT_CONTENT)).Length) bytes)"

      # List uploaded files for verification
      $blobs = Get-AzStorageBlob -Container $env:CONTAINER_NAME -Context $ctx
      Write-Output "Files in container '$env:CONTAINER_NAME':"
      $blobs | ForEach-Object { Write-Output "- $($_.Name) ($($_.Length) bytes)" }
    '''
  }
  dependsOn: [
    uploadIdentityBlobContributorRole
  ]
}


// ------------------------------
//    OUTPUTS
// ------------------------------

output deploymentScriptOutput string = uploadFilesScript.properties.outputs.text
output managedIdentityId string = uploadManagedIdentity.id
output uploadedFiles array = [
  'sample.txt'
]
