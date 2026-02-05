/**
 * @module nsg-flow-logs-v1
 * @description Enable NSG Flow Logs and Traffic Analytics for Network Security Groups
 */

// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location for resources')
param location string = resourceGroup().location

@description('Name of the NSG Flow Log')
param flowLogName string

@description('NSG Resource ID to enable flow logs on')
param nsgResourceId string

@description('Storage Account Resource ID for flow log storage')
param storageAccountResourceId string

@description('Log Analytics Workspace Resource ID for Traffic Analytics')
param logAnalyticsWorkspaceResourceId string

@description('Flow log retention in days (0 = indefinite)')
@minValue(0)
@maxValue(365)
param retentionDays int = 7

@description('Flow log version (1 or 2)')
@allowed([1, 2])
param flowLogVersion int = 2

@description('Enable Traffic Analytics')
param enableTrafficAnalytics bool = true

@description('Traffic Analytics interval in minutes')
@allowed([10, 60])
param trafficAnalyticsInterval int = 60

// ------------------------------
//    RESOURCES
// ------------------------------

// Network Watcher - using existing instance in the region
resource networkWatcher 'Microsoft.Network/networkWatchers@2025-01-01' existing = {
  name: 'NetworkWatcher_${location}'
}

// https://learn.microsoft.com/azure/templates/microsoft.network/networkwatchers/flowlogs
resource flowLog 'Microsoft.Network/networkWatchers/flowLogs@2025-01-01' = {
  name: flowLogName
  parent: networkWatcher
  location: location
  properties: {
    targetResourceId: nsgResourceId
    storageId: storageAccountResourceId
    enabled: true
    retentionPolicy: {
      days: retentionDays
      enabled: retentionDays > 0
    }
    format: {
      type: 'JSON'
      version: flowLogVersion
    }
    flowAnalyticsConfiguration: enableTrafficAnalytics ? {
      networkWatcherFlowAnalyticsConfiguration: {
        enabled: true
        workspaceResourceId: logAnalyticsWorkspaceResourceId
        trafficAnalyticsInterval: trafficAnalyticsInterval
      }
    } : null
  }
}

// ------------------------------
//    OUTPUTS
// ------------------------------

output flowLogId string = flowLog.id
output flowLogName string = flowLog.name
