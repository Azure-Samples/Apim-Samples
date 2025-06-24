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
@description('The name of the API Management Workspace. Defaults to "<apimName>-workspace".')
param apimWorkspaceName string = '${apimName}-workspace'
@description('The description of the API Management Workspace. Defaults to "API Management Workspace for <apimName>".')
param apimWorkspaceDescription string = 'API Management Workspace for ${apimName}'
@description('The display name of the API Management Workspace. Defaults to "<apimName> Workspace".')
param apimWorkspaceDisplayName string = '${apimName} Workspace'

// ------------------------------
//    VARIABLES
// ------------------------------
var apimWorkspaceGatewayNetworkConfig = 'config'

// ------------------------------
//    RESOURCES
// ------------------------------


resource apimService 'Microsoft.ApiManagement/service@2021-08-01' existing = {
  name: apimName
}

resource apimWorkspace 'Microsoft.ApiManagement/service/workspaces@2024-06-01-preview' = {
  parent: apimService
  name: apimWorkspaceName
  properties: {
    description: apimWorkspaceDescription
    displayName: apimWorkspaceDisplayName
  }
}


// ------------------------------
//    OUTPUTS
// ------------------------------

