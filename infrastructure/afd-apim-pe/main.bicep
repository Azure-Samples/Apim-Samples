// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

// Networking
@description('The name of the VNet.')
param vnetName string = 'vnet-${resourceSuffix}'
param apimSubnetName string = 'snet-apim'
param acaSubnetName string = 'snet-aca'

@description('The address prefixes for the VNet.')
param vnetAddressPrefixes array = [ '10.0.0.0/16' ]

@description('The address prefix for the APIM subnet.')
param apimSubnetPrefix string = '10.0.1.0/24'

@description('The address prefix for the ACA subnet. Requires a /23 or larger subnet for Consumption workloads.')
param acaSubnetPrefix string = '10.0.2.0/23'

// API Management
param apimName string = 'apim-${resourceSuffix}'
param apimSku string
param apis array = []
param policyFragments array = []

@description('Set to true to make APIM publicly accessible. If false, APIM will be deployed into a VNet subnet for egress only.')
param apimPublicAccess bool = true

@description('Reveals the backend API information. Defaults to true. *** WARNING: This will expose backend API information to the caller - For learning & testing only! ***')
param revealBackendApiInfo bool = true

// Front Door
param afdEndpointName string = 'afd-${resourceSuffix}'

// Container Apps
param acaName string = 'aca-${resourceSuffix}'
param useACA bool = false

// ------------------
//    "CONSTANTS"
// ------------------

var IMG_HELLO_WORLD = 'simonkurtzmsft/helloworld:latest'
var IMG_MOCK_WEB_API = 'simonkurtzmsft/mockwebapi:1.0.0-alpha.1'

// ------------------
//    RESOURCES
// ------------------

// 1. Log Analytics Workspace
module lawModule '../../shared/bicep/modules/operational-insights/v1/workspaces.bicep' = {
  name: 'lawModule'
}

var lawId = lawModule.outputs.id

// 2. Application Insights
module appInsightsModule '../../shared/bicep/modules/monitor/v1/appinsights.bicep' = {
  name: 'appInsightsModule'
  params: {
    lawId: lawId
    customMetricsOptedInType: 'WithDimensions'
  }
}

var appInsightsId = appInsightsModule.outputs.id
var appInsightsInstrumentationKey = appInsightsModule.outputs.instrumentationKey

// 3. Virtual Network and Subnets

// We are using a standard NSG for our subnets here. Production workloads should use a relevant, custom NSG for each subnet.
// We also do not presently use a custom route table for the subnets, which is a best practice for production workloads.

// https://learn.microsoft.com/azure/templates/microsoft.network/networksecuritygroups
resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-default'
  location: location
}

module vnetModule '../../shared/bicep/modules/vnet/v1/vnet.bicep' = {
  name: 'vnetModule'
  params: {
    vnetName: vnetName
    vnetAddressPrefixes: vnetAddressPrefixes
    subnets: [
      // APIM Subnet
      {
        name: apimSubnetName
        properties: {
          addressPrefix: apimSubnetPrefix
          networkSecurityGroup: {
            id: nsg.id
          }
          delegations: [
            {
              name: 'Microsoft.Web/serverFarms'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ]
        }
      }
      // ACA Subnet
      {
        name: acaSubnetName
        properties: {
          addressPrefix: acaSubnetPrefix
          networkSecurityGroup: {
            id: nsg.id
          }
          delegations: [
            {
              name: 'Microsoft.App/environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
    ]
  }
}

// Create explicit dependencies so subnet IDs are always available after the VNet module completes.
resource vnetExisting 'Microsoft.Network/virtualNetworks@2024-05-01' existing = {
  name: vnetName
  dependsOn: [
    vnetModule
  ]
}

resource apimSubnetResource 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = {
  parent: vnetExisting
  name: apimSubnetName
}

resource acaSubnetResource 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = {
  parent: vnetExisting
  name: acaSubnetName
}

var apimSubnetResourceId = apimSubnetResource.id
var acaSubnetResourceId  = acaSubnetResource.id

// 4. Azure Container App Environment (ACAE)
module acaEnvModule '../../shared/bicep/modules/aca/v1/environment.bicep' = if (useACA) {
  name: 'acaEnvModule'
  params: {
    name: 'cae-${resourceSuffix}'
    logAnalyticsWorkspaceCustomerId: lawModule.outputs.customerId
    logAnalyticsWorkspaceSharedKey: lawModule.outputs.clientSecret
    subnetResourceId: acaSubnetResourceId
  }
}

// 5. Azure Container Apps (ACA) for Mock Web API
module acaModule1 '../../shared/bicep/modules/aca/v1/containerapp.bicep' = if (useACA) {
  name: 'acaModule-1'
  params: {
    name: 'ca-${resourceSuffix}-mockwebapi-1'
    containerImage: IMG_MOCK_WEB_API
    environmentId: acaEnvModule!.outputs.environmentId
  }
}
module acaModule2 '../../shared/bicep/modules/aca/v1/containerapp.bicep' = if (useACA) {
  name: 'acaModule-2'
  params: {
    name: 'ca-${resourceSuffix}-mockwebapi-2'
    containerImage: IMG_MOCK_WEB_API
    environmentId: acaEnvModule!.outputs.environmentId
  }
}

// 6. API Management
module apimModule '../../shared/bicep/modules/apim/v1/apim.bicep' = {
  name: 'apimModule'
  params: {
    apimSku: apimSku
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    apimSubnetResourceId: apimSubnetResourceId
    publicAccess: apimPublicAccess
    globalPolicyXml: revealBackendApiInfo ? loadTextContent('../../shared/apim-policies/all-apis-reveal-backend.xml') : loadTextContent('../../shared/apim-policies/all-apis.xml')
  }
}

// 7. APIM Policy Fragments
module policyFragmentModule '../../shared/bicep/modules/apim/v1/policy-fragment.bicep' = [for pf in policyFragments: {
  name: 'pf-${pf.name}'
  params:{
    apimName: apimName
    policyFragmentName: pf.name
    policyFragmentDescription: pf.description
    policyFragmentValue: pf.policyXml
  }
  dependsOn: [
    apimModule
  ]
}]

// 8. APIM Backends for ACA
module backendModule1 '../../shared/bicep/modules/apim/v1/backend.bicep' = if (useACA) {
  name: 'aca-backend-1'
  params: {
    apimName: apimName
    backendName: 'aca-backend-1'
    url: 'https://${acaModule1!.outputs.containerAppFqdn}'
  }
  dependsOn: [
    apimModule
  ]
}

module backendModule2 '../../shared/bicep/modules/apim/v1/backend.bicep' = if (useACA) {
  name: 'aca-backend-2'
  params: {
    apimName: apimName
    backendName: 'aca-backend-2'
    url: 'https://${acaModule2!.outputs.containerAppFqdn}'
  }
  dependsOn: [
    apimModule
  ]
}

module backendPoolModule '../../shared/bicep/modules/apim/v1/backend-pool.bicep' = if (useACA) {
  name: 'aca-backend-pool'
  params: {
    apimName: apimName
    backendPoolName: 'aca-backend-pool'
    backendPoolDescription: 'Backend pool for ACA Hello World backends'
    backends: [
      {
        name: backendModule1!.outputs.backendName
        priority: 1
        weight: 75
      }
      {
        name: backendModule2!.outputs.backendName
        priority: 1
        weight: 25
      }
    ]
  }
  dependsOn: [
    apimModule
  ]
}

// 9. APIM APIs
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: if(length(apis) > 0) {
  name: 'api-${api.name}'
  params: {
    apimName: apimName
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    api: api
  }
  dependsOn: useACA ? [
    apimModule
    backendModule1
    backendModule2
    backendPoolModule
  ] : [
    apimModule
  ]
}]

// 10. APIM Private DNS Zone, VNet Link, and (optional) DNS Zone Group
module apimDnsPrivateLinkModule '../../shared/bicep/modules/dns/v1/dns-private-link.bicep' = {
  name: 'apimDnsPrivateLinkModule'
  params: {
    dnsZoneName: 'privatelink.azure-api.net'
    vnetId: vnetModule.outputs.vnetId
    vnetLinkName: 'link-apim'
    enableDnsZoneGroup: true
    dnsZoneGroupName: 'dnsZoneGroup-apim'
    dnsZoneConfigName: 'config-apim'
  }
}

// 11. ACA Private DNS Zone (regional, e.g., eastus2.azurecontainerapps.io), VNet Link, and wildcard A record via shared module
module acaDnsPrivateZoneModule '../../shared/bicep/modules/dns/v1/aca-dns-private-zone.bicep' = if (useACA && !empty(acaSubnetResourceId)) {
  name: 'acaDnsPrivateZoneModule'
  params: {
    acaEnvironmentRandomSubdomain: acaEnvModule!.outputs.environmentRandomSubdomain
    acaEnvironmentStaticIp: acaEnvModule!.outputs.environmentStaticIp
    vnetId: vnetModule.outputs.vnetId
  }
}

// 12. Front Door
module afdModule '../../shared/bicep/modules/afd/v1/afd.bicep' = {
  name: 'afdModule'
  params: {
    resourceSuffix: resourceSuffix
    afdName: afdEndpointName
    fdeName: afdEndpointName
    afdSku: 'Premium_AzureFrontDoor'
    apimName: apimName
    logAnalyticsWorkspaceId: lawId
  }
  dependsOn: [
    apimModule
  ]
}

// ------------------
//    MARK: OUTPUTS
// ------------------

output applicationInsightsAppId string = appInsightsModule.outputs.appId
output applicationInsightsName string = appInsightsModule.outputs.applicationInsightsName
output logAnalyticsWorkspaceId string = lawModule.outputs.customerId
output apimServiceId string = apimModule.outputs.id
output apimServiceName string = apimModule.outputs.name
output apimResourceGatewayURL string = apimModule.outputs.gatewayUrl
output fdeHostName string = afdModule.outputs.fdeHostName
output fdeSecureUrl string = afdModule.outputs.fdeSecureUrl

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
