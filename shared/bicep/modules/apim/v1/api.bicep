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

@description('Name of the APIM Logger')
param apimLoggerName string = 'apim-logger'

@description('The instrumentation key for Application Insights')
param appInsightsInstrumentationKey string = ''

@description('The resource ID for Application Insights')
param appInsightsId string = ''

@description('Array of product names to associate this API with. If empty, no product associations will be created.')
param productNames array = []

param api object = {}


// ------------------------------
//    VARIABLES
// ------------------------------

var logSettings = {
  headers: [ 'Content-type', 'User-agent' ]
  body: { bytes: 8192 }
}


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/apis
resource apimApi 'Microsoft.ApiManagement/service/apis@2024-06-01-preview' = {
  name: api.name
  parent: apimService
  properties: {
    apiType: 'http'
    description: api.description
    displayName: api.displayName
    path: api.path
    protocols: [
      'https'
    ]
    serviceUrl: contains(api, 'serviceUrl') && !empty(api.serviceUrl) ? api.serviceUrl : null
    subscriptionKeyParameterNames: {
      header: 'api-key'
      query: 'api-key'
    }
    subscriptionRequired: api.?subscriptionRequired ?? false
    type: 'http'
  }
}

// Create APIM tag resources for each tag in api.tags (array or object)
// Only support array of strings for tags (APIM tags)
var tagList = contains(api, 'tags') && !empty(api.tags) ? api.tags : []

resource apimTags 'Microsoft.ApiManagement/service/tags@2024-06-01-preview' = [for tag in tagList: {
  name: tag
  parent: apimService
  properties: {
    displayName: tag
  }
}]

resource apimApiTags 'Microsoft.ApiManagement/service/apis/tags@2024-06-01-preview' = [for tag in tagList: {
  name: tag
  parent: apimApi
}]

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/apis/policies
resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-06-01-preview' = if (contains(api, 'policyXml') && !empty(api.policyXml)) {
  name: 'policy'
  parent: apimApi
  properties: {
    format: 'rawxml'    // only use 'rawxml' for policies as it's what APIM expects and means we don't need to escape XML characters
    value: api.policyXml
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/apis/operations
resource apiOperation 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = [for (op, i) in api.operations: {
  name: '${api.name}-${op.name}-${i}-${resourceSuffix}'
  parent: apimApi
  properties: {
    displayName: op.displayName
    method: op.method
    urlTemplate: op.urlTemplate
    description: op.description
    templateParameters: op.?templateParameters ?? []
  }
}]

// Attach policy XML to each operation (only if policy XML exists)
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/apis/operations/policies
resource apiOperationPolicy 'Microsoft.ApiManagement/service/apis/operations/policies@2024-06-01-preview' = [for (op, i) in api.operations: if (contains(op, 'policyXml') && !empty(op.policyXml)) {
  name: 'policy'
  parent: apiOperation[i] // Associate with the correct apiOperation resource
  dependsOn: [
    apiOperation[i] // Ensure this policy waits for the corresponding operation to be created
  ]
  properties: {
    format: 'rawxml'
    value: op.policyXml // Use the policyXml specific to this operation
  }
}]

// Create diagnostics only if we have an App Insights ID and instrumentation key.
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/apis/diagnostics
resource apiDiagnostics 'Microsoft.ApiManagement/service/apis/diagnostics@2024-06-01-preview' = if (!empty(appInsightsId) && !empty(appInsightsInstrumentationKey)) {
  name: 'applicationinsights'
  parent: apimApi
  properties: {
    alwaysLog: 'allErrors'
    httpCorrelationProtocol: 'W3C'
    logClientIp: true
    loggerId: resourceId(resourceGroup().name, 'Microsoft.ApiManagement/service/loggers', apimName, apimLoggerName)
    metrics: true
    verbosity: 'verbose'
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    frontend: {
      request: logSettings
      response: logSettings
    }
    backend: {
      request: logSettings
      response: logSettings
    }  }
}

// Product associations are handled directly in this module with proper dependency management // to prevent race conditions while keeping the architecture simple
// Reference existing products for association (with explicit dependency timing)
resource apimProducts 'Microsoft.ApiManagement/service/products@2024-06-01-preview' existing = [for productName in productNames: {
  name: productName
  parent: apimService
}]

// Create product-API associations with proper dependency management
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/products/apis
resource apiProductAssociation 'Microsoft.ApiManagement/service/products/apis@2024-06-01-preview' = [for (productName, index) in productNames: {
  name: apimApi.name
  parent: apimProducts[index]
  dependsOn: [
    apimProducts[index]        // Ensure the specific product exists and is ready
    apiPolicy                  // Ensure API policy is applied if present
    apiOperation               // Ensure all operations are created
    apiOperationPolicy         // Ensure all operation policies are applied
    apiDiagnostics             // Ensure diagnostics are configured if present
  ]
}]


// ------------------------------
//    OUTPUTS
// ------------------------------

@description('The resource ID of the created API.')
output apiResourceId string = apimApi.id

@description('The name of the created API.')
output apiName string = apimApi.name

@description('The display name of the created API.')
output apiDisplayName string = apimApi.properties.displayName

@description('The path of the created API.')
output apiPath string = apimApi.properties.path

@description('Array of product names this API is associated with.')
output associatedProducts array = productNames

@description('Number of products this API is associated with.')
output productAssociationCount int = length(productNames)

//output subscriptionPrimaryKey string = apimSubscription.listSecrets().primaryKey
