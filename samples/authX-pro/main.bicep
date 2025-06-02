// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

param namedValues array = []
param apimName string = 'apim-${resourceSuffix}'
param appInsightsName string = 'appi-${resourceSuffix}'
param apis array = []
param products array = []
param policyFragments array = []

// [ADD RELEVANT PARAMETERS HERE]

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

// APIM Named Values
module namedValue '../../shared/bicep/modules/apim/v1/named-value.bicep' = [for nv in namedValues: {
  name: 'nv-${nv.name}'
  params:{
    apimName: apimName
    namedValueName: nv.name
    namedValueValue: nv.value
    namedValueIsSecret: nv.isSecret
  }
}]

// APIM Policy Fragments
module policyFragment '../../shared/bicep/modules/apim/v1/policy-fragment.bicep' = [for pf in policyFragments: {
  name: 'pf-${pf.name}'
  params:{
    apimName: apimName
    policyFragmentName: pf.name
    policyFragmentDescription: pf.description
    policyFragmentValue: pf.policyXml
  }
  dependsOn: [
    namedValue
  ]
}]

// APIM Products
module productHr '../../shared/bicep/modules/apim/v1/product.bicep' = [for product in products: {
  name: 'product-${product.name}'
  params: {
    apimName: apimName
    productName: product.name
    productDisplayName: product.displayName
    productDescription: product.description
    productState: product.state
    subscriptionRequired: product.subscriptionRequired
    approvalRequired: product.approvalRequired
    policyXml: product.policyXml
  }
  dependsOn: [
    namedValue
    policyFragment
  ]
}]

// APIM APIs
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
    namedValue              // ensure all named values are created before APIs
    productHr               // ensure products are created before APIs that reference them
  ]
}]

// [ADD RELEVANT BICEP MODULES HERE]

// ------------------
//    MARK: OUTPUTS
// ------------------

output apimServiceId string = apimService.id
output apimServiceName string = apimService.name
output apimResourceGatewayURL string = apimService.properties.gatewayUrl
// [ADD RELEVANT OUTPUTS HERE]
