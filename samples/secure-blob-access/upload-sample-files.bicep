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

var managedIdentityName = 'mi-upload-files-${resourceSuffix}'


// ------------------------------
//    CONSTANTS
// ------------------------------

var helloWorldBase64 = base64('Hello World!')

var blobName = 'hello.txt'


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

// https://learn.microsoft.com/azure/templates/microsoft.storage/storageaccounts/blobservices/containers
resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/${containerName}'
  properties: {
    publicAccess: 'None'
  }
  dependsOn: [
    storageAccount
  ]
}

// https://learn.microsoft.com/azure/templates/microsoft.resources/deploymentscripts
resource uploadHelloWorldScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'upload-hello-world-${resourceSuffix}'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uploadManagedIdentity.id}': {}
    }
  }
  properties: {
    azCliVersion: '2.50.0'
    scriptContent: '''
      echo "Hello World!" > hello.txt
      az storage blob upload \
        --account-name $STORAGE_ACCOUNT_NAME \
        --container-name $CONTAINER_NAME \
        --name $BLOB_NAME \
        --file hello.txt \
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
