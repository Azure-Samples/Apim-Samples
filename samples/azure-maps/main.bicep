// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

param mapsLocation string = 'eastus' // Azure Maps is only available in certain regions: https://learn.microsoft.com/en-us/azure/azure-maps/creator-geographic-scope#geographic-and-regional-mapping

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

param namedValues array = []
param mapsName string = 'maps-${resourceSuffix}'
param apimName string = 'apim-${resourceSuffix}'
param appInsightsName string = 'appi-${resourceSuffix}'
param userAssignedIdentityName string = 'uami-maps-${resourceSuffix}'
param apis array = []

// ------------------------------
//    VARIABLES
// ------------------------------

var azureRoles = loadJsonContent('../../shared/azure-roles.json')

// ------------------
//    RESOURCES
// ------------------

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

// Create user-assigned managed identity
resource userAssignedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: userAssignedIdentityName
  location: location
  tags: {
    Purpose: 'Azure Maps Access'
    Environment: 'Sample'
  }
}

// Create Azure Maps account
resource mapsAccount 'Microsoft.Maps/accounts@2024-07-01-preview' = {
  name: mapsName
  location: mapsLocation
  sku: {
    name: 'G2'
  }
  kind: 'Gen2'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentity.id}': {}
    }
  }
}

// Deploy user-provided named values (compile-time only)
module namedValueModule '../../shared/bicep/modules/apim/v1/named-value.bicep' = [for nv in namedValues: if (!empty(namedValues)) {
  name: 'nv-${nv.name}'
  params: {
    apimName: apimName
    namedValueName: nv.name
    namedValueValue: nv.value
    namedValueIsSecret: nv.isSecret
  }
}]

// Deploy Maps subscription key named value (runtime value, must be separate)
module mapsSubscriptionKeyNamedValue '../../shared/bicep/modules/apim/v1/named-value.bicep' = {
  name: 'nv-azuremaps-subscription-key'
  params: {
    apimName: apimName
    namedValueName: 'azuremaps-subscription-key'
    namedValueValue: mapsAccount.listKeys().primaryKey
    namedValueIsSecret: true
  }
}

// Deploy Maps client id named value (runtime value, must be separate)
module mapsClientIdNamedValue '../../shared/bicep/modules/apim/v1/named-value.bicep' = {
  name: 'nv-azure-maps-client-id'
  params: {
    apimName: apimName
    namedValueName: 'azure-maps-client-id'
    namedValueValue: mapsAccount.properties.uniqueId
    namedValueIsSecret: false
  }
}

// Deploy user-assigned managed identity client id named value
module userAssignedIdentityObjectIdNamedValue '../../shared/bicep/modules/apim/v1/named-value.bicep' = {
  name: 'nv-user-assigned-identity-object-id'
  params: {
    apimName: apimName
    namedValueName: 'user-assigned-identity-object-id'
    namedValueValue: userAssignedIdentity.properties.principalId
    namedValueIsSecret: false
  }
}

// Deploy Azure subscription id named value
module subscriptionIdNamedValue '../../shared/bicep/modules/apim/v1/named-value.bicep' = {
  name: 'nv-subscription-id'
  params: {
    apimName: apimName
    namedValueName: 'subscription-id'
    namedValueValue: subscription().subscriptionId
    namedValueIsSecret: true
  }
}

// Deploy resource group name named value
module resourceGroupNamedValue '../../shared/bicep/modules/apim/v1/named-value.bicep' = {
  name: 'nv-resource-group-name'
  params: {
    apimName: apimName
    namedValueName: 'resource-group-name'
    namedValueValue: resourceGroup().name
    namedValueIsSecret: false
  }
}
// Deploy resource group name named value
module azureMapsResourceNamedValue '../../shared/bicep/modules/apim/v1/named-value.bicep' = {
  name: 'nv-azure-maps-resource-name'
  params: {
    apimName: apimName
    namedValueName: 'azure-maps-resource-name'
    namedValueValue: mapsName
    namedValueIsSecret: false
  }
}

// APIM APIs
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: if(!empty(apis)) {
  name: '${api.name}-${resourceSuffix}'
  params: {
    apimName: apimName
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    api: api
  }
  dependsOn: [
    mapsSubscriptionKeyNamedValue
    mapsClientIdNamedValue
    userAssignedIdentityObjectIdNamedValue
    subscriptionIdNamedValue
    resourceGroupNamedValue
    azureMapsResourceNamedValue
  ]
}]

// Grant APIM managed identity Azure Maps Seaarch and Render Data Reader role to Azure Maps
resource mapsDataReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(mapsAccount.id, apimService.id, 'Azure Maps Search and Render Data Reader')
  scope: mapsAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureRoles.AzureMapsSearchAndRenderDataReader)
    principalId: apimService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Grant APIM managed identity 'Azure Maps Contributor' role to Azure Maps, this allows the creation of SAS tokens
resource mapsContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(mapsAccount.id, apimService.id, 'Azure Maps Contributor')
  scope: mapsAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureRoles.AzureMapsContributor)
    principalId: apimService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}


// Grant user-assigned managed identity Azure Maps Search and Render Data Reader role
resource userAssignedIdentityMapsDataReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(mapsAccount.id, userAssignedIdentity.id, 'Azure Maps Search and Render Data Reader')
  scope: mapsAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureRoles.AzureMapsSearchAndRenderDataReader)
    principalId: userAssignedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ------------------
//    MARK: OUTPUTS
// ------------------

output apimServiceId string = apimService.id
output apimServiceName string = apimService.name
output apimResourceGatewayURL string = apimService.properties.gatewayUrl
output mapsServiceName string = mapsAccount.name

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

// [ADD RELEVANT OUTPUTS HERE]
