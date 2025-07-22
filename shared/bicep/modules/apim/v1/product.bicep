/**
 * @module product-v1
 * @description This module defines the product resource using Bicep.
 * It includes configurations for creating and managing APIM products.
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

@description('The name of the product to create.')
param productName string

@description('The display name of the product.')
param productDisplayName string

@description('The description of the product.')
param productDescription string = ''

@description('Whether the product is published or not. Published products are discoverable by users of developer portal.')
@allowed([
  'published'
  'notPublished'
])
param productState string = 'notPublished'

@description('Whether a product subscription is required for accessing APIs included in this product.')
param subscriptionRequired bool = true

@description('Whether subscription approval is required. Only applies when subscriptionRequired is true.')
param approvalRequired bool = false

@description('The policy XML content to apply to the product. If empty, no policy will be created.')
param policyXml string = ''


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: apimName
}

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/products
resource product 'Microsoft.ApiManagement/service/products@2024-05-01' = {
  name: productName
  parent: apimService
  properties: union({
    displayName: productDisplayName
    description: productDescription
    state: productState
    subscriptionRequired: subscriptionRequired
    subscriptionsLimit: null
    terms: ''
  }, subscriptionRequired ? {
    approvalRequired: approvalRequired
  } : {})
}

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/products/policies
resource productPolicy 'Microsoft.ApiManagement/service/products/policies@2024-05-01' = if (!empty(policyXml)) {
  name: 'policy'
  parent: product
  properties: {
    format: 'rawxml'    // only use 'rawxml' for policies as it's what APIM expects and means we don't need to escape XML characters
    value: policyXml
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/subscriptions
resource productSubscription 'Microsoft.ApiManagement/service/subscriptions@2024-05-01' = if (subscriptionRequired) {
  name: 'product-${toLower(productName)}'
  parent: apimService
  properties: {
    allowTracing: true
    displayName: 'Subscription for ${productDisplayName} product'
    scope: '/products/${productName}'
    state: 'active'
  }
  dependsOn: [
    product
  ]
}


// ------------------------------
//    OUTPUTS
// ------------------------------

@description('The resource ID of the created product.')
output productResourceId string = product.id

@description('The name of the created product.')
output productName string = product.name

@description('The display name of the created product.')
output productDisplayName string = product.properties.displayName

@description('The state of the product.')
output productState string = product.properties.state

@description('Whether subscription is required for this product.')
output subscriptionRequired bool = product.properties.subscriptionRequired

@description('Whether approval is required for subscriptions. Only applicable when subscriptionRequired is true.')
output approvalRequired bool = subscriptionRequired ? product.properties.approvalRequired : false

@description('The resource ID of the product policy, if created.')
output policyResourceId string = !empty(policyXml) ? productPolicy.id : ''

@description('Whether a policy is attached to this product.')
output hasPolicyAttached bool = !empty(policyXml)

@description('The resource ID of the product subscription, if created.')
output subscriptionResourceId string = subscriptionRequired ? productSubscription.id : ''

@description('The name of the product subscription, if created.')
output subscriptionName string = subscriptionRequired ? productSubscription.name : ''

@description('The primary key of the product subscription, if created.')
output subscriptionPrimaryKey string = subscriptionRequired ? listSecrets('${apimService.id}/subscriptions/product-${toLower(productName)}', '2024-05-01').primaryKey : ''

@description('The secondary key of the product subscription, if created.')
output subscriptionSecondaryKey string = subscriptionRequired ? listSecrets('${apimService.id}/subscriptions/product-${toLower(productName)}', '2024-05-01').secondaryKey : ''
