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

@description('Reveals the backend API information. Defaults to true. *** WARNING: This will expose backend API information to the caller - For learning & testing only! ***')
param revealBackendApiInfo bool = true

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

// 3. API Management
module apimModule '../../shared/bicep/modules/apim/v1/apim.bicep' = {
  name: 'apimModule'
  params: {
    apimSku: apimSku
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    globalPolicyXml: revealBackendApiInfo ? loadTextContent('../../shared/apim-policies/all-apis-reveal-backend.xml') : loadTextContent('../../shared/apim-policies/all-apis.xml')
  }
}

// 4. APIM Policy Fragments
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

// 5. APIM APIs
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: if(length(apis) > 0) {
  name: 'api-${api.name}'
  params: {
    apimName: apimName
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    api: api
  }
  dependsOn: [
   apimModule
  ]
}]


// ------------------
//    MARK: OUTPUTS
// ------------------

output applicationInsightsAppId string = appInsightsModule.outputs.appId
output applicationInsightsName string = appInsightsModule.outputs.applicationInsightsName
output logAnalyticsWorkspaceId string = lawModule.outputs.customerId
output apimServiceId string = apimModule.outputs.id
output apimServiceName string = apimModule.outputs.name
output apimResourceGatewayURL string = apimModule.outputs.gatewayUrl

#disable-next-line outputs-should-not-contain-secrets
//output apimSubscription1Key string = apimModule.outputs.[0].listSecrets().primaryKey
