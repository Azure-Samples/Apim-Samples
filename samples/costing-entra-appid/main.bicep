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

@description('Array of APIs to deploy')
param apis array = []

@description('Deploy the cost attribution workbook. Defaults to true.')
param deployWorkbook bool = true


// ------------------
//    VARIABLES
// ------------------

var workbookName = 'APIM Cost Attribution by Caller ID ${index}'


// ------------------
//    RESOURCES
// ------------------

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// Reference the infrastructure's Application Insights and Log Analytics.
// The emit-metric policy sends custom metrics to the App Insights
// connected to the APIM service (configured by the infrastructure's apim-logger).
// Deploying a separate App Insights would leave it empty.
// https://learn.microsoft.com/azure/templates/microsoft.insights/components
resource infraAppInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: 'appi-${resourceSuffix}'
}

// https://learn.microsoft.com/azure/templates/microsoft.operationalinsights/workspaces
resource infraLogAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: 'log-${resourceSuffix}'
}

// APIM APIs
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: if(!empty(apis)) {
  name: 'api-${api.name}'
  params: {
    apimName: apimName
    appInsightsInstrumentationKey: infraAppInsights.properties.InstrumentationKey
    appInsightsId: infraAppInsights.id
    api: api
  }
}]

// https://learn.microsoft.com/azure/templates/microsoft.insights/workbooks
resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = if (deployWorkbook) {
  name: guid(resourceGroup().id, 'appid-costing-workbook', string(index))
  location: location
  kind: 'shared'
  properties: {
    displayName: workbookName
    serializedData: string(loadJsonContent('workbook.json'))
    version: '1.0'
    sourceId: infraAppInsights.id
    category: 'APIM'
  }
}


// ------------------
//    OUTPUTS
// ------------------

output apimServiceId string = apimService.id
output apimServiceName string = apimService.name
output apimResourceGatewayURL string = apimService.properties.gatewayUrl

@description('Name of the Application Insights resource (from infrastructure)')
output applicationInsightsName string = infraAppInsights.name

@description('Application Insights instrumentation key')
output applicationInsightsInstrumentationKey string = infraAppInsights.properties.InstrumentationKey

@description('Application Insights connection string')
output applicationInsightsConnectionString string = infraAppInsights.properties.ConnectionString

@description('Name of the Log Analytics Workspace (from infrastructure)')
output logAnalyticsWorkspaceName string = infraLogAnalytics.name

@description('Log Analytics Workspace ID')
output logAnalyticsWorkspaceId string = infraLogAnalytics.id

@description('Name of the Azure Monitor Workbook')
output workbookName string = workbookName

@description('Workbook ID')
output workbookId string = deployWorkbook ? workbook.id : ''

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
