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

// Azure Container Apps (ACA) for Mock Web API
module acaModule '../../shared/bicep/modules/aca/v1/containerapp.bicep' = {
  name: 'acaModule'
  params: {
    name: 'ca-${resourceSuffix}-webapi429'
    containerImage: IMG_WEB_API_429
    environmentId: acaEnvironment.id
  }
}

// APIM Backends for ACA
module backendModule1 '../../shared/bicep/modules/apim/v1/backend.bicep' = {
  name: 'aca-webapi429-1'
  params: {
    apimName: apimName
    backendName: 'aca-webapi429-1'
    url: 'https://${acaModule.outputs.containerAppFqdn}/api/0'
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
    url: 'https://${acaModule.outputs.containerAppFqdn}/api/1'
  }
  dependsOn: [
    apimService
  ]
}

module backendModule3 '../../shared/bicep/modules/apim/v1/backend.bicep' = {
  name: 'aca-webapi429-3'
  params: {
    apimName: apimName
    backendName: 'aca-webapi429-3'
    url: 'https://${acaModule.outputs.containerAppFqdn}/api/2'
  }
  dependsOn: [
    apimService
  ]
}

// APIM Backend Pools for ACA
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
    backendPoolName: 'aca-backend-pool-web-api-429-weighted-50-50'
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

module backendPoolModule3 '../../shared/bicep/modules/apim/v1/backend-pool.bicep' = {
  name: 'aca-webapi29-priority-pool-3'
  params: {
    apimName: apimName
    backendPoolName: 'aca-backend-pool-web-api-429-weighted-80-20'
    backendPoolDescription: 'Weighted (80/20) backend pool for ACA Web API 429'
    backends: [
      {
        name: backendModule1.outputs.backendName
        priority: 1
        weight: 80
      }
      {
        name: backendModule2.outputs.backendName
        priority: 1
        weight: 20
      }
    ]
  }
  dependsOn: [
    apimService
  ]
}

module backendPoolModule4 '../../shared/bicep/modules/apim/v1/backend-pool.bicep' = {
  name: 'aca-webapi29-priority-pool-4'
  params: {
    apimName: apimName
    backendPoolName: 'aca-backend-pool-web-api-429-prioritized-and-weighted'
    backendPoolDescription: 'Prioritized (1/2) and weighted (50/50) backend pool for ACA Web API 429'
    backends: [
      {
        name: backendModule1.outputs.backendName
        priority: 1
        weight: 100
      }
      {
        name: backendModule2.outputs.backendName
        priority: 2
        weight: 50
      }
      {
        name: backendModule3.outputs.backendName
        priority: 2
        weight: 50
      }      
    ]
  }
  dependsOn: [
    apimService
  ]
}

// APIM APIs
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


// ------------------
//    MARK: OUTPUTS
// ------------------

output applicationInsightsName string = appInsights.name
output apimServiceId string = apimService.id
output apimServiceName string = apimService.name
output apimResourceGatewayURL string = apimService.properties.gatewayUrl
