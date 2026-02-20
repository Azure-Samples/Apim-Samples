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

@description('Array of APIs to deploy')
param apis array = []

@description('Deploy the cost attribution workbook. Defaults to true.')
param deployWorkbook bool = true


// ------------------
//    VARIABLES
// ------------------

var applicationInsightsName = 'appi-appid-cost-${index}-${take(resourceSuffix, 4)}'
var logAnalyticsWorkspaceName = 'log-appid-cost-${index}-${take(resourceSuffix, 4)}'
var workbookName = 'APIM Cost Attribution by Caller ID ${index}'
var diagnosticSettingsNameSuffix = 'appid-costing-diagnostics-${index}'


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

// Helper variables to safely access properties from conditionally deployed resources
#disable-next-line BCP318
var appInsightsInstrKey = enableApplicationInsights ? applicationInsightsModule.outputs.instrumentationKey : ''

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
resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = if (deployWorkbook && enableApplicationInsights) {
  name: guid(resourceGroup().id, 'appid-costing-workbook', string(index))
  location: location
  kind: 'shared'
  properties: {
    displayName: workbookName
    serializedData: string(loadJsonContent('workbook.json'))
    version: '1.0'
    #disable-next-line BCP318
    sourceId: enableApplicationInsights ? applicationInsightsModule.outputs.id : ''
    category: 'APIM'
  }
}


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
output applicationInsightsConnectionString string = enableApplicationInsights ? 'InstrumentationKey=${appInsightsInstrKey}' : ''

@description('Name of the Log Analytics Workspace')
output logAnalyticsWorkspaceName string = enableLogAnalytics ? logAnalyticsWorkspaceName : ''

@description('Log Analytics Workspace ID')
#disable-next-line BCP318
output logAnalyticsWorkspaceId string = enableLogAnalytics ? logAnalyticsModule.outputs.id : ''

@description('Name of the Azure Monitor Workbook')
output workbookName string = workbookName

@description('Workbook ID')
output workbookId string = deployWorkbook && enableApplicationInsights ? workbook.id : ''

// API outputs
output apiOutputs array = [for i in range(0, length(apis)): {
  name: apis[i].name
  resourceId: apisModule[i].?outputs.?apiResourceId ?? ''
  displayName: apisModule[i].?outputs.?apiDisplayName ?? ''
  productAssociationCount: apisModule[i].?outputs.?productAssociationCount ?? 0
  subscriptionResourceId: apisModule[i].?outputs.?subscriptionResourceId ?? ''
  subscriptionName: apisModule[i].?outputs.?subscriptionName ?? ''
  subscriptionPrimaryKey: apisModule[i].?outputs.?subscriptionPrimaryKey ?? ''
  subscriptionSecondaryKey: apisModule[i].?outputs.?subscriptionSecondaryKey ?? ''
}]
