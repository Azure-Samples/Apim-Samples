// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

param apimName string = 'apim-${resourceSuffix}'
param apimSku string
param apis array = []


// ------------------
//    "CONSTANTS"
// ------------------

var IMG_HELLO_WORLD = 'simonkurtzmsft/helloworld:latest'
var IMG_MOCK_WEB_API = 'simonkurtzmsft/mockwebapi:1.0.0-alpha.1'


// ------------------
//    RESOURCES
// ------------------

// 1. Log Analytics Workspace
module lawModule '../../shared/bicep/modules/operational-insights/v1/workspaces.bicep' = {
  name: 'lawModule'
}

// 2. Application Insights
module appInsightsModule '../../shared/bicep/modules/monitor/v1/appinsights.bicep' = {
  name: 'appInsightsModule'
  params: {
    lawId: lawModule.outputs.id
    customMetricsOptedInType: 'WithDimensions'
  }
}

var appInsightsId = appInsightsModule.outputs.id
var appInsightsInstrumentationKey = appInsightsModule.outputs.instrumentationKey

// 3. Azure Container App Environment (ACAE)
module acaEnvModule '../../shared/bicep/modules/aca/v1/environment.bicep' = {
  name: 'acaEnvModule'
  params: {
    name: 'cae-${resourceSuffix}'
    location: location
    logAnalyticsWorkspaceCustomerId: lawModule.outputs.customerId
    logAnalyticsWorkspaceSharedKey: lawModule.outputs.clientSecret
  }
}

// 4. Azure Container Apps (ACA) for Mock Web API
module acaModule1 '../../shared/bicep/modules/aca/v1/containerapp.bicep' = {
  name: 'acaModule-1'
  params: {
    name: 'ca-${resourceSuffix}-mockwebapi-1'
    containerImage: IMG_MOCK_WEB_API
    environmentId: acaEnvModule.outputs.environmentId
  }
}

module acaModule2 '../../shared/bicep/modules/aca/v1/containerapp.bicep' = {
  name: 'acaModule-2'
  params: {
    name: 'ca-${resourceSuffix}-mockwebapi-2'
    containerImage: IMG_MOCK_WEB_API
    environmentId: acaEnvModule.outputs.environmentId
  }
}

// 5. API Management
module apimModule '../../shared/bicep/modules/apim/v1/apim.bicep' = {
  name: 'apimModule'
  params: {
    apimSku: apimSku
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
  }
}

// 6. APIM Backends for ACA
module backendModule1 '../../shared/bicep/modules/apim/v1/backend.bicep' = {
  name: 'aca-backend-1'
  params: {
    apimName: apimName
    backendName: 'aca-backend-1'
    url: 'https://${acaModule1.outputs.containerAppFqdn}'
  }
  dependsOn: [
    apimModule
  ]
}

module backendModule2 '../../shared/bicep/modules/apim/v1/backend.bicep' = {
  name: 'aca-backend-2'
  params: {
    apimName: apimName
    backendName: 'aca-backend-2'
    url: 'https://${acaModule2.outputs.containerAppFqdn}'
  }
  dependsOn: [
    apimModule
  ]
}

module backendPoolModule '../../shared/bicep/modules/apim/v1/backend-pool.bicep' = {
  name: 'aca-backend-pool'
  params: {
    apimName: apimName
    backendPoolName: 'aca-backend-pool'
    backendPoolDescription: 'Backend pool for ACA Hello World backends'
    backends: [
      {
        name: backendModule1.outputs.backendName
        priority: 1
        weight: 75
      }
      {
        name: backendModule2.outputs.backendName
        priority: 1
        weight: 25
      }
    ]
  }
  dependsOn: [
    apimModule
  ]
}

// 7. APIM APIs
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [
  for api in apis: if (length(apis) > 0) {
    name: 'api-${api.name}'
    params: {
      apimName: apimName
      appInsightsInstrumentationKey: appInsightsInstrumentationKey
      appInsightsId: appInsightsId
      api: api
    }
    dependsOn: [
      apimModule
      backendModule1
      backendModule2
      backendPoolModule
    ]
  }
]

// ------------------
//    MARK: OUTPUTS
// ------------------

output applicationInsightsAppId string = appInsightsModule.outputs.appId
output applicationInsightsName string = appInsightsModule.outputs.applicationInsightsName
output logAnalyticsWorkspaceId string = lawModule.outputs.customerId
output apimServiceId string = apimModule.outputs.id
output apimServiceName string = apimModule.outputs.name
output apimResourceGatewayURL string = apimModule.outputs.gatewayUrl
output acaUrl1 string = 'https://${acaModule1.outputs.containerAppFqdn}'
output acaUrl2 string = 'https://${acaModule2.outputs.containerAppFqdn}'
