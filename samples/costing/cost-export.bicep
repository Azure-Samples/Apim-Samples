// ------------------------------
//    COST MANAGEMENT EXPORT MODULE
// ------------------------------
// This module deploys a Cost Management export at subscription scope.
// It must be called from a resource-group-scoped template using:
//   scope: subscription()

targetScope = 'subscription'


// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Name of the cost export')
param costExportName string

@description('Resource ID of the storage account for export delivery')
param storageAccountId string

@description('Container name for cost export data')
param containerName string = 'cost-exports'

@description('Root folder path within the container')
param rootFolderPath string = 'apim-costing'

@description('Export recurrence frequency')
@allowed([
  'Daily'
  'Weekly'
  'Monthly'
])
param recurrence string = 'Daily'

@description('Start date for the export schedule (UTC)')
param startDate string


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.costmanagement/exports
resource costExport 'Microsoft.CostManagement/exports@2023-11-01' = {
  name: costExportName
  properties: {
    definition: {
      type: 'ActualCost'
      timeframe: 'MonthToDate'
      dataSet: {
        granularity: 'Daily'
      }
    }
    deliveryInfo: {
      destination: {
        resourceId: storageAccountId
        container: containerName
        rootFolderPath: rootFolderPath
      }
    }
    format: 'Csv'
    schedule: {
      status: 'Active'
      recurrence: recurrence
      recurrencePeriod: {
        from: startDate
        to: '2099-12-31T00:00:00Z'
      }
    }
  }
}


// ------------------------------
//    OUTPUTS
// ------------------------------

@description('Name of the deployed cost export')
output costExportName string = costExport.name
