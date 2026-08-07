/**
 * @module backend-v1
 * @description This module defines the Azure API Management (APIM) backend resources using Bicep.
 */


// ------------------------------
//    PARAMETERS
// ------------------------------

@description('The name of the API Management instance.')
param apimName string

@description('The name of the backend.')
param backendName string

@description('The URL of the backend service (e.g., ACA public FQDN).')
param url string

@description('The description of the backend. Defaults to a description derived from the backend name.')
param backendDescription string = ''

@description('The backend type. Leave empty to use the API Management default.')
param backendType string = ''

@description('The TLS validation settings for the backend. Leave empty to use the API Management defaults.')
param tls object = {}

@description('The circuit breaker configuration for the backend.')
param circuitBreaker object = {
  rules: [
    {
      failureCondition: {
        count: 1
        errorReasons: [
          'Server errors'
        ]
        interval: 'PT5M'
        statusCodeRanges: [
          {
            min: 429
            max: 429
          }
        ]
      }
      name: 'backend-circuit-breaker'
      tripDuration: 'PT1M'
      acceptRetryAfter: true
    }
  ]
}


// ------------------------------
//    VARIABLES
// ------------------------------

@description('Backend properties with optional type and TLS settings included only when explicitly configured.')
var backendProperties = union(
  {
    url: url
    description: empty(backendDescription) ? 'This is the backend for ${backendName}' : backendDescription
    protocol: 'http'
    circuitBreaker: circuitBreaker
  },
  empty(backendType) ? {} : {
    type: backendType
  },
  empty(tls) ? {} : {
    tls: tls
  }
)


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/backends
resource backend 'Microsoft.ApiManagement/service/backends@2024-06-01-preview' = {
  name: backendName
  parent: apimService
  properties: backendProperties
}


// ------------------------------
//    OUTPUTS
// ------------------------------

output backendId string = backend.id
output backendName string = backend.name
