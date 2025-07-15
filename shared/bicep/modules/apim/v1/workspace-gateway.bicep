/**
 * @module api-v1
 * @description This module defines the API resources using Bicep.
 * It includes configurations for creating and managing APIs, products, and policies.
 */


// ------------------------------
//    PARAMETERS
// ------------------------------

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('The name of the API Management instance. Defaults to "apim-<resourceSuffix>".')
param apimName string = 'apim-${resourceSuffix}'

@description('The capacity for the Workspace Gateway. Defaults to 1.')
param apimWorkspaceGatewayCapacity int = 1
@description('The SKU for the Workspace Gateway. Defaults to "WorkspaceGatewayPremium".')
@allowed(['WorkspaceGatewayPremium', 'WorkspaceGatewayStandard', 'Standard'])
param apimWorkspaceGatewaySku string = 'WorkspaceGatewayPremium'
@description('The resource id of the subnet for the Workspace Gateway.')
param apimWorkspaceGatewaySubnetId string
@description('The type of network for the Workspace Gateway. Defaults to "External".')
@allowed(['External', 'Internal', 'None'])
param apimWorkspaceGatewayNetworkType string
@description('The name of the Workspace Gateway. Defaults to "<apimName>-gateway".')
param apimWorkspaceGatewayName string = '${apimName}-gateway'
@description('The name of the API Management Workspace. Defaults to "<apimName>-workspace".')
param apimWorkspaceName string

// ------------------------------
//    VARIABLES
// ------------------------------
var apimWorkspaceGatewayNetworkConfig = 'config'

// ------------------------------
//    RESOURCES
// ------------------------------

resource workspaceGateway 'Microsoft.ApiManagement/gateways@2024-06-01-preview' = {
  name: apimWorkspaceGatewayName
  location: resourceGroup().location
  sku: {
    name: apimWorkspaceGatewaySku
    capacity: apimWorkspaceGatewayCapacity
  }
  properties: {
    backend: apimWorkspaceGatewayNetworkType != 'None' ? {
      subnet: {
        id: apimWorkspaceGatewaySubnetId
      }
    } : null
    configurationApi: {}
    frontend: {}
    virtualNetworkType: apimWorkspaceGatewayNetworkType
  }
}

resource workspaceGatewayConfigConnection 'Microsoft.ApiManagement/gateways/configConnections@2024-06-01-preview' = {
  parent: workspaceGateway
  name: apimWorkspaceGatewayNetworkConfig
  properties: {
    sourceId: '${resourceId('Microsoft.ApiManagement/service', apimName)}/workspaces/${apimWorkspaceName}'
  }
}

// ------------------------------
//    OUTPUTS
// ------------------------------

