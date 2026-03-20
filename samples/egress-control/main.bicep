// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('The name of the existing APIM instance.')
param apimName string = 'apim-${resourceSuffix}'

@description('The name of the existing Application Insights instance.')
param appInsightsName string = 'appi-${resourceSuffix}'

@description('The APIM APIs to deploy into the existing APIM instance.')
param apis array = []

// Networking - Spoke (existing infrastructure VNet)

@description('The name of the existing spoke VNet (infrastructure VNet).')
param spokeVnetName string = 'vnet-${resourceSuffix}'

@description('The name of the APIM subnet in the spoke VNet.')
param apimSubnetName string = 'snet-apim'

@description('The address prefix of the APIM subnet.')
param apimSubnetPrefix string = '10.0.1.0/24'

@description('The address prefix of the spoke VNet. Used to create a local route so VNet traffic bypasses the NVA.')
param spokeVnetAddressPrefix string = '10.0.0.0/16'

@description('The name of the NSG currently attached to the APIM subnet (nsg-apim or nsg-apim-strict).')
param apimNsgName string = 'nsg-apim'

@description('Set to true when APIM is running in VNet integration mode (V2 SKUs: Basicv2, Standardv2, Premiumv2). False for VNet injection (V1 SKUs: Developer, Premium).')
param apimVnetIntegration bool = false

// Networking - Hub (deployed by this sample)

@description('The name of the hub VNet to create for the Azure Firewall.')
param hubVnetName string = 'vnet-hub-nva-${resourceSuffix}'

@description('The address prefix for the hub VNet. Must not overlap with the spoke VNet.')
param hubVnetAddressPrefix string = '10.1.0.0/16'

@description('The address prefix for the AzureFirewallSubnet in the hub VNet. Minimum /26.')
param firewallSubnetPrefix string = '10.1.0.0/26'

// Azure Firewall

@description('The name of the Azure Firewall.')
param firewallName string = 'afw-nva-${resourceSuffix}'

@description('The name of the Azure Firewall Policy.')
param firewallPolicyName string = 'afwp-nva-${resourceSuffix}'


// ------------------
//    RESOURCES
// ------------------

// Existing infrastructure resources

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

// 1. Azure Firewall (hub VNet, peerings, route table, APIM subnet update)

// https://learn.microsoft.com/azure/templates/microsoft.network/azurefirewalls
module firewallModule '../../shared/bicep/modules/network/v1/firewall.bicep' = {
  name: 'firewallModule'
  params: {
    location: location
    resourceSuffix: resourceSuffix
    firewallName: firewallName
    firewallPolicyName: firewallPolicyName
    hubVnetName: hubVnetName
    hubVnetAddressPrefix: hubVnetAddressPrefix
    firewallSubnetPrefix: firewallSubnetPrefix
    spokeVnetName: spokeVnetName
    spokeVnetAddressPrefix: spokeVnetAddressPrefix
    apimSubnetName: apimSubnetName
    apimSubnetPrefix: apimSubnetPrefix
    apimNsgName: apimNsgName
    apimVnetIntegration: apimVnetIntegration
    applicationRules: [
      {
        ruleType: 'ApplicationRule'
        name: 'AllowWeatherGovHttps'
        description: 'Allow HTTPS access to api.weather.gov for weather forecast data'
        sourceAddresses: ['*']
        protocols: [
          {
            protocolType: 'Https'
            port: 443
          }
        ]
        targetFqdns: ['api.weather.gov']
      }
    ]
  }
}

// 2. APIM APIs

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service/apis
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: if (!empty(apis)) {
  name: '${api.name}-${resourceSuffix}'
  params: {
    apimName: apimName
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    api: api
  }
  dependsOn: [firewallModule]
}]


// ------------------
//    MARK: OUTPUTS
// ------------------

output apimServiceId string = apimService.id
output apimServiceName string = apimService.name
output apimResourceGatewayURL string = apimService.properties.gatewayUrl
output firewallPrivateIpAddress string = firewallModule.outputs.firewallPrivateIpAddress
output firewallPublicIpAddress string = firewallModule.outputs.firewallPublicIpAddress

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
