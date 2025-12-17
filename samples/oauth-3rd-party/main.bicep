// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

param namedValues array = []
param apimName string = 'apim-${resourceSuffix}'
param appInsightsName string = 'appi-${resourceSuffix}'
param apis array = []
param products array = []
param policyFragments array = []

// OAuth Parameters
@description('The OAuth client ID for Spotify API')
param clientId string

@description('The OAuth client secret for Spotify API')
@secure()
param clientSecret string

@description('The OAuth flow type to use')
@allowed([
  'client_credentials'
  'authorization_code'
  'authorization_code_pkce'
  'refresh_token'
])
param oauthFlowType string = 'authorization_code_pkce'

@description('PKCE code challenge method when using PKCE flow')
@allowed([
  'plain'
  'S256'
  ''
])
param pkceCodeChallengeMethod string = 'S256'

@description('Whether to create the Authorization Provider for Credential Manager')
param createAuthorizationProvider bool = true

@description('Whether to create the Authorization connection (requires manual consent)')
param createAuthorization bool = false

// ------------------
//    RESOURCES
// ------------------

// https://learn.microsoft.com/azure/templates/microsoft.insights/components
resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

var appInsightsId = appInsights.id
var appInsightsInstrumentationKey = appInsights.properties.InstrumentationKey

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// APIM Named Values
module namedValueModule '../../shared/bicep/modules/apim/v1/named-value.bicep' = [for nv in namedValues: {
  name: 'nv-${nv.name}'
  params:{
    apimName: apimName
    namedValueName: nv.name
    namedValueValue: nv.value
    namedValueIsSecret: nv.isSecret
  }
}]

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/authorizationproviders
resource spotifyAuthorizationProvider 'Microsoft.ApiManagement/service/authorizationProviders@2024-06-01-preview' = {
  name: 'spotify'
  parent: apimService
  properties: {
    displayName: 'spotify'
    identityProvider: 'oauth2pkce'
    oauth2: {
      redirectUrl: 'https://authorization-manager.consent.azure-apim.net/redirect/apim/${apimName}'
      grantTypes: {
        authorizationCode: {
          clientId: clientId
          clientSecret: clientSecret
          scopes: 'user-read-recently-played'
          authorizationUrl: 'https://accounts.spotify.com/authorize'
          refreshUrl: 'https://accounts.spotify.com/api/token'
          tokenUrl: 'https://accounts.spotify.com/api/token'
        }
      }
    }
  }
}

// https://learn.microsoft.com/en-us/azure/templates/microsoft.apimanagement/service/authorizationproviders/authorizations
resource spotifyAuthorization 'Microsoft.ApiManagement/service/authorizationProviders/authorizations@2024-06-01-preview' = {
  parent: spotifyAuthorizationProvider
  name: 'spotify-auth'
  properties: {
    authorizationType: 'OAuth2'
    oauth2grantType: 'AuthorizationCode'
  }
}

// https://learn.microsoft.com/en-us/azure/templates/microsoft.apimanagement/service/authorizationproviders/authorizations/accesspolicies
resource spotifyAccessPolicies 'Microsoft.ApiManagement/service/authorizationProviders/authorizations/accessPolicies@2024-06-01-preview' = {
  parent: spotifyAuthorization
  name: 'spotify-auth-access-policies'
  properties: {
    objectId: apimService.identity.principalId  // APIM managed identity principal ID
    tenantId: tenant().tenantId
  }
}

// APIM Policy Fragments
module policyFragmentModule '../../shared/bicep/modules/apim/v1/policy-fragment.bicep' = [for pf in policyFragments: {
  name: 'pf-${pf.name}'
  params:{
    apimName: apimName
    policyFragmentName: pf.name
    policyFragmentDescription: pf.description
    policyFragmentValue: pf.policyXml
  }
  dependsOn: [
    namedValueModule
  ]
}]

// APIM APIs (deployed after products are ready to avoid race conditions)
@batchSize(1)  // Deploy APIs sequentially to avoid race conditions
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: {
  name: 'api-${api.name}'
  params:{
    apimName: apimName
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    api: api
    productNames: api.productNames ?? []
  }
  dependsOn: [
    namedValueModule              // ensure all named values are created before APIs
    policyFragmentModule          // ensure all policy fragments are created before APIs
  ]
}]

// ------------------
//    MARK: OUTPUTS
// ------------------

output apimServiceId string = apimService.id
output apimServiceName string = apimService.name
output apimResourceGatewayURL string = apimService.properties.gatewayUrl
output spotifyOAuthRedirectUrl string = spotifyAuthorizationProvider.properties.oauth2.redirectUrl

// API outputs
output apiOutputs array = [for i in range(0, length(apis)): {
  name: apis[i].name
  resourceId: apisModule[i].?outputs.?apiResourceId ?? ''
  displayName: apisModule[i].?outputs.?apiDisplayName ?? ''
  productAssociationCount: apisModule[i].?outputs.?productAssociationCount ?? 0
  subscriptionResourceId: apisModule[i].?outputs.?subscriptionResourceId ?? ''
  subscriptionName: apisModule[i].?outputs.?subscriptionName ?? ''
  subscriptionPrimaryKey: apisModule[i].?outputs.?subscriptionPrimaryKey ?? ''
  subscriptionSecondaryKey: apisModule[i].?outputs.?subscriptionSecondaryKey ?? ''
}]
