// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

param apimName string = 'apim-${resourceSuffix}'
param appInsightsName string = 'appi-${resourceSuffix}'
param storageAccountName string = 'st${take(replace(resourceSuffix, '-', ''), 18)}'
param apis array = []
param namedValues array = []
param policyFragments array = []

@description('Container name where files will be uploaded')
@minLength(3)
@maxLength(63)
param containerName string

param blobName string


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.insights/components
resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

var appInsightsId = appInsights.id
var appInsightsInstrumentationKey = appInsights.properties.InstrumentationKey

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// https://learn.microsoft.com/azure/templates/microsoft.storage/storageaccounts
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.storage/storageaccounts/blobservices
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' = {
  parent: storageAccount
  name: 'default'
}

// https://learn.microsoft.com/azure/templates/microsoft.storage/storageaccounts/blobservices/containers
resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}

// Upload sample files to blob storage using deployment script
module uploadSampleFilesModule 'upload-sample-files.bicep' = {
  name: 'upload-sample-files'
  params: {
    location: location
    resourceSuffix: resourceSuffix
    storageAccountName: storageAccount.name
    containerName: containerName
    blobName: blobName
  }
  dependsOn: [
    blobContainer
  ]
}

// https://learn.microsoft.com/azure/templates/microsoft.authorization/roleassignments
resource apimStorageBlobDataReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, apimService.id, 'Storage Blob Data Reader')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1') // Storage Blob Data Reader
    principalId: apimService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Add storage account name as APIM named value
resource storageAccountNamedValue 'Microsoft.ApiManagement/service/namedValues@2024-06-01-preview' = {
  parent: apimService
  name: 'storage-account-name'
  properties: {
    displayName: 'storage-account-name'
    value: storageAccountName
    secret: false
  }
}

// Add storage account key as APIM named value (for demo purposes - use Key Vault in production)
resource storageAccountKeyNamedValue 'Microsoft.ApiManagement/service/namedValues@2024-06-01-preview' = {
  parent: apimService
  name: 'storage-account-key'
  properties: {
    displayName: 'storage-account-key'
    value: storageAccount.listKeys().keys[0].value
    secret: true
  }
}

// APIM Named Values
module namedValueModule '../../shared/bicep/modules/apim/v1/named-value.bicep' = [for nv in namedValues: {
  name: 'nv-${nv.name}'
  params:{
    apimName: apimName
    namedValueName: nv.name
    namedValueValue: nv.value
    namedValueIsSecret: nv.isSecret
  }
}]

// APIM Policy Fragments
module policyFragmentModule '../../shared/bicep/modules/apim/v1/policy-fragment.bicep' = [for pf in policyFragments: {
  name: 'pf-${pf.name}'
  params:{
    apimName: apimName
    policyFragmentName: pf.name
    policyFragmentDescription: pf.description
    policyFragmentValue: pf.policyXml
  }
  dependsOn: [
    namedValueModule
  ]
}]

// APIM APIs (deployed after products are ready to avoid race conditions)
@batchSize(1)  // Deploy APIs sequentially to avoid race conditions
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: {
  name: 'api-${api.name}'
  params:{
    apimName: apimName
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    api: api
    productNames: api.productNames ?? []
  }
  dependsOn: [
    namedValueModule              // ensure all named values are created before APIs
    policyFragmentModule          // ensure all policy fragments are created before APIs
    storageAccountNamedValue
    storageAccountKeyNamedValue
    apimStorageBlobDataReaderRole // ensure role assignment is complete before APIs
  ]
}]


// ------------------------------
//    OUTPUTS
// ------------------------------

output apimServiceId string = apimService.id
output apimServiceName string = apimService.name
output apimResourceGatewayURL string = apimService.properties.gatewayUrl
output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
output blobContainerName string = containerName
output storageAccountEndpoint string = storageAccount.properties.primaryEndpoints.blob
output uploadedFiles array = uploadSampleFilesModule.outputs.uploadedFiles

// API outputs
output apiOutputs array = [for i in range(0, length(apis)): {
  name: apis[i].name
  resourceId: apisModule[i].?outputs.?apiResourceId ?? ''
  displayName: apisModule[i].?outputs.?apiDisplayName ?? ''
  productAssociationCount: apisModule[i].?outputs.?productAssociationCount ?? 0
  subscriptionResourceId: apisModule[i].?outputs.?subscriptionResourceId ?? ''
  subscriptionName: apisModule[i].?outputs.?subscriptionName ?? ''
  subscriptionPrimaryKey: apisModule[i].?outputs.?subscriptionPrimaryKey ?? ''
  subscriptionSecondaryKey: apisModule[i].?outputs.?subscriptionSecondaryKey ?? ''
}]
