// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Default account region.')
param location string = resourceGroup().location

@description('Repository infrastructure resource suffix.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Existing infrastructure APIM service.')
param apimName string = 'apim-${resourceSuffix}'

@description('Existing infrastructure logger; never create a second logger.')
param apimLoggerName string = 'apim-logger'

@description('Model list; deploymentName equals the caller model selector on every account.')
@minLength(1)
param models array

@description('PAYG only, regardless of simulated semantic tier labels.')
@allowed(['GlobalStandard', 'Standard'])
param modelSku string = 'GlobalStandard'

@description('Four APIs in order: body, header, subscription and recommended. Each exposes Chat Completions and Responses with a focused XML policy.')
@minLength(4)
@maxLength(4)
param apis array


// ------------------------------
//    VARIABLES
// ------------------------------

@description('Fixed sample prefix matching the literal fragment, pool and subscription names in the policies.')
var sampleName = 'aoai-v1-routing-1'

@description('Semantic labels are simulations only. All three are real, separate Foundry PAYG accounts.')
var accounts = [
  { label: 'global-standard', region: location }
  { label: 'ptu', region: location }
  { label: 'consumption', region: location }
]

@description('A single backend per account/model, reused by all pool families for shared breaker state.')
var destinations = flatten(map(models, model => map(range(0, length(accounts)), accountIndex => {
  model: model.deploymentName
  accountIndex: accountIndex
  backendName: '${sampleName}-${model.deploymentName}-${accounts[accountIndex].label}'
})))

@description('Both priorities and weights matter: lower numeric priority wins; weights apply within a priority.')
var families = [
  { name: 'standard', priorities: [1, 2, 1], weights: [3, 1, 1] }
  { name: 'priority', priorities: [2, 1, 1], weights: [1, 3, 1] }
]

@description('Pool names follow a convention, not a model-to-pool lookup.')
var poolConfigurations = flatten(map(models, model => map(families, family => {
  name: '${sampleName}-${model.deploymentName}-${family.name}-pool'
  description: 'Native PAYG ${family.name} pool with simulated tier preference; no PTU purchase.'
  members: map(range(0, length(accounts)), i => {
    name: '${sampleName}-${model.deploymentName}-${accounts[i].label}'
    priority: family.priorities[i]
    weight: family.weights[i]
  })
})))

@description('Sample-scoped validated subscription identifiers, not display names or client claims.')
var standardSubscriptionId = 'api-${toLower(apis[2].name)}'

@description('The priority subscription is separately scoped to the same API.')
var prioritySubscriptionId = '${sampleName}-priority'

@description('Separate API-scoped priority identity for the combined recommended endpoint.')
var recommendedPrioritySubscriptionId = '${sampleName}-recommended-priority'

@description('Deploy-time policy selection; no scenario switches execute at the gateway.')
var policyDefinitions = [
  loadTextContent('apim-policies/body.xml')
  loadTextContent('apim-policies/header.xml')
  loadTextContent('apim-policies/subscription.xml')
  loadTextContent('apim-policies/recommended.xml')
]

@description('Sample-local fragments share mechanics, not scenario-dependent routing branches.')
var policyFragments = [
  { name: 'body-model', xml: loadTextContent('apim-policies/fragments/body-model.xml') }
  { name: 'header-model', xml: loadTextContent('apim-policies/fragments/header-model.xml') }
  { name: 'subscription-family', xml: loadTextContent('apim-policies/fragments/subscription-family.xml') }
  { name: 'route-request', xml: loadTextContent('apim-policies/fragments/route-request.xml') }
  { name: 'safe-response', xml: loadTextContent('apim-policies/fragments/safe-response.xml') }
  { name: 'safe-error', xml: loadTextContent('apim-policies/fragments/safe-error.xml') }
]

@description('No request/response payload capture or selector/header capture in diagnostics.')
var safeLogSettings = { headers: [], body: { bytes: 0 } }


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apim 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

module foundryAccounts 'foundry-account.bicep' = [for account in accounts: {
  name: '${sampleName}-${account.label}-account'
  params: {
    location: account.region
    accountName: 'oai-r-${uniqueString(resourceGroup().id, sampleName, account.label)}'
    models: models
    modelSku: modelSku
    principalId: apim.identity.principalId
  }
}]

module backends '../../shared/bicep/modules/apim/v1/backend.bicep' = [for destination in destinations: {
  name: destination.backendName
  params: {
    apimName: apimName
    backendName: destination.backendName
    backendType: 'Single'
    backendDescription: 'Shared Foundry PAYG account/model destination. Semantic tier label is only a simulation.'
    url: uri(foundryAccounts[destination.accountIndex].outputs.endpoint, 'openai/v1')
    tls: { validateCertificateChain: true, validateCertificateName: true }
    circuitBreaker: {
      rules: [{
        name: 'capacity-and-service-failures'
        acceptRetryAfter: true
        failureCondition: {
          count: 1
          interval: 'PT1M'
          statusCodeRanges: [
            { min: 429, max: 429 }
            { min: 500, max: 504 }
          ]
        }
        tripDuration: 'PT1M'
      }]
    }
  }
}]

module pools '../../shared/bicep/modules/apim/v1/backend-pool.bicep' = [for pool in poolConfigurations: {
  name: pool.name
  params: {
    apimName: apimName
    backendPoolName: pool.name
    backendPoolDescription: pool.description
    backends: pool.members
  }
  dependsOn: [backends]
}]

module policyFragmentModule '../../shared/bicep/modules/apim/v1/policy-fragment.bicep' = [for fragment in policyFragments: {
  name: '${sampleName}-${fragment.name}-fragment'
  params: {
    apimName: apimName
    policyFragmentName: '${sampleName}-${fragment.name}'
    policyFragmentDescription: 'Shared mechanics for the Azure OpenAI v1 Routing sample.'
    policyFragmentValue: fragment.xml
  }
}]

module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for (api, i) in apis: {
  name: '${api.name}-${resourceSuffix}'
  params: {
    apimName: apimName
    // Omit App Insights parameters: the shared module otherwise captures 8192 body bytes.
    api: union(api, {
      subscriptionRequired: true
      enableLlmLogging: false
      policyXml: policyDefinitions[i]
    })
  }
  dependsOn: [pools, policyFragmentModule]
}]

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/apis
resource apiResources 'Microsoft.ApiManagement/service/apis@2024-06-01-preview' existing = [for api in apis: {
  parent: apim
  name: api.name
}]

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/apis/diagnostics
resource diagnostics 'Microsoft.ApiManagement/service/apis/diagnostics@2024-06-01-preview' = [for (api, i) in apis: {
  parent: apiResources[i]
  name: 'applicationinsights'
  properties: {
    loggerId: resourceId('Microsoft.ApiManagement/service/loggers', apimName, apimLoggerName)
    verbosity: 'verbose'
    alwaysLog: 'allErrors'
    httpCorrelationProtocol: 'W3C'
    logClientIp: false
    sampling: { samplingType: 'fixed', percentage: 100 }
    frontend: { request: safeLogSettings, response: safeLogSettings }
    backend: { request: safeLogSettings, response: safeLogSettings }
  }
  dependsOn: [apisModule]
}]

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/subscriptions
resource prioritySubscription 'Microsoft.ApiManagement/service/subscriptions@2024-05-01' = {
  parent: apim
  name: prioritySubscriptionId
  properties: {
    displayName: 'Azure OpenAI v1 Routing - Priority'
    scope: '/apis/${apis[2].name}'
    state: 'active'
  }
  dependsOn: [apisModule]
}

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/subscriptions
resource recommendedPrioritySubscription 'Microsoft.ApiManagement/service/subscriptions@2024-05-01' = {
  parent: apim
  name: recommendedPrioritySubscriptionId
  properties: {
    displayName: 'Azure OpenAI v1 Routing - Recommended Priority'
    scope: '/apis/${apis[3].name}'
    state: 'active'
  }
  dependsOn: [apisModule]
}


// ------------------------------
//    OUTPUTS
// ------------------------------

output apimServiceId string = apim.id
output apimServiceName string = apim.name
output apimResourceGatewayURL string = apim.properties.gatewayUrl
output accountOutputs array = [for i in range(0, length(accounts)): {
  label: accounts[i].label
  name: foundryAccounts[i].outputs.accountName
  resourceId: foundryAccounts[i].outputs.accountId
}]
output poolNames array = map(poolConfigurations, pool => pool.name)
output standardSubscriptionName string = standardSubscriptionId
output prioritySubscriptionName string = prioritySubscription.name
#disable-next-line outputs-should-not-contain-secrets // Intentional NotebookHelper sample output; never print.
output prioritySubscriptionPrimaryKey string = prioritySubscription.listSecrets().primaryKey
output recommendedStandardSubscriptionName string = 'api-${toLower(apis[3].name)}'
output recommendedPrioritySubscriptionName string = recommendedPrioritySubscription.name
#disable-next-line outputs-should-not-contain-secrets // Intentional NotebookHelper sample output; never print.
output recommendedPrioritySubscriptionPrimaryKey string = recommendedPrioritySubscription.listSecrets().primaryKey
output apiOutputs array = [for i in range(0, length(apis)): {
  name: apis[i].name
  resourceId: apisModule[i].outputs.apiResourceId
  displayName: apisModule[i].outputs.apiDisplayName
  productAssociationCount: apisModule[i].outputs.productAssociationCount
  subscriptionResourceId: apisModule[i].outputs.subscriptionResourceId
  subscriptionName: apisModule[i].outputs.subscriptionName
  subscriptionPrimaryKey: apisModule[i].outputs.subscriptionPrimaryKey
  subscriptionSecondaryKey: apisModule[i].outputs.subscriptionSecondaryKey
}]
