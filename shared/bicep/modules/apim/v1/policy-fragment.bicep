/**
 * @module policy-fragment-v1
 * @description This module defines the policy fragment resource using Bicep.
 * It includes configurations for creating and managing APIM policy fragments.
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

@description('The name of the policy fragment to create.')
param policyFragmentName string

@description('The description of the policy fragment.')
param policyFragmentDescription string = ''

@description('The content/value of the policy fragment.')
param policyFragmentValue string


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: apimName
}

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/policyfragments
resource policyFragment 'Microsoft.ApiManagement/service/policyFragments@2024-05-01' = {
  name: policyFragmentName
  parent: apimService
  properties: {
    description: policyFragmentDescription
    format: 'rawxml'    // only use 'rawxml' for policies as it's what APIM expects and means we don't need to escape XML characters 
    value: policyFragmentValue
  }
}


// ------------------------------
//    OUTPUTS
// ------------------------------

@description('The resource ID of the created policy fragment.')
output policyFragmentResourceId string = policyFragment.id

@description('The name of the created policy fragment.')
output policyFragmentName string = policyFragment.name

@description('The provisioning state of the policy fragment.')
output policyFragmentProvisioningState string = policyFragment.properties.provisioningState
