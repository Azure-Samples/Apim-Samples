/**
 * @module apim-v1
 * @description This module defines the API resources using Bicep.
 * It includes configurations for creating and managing APIs, products, and policies.
 */


// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

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
    subscriptionKeyParameterNames: {
      header: 'api-key'
      query: 'api-key'
    }
    subscriptionRequired: false
    type: 'http'
  }
}

// Create APIM tag resources for each tag in api.tags (array or object)
// Only support array of strings for tags (APIM tags)
var tagList = empty(api.tags) ? [] : api.tags

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
resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-06-01-preview' = if (!empty(api.policyXml)) {
  name: 'policy'
  parent: apimApi
  properties: {
    format: 'rawxml'
    value: api.policyXml
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/apis/operations
resource apiOperation 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = [for (op, i) in api.operations: if(length(api.operations) > 0) {
  name: '${api.name}-${op.name}-${i}-${resourceSuffix}'
  parent: apimApi
  properties: {
    displayName: op.displayName
    method: op.method
    urlTemplate: op.urlTemplate
    description: op.description
  }
}]

// Attach policy XML to each operation
// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/apis/operations/policies
resource apiOperationPolicy 'Microsoft.ApiManagement/service/apis/operations/policies@2024-06-01-preview' = [for (op, i) in api.operations: if(length(api.operations) > 0) {
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
    }
  }
}


// ------------------------------
//    OUTPUTS
// ------------------------------

//output subscriptionPrimaryKey string = apimSubscription.listSecrets().primaryKey
