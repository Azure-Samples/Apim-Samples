// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Name of the existing API Management service.')
param apimName string = 'apim-${resourceSuffix}'

@description('Name of the existing infrastructure-deployed Application Insights component to reuse for API diagnostics.')
param appInsightsName string = 'appi-${resourceSuffix}'

@description('Array of inference APIs assembled by the notebook.')
param apis array = []

@maxLength(2)
@description('Optional pair of infrastructure mockApiDashboardUrls. When omitted, reuse the URLs published by infrastructure-owned aca-backend-1 and aca-backend-2.')
param mockApiBaseUrls array = []

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

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/backends
resource infrastructureMockApiBackends 'Microsoft.ApiManagement/service/backends@2024-06-01-preview' existing = [for index in range(1, 2): {
  parent: apimService
  name: 'aca-backend-${index}'
}]

// Infrastructure backend URLs follow either public or private-storage app generations.
var mockApiOrigins = empty(mockApiBaseUrls)
  ? [
      uri(infrastructureMockApiBackends[0].properties.url, '/')
      uri(infrastructureMockApiBackends[1].properties.url, '/')
    ]
  : map(mockApiBaseUrls, url => uri(string(url), '/'))

// Keep backend resource IDs stable for existing policies, but reuse infrastructure-owned MockAPI.
var mockApiCredentialHeaders = {
  'X-MockAPI-Key': ['{{mockapi-key}}']
}

@description('Match the five-permit MockAPI three-second window rather than inheriting a one-minute circuit trip.')
var mockApiCircuitBreaker = {
  rules: [
    {
      name: 'mockapi-capacity'
      failureCondition: {
        count: 1
        interval: 'PT3S'
        statusCodeRanges: [
          {
            min: 429
            max: 429
          }
        ]
      }
      tripDuration: 'PT3S'
      acceptRetryAfter: true
    }
  ]
}

// APIM Backends for ACA
module backendModule1 '../../shared/bicep/modules/apim/v1/backend.bicep' = {
  name: 'aca-webapi429-1'
  params: {
    apimName: apimName
    backendName: 'aca-webapi429-1'
    url: '${mockApiOrigins[0]}load-balancing/backend-0'
    credentialHeaders: mockApiCredentialHeaders
    circuitBreaker: mockApiCircuitBreaker
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
    url: '${mockApiOrigins[1]}load-balancing/backend-1'
    credentialHeaders: mockApiCredentialHeaders
    circuitBreaker: mockApiCircuitBreaker
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
    url: '${mockApiOrigins[0]}load-balancing/backend-2'
    credentialHeaders: mockApiCredentialHeaders
    circuitBreaker: mockApiCircuitBreaker
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
    backendPoolDescription: 'Prioritized backend pool for infrastructure-owned MockAPI'
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
    backendPoolDescription: 'Weighted (50/50) backend pool for infrastructure-owned MockAPI'
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
    backendPoolDescription: 'Weighted (80/20) backend pool for infrastructure-owned MockAPI'
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
    backendPoolDescription: 'Prioritized (1/2) and weighted (50/50) backend pool for infrastructure-owned MockAPI'
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
  for api in apis: if (!empty(apis)) {
    name: 'api-${api.name}'
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
      backendPoolModule3
      backendPoolModule4
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
output mockApiResourceSuffix string = resourceSuffix
output mockApiDashboardUrls array = mockApiOrigins

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
