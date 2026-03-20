/**
 * @module firewall-v1
 * @description Deploys an Azure Firewall NVA in a hub VNet, peers it with an existing spoke VNet,
 * and routes APIM egress traffic through the firewall via a route table.
 * The module always includes the standard APIM management network rules. Additional network and
 * application rules can be supplied by the caller.
 */


// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for resources. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

// Azure Firewall

@description('The name of the Azure Firewall.')
param firewallName string = 'afw-nva-${resourceSuffix}'

@description('The name of the Azure Firewall Policy.')
param firewallPolicyName string = 'afwp-nva-${resourceSuffix}'

// Hub VNet

@description('The name of the hub VNet to create for the Azure Firewall.')
param hubVnetName string = 'vnet-hub-nva-${resourceSuffix}'

@description('The address prefix for the hub VNet. Must not overlap with the spoke VNet.')
param hubVnetAddressPrefix string = '10.1.0.0/16'

@description('The address prefix for the AzureFirewallSubnet in the hub VNet. Minimum /26.')
param firewallSubnetPrefix string = '10.1.0.0/26'

// Spoke VNet (existing infrastructure VNet)

@description('The name of the existing spoke VNet (infrastructure VNet).')
param spokeVnetName string = 'vnet-${resourceSuffix}'

@description('The address prefix of the spoke VNet. Used to create a local route so VNet traffic bypasses the NVA.')
param spokeVnetAddressPrefix string = '10.0.0.0/16'

// APIM subnet (in the spoke VNet)

@description('The name of the APIM subnet in the spoke VNet.')
param apimSubnetName string = 'snet-apim'

@description('The address prefix of the APIM subnet.')
param apimSubnetPrefix string = '10.0.1.0/24'

@description('The name of the NSG currently attached to the APIM subnet (nsg-apim or nsg-apim-strict).')
param apimNsgName string = 'nsg-apim'

@description('Set to true when APIM is running in VNet integration mode (V2 SKUs: Basicv2, Standardv2, Premiumv2). False for VNet injection (V1 SKUs: Developer, Premium).')
param apimVnetIntegration bool = false

// Firewall rules

@description('Additional network rules to add to the AllowApimManagementTraffic rule collection (priority 100), alongside the built-in APIM management rules.')
param additionalNetworkRules array = []

@description('Application rules to add to the firewall policy as an AllowedInternetApis rule collection (priority 200). Each entry must be a FirewallPolicyApplicationRule object. Leave empty to omit the application rule collection.')
param applicationRules array = []


// ------------------------------
//    RESOURCES
// ------------------------------

// Existing spoke VNet and NSG

// https://learn.microsoft.com/azure/templates/microsoft.network/virtualnetworks
resource spokeVnet 'Microsoft.Network/virtualNetworks@2024-05-01' existing = {
  name: spokeVnetName
}

// https://learn.microsoft.com/azure/templates/microsoft.network/networksecuritygroups
resource apimNsg 'Microsoft.Network/networkSecurityGroups@2025-01-01' existing = {
  name: apimNsgName
}

// 1. Azure Firewall Public IP

// https://learn.microsoft.com/azure/templates/microsoft.network/publicipaddresses
resource firewallPip 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: 'pip-${firewallName}'
  location: location
  sku: {
    name: 'Standard'
    tier: 'Regional'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
    publicIPAddressVersion: 'IPv4'
  }
}

// 2. Azure Firewall Policy

// https://learn.microsoft.com/azure/templates/microsoft.network/firewallpolicies
resource firewallPolicy 'Microsoft.Network/firewallPolicies@2024-05-01' = {
  name: firewallPolicyName
  location: location
  properties: {
    sku: {
      tier: 'Standard'
    }
    threatIntelMode: 'Deny'
  }
}

// 3. Azure Firewall Policy Rule Collection Group
//    Always includes the standard APIM management network rules.
//    Caller may supply additional network rules and application rules.

// https://learn.microsoft.com/azure/templates/microsoft.network/firewallpolicies/rulecollectiongroups
resource firewallRuleGroup 'Microsoft.Network/firewallPolicies/ruleCollectionGroups@2024-05-01' = {
  name: 'DefaultRuleCollectionGroup'
  parent: firewallPolicy
  properties: {
    priority: 300
    ruleCollections: concat(
      [
        // Network rules: allow APIM management-plane outbound traffic to Azure services
        {
          ruleCollectionType: 'FirewallPolicyFilterRuleCollection'
          name: 'AllowApimManagementTraffic'
          priority: 100
          action: {
            type: 'Allow'
          }
          rules: concat(
            [
              {
                ruleType: 'NetworkRule'
                name: 'AllowApimToAzureMonitor'
                description: 'APIM requires outbound access to Azure Monitor for diagnostics logs and metrics'
                ipProtocols: ['TCP']
                sourceAddresses: ['*']
                destinationAddresses: ['AzureMonitor']
                destinationPorts: ['443', '1886']
              }
              {
                ruleType: 'NetworkRule'
                name: 'AllowApimToStorage'
                description: 'APIM requires outbound access to Azure Storage for internal operations'
                ipProtocols: ['TCP']
                sourceAddresses: ['*']
                destinationAddresses: ['Storage']
                destinationPorts: ['443', '445']
              }
              {
                ruleType: 'NetworkRule'
                name: 'AllowApimToSql'
                description: 'APIM requires outbound access to Azure SQL for analytics'
                ipProtocols: ['TCP']
                sourceAddresses: ['*']
                destinationAddresses: ['Sql']
                destinationPorts: ['1433']
              }
              {
                ruleType: 'NetworkRule'
                name: 'AllowApimToKeyVault'
                description: 'APIM requires outbound access to Azure Key Vault for named value secrets'
                ipProtocols: ['TCP']
                sourceAddresses: ['*']
                destinationAddresses: ['AzureKeyVault']
                destinationPorts: ['443']
              }
              {
                ruleType: 'NetworkRule'
                name: 'AllowApimToEntraId'
                description: 'APIM requires outbound access to Microsoft Entra ID for authentication'
                ipProtocols: ['TCP']
                sourceAddresses: ['*']
                destinationAddresses: ['AzureActiveDirectory']
                destinationPorts: ['443']
              }
            ],
            additionalNetworkRules
          )
        }
      ],
      !empty(applicationRules) ? [
        // Application rules: allow HTTPS to specific internet FQDNs
        {
          ruleCollectionType: 'FirewallPolicyFilterRuleCollection'
          name: 'AllowedInternetApis'
          priority: 200
          action: {
            type: 'Allow'
          }
          rules: applicationRules
        }
      ] : []
    )
  }
}

// 4. Hub VNet with AzureFirewallSubnet

// https://learn.microsoft.com/azure/templates/microsoft.network/virtualnetworks
resource hubVnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: hubVnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [hubVnetAddressPrefix]
    }
    subnets: [
      {
        name: 'AzureFirewallSubnet'
        properties: {
          addressPrefix: firewallSubnetPrefix
        }
      }
    ]
  }
}

// 5. Azure Firewall

// https://learn.microsoft.com/azure/templates/microsoft.network/azurefirewalls
resource azureFirewall 'Microsoft.Network/azureFirewalls@2024-05-01' = {
  name: firewallName
  location: location
  properties: {
    sku: {
      name: 'AZFW_VNet'
      tier: 'Standard'
    }
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: '${hubVnet.id}/subnets/AzureFirewallSubnet'
          }
          publicIPAddress: {
            id: firewallPip.id
          }
        }
      }
    ]
    firewallPolicy: {
      id: firewallPolicy.id
    }
  }
  dependsOn: [firewallRuleGroup]
}

var firewallPrivateIp = azureFirewall.properties.ipConfigurations[0].properties.privateIPAddress

// 6. VNet Peering: Spoke → Hub

// https://learn.microsoft.com/azure/templates/microsoft.network/virtualnetworks/virtualnetworkpeerings
resource spokeToHubPeering 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2024-05-01' = {
  name: 'peer-spoke-to-hub'
  parent: spokeVnet
  properties: {
    remoteVirtualNetwork: {
      id: hubVnet.id
    }
    allowVirtualNetworkAccess: true
    allowForwardedTraffic: true
    allowGatewayTransit: false
    useRemoteGateways: false
  }
  dependsOn: [azureFirewall]
}

// 7. VNet Peering: Hub → Spoke

// https://learn.microsoft.com/azure/templates/microsoft.network/virtualnetworks/virtualnetworkpeerings
resource hubToSpokePeering 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2024-05-01' = {
  name: 'peer-hub-to-spoke'
  parent: hubVnet
  properties: {
    remoteVirtualNetwork: {
      id: spokeVnet.id
    }
    allowVirtualNetworkAccess: true
    allowForwardedTraffic: true
    allowGatewayTransit: false
    useRemoteGateways: false
  }
  dependsOn: [azureFirewall]
}

// 8. Route Table — forces internet traffic through Azure Firewall and keeps VNet traffic local

// https://learn.microsoft.com/azure/templates/microsoft.network/routetables
resource routeTable 'Microsoft.Network/routeTables@2024-05-01' = {
  name: 'rt-apim-nva-${resourceSuffix}'
  location: location
  properties: {
    disableBgpRoutePropagation: false
    routes: [
      {
        name: 'route-internet-via-nva'
        properties: {
          addressPrefix: '0.0.0.0/0'
          nextHopType: 'VirtualAppliance'
          nextHopIpAddress: firewallPrivateIp
        }
      }
      {
        name: 'route-spoke-vnet-local'
        properties: {
          addressPrefix: spokeVnetAddressPrefix
          nextHopType: 'VirtualNetwork'
        }
      }
    ]
  }
  dependsOn: [spokeToHubPeering, hubToSpokePeering]
}

// 9. Update APIM subnet — associate route table while preserving the existing NSG and delegations

// https://learn.microsoft.com/azure/templates/microsoft.network/virtualnetworks/subnets
resource apimSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  name: apimSubnetName
  parent: spokeVnet
  properties: {
    addressPrefix: apimSubnetPrefix
    networkSecurityGroup: {
      id: apimNsg.id
    }
    delegations: apimVnetIntegration ? [
      {
        name: 'delegation-apim'
        properties: {
          serviceName: 'Microsoft.Web/serverFarms'
        }
      }
    ] : []
    routeTable: {
      id: routeTable.id
    }
  }
}


// ------------------------------
//    OUTPUTS
// ------------------------------

output firewallPrivateIpAddress string = firewallPrivateIp
output firewallPublicIpAddress string = firewallPip.properties.ipAddress
output apimSubnetId string = apimSubnet.id
