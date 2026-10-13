// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location of the sample-owned PAYG Azure OpenAI account.')
param location string = resourceGroup().location

@description('Repository infrastructure resource suffix.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Existing infrastructure APIM service.')
param apimName string = 'apim-${resourceSuffix}'

@description('Existing infrastructure Application Insights component; no monitoring resources are created.')
param appInsightsName string = 'appi-${resourceSuffix}'

@description('Sample-owned namespace for APIs, model deployments, backends and pools.')
@minLength(1)
@maxLength(40)
param sampleName string = 'aoai-v1-migration-1'

@description('APIs for this stage: simple legacy first, then simple legacy/v1 plus advanced legacy/v1.')
param apis array

@description('Two model records: name, version, capacity, deploymentName, backendName and poolName.')
@minLength(2)
@maxLength(2)
param models array

@description('PAYG deployment type. No provisioned throughput is used.')
@allowed(['Standard', 'GlobalStandard'])
param modelSku string = 'GlobalStandard'


// ------------------------------
//    VARIABLES
// ------------------------------

@description('Deterministic sample account name, independent of deployment stage.')
var accountName = 'oai-v1-${uniqueString(resourceGroup().id, sampleName)}'

@description('Cognitive Services OpenAI User role for APIM managed identity.')
var openAiUserRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// https://learn.microsoft.com/azure/templates/microsoft.insights/components
resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

// Uses the same account/deployment/RBAC pattern as inference-failover, without simulated PTU tiers.
// https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/accounts
resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: accountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/accounts/deployments
// Azure OpenAI serializes deployment changes on the parent account; parallel writes can return RequestConflict.
@batchSize(1)
resource modelDeploymentResources 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = [for model in models: {
  name: model.deploymentName
  parent: openAiAccount
  sku: {
    name: modelSku
    capacity: model.capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: model.name
      version: model.version
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}]

// https://learn.microsoft.com/azure/templates/microsoft.authorization/roleassignments
resource apimOpenAiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAiAccount.id, apimService.id, openAiUserRole)
  scope: openAiAccount
  properties: {
    principalId: apimService.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: openAiUserRole
  }
}

module backends '../../shared/bicep/modules/apim/v1/backend.bicep' = [for model in models: {
  name: model.backendName
  params: {
    apimName: apimName
    backendName: model.backendName
    backendDescription: 'PAYG ${model.name} destination for both API contracts.'
    backendType: 'Single'
    url: openAiAccount.properties.endpoint
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}]

module pools '../../shared/bicep/modules/apim/v1/backend-pool.bicep' = [for model in models: {
  name: model.poolName
  params: {
    apimName: apimName
    backendPoolName: model.poolName
    backendPoolDescription: '${model.name} singleton pool shared by legacy and v1.'
    backends: [
      { name: model.backendName, priority: 1, weight: 100 }
    ]
  }
  dependsOn: [backends]
}]

// Separate APIM breaker state preserves the simpler APIs; no additional OpenAI capacity is deployed.
module advancedBackends '../../shared/bicep/modules/apim/v1/backend.bicep' = [for model in models: {
  name: '${model.deploymentName}-advanced-backend'
  params: {
    apimName: apimName
    backendName: '${model.deploymentName}-advanced-backend'
    backendDescription: 'Inference-failover policy destination for ${model.name}, reusing the PAYG deployment.'
    backendType: 'Single'
    url: openAiAccount.properties.endpoint
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
    circuitBreaker: {
      rules: [
        {
          name: 'failover-on-capacity-or-infrastructure-failure'
          acceptRetryAfter: true
          failureCondition: {
            count: 1
            interval: 'PT1M'
            statusCodeRanges: [
              { min: 408, max: 408 }
              { min: 429, max: 429 }
              { min: 499, max: 500 }
              { min: 502, max: 504 }
            ]
          }
          tripDuration: 'PT1M'
        }
      ]
    }
  }
}]

module advancedPools '../../shared/bicep/modules/apim/v1/backend-pool.bicep' = [for model in models: {
  name: '${model.deploymentName}-advanced-pool'
  params: {
    apimName: apimName
    backendPoolName: '${model.deploymentName}-advanced-pool'
    backendPoolDescription: '${model.name} singleton pool for the advanced legacy and v1 policies.'
    backends: [
      { name: '${model.deploymentName}-advanced-backend', priority: 1, weight: 100 }
    ]
  }
  dependsOn: [advancedBackends]
}]

// The notebook deliberately supplies only legacy in stage one.
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: {
  name: '${api.name}-${resourceSuffix}'
  params: {
    apimName: apimName
    api: api
  }
  dependsOn: [pools, advancedPools, modelDeploymentResources, apimOpenAiRole]
}]


// ------------------------------
//    OUTPUTS
// ------------------------------

output apimServiceId string = apimService.id
output apimServiceName string = apimService.name
output apimResourceGatewayURL string = apimService.properties.gatewayUrl
output applicationInsightsName string = appInsights.name
output openAiAccountName string = openAiAccount.name
output openAiAccountId string = openAiAccount.id
output modelDeployments array = [for model in models: {
  name: model.name
  version: model.version
  deploymentName: model.deploymentName
  backendName: model.backendName
  poolName: model.poolName
  advancedBackendName: '${model.deploymentName}-advanced-backend'
  advancedPoolName: '${model.deploymentName}-advanced-pool'
}]
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
