// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for sample-scoped resources. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Name of the existing API Management service.')
param apimName string = 'apim-${resourceSuffix}'

@description('Deployment index for readable sample resource naming.')
param index int = 1

@description('Name of the existing infrastructure-deployed Application Insights component to reuse for API diagnostics.')
param appInsightsName string = 'appi-${resourceSuffix}'

@description('Name of the existing infrastructure-deployed Log Analytics workspace to reuse for AI Gateway telemetry.')
param logAnalyticsWorkspaceName string = 'log-${resourceSuffix}'

@description('Array of inference APIs assembled by the notebook.')
param apis array = []

@description('Deploy a regional Event Hub and stream APIM logs and metrics for external consumers.')
param enableEventHubExport bool = false


// ------------------------------
//    VARIABLES
// ------------------------------

@description('Resource ID of the Cognitive Services OpenAI User built-in role assigned to the APIM managed identity.')
var openAiUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')

@description('Suffix for the APIM diagnostic setting associated with this sample.')
var diagnosticsSuffix = 'inference-failover-${index}'

@description('Display name of the telemetry workbook deployed for this sample.')
var workbookName = 'APIM Inference Failover ${index}'

@description('Deterministic resource name of the telemetry workbook.')
var workbookResourceName = guid(resourceGroup().id, 'inference-failover', string(index))

@description('Name of the optional Event Hubs namespace deployed in the APIM region.')
var eventHubNamespaceName = 'evhns-if-${index}-${take(resourceSuffix, 6)}'

@description('Name of the optional Event Hub receiving APIM telemetry.')
var eventHubName = 'apim-inference-failover'

@description('Name of the optional Event Hub consumer group for external observability processors.')
var eventHubConsumerGroupName = 'external-observability'

@description('Regional Azure OpenAI resources used as the source of model-safe backend destinations.')
var aoaiAccounts = [
  {
    name: 'oai-if-eastus2-${index}-${take(resourceSuffix, 6)}'
    location: 'eastus2'
  }
  {
    name: 'oai-if-westus3-${index}-${take(resourceSuffix, 6)}'
    location: 'westus3'
  }
  {
    name: 'oai-if-southcentral-${index}-${take(resourceSuffix, 6)}'
    location: 'southcentralus'
  }
]
@description('Azure OpenAI model deployments and their concrete APIM backend identity labels.')
var deployments = [
  {
    accountIndex: 0
    backendName: 'gpt-5-1-PTU-eastus2'
    deploymentName: 'a-gpt-5-1'
    modelName: 'gpt-5.1'
    modelVersion: '2025-11-13'
    region: 'eastus2'
    route: 'In-region PTU'
  }
  {
    accountIndex: 1
    backendName: 'gpt-5-1-PTU-westus3'
    deploymentName: 'd-gpt-5-1'
    modelName: 'gpt-5.1'
    modelVersion: '2025-11-13'
    region: 'westus3'
    route: 'Out-of-region PTU'
  }
  {
    accountIndex: 0
    backendName: 'gpt-5-1-PAYG-eastus2'
    deploymentName: 'b-gpt-5-1'
    modelName: 'gpt-5.1'
    modelVersion: '2025-11-13'
    region: 'eastus2'
    route: 'In-region PAYG'
  }
  {
    accountIndex: 1
    backendName: 'gpt-5-1-PAYG-westus3'
    deploymentName: 'e-gpt-5-1'
    modelName: 'gpt-5.1'
    modelVersion: '2025-11-13'
    region: 'westus3'
    route: 'Out-of-region PAYG'
  }
  {
    accountIndex: 2
    backendName: 'gpt-5-1-PAYG-southcentralus'
    deploymentName: 'g-gpt-5-1'
    modelName: 'gpt-5.1'
    modelVersion: '2025-11-13'
    region: 'southcentralus'
    route: 'Out-of-region PAYG'
  }
  {
    accountIndex: 0
    backendName: 'gpt-4-1-mini-PTU-eastus2'
    deploymentName: 'c-gpt-4-1-mini'
    modelName: 'gpt-4.1-mini'
    modelVersion: '2025-04-14'
    region: 'eastus2'
    route: 'In-region PTU'
  }
  {
    accountIndex: 1
    backendName: 'gpt-4-1-mini-PTU-westus3'
    deploymentName: 'f-gpt-4-1-mini'
    modelName: 'gpt-4.1-mini'
    modelVersion: '2025-04-14'
    region: 'westus3'
    route: 'Out-of-region PTU'
  }
  {
    accountIndex: 0
    backendName: 'gpt-4-1-mini-PAYG-eastus2'
    deploymentName: 'd-gpt-4-1-mini'
    modelName: 'gpt-4.1-mini'
    modelVersion: '2025-04-14'
    region: 'eastus2'
    route: 'In-region PAYG'
  }
  {
    accountIndex: 2
    backendName: 'gpt-4-1-mini-PAYG-southcentralus'
    deploymentName: 'h-gpt-4-1-mini'
    modelName: 'gpt-4.1-mini'
    modelVersion: '2025-04-14'
    region: 'southcentralus'
    route: 'Out-of-region PAYG'
  }
]


// ------------------------------
//    EXISTING INFRASTRUCTURE RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// https://learn.microsoft.com/azure/templates/microsoft.insights/components
resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

// https://learn.microsoft.com/azure/templates/microsoft.operationalinsights/workspaces
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: logAnalyticsWorkspaceName
}


// ------------------------------
//    OPTIONAL EVENT HUB EXPORT
// ------------------------------

// Azure Monitor requires regional resources to export diagnostics to an Event Hubs namespace in the same region.
// The notebook passes its infrastructure/APIM region as the sample location parameter.
// https://learn.microsoft.com/azure/templates/microsoft.eventhub/namespaces
resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = if (enableEventHubExport) {
  name: eventHubNamespaceName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
    capacity: 1
  }
  properties: {
    disableLocalAuth: false
    isAutoInflateEnabled: true
    kafkaEnabled: false
    maximumThroughputUnits: 5
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    zoneRedundant: false
  }
}

// Azure Monitor diagnostic streaming does not support compacted event hubs.
// https://learn.microsoft.com/azure/templates/microsoft.eventhub/namespaces/eventhubs
resource eventHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = if (enableEventHubExport) {
  name: eventHubName
  parent: eventHubNamespace
  properties: {
    messageRetentionInDays: 7
    partitionCount: 4
    status: 'Active'
  }
}

// Provide a dedicated consumer-group checkpoint scope for downstream observability processors.
// https://learn.microsoft.com/azure/templates/microsoft.eventhub/namespaces/eventhubs/consumergroups
resource eventHubConsumerGroup 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = if (enableEventHubExport) {
  name: eventHubConsumerGroupName
  parent: eventHub
  properties: {}
}

// Azure Monitor diagnostic streaming requires Manage, Send, and Listen permissions on a namespace authorization rule.
// https://learn.microsoft.com/azure/templates/microsoft.eventhub/namespaces/authorizationrules
resource eventHubExportAuthorizationRule 'Microsoft.EventHub/namespaces/authorizationRules@2024-01-01' = if (enableEventHubExport) {
  name: 'diagnostic-export'
  parent: eventHubNamespace
  properties: {
    rights: [
      'Listen'
      'Send'
      'Manage'
    ]
  }
}


// ------------------------------
//    AZURE OPENAI DEPLOYMENTS
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/accounts
resource openAiAccounts 'Microsoft.CognitiveServices/accounts@2024-10-01' = [for account in aoaiAccounts: {
  name: account.name
  location: account.location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: account.name
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}]

// All deployments use regional Standard PAYG capacity. The PTU/PAYG label is only the route tier being simulated.
// https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/accounts/deployments
@batchSize(1)
resource openAiDeployments 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = [for deployment in deployments: {
  name: deployment.deploymentName
  parent: openAiAccounts[deployment.accountIndex]
  sku: {
    name: 'Standard'
    capacity: 1
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: deployment.modelName
      version: deployment.modelVersion
    }
  }
}]

// https://learn.microsoft.com/azure/templates/microsoft.authorization/roleassignments
resource apimOpenAiRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (account, accountIndex) in aoaiAccounts: {
  name: guid(openAiAccounts[accountIndex].id, apimService.id, openAiUserRoleDefinitionId)
  scope: openAiAccounts[accountIndex]
  properties: {
    principalId: apimService.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: openAiUserRoleDefinitionId
  }
}]


// ------------------------------
//    AI GATEWAY ROUTING
// ------------------------------

// Each backend targets exactly one compatible deployment. Managed identity authentication is applied by the inference API policy for the selected backend.
module inferenceBackends '../../shared/bicep/modules/apim/v1/backend.bicep' = [for (deployment, deploymentIndex) in deployments: {
  name: 'backend-${deployment.backendName}'
  params: {
    apimName: apimName
    backendName: deployment.backendName
    backendDescription: '${deployment.route}: ${deployment.deploymentName} (${deployment.modelName})'
    backendType: 'Single'
    url: '${openAiAccounts[deployment.accountIndex].properties.endpoint}openai/deployments/${deployment.deploymentName}'
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
    circuitBreaker: {
      rules: [
        {
          name: 'throttled-or-unavailable'
          acceptRetryAfter: true
          failureCondition: {
            count: 1
            errorReasons: [
              'Server errors'
            ]
            interval: 'PT1M'
            statusCodeRanges: [
              {
                min: 429
                max: 429
              }
              {
                min: 503
                max: 503
              }
            ]
          }
          tripDuration: 'PT1M'
        }
      ]
    }
  }
  dependsOn: [
    apimOpenAiRoleAssignments
    openAiDeployments[deploymentIndex]
  ]
}]

module gpt51BackendPool '../../shared/bicep/modules/apim/v1/backend-pool.bicep' = {
  name: 'pool-gpt-5-1'
  params: {
    apimName: apimName
    backendPoolName: 'inference-gpt-5-1-pool'
    backendPoolDescription: 'gpt-5.1 routing preference: in-region PTU, out-of-region PTU, in-region PAYG, then equal-weight out-of-region PAYG.'
    backends: [
      {
        name: 'gpt-5-1-PTU-eastus2'
        priority: 1
        weight: 100
      }
      {
        name: 'gpt-5-1-PTU-westus3'
        priority: 2
        weight: 100
      }
      {
        name: 'gpt-5-1-PAYG-eastus2'
        priority: 3
        weight: 100
      }
      {
        name: 'gpt-5-1-PAYG-westus3'
        priority: 4
        weight: 50
      }
      {
        name: 'gpt-5-1-PAYG-southcentralus'
        priority: 4
        weight: 50
      }
    ]
  }
  dependsOn: [
    inferenceBackends
  ]
}

module gpt41MiniBackendPool '../../shared/bicep/modules/apim/v1/backend-pool.bicep' = {
  name: 'pool-gpt-4-1-mini'
  params: {
    apimName: apimName
    backendPoolName: 'inference-gpt-4-1-mini-pool'
    backendPoolDescription: 'gpt-4.1-mini routing preference: in-region PTU, out-of-region PTU, in-region PAYG, then out-of-region PAYG.'
    backends: [
      {
        name: 'gpt-4-1-mini-PTU-eastus2'
        priority: 1
        weight: 100
      }
      {
        name: 'gpt-4-1-mini-PTU-westus3'
        priority: 2
        weight: 100
      }
      {
        name: 'gpt-4-1-mini-PAYG-eastus2'
        priority: 3
        weight: 100
      }
      {
        name: 'gpt-4-1-mini-PAYG-southcentralus'
        priority: 4
        weight: 100
      }
    ]
  }
  dependsOn: [
    inferenceBackends
  ]
}

module apimDiagnostics '../../shared/bicep/modules/apim/v1/diagnostics.bicep' = {
  name: 'diagnostics-inference-failover'
  params: {
    location: location
    apimServiceName: apimName
    apimResourceGroupName: resourceGroup().name
    diagnosticSettingsNameSuffix: diagnosticsSuffix
    enableApplicationInsights: false
    enableEventHub: enableEventHubExport
    enableLlmLogs: true
    enableLogAnalytics: true
    eventHubAuthorizationRuleId: enableEventHubExport ? eventHubExportAuthorizationRule.id : ''
    eventHubName: enableEventHubExport ? eventHub.name : ''
    logAnalyticsWorkspaceId: logAnalyticsWorkspace.id
  }
}

module inferenceApis '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: if (!empty(apis)) {
  name: 'api-${api.name}'
  params: {
    api: api
    apimName: apimName
    appInsightsId: appInsights.id
    appInsightsInstrumentationKey: appInsights.properties.InstrumentationKey
  }
  dependsOn: [
    apimDiagnostics
    gpt51BackendPool
    gpt41MiniBackendPool
  ]
}]


// ------------------------------
//    TELEMETRY WORKBOOK
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.insights/workbooks
resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: workbookResourceName
  location: location
  kind: 'shared'
  properties: {
    category: 'APIM'
    displayName: workbookName
    serializedData: string(loadJsonContent('inference-failover.workbook.json'))
    sourceId: logAnalyticsWorkspace.id
    version: '1.0'
  }
}


// ------------------------------
//    OUTPUTS
// ------------------------------

@description('Name of the existing Application Insights component used for API diagnostics.')
output applicationInsightsName string = appInsights.name

@description('Name of the existing Log Analytics workspace used for gateway and LLM telemetry.')
output logAnalyticsWorkspaceName string = logAnalyticsWorkspace.name

@description('Resource ID of the Log Analytics workspace.')
output logAnalyticsWorkspaceId string = logAnalyticsWorkspace.id

@description('Name of the existing APIM service.')
output apimServiceName string = apimService.name

@description('APIM gateway URL.')
output apimResourceGatewayURL string = apimService.properties.gatewayUrl

@description('Display name of the deployed telemetry workbook.')
output workbookName string = workbookName

@description('Resource ID of the deployed telemetry workbook.')
output workbookId string = workbook.id

@description('Whether optional APIM telemetry streaming to Event Hubs is enabled.')
output eventHubExportEnabled bool = enableEventHubExport

@description('Resource ID of the optional Event Hubs namespace.')
output eventHubNamespaceId string = enableEventHubExport ? eventHubNamespace.id : ''

@description('Name of the optional Event Hubs namespace.')
output eventHubNamespaceName string = enableEventHubExport ? eventHubNamespace.name : ''

@description('Resource ID of the optional Event Hub receiving APIM telemetry.')
output eventHubId string = enableEventHubExport ? eventHub.id : ''

@description('Name of the optional Event Hub receiving APIM telemetry.')
output eventHubName string = enableEventHubExport ? eventHub.name : ''

@description('Name of the optional Event Hub consumer group for external observability processors.')
output eventHubConsumerGroupName string = enableEventHubExport ? eventHubConsumerGroup.name : ''

@description('Location of the optional Event Hubs namespace. This matches the APIM service region.')
output eventHubLocation string = eventHubNamespace.?location ?? ''

@description('Regional Azure OpenAI resource names deployed for the experiment.')
output openAiAccountNames array = [for account in aoaiAccounts: account.name]

@description('Model deployment names deployed for the experiment.')
output modelDeploymentNames array = [for deployment in deployments: deployment.deploymentName]

@description('Per-API subscription metadata and keys required by notebook request tests.')
output apiOutputs array = [for (api, apiIndex) in apis: {
  name: api.name
  resourceId: inferenceApis[apiIndex].?outputs.?apiResourceId ?? ''
  displayName: inferenceApis[apiIndex].?outputs.?apiDisplayName ?? ''
  subscriptionName: inferenceApis[apiIndex].?outputs.?subscriptionName ?? ''
  #disable-next-line outputs-should-not-contain-secrets // Intentional: notebook needs API-scoped keys for test traffic.
  subscriptionPrimaryKey: inferenceApis[apiIndex].?outputs.?subscriptionPrimaryKey ?? ''
}]
