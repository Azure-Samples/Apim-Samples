/**
 * @module apim-v1
 * @description This module defines the Azure API Management (APIM) resources using Bicep.
 * It includes configurations for creating and managing an APIM instance.
 */


// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('The name of the API Management instance. Defaults to "apim-<resourceSuffix>".')
param apimName string = 'apim-${resourceSuffix}'

@description('If provided, APIM will be integrated into this subnet for egress. Leave empty for public APIM.')
param apimSubnetResourceId string = ''

@description('Set to true to make APIM publicly accessible. If false, APIM will be deployed into a VNet subnet for egress only.')
param publicAccess bool = true

@description('The email address of the publisher. Defaults to "noreply@microsoft.com".')
param publisherEmail string = 'noreply@microsoft.com'

@description('The name of the publisher. Defaults to "Microsoft".')
param publisherName string = 'Microsoft'

@description('Name of the APIM Logger')
param apimLoggerName string = 'apim-logger'

@description('Description of the APIM Logger')
param apimLoggerDescription string  = 'APIM Logger'

@description('The pricing tier of this API Management service')
@allowed([
  'Consumption'
  'Developer'
  'Basic'
  'Basicv2'
  'Standard'
  'Standardv2'
  'Premium'
  'Premiumv2'
])
param apimSku string = 'Basicv2'

@description('The APIM virtual network type when integrated with a VNet')
@allowed([
  'External'
  'Internal'
])
param apimVirtualNetworkType string = 'External'

@description('The instrumentation key for Application Insights')
param appInsightsInstrumentationKey string = ''

@description('The resource ID for Application Insights')
param appInsightsId string = ''

@description('The type of managed identity to by used with API Management')
@allowed([
  'SystemAssigned'
  'UserAssigned'
  'SystemAssigned, UserAssigned'
])
param apimManagedIdentityType string = 'SystemAssigned'

@description('The user-assigned managed identity ID to be used with API Management')
param apimUserAssignedManagedIdentityId string = ''


@description('Content of the global All APIs policy XML. If provided, sets the global policy.')
param globalPolicyXml string = loadTextContent('../../../../apim-policies/all-apis.xml')

// ------------------------------
//    RESOURCES
// ------------------------------
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/policies
resource apimGlobalPolicy 'Microsoft.ApiManagement/service/policies@2024-06-01-preview' = if (!empty(globalPolicyXml)) {
  name: 'policy'
  parent: apimService
  properties: {
    format: 'xml'
    value: globalPolicyXml
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' = {
  name: apimName
  location: location
  sku: {
    name: apimSku
    capacity: 1
  }
  properties: union({
    publisherEmail: publisherEmail
    publisherName: publisherName
    publicNetworkAccess: publicAccess ? 'Enabled' : 'Disabled'
    virtualNetworkType: apimVirtualNetworkType
  }, (!empty(apimSubnetResourceId)) ? {
    virtualNetworkConfiguration: {
      subnetResourceId: apimSubnetResourceId
    }
    publicIPAddresses: []
  } : {})
  identity: {
    type: apimManagedIdentityType
    userAssignedIdentities: apimManagedIdentityType == 'UserAssigned' && apimUserAssignedManagedIdentityId != '' ? {
      // BCP037: Not yet added to latest API:
      '${apimUserAssignedManagedIdentityId}': {}
    } : null
  }
}

// Create a logger only if we have an App Insights ID and instrumentation key.
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/loggers
resource apimLogger 'Microsoft.ApiManagement/service/loggers@2024-06-01-preview' = if (!empty(appInsightsId) && !empty(appInsightsInstrumentationKey)) {
  name: apimLoggerName
  parent: apimService
  properties: {
    credentials: {
      instrumentationKey: appInsightsInstrumentationKey
    }
    description: apimLoggerDescription
    isBuffered: false
    loggerType: 'applicationInsights'
    resourceId: appInsightsId
  }
}


// ------------------------------
//    OUTPUTS
// ------------------------------

output id string = apimService.id
output name string = apimService.name
output principalId string = apimService.identity.principalId
output gatewayUrl string = apimService.properties.gatewayUrl
output privateIpAddresses array = apimService.properties.privateIPAddresses ?? []
