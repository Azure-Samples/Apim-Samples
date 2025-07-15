// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

param apimName string = 'apim-${resourceSuffix}'

param apimSku string
param apis array = []
param policyFragments array = []

@description('Reveals the backend API information. Defaults to true. *** WARNING: This will expose backend API information to the caller - For learning & testing only! ***')
param revealBackendApiInfo bool = true

param vnetName string = 'vnet-${resourceSuffix}'
param vnetAddressPrefixes array = ['10.0.0.0/16']
param apimSubnetName string = 'snet-apim'
param apimSubnetPrefix string = '10.0.0.0/24'

@description('The name of the subnet for the API Management Workspace Gateway. Defaults to "snet-gateway".')
param gatewaySubnetName string = 'snet-gateway'
@description('The prefix for the gateway subnet. Defaults to 10.0.1.0/24.')
param gatewaySubnetPrefix string = '10.0.1.0/24'
@description('The capacity for the Workspace Gateway. Defaults to 1.')
param gatewayCapacity int = 1
@description('The SKU for the Workspace Gateway. Defaults to "WorkspaceGatewayPremium".')
@allowed(['WorkspaceGatewayPremium', 'WorkspaceGatewayStandard', 'Standard'])
param gatewaySku string = 'WorkspaceGatewayPremium'
@description('The type of network for the Workspace Gateway. Defaults to "External".')
@allowed(['External', 'Internal', 'None'])
param gatewayNetworkType string = 'Internal'

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

// 3. Virtual Networks and Subnets
resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-default'
  location: location
  properties: {
    securityRules: [
      // Inbound rules
      {
        name: 'Allow-ApiManagement-Management'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'ApiManagement'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '3443'
        }
      }
      {
        name: 'Allow-AzureLoadBalancer-6390'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'AzureLoadBalancer'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '6390'
        }
      }
      // Outbound rules
      {
        name: 'Allow-VNet-Storage-443'
        properties: {
          priority: 200
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'Storage'
          destinationPortRange: '443'
        }
      }
      {
        name: 'Allow-VNet-Internet-80'
        properties: {
          priority: 210
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'Internet'
          destinationPortRange: '80'
        }
      }
      {
        name: 'Allow-VNet-Internet-443'
        properties: {
          priority: 220
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'Internet'
          destinationPortRange: '443'
        }
      }
      {
        name: 'Allow-VNet-Sql-1433'
        properties: {
          priority: 230
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'Sql'
          destinationPortRange: '1433'
        }
      }
      {
        name: 'Allow-VNet-AzureKeyVault-443'
        properties: {
          priority: 240
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'AzureKeyVault'
          destinationPortRange: '443'
        }
      }
      {
        name: 'Allow-VNet-AzureMonitor-1886-443'
        properties: {
          priority: 250
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'AzureMonitor'
          destinationPortRanges: [ '1886', '443' ]
        }
      }
      {
        name: 'Allow-VNet-AzureActiveDirectory-443'
        properties: {
          priority: 260
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'AzureActiveDirectory'
          destinationPortRange: '443'
        }
      }
    ]
  }
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
          delegations: []
        }
      }
      gatewayNetworkType != 'None' ? {
        // Gateway Subnet
          name: gatewaySubnetName
          properties: {
            addressPrefix: gatewaySubnetPrefix
            networkSecurityGroup: {
              id: nsg.id
            }
            delegations: [
              {
                name: gatewayNetworkType == 'External' ? 'Microsoft.Web/serverFarms' : 'Microsoft.Web/hostingEnvironments'
                properties: {
                  serviceName: gatewayNetworkType == 'External' ? 'Microsoft.Web/serverFarms' : 'Microsoft.Web/hostingEnvironments'
                }
              }
            ]
          }
      } : null
    ]
  }
}

// TODO: We have a timing issue here in that we may get a null if this happens too quickly after the vnet module executes.
var apimSubnetResourceId = resourceId(resourceGroup().name, 'Microsoft.Network/virtualNetworks/subnets', vnetName, apimSubnetName)


// 3. API Management
module apimModule '../../shared/bicep/modules/apim/v1/apim.bicep' = {
  name: 'apimModule'
  params: {
    apimSku: apimSku
    apimSubnetResourceId: apimSubnetResourceId
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    globalPolicyXml: revealBackendApiInfo ? loadTextContent('../../shared/apim-policies/all-apis-reveal-backend.xml') : loadTextContent('../../shared/apim-policies/all-apis.xml')
  }
}

module workspaceModule '../../shared/bicep/modules/apim/v1/workspace.bicep' = {
  name: 'workspaceModule'
  params: {
    apimName: apimName
    apimWorkspaceName: '${apimName}-workspace'
    apimWorkspaceDescription: 'API Management Workspace for ${apimName}'
    apimWorkspaceDisplayName: '${apimName} Workspace'
  }
  dependsOn: [
    apimModule
  ]
}

module gatewayModule '../../shared/bicep/modules/apim/v1/workspace-gateway.bicep' = {
  name: 'gatewayModule'
  params: {
    apimName: apimName
    apimWorkspaceGatewayCapacity: gatewayCapacity
    apimWorkspaceGatewaySku: gatewaySku
    apimWorkspaceGatewaySubnetId: resourceId(resourceGroup().name, 'Microsoft.Network/virtualNetworks/subnets', vnetName, gatewaySubnetName)
    apimWorkspaceGatewayNetworkType: gatewayNetworkType
    apimWorkspaceName: '${apimName}-workspace'
  }
  dependsOn: [
    apimModule
    workspaceModule
  ]
}

// 4. APIM Policy Fragments
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

// 5. APIM APIs
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: if(length(apis) > 0) {
  name: 'api-${api.name}'
  params: {
    apimName: apimName
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    api: api
  }
  dependsOn: [
   apimModule
  ]
}]


// ------------------
//    MARK: OUTPUTS
// ------------------

output applicationInsightsAppId string = appInsightsModule.outputs.appId
output applicationInsightsName string = appInsightsModule.outputs.applicationInsightsName
output logAnalyticsWorkspaceId string = lawModule.outputs.customerId
output apimServiceId string = apimModule.outputs.id
output apimServiceName string = apimModule.outputs.name
output apimResourceGatewayURL string = apimModule.outputs.gatewayUrl

#disable-next-line outputs-should-not-contain-secrets
//output apimSubscription1Key string = apimModule.outputs.[0].listSecrets().primaryKey
