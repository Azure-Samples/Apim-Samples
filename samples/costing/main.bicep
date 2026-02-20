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


// ------------------
//    VARIABLES
// ------------------

var applicationInsightsName = 'appi-cost-${index}-${take(resourceSuffix, 4)}'
var logAnalyticsWorkspaceName = 'log-cost-${index}-${take(resourceSuffix, 4)}'
var storageAccountName = 'stcost${take(string(index), 1)}${take(replace(resourceSuffix, '-', ''), 12)}'
var workbookName = 'APIM Cost Tracking ${index}'
var costExportName = 'apim-cost-export'
var diagnosticSettingsNameSuffix = 'costing-diagnostics-${index}'


// ------------------
//    RESOURCES
// ------------------

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// APIM APIs
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: if(!empty(apis)) {
  name: 'api-${api.name}'
  params: {
    apimName: apimName
    appInsightsInstrumentationKey: appInsightsInstrKey
    appInsightsId: appInsightsResourceId
    api: api
  }
}]

// Create subscriptions for different business units
resource subscriptions 'Microsoft.ApiManagement/service/subscriptions@2024-06-01-preview' = [for bu in businessUnits: {
  name: bu.name
  parent: apimService
  properties: {
    displayName: bu.displayName
    scope: '/apis/${apis[0].name}'
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
  }
}


// https://learn.microsoft.com/azure/templates/microsoft.insights/workbooks
resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = if (enableLogAnalytics) {
  name: guid(resourceGroup().id, 'apim-costing-workbook', string(index))
  location: location
  kind: 'shared'
  properties: {
    displayName: workbookName
    serializedData: string(loadJsonContent('workbook.json'))
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
  primaryKey: listSecrets(subscriptions[i].id, '2024-06-01-preview').primaryKey
}]
