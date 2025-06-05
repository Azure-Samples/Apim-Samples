// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Storage account name where files will be uploaded')
param storageAccountName string

@description('Container name where files will be uploaded')
@minLength(3)
@maxLength(63)
param containerName string

param blobName string


// ------------------------------
//    VARIABLES
// ------------------------------

var managedIdentityName = 'id-upload-files-${resourceSuffix}'
var azureRoles = loadJsonContent('../../shared/azure-roles.json')


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.managedidentity/userassignedidentities
resource uploadManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: managedIdentityName
  location: location
}

// https://learn.microsoft.com/azure/templates/microsoft.storage/storageaccounts
resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' existing = {
  name: storageAccountName
}

// Grant the managed identity Storage Blob Data Contributor role
// https://learn.microsoft.com/azure/templates/microsoft.authorization/roleassignments
resource uploadIdentityBlobContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, uploadManagedIdentity.id, 'Storage Blob Data Contributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureRoles.StorageBlobDataContributor)
    principalId: uploadManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.storage/storageaccounts/blobservices/containers
resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  name: '${storageAccount.name}/default/${containerName}'
  properties: {
    publicAccess: 'None'
  }
  dependsOn: [
    storageAccount
  ]
}

// https://learn.microsoft.com/azure/templates/microsoft.resources/deploymentscripts
resource deploymentScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'deployment-script-${resourceSuffix}'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uploadManagedIdentity.id}': {}
    }
  }
  properties: {
    azCliVersion: '2.71.0'
    scriptContent: '''
      echo "This is an HR document." > file.txt
      az storage blob upload \
        --account-name $STORAGE_ACCOUNT_NAME \
        --container-name $CONTAINER_NAME \
        --name $BLOB_NAME \
        --file file.txt \
        --auth-mode login \
        --overwrite
      echo "Successfully uploaded $BLOB_NAME to $CONTAINER_NAME"
    '''
    environmentVariables: [
      {
        name: 'STORAGE_ACCOUNT_NAME'
        value: storageAccountName
      }
      {
        name: 'CONTAINER_NAME'
        value: containerName
      }
      {
        name: 'BLOB_NAME'
        value: blobName
      }
    ]
    retentionInterval: 'PT1H'
  }
  dependsOn: [
    uploadIdentityBlobContributorRole
    blobContainer
  ]
}


// ------------------------------
//    OUTPUTS
// ------------------------------

output uploadedFiles array = [
  blobName
]
