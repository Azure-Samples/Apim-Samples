/**
 * @module named-value-v1
 * @description This module defines the named value resource using Bicep.
 * It includes configurations plain text and secret named values but not for Key Vault (may create a separate module for that).
 */


// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('The name of the API Management service.')
param apimName string

@description('The name of the named value to create.')
param namedValueName string

@description('The value to assign to the named value.')
param namedValueValue string

@description('Whether the value is a secret.')
param namedValueIsSecret bool = false

// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/namedvalues
resource namedValue 'Microsoft.ApiManagement/service/namedValues@2024-06-01-preview' = {
  name: namedValueName
  parent: apimService
  properties: {
    displayName: namedValueName
    value: namedValueValue
    secret: namedValueIsSecret
    tags: []
  }
}

// ------------------------------
//    OUTPUTS
// ------------------------------

@description('The resource ID of the created named value.')
output namedValueResourceId string = namedValue.id
