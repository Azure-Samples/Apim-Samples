/**
 * @module workspaces-v1
 * @description This module defines the Azure Log Analytics Workspaces (LAW) resources using Bicep.
 */


// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Name of the Log Analytics resource. Defaults to "log-<resourceSuffix>".')
param logAnalyticsName string = 'log-${resourceSuffix}'


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.operationalinsights/workspaces
#disable-next-line BCP081
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: logAnalyticsName
  location: location
  properties: any({
    retentionInDays: 30
    features: {
      searchVersion: 1
    }
    sku: {
      name: 'PerGB2018'
    }
  })
}


// ------------------------------
//    OUTPUTS
// ------------------------------

output id string = logAnalytics.id
output customerId string = logAnalytics.properties.customerId

@secure()
output clientSecret string = logAnalytics.listKeys().primarySharedKey
