// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Name of the existing API Management service')
param apimServiceName string

@description('Sample deployment index for unique resource naming')
param sampleIndex int = 1

@description('Enable Application Insights for APIM diagnostics')
param enableApplicationInsights bool = true

@description('Enable Log Analytics for APIM diagnostics')
param enableLogAnalytics bool = true

@description('Log Analytics data retention in days')
param logRetentionDays int = 30

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


// ------------------------------
//    VARIABLES
// ------------------------------

var applicationInsightsName = 'appi-costing-${sampleIndex}-${resourceSuffix}'
var logAnalyticsWorkspaceName = 'log-costing-${sampleIndex}-${resourceSuffix}'
var storageAccountName = 'stcost${sampleIndex}${take(replace(resourceSuffix, '-', ''), 16)}'
var diagnosticSettingsName = 'costing-diagnostics-${sampleIndex}'
var workbookName = 'APIM Cost Analysis by Business Unit ${sampleIndex}'
var costExportName = 'apim-cost-export-${sampleIndex}-${resourceGroup().name}'


// ------------------------------
//    RESOURCES
// ------------------------------


// https://learn.microsoft.com/azure/templates/microsoft.operationalinsights/workspaces
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (enableLogAnalytics) {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: logRetentionDays
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}


// https://learn.microsoft.com/azure/templates/microsoft.insights/components
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = if (enableApplicationInsights) {
  name: applicationInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: enableLogAnalytics ? logAnalyticsWorkspace.id : null
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
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


// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: apimServiceName
}


// https://learn.microsoft.com/azure/templates/microsoft.insights/diagnosticsettings
resource apimDiagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: diagnosticSettingsName
  scope: apimService
  properties: {
    workspaceId: enableLogAnalytics ? logAnalyticsWorkspace.id : null
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      {
        category: 'GatewayLogs'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'WebSocketConnectionLogs'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}


// Configure APIM logger for Application Insights
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/loggers
resource apimLogger 'Microsoft.ApiManagement/service/loggers@2023-09-01-preview' = if (enableApplicationInsights) {
  name: 'applicationinsights-logger'
  parent: apimService
  properties: {
    loggerType: 'applicationInsights'
    description: 'Application Insights logger for cost tracking'
    credentials: {
      instrumentationKey: enableApplicationInsights ? applicationInsights.properties.InstrumentationKey : ''
    }
    isBuffered: true
    resourceId: enableApplicationInsights ? applicationInsights.id : ''
  }
}


// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/diagnostics
resource apimDiagnostic 'Microsoft.ApiManagement/service/diagnostics@2023-09-01-preview' = if (enableApplicationInsights) {
  name: 'applicationinsights'
  parent: apimService
  properties: {
    alwaysLog: 'allErrors'
    loggerId: enableApplicationInsights ? apimLogger.id : ''
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    frontend: {
      request: {
        headers: []
        body: {
          bytes: 0
        }
      }
      response: {
        headers: []
        body: {
          bytes: 0
        }
      }
    }
    backend: {
      request: {
        headers: []
        body: {
          bytes: 0
        }
      }
      response: {
        headers: []
        body: {
          bytes: 0
        }
      }
    }
    logClientIp: true
    httpCorrelationProtocol: 'W3C'
    verbosity: 'information'
  }
}


// Configure APIM diagnostic for Azure Monitor (Log Analytics)
// This ensures gateway logs include subscription IDs and other details
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/diagnostics
resource apimAzureMonitorDiagnostic 'Microsoft.ApiManagement/service/diagnostics@2023-09-01-preview' = if (enableLogAnalytics) {
  name: 'azuremonitor'
  parent: apimService
  properties: {
    loggerId: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.ApiManagement/service/${apimServiceName}/loggers/azuremonitor'
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    logClientIp: true
    verbosity: 'information'
  }
}


// https://learn.microsoft.com/azure/templates/microsoft.insights/workbooks
resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = if (enableLogAnalytics) {
  name: guid(resourceGroup().id, 'apim-costing-workbook', string(sampleIndex))
  location: location
  kind: 'shared'
  properties: {
    displayName: workbookName
    serializedData: string(loadJsonContent('workbook.json'))
    version: '1.0'
    sourceId: logAnalyticsWorkspace.id
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


// ------------------------------
//    OUTPUTS
// ------------------------------

@description('Name of the Application Insights resource')
output applicationInsightsName string = enableApplicationInsights ? applicationInsights.name : ''

@description('Application Insights instrumentation key')
output applicationInsightsInstrumentationKey string = enableApplicationInsights ? applicationInsights.properties.InstrumentationKey : ''

@description('Application Insights connection string')
output applicationInsightsConnectionString string = enableApplicationInsights ? applicationInsights.properties.ConnectionString : ''

@description('Name of the Log Analytics Workspace')
output logAnalyticsWorkspaceName string = enableLogAnalytics ? logAnalyticsWorkspace.name : ''

@description('Log Analytics Workspace ID')
output logAnalyticsWorkspaceId string = enableLogAnalytics ? logAnalyticsWorkspace.id : ''

@description('Name of the Storage Account for cost exports')
output storageAccountName string = storageAccount.name

@description('Storage Account ID')
output storageAccountId string = storageAccount.id

@description('Cost exports container name')
output costExportsContainerName string = 'cost-exports'

@description('Name of the Azure Monitor Workbook')
output workbookName string = enableLogAnalytics ? workbook.properties.displayName : ''

@description('Workbook ID')
output workbookId string = enableLogAnalytics ? workbook.id : ''

@description('Name of the Cost Management export')
output costExportName string = enableCostExport ? costExportModule.outputs.costExportName : costExportName
