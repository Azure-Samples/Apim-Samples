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
module namedValueModule '../../shared/bicep/modules/apim/v1/named-value.bicep' = [for nv in namedValues: {
  name: 'nv-${nv.name}'
  params:{
    apimName: apimName
    namedValueName: nv.name
    namedValueValue: nv.value
    namedValueIsSecret: nv.isSecret
  }
}]

// APIM Policy Fragments
module policyFragmentModule '../../shared/bicep/modules/apim/v1/policy-fragment.bicep' = [for pf in policyFragments: {
  name: 'pf-${pf.name}'
  params:{
    apimName: apimName
    policyFragmentName: pf.name
    policyFragmentDescription: pf.description
    policyFragmentValue: pf.policyXml
  }
  dependsOn: [
    namedValueModule
  ]
}]

// APIM Products
module productModule '../../shared/bicep/modules/apim/v1/product.bicep' = [for product in products: {
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
    namedValueModule
    policyFragmentModule
  ]
}]

// APIM APIs (deployed after products are ready to avoid race conditions)
@batchSize(4)
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
    namedValueModule              // ensure all named values are created before APIs
    policyFragmentModule          // ensure all policy fragments are created before APIs
    productModule                 // ensure all products are fully created before APIs
  ]
}]

// ------------------
//    MARK: OUTPUTS
// ------------------

output apimServiceId string = apimService.id
output apimServiceName string = apimService.name
output apimResourceGatewayURL string = apimService.properties.gatewayUrl

// Product outputs
output productOutputs array = [for i in range(0, length(products)): {
  resourceId: productModule[i].outputs.productResourceId
  name: productModule[i].outputs.productName
  displayName: productModule[i].outputs.productDisplayName
  state: productModule[i].outputs.productState
  subscriptionRequired: productModule[i].outputs.subscriptionRequired
  approvalRequired: productModule[i].outputs.approvalRequired
  policyResourceId: productModule[i].outputs.policyResourceId
  hasPolicyAttached: productModule[i].outputs.hasPolicyAttached
  subscriptionResourceId: productModule[i].outputs.subscriptionResourceId
  subscriptionName: productModule[i].outputs.subscriptionName
  subscriptionPrimaryKey: productModule[i].outputs.subscriptionPrimaryKey
  subscriptionSecondaryKey: productModule[i].outputs.subscriptionSecondaryKey
}]
