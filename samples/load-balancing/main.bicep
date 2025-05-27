// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

param apimName string = 'apim-${resourceSuffix}'
param appInsightsName string = 'appi-${resourceSuffix}'
param apis array = []

// [ADD RELEVANT PARAMETERS HERE]


// ------------------
//    "CONSTANTS"
// ------------------

var IMG_WEB_API_429 = 'simonkurtzmsft/webapi429:1.0.0'


// ------------------
//    RESOURCES
// ------------------

// Log Analytics Workspace
// resource lawModule 'Microsoft.OperationalInsights/workspaces@2025-02-01' existing = {
//   name: 'lawModule'
// }

// var 

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

// https://learn.microsoft.com/azure/templates/microsoft.app/managedenvironments
#disable-next-line BCP081
resource acaEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: 'cae-${resourceSuffix}'
}

// 4. Azure Container Apps (ACA) for Mock Web API
module acaModule1 '../../shared/bicep/modules/aca/v1/containerapp.bicep' = {
  name: 'acaModule-1'
  params: {
    name: 'ca-${resourceSuffix}-webapi429-1'
    containerImage: IMG_WEB_API_429
    environmentId: acaEnvironment.id
  }
}

module acaModule2 '../../shared/bicep/modules/aca/v1/containerapp.bicep' = {
  name: 'acaModule-2'
  params: {
    name: 'ca-${resourceSuffix}-webapi429-2'
    containerImage: IMG_WEB_API_429
    environmentId: acaEnvironment.id
  }
}

// 6. APIM Backends for ACA
module backendModule1 '../../shared/bicep/modules/apim/v1/backend.bicep' = {
  name: 'aca-webapi429-1'
  params: {
    apimName: apimName
    backendName: 'aca-webapi429-1'
    url: 'https://${acaModule1.outputs.containerAppFqdn}/api/0'
  }
  dependsOn: [
    apimService
  ]
}

module backendModule2 '../../shared/bicep/modules/apim/v1/backend.bicep' = {
  name: 'aca-webapi429-2'
  params: {
    apimName: apimName
    backendName: 'aca-webapi429-2'
    url: 'https://${acaModule2.outputs.containerAppFqdn}/api/1'
  }
  dependsOn: [
    apimService
  ]
}

module backendPoolModule1 '../../shared/bicep/modules/apim/v1/backend-pool.bicep' = {
  name: 'aca-webapi29-priority-pool-1'
  params: {
    apimName: apimName
    backendPoolName: 'aca-backend-pool-web-api-429-prioritized'
    backendPoolDescription: 'Prioritized backend pool for ACA Web API 429'
    backends: [
      {
        name: backendModule1.outputs.backendName
        priority: 1
        weight: 100
      }
      {
        name: backendModule2.outputs.backendName
        priority: 2
        weight: 100
      }
    ]
  }
  dependsOn: [
    apimService
  ]
}

module backendPoolModule2 '../../shared/bicep/modules/apim/v1/backend-pool.bicep' = {
  name: 'aca-webapi29-priority-pool-2'
  params: {
    apimName: apimName
    backendPoolName: 'aca-backend-pool-web-api-429-weighted'
    backendPoolDescription: 'Weighted (50/50) backend pool for ACA Web API 429'
    backends: [
      {
        name: backendModule1.outputs.backendName
        priority: 1
        weight: 50
      }
      {
        name: backendModule2.outputs.backendName
        priority: 1
        weight: 50
      }
    ]
  }
  dependsOn: [
    apimService
  ]
}

// 7. APIM APIs
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [
  for api in apis: if (length(apis) > 0) {
    name: '${api.name}-${resourceSuffix}'
    params: {
      apimName: apimName
      appInsightsInstrumentationKey: appInsightsInstrumentationKey
      appInsightsId: appInsightsId
      api: api
    }
    dependsOn: [
      apimService
      backendPoolModule1
      backendPoolModule2
    ]
  }
]

// [ADD RELEVANT BICEP MODULES HERE]

// ------------------
//    MARK: OUTPUTS
// ------------------

output apimServiceId string = apimService.id
output apimServiceName string = apimService.name
output apimResourceGatewayURL string = apimService.properties.gatewayUrl
// [ADD RELEVANT OUTPUTS HERE]
