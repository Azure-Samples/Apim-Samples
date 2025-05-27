/**
 * @module aca-dns-private-zone-v1
 * @description This module creates a regional Azure Container Apps private DNS zone (e.g., eastus2.azurecontainerapps.io), links it to a VNet, and creates a wildcard A record for the ACA environment's static IP.
 */

// ------------------------------
//    PARAMETERS
// ------------------------------

@description('The Azure region in which the Azure Container Apps environment resides (e.g., eastus2). Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique subdomain of the ACA environment (used for the wildcard A record).')
param acaEnvironmentRandomSubdomain string

@description('The static IPv4 address of the ACA environment.')
param acaEnvironmentStaticIp string

@description('The resource ID of the virtual network to link.')
param vnetId string

@description('The name of the virtual network link resource.')
param vnetLinkName string = 'link-aca'

@description('TTL for the A record.')
param ttl int = 300

// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.network/privateDnsZones
resource acaPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: '${location}.azurecontainerapps.io'
  location: 'global'
}

// https://learn.microsoft.com/azure/templates/microsoft.network/privateDnsZones/virtualNetworkLinks
resource acaPrivateDnsZoneVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: vnetLinkName
  location: 'global'
  parent: acaPrivateDnsZone
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.network/privateDnsZones/a
resource acaWildcardARecord 'Microsoft.Network/privateDnsZones/A@2024-06-01' = {
  name: '*.${acaEnvironmentRandomSubdomain}'
  parent: acaPrivateDnsZone
  properties: {
    ttl: ttl
    aRecords: [
      {
        ipv4Address: acaEnvironmentStaticIp
      }
    ]
  }
}

// ------------------------------
//    OUTPUTS
// ------------------------------

output privateDnsZoneId string = acaPrivateDnsZone.id
output privateDnsZoneName string = acaPrivateDnsZone.name
output wildcardARecordFqdn string = '*.${acaEnvironmentRandomSubdomain}.${acaPrivateDnsZone.name}'
