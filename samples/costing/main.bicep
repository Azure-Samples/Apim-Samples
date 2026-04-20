// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Name of the API Management service')
param apimName string = 'apim-${resourceSuffix}'

@description('Deployment index for unique resource naming')
param index int

@description('Enable Application Insights for APIM diagnostics')
param enableApplicationInsights bool = true

@description('Enable Log Analytics for APIM diagnostics')
param enableLogAnalytics bool = true

@description('Storage account SKU for cost exports')
@allowed([
  'Standard_LRS'
  'Standard_GRS'
  'Standard_ZRS'
])
param storageAccountSku string = 'Standard_LRS'

@description('Cost export frequency')
@allowed([
  'Daily'
  'Weekly'
  'Monthly'
])
param costExportFrequency string = 'Daily'

@description('Start date for cost export schedule. Defaults to current deployment time.')
param costExportStartDate string = utcNow('yyyy-MM-ddT00:00:00Z')

@description('Deploy the Cost Management export from Bicep. When false (default), the notebook handles export creation with retry logic to avoid key-access propagation failures.')
param enableCostExport bool = false

@description('Array of APIs to deploy')
param apis array = []

@description('Array of business units to create subscriptions for')
param businessUnits array = []

@description('Array of policy fragments to deploy')
param policyFragments array = []

@description('Display name of the APIM SKU (e.g. Basicv2). Injected into the workbook as a label.')
param apimSkuDisplayName string = 'Basicv2'

@description('Base monthly cost for the APIM SKU in USD. Injected into the workbook default.')
param baseMonthlyCost string = '150.01'

@description('Variable cost per 1K API requests in USD. Injected into the workbook default.')
param perKRate string = '0.003'

@description('Deploy Microsoft Foundry (Hub + Project) and Azure AI Services with a model deployment for real AOAI interactions. When false (default), the mock response policy is used instead.')
param enableFoundry bool = false

@description('AI model to deploy when enableFoundry is true')
param aiModelName string = 'gpt-5-mini'

@description('AI model version when enableFoundry is true')
param aiModelVersion string = '2025-08-07'

@description('Model deployment SKU name when enableFoundry is true')
param aiModelSkuName string = 'GlobalStandard'

@description('Model deployment capacity in thousands of tokens per minute when enableFoundry is true')
param aiModelCapacity int = 10


// ------------------
//    VARIABLES
// ------------------

var applicationInsightsName = 'appi-cost-${index}-${take(resourceSuffix, 4)}'
var logAnalyticsWorkspaceName = 'log-cost-${index}-${take(resourceSuffix, 4)}'
var storageAccountName = 'stcost${take(string(index), 1)}${take(replace(resourceSuffix, '-', ''), 12)}'
var workbookName = 'APIM Cost Tracking ${index}'
var costExportName = 'apim-cost-export'
var diagnosticSettingsNameSuffix = 'costing-diagnostics-${index}'

// Foundry resource names (only used when enableFoundry is true)
var aiServicesName = 'ais-cost-${index}-${take(resourceSuffix, 4)}'
var foundryKeyVaultName = 'kvai-cost-${index}-${take(resourceSuffix, 4)}'
var foundryStorageName = 'stfndry${take(string(index), 1)}${take(replace(resourceSuffix, '-', ''), 8)}'
var foundryHubName = 'hub-cost-${index}-${take(resourceSuffix, 4)}'
var foundryProjectName = 'proj-cost-${index}-${take(resourceSuffix, 4)}'


// ------------------
//    RESOURCES
// ------------------

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// APIM Policy Fragments
module policyFragmentModule '../../shared/bicep/modules/apim/v1/policy-fragment.bicep' = [for pf in policyFragments: {
  name: 'pf-${pf.name}'
  params: {
    apimName: apimName
    policyFragmentName: pf.name
    policyFragmentDescription: pf.description
    policyFragmentValue: pf.policyXml
  }
}]

// APIM APIs
// Use the costing sample's own App Insights logger so that emit-metric
// custom metrics (caller-requests) flow to the costing
// App Insights resource instead of the infrastructure-level one.
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: if(!empty(apis)) {
  name: 'api-${api.name}'
  params: {
    apimName: apimName
    apimLoggerName: 'applicationinsights-logger'
    appInsightsInstrumentationKey: appInsightsInstrKey
    appInsightsId: appInsightsResourceId
    api: api
  }
  dependsOn: [
    apimDiagnosticsModule
    policyFragmentModule
  ]
}]

// Create subscriptions for different business units (service-level scope so each
// BU subscription works across all APIs, including the AOAI gateway)
resource subscriptions 'Microsoft.ApiManagement/service/subscriptions@2024-06-01-preview' = [for bu in businessUnits: {
  name: bu.name
  parent: apimService
  properties: {
    displayName: bu.displayName
    scope: '/apis'
    state: 'active'
  }
  dependsOn: [
    apisModule
  ]
}]

// Deploy Log Analytics Workspace using shared module
// https://learn.microsoft.com/azure/templates/microsoft.operationalinsights/workspaces
module logAnalyticsModule '../../shared/bicep/modules/operational-insights/v1/workspaces.bicep' = if (enableLogAnalytics) {
  name: 'logAnalytics'
  params: {
    location: location
    resourceSuffix: resourceSuffix
    logAnalyticsName: logAnalyticsWorkspaceName
  }
}

// Deploy Application Insights using shared module
// https://learn.microsoft.com/azure/templates/microsoft.insights/components
module applicationInsightsModule '../../shared/bicep/modules/monitor/v1/appinsights.bicep' = if (enableApplicationInsights) {
  name: 'applicationInsights'
  params: {
    location: location
    resourceSuffix: resourceSuffix
    applicationInsightsName: applicationInsightsName
    applicationInsightsLocation: location
    customMetricsOptedInType: 'WithDimensions'
    useWorkbook: false
    #disable-next-line BCP318
    lawId: enableLogAnalytics ? logAnalyticsModule.outputs.id : ''
  }
}


// https://learn.microsoft.com/azure/templates/microsoft.storage/storageaccounts
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: storageAccountSku
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
  }

  resource blobService 'blobServices' = {
    name: 'default'

    resource costExportsContainer 'containers' = {
      name: 'cost-exports'
      properties: {
        publicAccess: 'None'
      }
    }
  }
}

// Helper variables to safely access properties from conditionally deployed resources
#disable-next-line BCP318
var appInsightsInstrKey = enableApplicationInsights ? applicationInsightsModule.outputs.instrumentationKey : ''
var appInsightsConnectionStr = enableApplicationInsights ? 'InstrumentationKey=${appInsightsInstrKey}' : ''

// Helper variables for diagnostics module
#disable-next-line BCP318
var logAnalyticsWorkspaceId = enableLogAnalytics ? logAnalyticsModule.outputs.id : ''
#disable-next-line BCP318
var appInsightsResourceId = enableApplicationInsights ? applicationInsightsModule.outputs.id : ''

// Deploy APIM diagnostics using shared module
module apimDiagnosticsModule '../../shared/bicep/modules/apim/v1/diagnostics.bicep' = if (!empty(apimName)) {
  name: 'apimDiagnostics'
  params: {
    location: location
    apimServiceName: apimName
    apimResourceGroupName: resourceGroup().name
    enableLogAnalytics: enableLogAnalytics
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    enableApplicationInsights: enableApplicationInsights
    appInsightsInstrumentationKey: appInsightsInstrKey
    appInsightsResourceId: appInsightsResourceId
    diagnosticSettingsNameSuffix: diagnosticSettingsNameSuffix
    enableLlmLogs: enableFoundry
  }
}


// The workbook JSON contains '__APP_INSIGHTS_NAME__' tokens in cross-resource
// KQL queries (Entra ID tab). Replace them with the Application Insights AppId
// (GUID) so the app() function resolves correctly at runtime.
#disable-next-line BCP318
var appInsightsAppId = enableApplicationInsights ? applicationInsightsModule.outputs.appId : ''
var rawWorkbookJson = string(loadJsonContent('workbook.json'))
var wbStep1 = replace(rawWorkbookJson, '__APP_INSIGHTS_NAME__', appInsightsAppId)
var wbStep2 = replace(wbStep1, '__APIM_SKU__', apimSkuDisplayName)
var wbStep3 = replace(wbStep2, '__BASE_MONTHLY_COST__', baseMonthlyCost)
var workbookJsonWithTokens = replace(wbStep3, '__PER_K_RATE__', perKRate)

// https://learn.microsoft.com/azure/templates/microsoft.insights/workbooks
resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = if (enableLogAnalytics) {
  name: guid(resourceGroup().id, 'apim-costing-workbook', string(index))
  location: location
  kind: 'shared'
  properties: {
    displayName: workbookName
    serializedData: workbookJsonWithTokens
    version: '1.0'
    #disable-next-line BCP318
    sourceId: enableLogAnalytics ? logAnalyticsModule.outputs.id : ''
    category: 'APIM'
  }
}

// Cost Management exports are subscription-scoped and must be deployed via a module.
// https://learn.microsoft.com/azure/templates/microsoft.costmanagement/exports
module costExportModule './cost-export.bicep' = if (enableCostExport) {
  name: 'costExportDeployment'
  scope: subscription()
  params: {
    costExportName: costExportName
    storageAccountId: storageAccount.id
    recurrence: costExportFrequency
    startDate: costExportStartDate
  }
  dependsOn: [
    storageAccount::blobService::costExportsContainer
  ]
}

#disable-next-line BCP318
var costExportOutputName = enableCostExport ? costExportModule.outputs.costExportName : costExportName


// ------------------
//    FOUNDRY RESOURCES (gated by enableFoundry)
// ------------------

// Key Vault for Foundry Hub (required dependency)
// https://learn.microsoft.com/azure/templates/microsoft.keyvault/vaults
resource foundryKeyVault 'Microsoft.KeyVault/vaults@2023-07-01' = if (enableFoundry) {
  name: foundryKeyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

// Storage Account for Foundry Hub (separate from cost export storage because Foundry may require shared key access)
// https://learn.microsoft.com/azure/templates/microsoft.storage/storageaccounts
resource foundryStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = if (enableFoundry) {
  name: foundryStorageName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true
  }
}

// Azure AI Services (includes Azure OpenAI capabilities)
// https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/accounts
resource aiServices 'Microsoft.CognitiveServices/accounts@2024-10-01' = if (enableFoundry) {
  name: aiServicesName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    customSubDomainName: aiServicesName
  }
}

// Model deployment (e.g. gpt-5-mini) on the AI Services account
// https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/accounts/deployments
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (enableFoundry) {
  name: aiModelName
  parent: aiServices
  sku: {
    name: aiModelSkuName
    capacity: aiModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: aiModelName
      version: aiModelVersion
    }
  }
}

// Foundry Hub workspace
// https://learn.microsoft.com/azure/templates/microsoft.machinelearningservices/workspaces
resource foundryHub 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = if (enableFoundry) {
  name: foundryHubName
  location: location
  kind: 'Hub'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: 'APIM Costing Foundry Hub'
    description: 'Foundry Hub for the APIM costing sample'
    keyVault: foundryKeyVault.id
    storageAccount: foundryStorage.id
    applicationInsights: appInsightsResourceId
  }
}

// Azure OpenAI connection in the Foundry Hub
// https://learn.microsoft.com/azure/templates/microsoft.machinelearningservices/workspaces/connections
resource aoaiConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-10-01' = if (enableFoundry) {
  name: 'aoai-connection'
  parent: foundryHub
  properties: {
    authType: 'AAD'
    category: 'AzureOpenAI'
    target: aiServices!.properties.endpoint
    metadata: {
      ApiType: 'Azure'
      ResourceId: aiServices.id
    }
  }
}

// Foundry Project workspace
// https://learn.microsoft.com/azure/templates/microsoft.machinelearningservices/workspaces
resource foundryProject 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = if (enableFoundry) {
  name: foundryProjectName
  location: location
  kind: 'Project'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: 'APIM Costing Project'
    description: 'Foundry Project for the APIM costing sample'
    hubResourceId: foundryHub.id
  }
}

// Role: APIM system-assigned identity -> Cognitive Services OpenAI User on AI Services
// This allows APIM to call Azure OpenAI endpoints using managed identity authentication.
// https://learn.microsoft.com/azure/templates/microsoft.authorization/roleassignments
resource apimAoaiRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableFoundry) {
  name: guid(aiServices.id, apimService.id, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: aiServices
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User
    )
    principalId: apimService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// APIM Backend for Azure OpenAI with managed identity credentials
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/backends
resource aoaiBackend 'Microsoft.ApiManagement/service/backends@2024-06-01-preview' = if (enableFoundry) {
  name: 'aoai-backend'
  parent: apimService
  properties: {
    description: 'Azure OpenAI backend via Foundry AI Services'
    url: '${aiServices!.properties.endpoint}openai'
    protocol: 'http'
  }
  dependsOn: [
    apimAoaiRoleAssignment
  ]
}


// Variables for output values
var workbookDisplayName = workbookName
var workbookIdOutput = enableLogAnalytics ? workbook.id : ''

// ------------------
//    OUTPUTS
// ------------------

output apimServiceId string = apimService.id
output apimServiceName string = apimService.name
output apimResourceGatewayURL string = apimService.properties.gatewayUrl

@description('Name of the Application Insights resource')
#disable-next-line BCP318
output applicationInsightsName string = enableApplicationInsights ? applicationInsightsModule.outputs.applicationInsightsName : ''

@description('Application Insights instrumentation key')
output applicationInsightsInstrumentationKey string = appInsightsInstrKey

@description('Application Insights connection string')
output applicationInsightsConnectionString string = appInsightsConnectionStr

@description('Name of the Log Analytics Workspace')
output logAnalyticsWorkspaceName string = enableLogAnalytics ? logAnalyticsWorkspaceName : ''

@description('Log Analytics Workspace ID')
#disable-next-line BCP318
output logAnalyticsWorkspaceId string = enableLogAnalytics ? logAnalyticsModule.outputs.id : ''

@description('Name of the Storage Account for cost exports')
output storageAccountName string = storageAccount.name

@description('Storage Account ID')
output storageAccountId string = storageAccount.id

@description('Cost exports container name')
output costExportsContainerName string = 'cost-exports'

@description('Name of the Azure Monitor Workbook')
output workbookName string = workbookDisplayName

@description('Workbook ID')
output workbookId string = workbookIdOutput

@description('Name of the Cost Management export')
output costExportName string = costExportOutputName

@description('Subscription keys for the business units')
output subscriptionKeys array = [for (bu, i) in businessUnits: {
  name: bu.name
  #disable-next-line outputs-should-not-contain-secrets // Intentional: notebook needs keys for traffic generation
  primaryKey: listSecrets(subscriptions[i].id, '2024-06-01-preview').primaryKey
}]

@description('Per-API subscription metadata (subscription keys are not exposed; retrieve keys via APIM RBAC-controlled mechanisms)')
output apiSubscriptionKeys array = [for (api, i) in apis: {
  name: api.name
}]

@description('Azure OpenAI endpoint URL (empty when enableFoundry is false)')
#disable-next-line BCP318
output aoaiEndpoint string = enableFoundry ? aiServices.properties.endpoint : ''

@description('Azure AI Services resource name (empty when enableFoundry is false)')
output aoaiName string = enableFoundry ? aiServicesName : ''

@description('Deployed model name (empty when enableFoundry is false)')
output modelDeploymentName string = enableFoundry ? aiModelName : ''

@description('Foundry Hub name (empty when enableFoundry is false)')
output foundryHubName string = enableFoundry ? foundryHubName : ''

@description('Foundry Project name (empty when enableFoundry is false)')
output foundryProjectName string = enableFoundry ? foundryProjectName : ''
