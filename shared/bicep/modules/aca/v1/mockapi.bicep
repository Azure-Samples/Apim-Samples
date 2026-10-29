// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location for the MockAPI containers and configuration storage.')
param location string = resourceGroup().location

@description('Infrastructure resource suffix used to preserve existing container names.')
param resourceSuffix string

@description('Existing Container Apps environment resource ID.')
param environmentId string

@description('VNet linked to private Blob DNS. Empty retains the authenticated public storage architecture.')
param storageVirtualNetworkId string = ''

@description('Non-delegated subnet for the Blob private endpoint. Required when storageVirtualNetworkId is supplied.')
param storagePrivateEndpointSubnetId string = ''

@description('Object ID of the deployment principal that seeds initial configurations.')
param configurationWriterPrincipalId string

@secure()
@description('Generated dashboardPassword, dashboardPasswordHash and apiKey, reused on redeployment.')
param credentials object


// ------------------------------
//    VARIABLES
// ------------------------------

@description('Immutable MockAPI image, exempt from the dependency release waiting period.')
var containerImage = 'simonkurtzmsft/mockapi:1.11.0@sha256:57d640ea8cea58c3029897cfb30bf7b2b4a3a2865e32cea710f38f0c13613e35'

@description('Shared role definitions.')
var azureRoles = loadJsonContent('../../../../azure-roles.json')

@description('Storage Blob Data Contributor role used for configuration and security persistence.')
var blobContributorRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureRoles.StorageBlobDataContributor)


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.managedidentity/userassignedidentities
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-mockapi-${resourceSuffix}'
  location: location
}

// https://learn.microsoft.com/azure/templates/microsoft.storage/storageaccounts
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'stmock${resourceSuffix}'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    publicNetworkAccess: empty(storageVirtualNetworkId) ? 'Enabled' : 'Disabled'
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.storage/storageaccounts/blobservices
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

// https://learn.microsoft.com/azure/templates/microsoft.storage/storageaccounts/blobservices/containers
resource configuration 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'mockapi-config'
  properties: {
    publicAccess: 'None'
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.authorization/roleassignments
resource runtimeRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(configuration.id, identity.id, blobContributorRoleId)
  scope: configuration
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: blobContributorRoleId
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.authorization/roleassignments
resource writerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(storageVirtualNetworkId)) {
  name: guid(configuration.id, configurationWriterPrincipalId, blobContributorRoleId)
  scope: configuration
  properties: {
    principalId: configurationWriterPrincipalId
    roleDefinitionId: blobContributorRoleId
  }
}

module storageDns '../../dns/v1/dns-private-zone.bicep' = if (!empty(storageVirtualNetworkId)) {
  name: 'mockApiStorageDns'
  params: {
    dnsZoneName: 'privatelink.blob.${environment().suffixes.storage}'
    vnetId: storageVirtualNetworkId
    vnetLinkName: 'link-mockapi'
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.network/privateendpoints
resource storagePrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = if (!empty(storageVirtualNetworkId)) {
  name: 'pe-mockapi-${resourceSuffix}'
  location: location
  properties: {
    subnet: {
      id: storagePrivateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'mockapi-blob'
        properties: {
          privateLinkServiceId: storage.id
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.network/privateendpoints/privatednszonegroups
resource storageDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (!empty(storageVirtualNetworkId)) {
  parent: storagePrivateEndpoint
  name: 'blob'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'blob'
        properties: {
          privateDnsZoneId: storageDns!.outputs.privateDnsZoneId
        }
      }
    ]
  }
}

module containers 'containerapp.bicep' = [for index in range(1, 2): {
  name: 'acaModule-${index}'
  params: {
    name: 'ca-${resourceSuffix}-${empty(storageVirtualNetworkId) ? 'mockwebapi' : 'mockapi'}-${index}'
    location: location
    environmentId: environmentId
    containerImage: containerImage
    userAssignedIdentityId: identity.id
    minReplicas: 1
    maxReplicas: 1
    secretConfiguration: {
      secrets: [
        {
          name: 'dashboard-password'
          value: credentials.dashboardPassword
        }
        {
          name: 'dashboard-password-hash'
          value: credentials.dashboardPasswordHash
        }
        {
          name: 'mock-api-key'
          value: credentials.apiKey
        }
      ]
    }
    environmentVariables: [
      {
        name: 'MockApi__ConfigurationBlobUri'
        value: '${storage.properties.primaryEndpoints.blob}${configuration.name}/mockapi-${index}.json'
      }
      {
        name: 'MockApi__ManagedIdentityClientId'
        value: identity.properties.clientId
      }
      {
        name: 'MockApi__AllowEmptyConfiguration'
        value: 'true'
      }
      {
        name: 'MockApi__DashboardUsername'
        value: 'admin'
      }
      {
        name: 'MockApi__DashboardPasswordHash'
        secretRef: 'dashboard-password-hash'
      }
      {
        name: 'MockApi__ApiKey'
        secretRef: 'mock-api-key'
      }
    ]
    probes: [for probe in ['Liveness', 'Readiness']: {
      type: probe
      httpGet: {
        path: probe == 'Liveness' ? '/health/live' : '/health/ready'
        port: 8080
        scheme: 'HTTP'
      }
      initialDelaySeconds: 5
      periodSeconds: 10
    }]
  }
  dependsOn: [
    runtimeRole
    writerRole
    storageDnsGroup
  ]
}]


// ------------------------------
//    OUTPUTS
// ------------------------------

output storageAccountName string = storage.name
output containerAppNames array = [for index in range(0, 2): containers[index].outputs.containerAppName]
output containerAppFqdns array = [for index in range(0, 2): containers[index].outputs.containerAppFqdn]
