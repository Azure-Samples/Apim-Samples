/**
 * @module apim-diagnostics-v1
 * @description This module configures observability for an existing Azure API Management (APIM) service.
 * It sets up diagnostic settings, loggers, and diagnostic policies for both Log Analytics and Application Insights.
 */


// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('Name of the existing API Management service')
param apimServiceName string

@description('Resource group name where the APIM service is deployed')
param apimResourceGroupName string = resourceGroup().name

@description('Enable Log Analytics diagnostic settings for APIM')
param enableLogAnalytics bool = true

@description('Log Analytics Workspace ID for diagnostic settings')
param logAnalyticsWorkspaceId string = ''

@description('Enable Application Insights logger and diagnostic policy for APIM')
param enableApplicationInsights bool = true

@description('Application Insights instrumentation key')
param appInsightsInstrumentationKey string = ''

@description('Application Insights resource ID')
param appInsightsResourceId string = ''

@description('Name suffix for the diagnostic settings resource')
param diagnosticSettingsNameSuffix string = 'diagnostics'

@description('Name of the APIM logger resource')
param apimLoggerName string = 'applicationinsights-logger'

@description('Description of the APIM logger')
param apimLoggerDescription string = 'Application Insights logger for APIM diagnostics'


// ------------------
//    VARIABLES
// ------------------

var diagnosticSettingsName = 'apim-${diagnosticSettingsNameSuffix}'


// ------------------
//    RESOURCES
// ------------------

// Reference the existing APIM service
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimServiceName
}

// Configure diagnostic settings to send logs to Log Analytics Workspace
// https://learn.microsoft.com/azure/templates/microsoft.insights/diagnosticsettings
resource apimDiagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableLogAnalytics && !empty(logAnalyticsWorkspaceId)) {
  name: diagnosticSettingsName
  scope: apimService
  properties: {
    workspaceId: logAnalyticsWorkspaceId
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
#disable-next-line BCP318
resource apimLogger 'Microsoft.ApiManagement/service/loggers@2024-06-01-preview' = if (enableApplicationInsights && !empty(appInsightsInstrumentationKey) && !empty(appInsightsResourceId)) {
  name: '${apimServiceName}/${apimLoggerName}'
  properties: {
    loggerType: 'applicationInsights'
    description: apimLoggerDescription
    credentials: {
      instrumentationKey: appInsightsInstrumentationKey
    }
    isBuffered: true
    #disable-next-line BCP318
    resourceId: appInsightsResourceId
  }
}

// Configure diagnostic policy for Application Insights
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/diagnostics
#disable-next-line BCP318
resource apimDiagnostic 'Microsoft.ApiManagement/service/diagnostics@2024-06-01-preview' = if (enableApplicationInsights && !empty(appInsightsInstrumentationKey) && !empty(appInsightsResourceId)) {
  name: '${apimServiceName}/applicationinsights'
  properties: {
    alwaysLog: 'allErrors'
    loggerId: enableApplicationInsights && !empty(appInsightsInstrumentationKey) && !empty(appInsightsResourceId) ? apimLogger.id : ''
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

// Configure Azure Monitor diagnostic settings for APIM
// This ensures gateway logs include subscription IDs and other details
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/diagnostics
resource apimAzureMonitorDiagnostic 'Microsoft.ApiManagement/service/diagnostics@2024-06-01-preview' = if (enableLogAnalytics) {
  name: '${apimServiceName}/azuremonitor'
  properties: {
    loggerId: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${apimResourceGroupName}/providers/Microsoft.ApiManagement/service/${apimServiceName}/loggers/azuremonitor'
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    logClientIp: true
    verbosity: 'information'
  }
}


// ------------------
//    OUTPUTS
// ------------------

@description('APIM diagnostic settings resource ID')
output diagnosticSettingsId string = enableLogAnalytics && !empty(logAnalyticsWorkspaceId) ? apimDiagnosticSettings.id : ''

@description('APIM logger resource ID')
output apimLoggerId string = enableApplicationInsights && !empty(appInsightsInstrumentationKey) && !empty(appInsightsResourceId) ? apimLogger.id : ''

@description('APIM Application Insights diagnostic resource ID')
output apimDiagnosticId string = enableApplicationInsights && !empty(appInsightsInstrumentationKey) && !empty(appInsightsResourceId) ? apimDiagnostic.id : ''

@description('APIM Azure Monitor diagnostic resource ID')
output apimAzureMonitorDiagnosticId string = enableLogAnalytics ? apimAzureMonitorDiagnostic.id : ''
