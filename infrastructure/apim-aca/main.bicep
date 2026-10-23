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
param policyFragments array = []

@secure()
@description('MockAPI credentials generated and preserved by the infrastructure deployment helper.')
param mockApiCredentials object

@description('Object ID of the deployment principal that seeds initial MockAPI configurations.')
param currentUserId string

@description('Reveals the backend API information. Defaults to true. *** WARNING: This will expose backend API information to the caller - For learning & testing only! ***')
param revealBackendApiInfo bool = true

// ------------------
//    "CONSTANTS"
// ------------------

// ------------------
//    RESOURCES
// ------------------

// 1. Log Analytics Workspace
module lawModule '../../shared/bicep/modules/operational-insights/v1/workspaces.bicep' = {
  name: 'lawModule'
}

var lawId = lawModule.outputs.id

// 2. Application Insights
module appInsightsModule '../../shared/bicep/modules/monitor/v1/appinsights.bicep' = {
  name: 'appInsightsModule'
  params: {
    lawId: lawId
    customMetricsOptedInType: 'WithDimensions'
  }
}

var appInsightsId = appInsightsModule.outputs.id
var appInsightsInstrumentationKey = appInsightsModule.outputs.instrumentationKey

// 3. Container Apps networking and private Blob connectivity
module nsgAcaModule '../../shared/bicep/modules/vnet/v1/nsg-aca.bicep' = {
  name: 'nsgAcaModule'
  params: {
    location: location
    acaSubnetPrefix: '10.42.0.0/23'
  }
}

module vnetModule '../../shared/bicep/modules/vnet/v1/vnet.bicep' = {
  name: 'vnetModule'
  params: {
    location: location
    vnetName: 'vnet-mockapi-${resourceSuffix}'
    vnetAddressPrefixes: [
      '10.42.0.0/16'
    ]
    subnets: [
      {
        name: 'aca'
        properties: {
          addressPrefix: '10.42.0.0/23'
          networkSecurityGroup: {
            id: nsgAcaModule.outputs.nsgId
          }
          delegations: [
            {
              name: 'Microsoft.App/environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: 'private-endpoints'
        properties: {
          addressPrefix: '10.42.2.0/27'
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

// A new environment preserves the old non-VNet environment until migration is verified.
module acaEnvModule '../../shared/bicep/modules/aca/v1/environment.bicep' = {
  name: 'acaEnvModule'
  params: {
    name: 'cae-${resourceSuffix}-private'
    location: location
    subnetResourceId: '${vnetModule.outputs.vnetId}/subnets/aca'
    internalVnet: false
    logAnalyticsWorkspaceCustomerId: lawModule.outputs.customerId
    logAnalyticsWorkspaceSharedKey: lawModule.outputs.clientSecret
  }
}

// 4. Persistent MockAPI backends
module mockApiModule '../../shared/bicep/modules/aca/v1/mockapi.bicep' = {
  name: 'mockApiModule'
  params: {
    location: location
    resourceSuffix: resourceSuffix
    environmentId: acaEnvModule.outputs.environmentId
    storageVirtualNetworkId: vnetModule.outputs.vnetId
    storagePrivateEndpointSubnetId: '${vnetModule.outputs.vnetId}/subnets/private-endpoints'
    configurationWriterPrincipalId: currentUserId
    credentials: mockApiCredentials
  }
}

// 5. API Management
module apimModule '../../shared/bicep/modules/apim/v1/apim.bicep' = {
  name: 'apimModule'
  params: {
    apimSku: apimSku
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    globalPolicyXml: revealBackendApiInfo ? loadTextContent('../../shared/apim-policies/all-apis-reveal-backend.xml') : loadTextContent('../../shared/apim-policies/all-apis.xml')
  }
}

// 6. APIM Policy Fragments
module apimDiagnosticsModule '../../shared/bicep/modules/apim/v1/diagnostics.bicep' = {
  name: 'apimDiagnosticsModule'
  params: {
    apimServiceName: apimName
    diagnosticSettingsNameSuffix: 'diagnostics'
    enableApplicationInsights: false
    enableEventHub: false
    enableLlmLogs: true
    enableLogAnalytics: true
    logAnalyticsWorkspaceId: lawId
  }
  dependsOn: [
    apimModule
  ]
}

module policyFragmentModule '../../shared/bicep/modules/apim/v1/policy-fragment.bicep' = [for pf in policyFragments: {
  name: 'pf-${pf.name}'
  params:{
    apimName: apimName
    policyFragmentName: pf.name
    policyFragmentDescription: pf.description
    policyFragmentValue: pf.policyXml
  }
  dependsOn: [
    apimModule
  ]
}]

// 7. APIM Backends for ACA
module mockApiKeyNamedValue '../../shared/bicep/modules/apim/v1/named-value.bicep' = {
  name: 'mockApiKeyNamedValue'
  params: {
    apimName: apimName
    namedValueName: 'mockapi-key'
    namedValueValue: mockApiCredentials.apiKey
    namedValueIsSecret: true
  }
  dependsOn: [
    apimModule
  ]
}

module backendModule1 '../../shared/bicep/modules/apim/v1/backend.bicep' = {
  name: 'aca-backend-1'
  params: {
    apimName: apimName
    backendName: 'aca-backend-1'
    url: 'https://${mockApiModule.outputs.containerAppFqdns[0]}'
    credentialHeaders: {
      'X-MockAPI-Key': ['{{mockapi-key}}']
    }
  }
  dependsOn: [
    apimModule
    mockApiKeyNamedValue
  ]
}

module backendModule2 '../../shared/bicep/modules/apim/v1/backend.bicep' = {
  name: 'aca-backend-2'
  params: {
    apimName: apimName
    backendName: 'aca-backend-2'
    url: 'https://${mockApiModule.outputs.containerAppFqdns[1]}'
    credentialHeaders: {
      'X-MockAPI-Key': ['{{mockapi-key}}']
    }
  }
  dependsOn: [
    apimModule
    mockApiKeyNamedValue
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
output acaUrl1 string = 'https://${mockApiModule.outputs.containerAppFqdns[0]}/hello'
output acaUrl2 string = 'https://${mockApiModule.outputs.containerAppFqdns[1]}/hello'
output mockApiStorageAccountName string = mockApiModule.outputs.storageAccountName
output mockApiContainerAppNames array = mockApiModule.outputs.containerAppNames
output mockApiDashboardUrls array = map(mockApiModule.outputs.containerAppFqdns, fqdn => 'https://${fqdn}/')

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
