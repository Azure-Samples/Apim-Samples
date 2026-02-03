/**
 * @module network-watcher-v1
 * @description This module defines the Azure Network Watcher resource using Bicep.
 * Network Watcher is required for NSG flow logs and other network monitoring features.
 */


// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for Network Watcher. Defaults to the resource group location')
param location string = resourceGroup().location

@description('Name of the Network Watcher resource. Defaults to "NetworkWatcher_<location>".')
param networkWatcherName string = 'NetworkWatcher_${location}'


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.network/networkwatchers
resource networkWatcher 'Microsoft.Network/networkWatchers@2023-11-01' = {
  name: networkWatcherName
  location: location
  properties: {}
}


// ------------------------------
//    OUTPUTS
// ------------------------------

output id string = networkWatcher.id
output name string = networkWatcher.name
output location string = networkWatcher.location
