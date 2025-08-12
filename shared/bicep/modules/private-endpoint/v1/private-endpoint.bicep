/**
 * @module private-endpoint-v1
 * @description Private Endpoint with Private DNS Zone and VNet link. Designed for APIM (groupIds like 'gateway'), but generic enough for other services.
 */


// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Name of the Private Endpoint resource')
param privateEndpointName string = 'pe-${resourceSuffix}'

@description('Subnet resource ID to place the Private Endpoint in')
param subnetResourceId string

@description('The resource ID of the target resource to connect via Private Link (e.g., APIM service id)')
param targetResourceId string

@description('Group IDs for the private link service connection (e.g., ["Gateway"])')
param groupIds array = [ 'Gateway' ]

@description('Private DNS zone name to create and link (e.g., privatelink.azure-api.net)')
param privateDnsZoneName string

@description('Virtual network resource ID to link the Private DNS zone to')
param vnetId string

@description('Virtual network link resource name')
param vnetLinkName string = 'link-${resourceSuffix}'

@description('DNS Zone Group name to attach to the Private Endpoint')
param dnsZoneGroupName string = 'dnsZoneGroup-${resourceSuffix}'

@description('DNS Zone Config name inside the DNS Zone Group')
param dnsZoneConfigName string = 'config-${resourceSuffix}'


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.network/privateDnsZones
resource privateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: privateDnsZoneName
  location: 'global'
}

// https://learn.microsoft.com/azure/templates/microsoft.network/privateDnsZones/virtualNetworkLinks
resource privateDnsZoneVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: vnetLinkName
  location: 'global'
  parent: privateDnsZone
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.network/privateendpoints
resource privateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: privateEndpointName
  location: location
  properties: {
    subnet: {
      id: subnetResourceId
    }
    privateLinkServiceConnections: [
      {
        name: '${privateEndpointName}-pls'
        properties: {
          privateLinkServiceId: targetResourceId
          groupIds: groupIds
        }
      }
    ]
    customNetworkInterfaceName: 'nic-${privateEndpointName}'
  }
}

// Attach Private DNS Zone Group to the Private Endpoint
// https://learn.microsoft.com/azure/templates/microsoft.network/privateendpoints/privatednszonegroups
resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  name: dnsZoneGroupName
  parent: privateEndpoint
  properties: {
    privateDnsZoneConfigs: [
      {
        name: dnsZoneConfigName
        properties: {
          privateDnsZoneId: privateDnsZone.id
        }
      }
    ]
  }
}


// ------------------------------
//    OUTPUTS
// ------------------------------

output privateEndpointId string = privateEndpoint.id
output privateDnsZoneId string = privateDnsZone.id
