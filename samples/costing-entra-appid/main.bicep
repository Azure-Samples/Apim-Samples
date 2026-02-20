// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Name of the existing API Management service.')
param apimServiceName string

@description('Sample deployment index for unique resource naming.')
param sampleIndex int = 1

@description('Log Analytics data retention in days.')
param logRetentionDays int = 30

@description('Deploy the cost attribution workbook. Defaults to true.')
param deployWorkbook bool = true


// ------------------
//    VARIABLES
// ------------------

var applicationInsightsName = 'appi-appid-costing-${sampleIndex}-${resourceSuffix}'
var logAnalyticsWorkspaceName = 'log-appid-costing-${sampleIndex}-${resourceSuffix}'
var diagnosticSettingsName = 'appid-costing-diagnostics-${sampleIndex}'
var workbookDisplayName = 'APIM Cost Attribution by Caller ID'


// ------------------
//    RESOURCES
// ------------------

// https://learn.microsoft.com/azure/templates/microsoft.operationalinsights/workspaces
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: logRetentionDays
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.insights/components
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
    IngestionMode: 'LogAnalytics'
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: apimServiceName
}

// Route APIM gateway logs to Log Analytics (resource-specific mode)
// https://learn.microsoft.com/azure/templates/microsoft.insights/diagnosticsettings
resource apimDiagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: diagnosticSettingsName
  scope: apimService
  properties: {
    workspaceId: logAnalyticsWorkspace.id
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// Configure APIM logger for Application Insights
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/loggers
resource apimLogger 'Microsoft.ApiManagement/service/loggers@2023-09-01-preview' = {
  parent: apimService
  name: applicationInsightsName
  properties: {
    loggerType: 'applicationInsights'
    credentials: {
      instrumentationKey: applicationInsights.properties.InstrumentationKey
    }
    resourceId: applicationInsights.id
  }
}

// Configure APIM diagnostic for Application Insights
// Enables 100% sampling and metrics to support emit-metric policy
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/diagnostics
resource apimDiagnostic 'Microsoft.ApiManagement/service/diagnostics@2023-09-01-preview' = {
  name: 'applicationinsights'
  parent: apimService
  properties: {
    loggerId: apimLogger.id
    alwaysLog: 'allErrors'
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    metrics: true
    frontend: {
      request: {
        headers: []
        body: { bytes: 0 }
      }
      response: {
        headers: []
        body: { bytes: 0 }
      }
    }
    backend: {
      request: {
        headers: []
        body: { bytes: 0 }
      }
      response: {
        headers: []
        body: { bytes: 0 }
      }
    }
    logClientIp: true
    httpCorrelationProtocol: 'W3C'
    verbosity: 'information'
    operationNameFormat: 'Name'
  }
}


// Azure Workbook: Cost Attribution Dashboard
// https://learn.microsoft.com/azure/templates/microsoft.insights/workbooks
resource costWorkbook 'Microsoft.Insights/workbooks@2023-06-01' = if (deployWorkbook) {
  name: guid(resourceGroup().id, 'appid-costing-workbook-${sampleIndex}')
  location: location
  kind: 'shared'
  properties: {
    displayName: workbookDisplayName
    serializedData: workbookSerializedData
    sourceId: applicationInsights.id
    category: 'tsg'
  }
}

var workbookSerializedData = string({
  version: 'Notebook/1.0'
  items: [
    // ── Title & Description ──
    {
      type: 1
      content: {
        json: '# APIM Cost Attribution by Caller ID\n\nThis workbook shows API usage and cost allocation by Entra ID application (`appid` claim). Data comes from the `emit-metric` policy\'s `caller-requests` custom metric.\n\n> **Note:** Data typically takes 5-10 minutes to appear after API calls.'
      }
      name: 'title'
      styleSettings: {
        margin: '0 0 16px 0'
      }
    }
    // ── Global Parameters ──
    {
      type: 9
      content: {
        version: 'KqlParameterItem/1.0'
        parameters: [
          {
            id: guid(resourceGroup().id, 'timerange-param')
            version: 'KqlParameterItem/1.0'
            name: 'TimeRange'
            label: 'Time Range'
            type: 4
            description: 'Select the time window for all charts and tables below.'
            isRequired: true
            typeSettings: {
              selectableValues: [
                { durationMs: 3600000 }
                { durationMs: 14400000 }
                { durationMs: 43200000 }
                { durationMs: 86400000 }
                { durationMs: 172800000 }
                { durationMs: 604800000 }
                { durationMs: 2592000000 }
              ]
              allowCustom: true
            }
            value: {
              durationMs: 86400000
            }
          }
          {
            id: guid(resourceGroup().id, 'basecost-param')
            version: 'KqlParameterItem/1.0'
            name: 'BaseCost'
            label: 'Monthly Base Cost (USD)'
            type: 1
            description: 'The total monthly APIM base cost used to calculate proportional cost shares.'
            isRequired: true
            value: '150.00'
          }
          {
            id: guid(resourceGroup().id, 'appidnames-param')
            version: 'KqlParameterItem/1.0'
            name: 'AppIdNames'
            label: 'App ID Names (JSON)'
            type: 1
            description: 'Optional JSON mapping of App IDs to friendly names. Example: {"a5846c0e-...":"HR Service","9e6bfb3f-...":"Mobile Gateway"}'
            isRequired: false
            value: '{}'
          }
        ]
        style: 'pills'
      }
      name: 'parameters'
      styleSettings: {
        margin: '0 0 8px 0'
      }
    }

    // ══════════════════════════════════════════════════════════════════
    //  Section 1: Usage by Caller ID (collapsible group)
    // ══════════════════════════════════════════════════════════════════
    {
      type: 12
      content: {
        version: 'NotebookGroup/1.0'
        groupType: 0
        title: 'Usage by Caller ID'
        expandable: true
        expanded: true
        items: [
          {
            type: 1
            content: {
              json: 'Total API request counts grouped by the caller identifier extracted from JWT `appid`/`azp` claims or APIM subscription ID.'
            }
            name: 'usage-description'
            styleSettings: {
              margin: '0 0 8px 0'
            }
          }
          {
            type: 3
            content: {
              version: 'KqlItem/1.0'
              query: 'let appNames = parse_json(\'{AppIdNames}\');\ncustomMetrics\n| where name == "caller-requests"\n| extend CallerId = tostring(customDimensions.CallerId)\n| where isnotempty(CallerId)\n| summarize RequestCount = sum(value) by CallerId\n| extend Caller = iif(isnotempty(tostring(appNames[CallerId])), strcat(tostring(appNames[CallerId]), " (", CallerId, ")"), CallerId)\n| project Caller, RequestCount\n| order by RequestCount desc'
              size: 1
              title: 'Total Requests by Caller ID'
              noDataMessage: 'No caller-requests metrics found in the selected time range.'
              timeContext: {
                durationMs: 0
              }
              timeContextFromParameter: 'TimeRange'
              queryType: 0
              resourceType: 'microsoft.insights/components'
              visualization: 'barchart'
              chartSettings: {
                xAxis: 'Caller'
                yAxis: ['RequestCount']
                seriesLabelSettings: [
                  {
                    seriesName: 'RequestCount'
                    label: 'Request Count'
                  }
                ]
              }
            }
            customWidth: '60'
            name: 'usage-chart'
            styleSettings: {
              maxWidth: '60%'
              showBorder: true
            }
          }
          {
            type: 3
            content: {
              version: 'KqlItem/1.0'
              query: 'let appNames = parse_json(\'{AppIdNames}\');\ncustomMetrics\n| where name == "caller-requests"\n| extend CallerId = tostring(customDimensions.CallerId)\n| where isnotempty(CallerId)\n| summarize RequestCount = sum(value) by CallerId\n| extend Caller = iif(isnotempty(tostring(appNames[CallerId])), strcat(tostring(appNames[CallerId]), " (", CallerId, ")"), CallerId)\n| project Caller, RequestCount\n| order by RequestCount desc'
              size: 0
              title: 'Usage Summary'
              noDataMessage: 'No caller-requests metrics found in the selected time range.'
              timeContext: {
                durationMs: 0
              }
              timeContextFromParameter: 'TimeRange'
              queryType: 0
              resourceType: 'microsoft.insights/components'
              visualization: 'table'
              gridSettings: {
                formatters: [
                  {
                    columnMatch: 'Caller'
                    formatter: 0
                    formatOptions: {
                      customColumnWidthSetting: '60%'
                    }
                  }
                  {
                    columnMatch: 'RequestCount'
                    formatter: 1
                    numberFormat: {
                      unit: 17
                      options: {
                        style: 'decimal'
                        useGrouping: true
                      }
                    }
                  }
                ]
                sortBy: [
                  {
                    itemKey: 'RequestCount'
                    sortOrder: 2
                  }
                ]
                labelSettings: [
                  {
                    columnId: 'Caller'
                    label: 'Caller'
                  }
                  {
                    columnId: 'RequestCount'
                    label: 'Requests'
                  }
                ]
              }
            }
            customWidth: '40'
            name: 'usage-table'
            styleSettings: {
              maxWidth: '40%'
              showBorder: true
            }
          }
        ]
      }
      name: 'usage-group'
      styleSettings: {
        margin: '8px 0'
        showBorder: true
      }
    }

    // ══════════════════════════════════════════════════════════════════
    //  Section 2: Cost Allocation (collapsible group)
    // ══════════════════════════════════════════════════════════════════
    {
      type: 12
      content: {
        version: 'NotebookGroup/1.0'
        groupType: 0
        title: 'Cost Allocation'
        expandable: true
        expanded: true
        items: [
          {
            type: 1
            content: {
              json: 'Proportional cost breakdown based on the **Monthly Base Cost** parameter above. Each caller\'s share is calculated as their percentage of total requests applied to the base cost.'
            }
            name: 'cost-description'
            styleSettings: {
              margin: '0 0 8px 0'
            }
          }
          {
            type: 3
            content: {
              version: 'KqlItem/1.0'
              query: 'let appNames = parse_json(\'{AppIdNames}\');\nlet baseCost = {BaseCost};\nlet metrics = customMetrics\n| where name == "caller-requests"\n| extend CallerId = tostring(customDimensions.CallerId)\n| where isnotempty(CallerId);\nlet totalRequests = toscalar(metrics | summarize sum(value));\nmetrics\n| summarize RequestCount = sum(value) by CallerId\n| extend Caller = iif(isnotempty(tostring(appNames[CallerId])), strcat(tostring(appNames[CallerId]), " (", CallerId, ")"), CallerId)\n| extend UsagePercent = round(RequestCount * 100.0 / totalRequests, 2)\n| extend AllocatedCost = round(baseCost * RequestCount / totalRequests, 2)\n| project Caller, RequestCount, UsagePercent, AllocatedCost\n| order by AllocatedCost desc'
              size: 0
              title: 'Cost Allocation by Caller ID'
              noDataMessage: 'No caller-requests metrics found in the selected time range.'
              timeContext: {
                durationMs: 0
              }
              timeContextFromParameter: 'TimeRange'
              queryType: 0
              resourceType: 'microsoft.insights/components'
              visualization: 'table'
              gridSettings: {
                formatters: [
                  {
                    columnMatch: 'Caller'
                    formatter: 0
                    formatOptions: {
                      customColumnWidthSetting: '40%'
                    }
                  }
                  {
                    columnMatch: 'RequestCount'
                    formatter: 1
                    numberFormat: {
                      unit: 17
                      options: {
                        style: 'decimal'
                        useGrouping: true
                      }
                    }
                  }
                  {
                    columnMatch: 'UsagePercent'
                    formatter: 4
                    formatOptions: {
                      min: 0
                      max: 100
                      palette: 'blue'
                    }
                    numberFormat: {
                      unit: 1
                      options: {
                        style: 'decimal'
                        minimumFractionDigits: 1
                        maximumFractionDigits: 1
                      }
                    }
                  }
                  {
                    columnMatch: 'AllocatedCost'
                    formatter: 1
                    numberFormat: {
                      unit: 0
                      options: {
                        style: 'currency'
                        currency: 'USD'
                        minimumFractionDigits: 2
                        maximumFractionDigits: 2
                      }
                    }
                  }
                ]
                sortBy: [
                  {
                    itemKey: 'AllocatedCost'
                    sortOrder: 2
                  }
                ]
                labelSettings: [
                  {
                    columnId: 'Caller'
                    label: 'Caller'
                  }
                  {
                    columnId: 'RequestCount'
                    label: 'Requests'
                  }
                  {
                    columnId: 'UsagePercent'
                    label: 'Usage %'
                  }
                  {
                    columnId: 'AllocatedCost'
                    label: 'Allocated Cost'
                  }
                ]
              }
            }
            customWidth: '60'
            name: 'cost-table'
            styleSettings: {
              maxWidth: '60%'
              showBorder: true
            }
          }
          {
            type: 3
            content: {
              version: 'KqlItem/1.0'
              query: 'let appNames = parse_json(\'{AppIdNames}\');\nlet baseCost = {BaseCost};\nlet metrics = customMetrics\n| where name == "caller-requests"\n| extend CallerId = tostring(customDimensions.CallerId)\n| where isnotempty(CallerId);\nlet totalRequests = toscalar(metrics | summarize sum(value));\nmetrics\n| summarize RequestCount = sum(value) by CallerId\n| extend Caller = iif(isnotempty(tostring(appNames[CallerId])), strcat(tostring(appNames[CallerId]), " (", CallerId, ")"), CallerId)\n| extend AllocatedCost = round(baseCost * RequestCount / totalRequests, 2)\n| project Caller, AllocatedCost\n| order by AllocatedCost desc'
              size: 1
              title: 'Cost Distribution'
              noDataMessage: 'No caller-requests metrics found in the selected time range.'
              timeContext: {
                durationMs: 0
              }
              timeContextFromParameter: 'TimeRange'
              queryType: 0
              resourceType: 'microsoft.insights/components'
              visualization: 'piechart'
              chartSettings: {
                seriesLabelSettings: [
                  {
                    seriesName: '*'
                    label: 'Allocated Cost'
                  }
                ]
              }
            }
            customWidth: '40'
            name: 'cost-pie'
            styleSettings: {
              maxWidth: '40%'
              showBorder: true
            }
          }
        ]
      }
      name: 'cost-group'
      styleSettings: {
        margin: '8px 0'
        showBorder: true
      }
    }

    // ══════════════════════════════════════════════════════════════════
    //  Section 3: Request Trend (collapsible group)
    // ══════════════════════════════════════════════════════════════════
    {
      type: 12
      content: {
        version: 'NotebookGroup/1.0'
        groupType: 0
        title: 'Request Trend'
        expandable: true
        expanded: true
        items: [
          {
            type: 1
            content: {
              json: 'Hourly request volume by caller over time. Use this to spot traffic spikes, identify peak usage periods, and detect anomalies by caller.'
            }
            name: 'trend-description'
            styleSettings: {
              margin: '0 0 8px 0'
            }
          }
          {
            type: 3
            content: {
              version: 'KqlItem/1.0'
              query: 'let appNames = parse_json(\'{AppIdNames}\');\ncustomMetrics\n| where name == "caller-requests"\n| extend CallerId = tostring(customDimensions.CallerId)\n| where isnotempty(CallerId)\n| extend Caller = iif(isnotempty(tostring(appNames[CallerId])), strcat(tostring(appNames[CallerId]), " (", CallerId, ")"), CallerId)\n| summarize Requests = sum(value) by Caller, bin(timestamp, 1h)\n| order by timestamp asc'
              size: 0
              title: 'Hourly Request Trend by Caller ID'
              noDataMessage: 'No caller-requests metrics found in the selected time range.'
              timeContext: {
                durationMs: 0
              }
              timeContextFromParameter: 'TimeRange'
              queryType: 0
              resourceType: 'microsoft.insights/components'
              visualization: 'timechart'
            }
            name: 'trend-chart'
            styleSettings: {
              showBorder: true
            }
          }
        ]
      }
      name: 'trend-group'
      styleSettings: {
        margin: '8px 0'
        showBorder: true
      }
    }
  ]
  isLocked: false
  fallbackResourceIds: [
    applicationInsights.id
  ]
})


// ------------------
//    OUTPUTS
// ------------------

@description('Name of the Application Insights resource')
output applicationInsightsName string = applicationInsights.name

@description('Application Insights connection string')
output applicationInsightsConnectionString string = applicationInsights.properties.ConnectionString

@description('Name of the Log Analytics Workspace')
output logAnalyticsWorkspaceName string = logAnalyticsWorkspace.name

@description('Log Analytics Workspace ID (for queries)')
output logAnalyticsWorkspaceId string = logAnalyticsWorkspace.properties.customerId

@description('Workbook resource name (if deployed)')
output workbookName string = deployWorkbook ? costWorkbook.name : ''
