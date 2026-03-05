/**
 * @module nsg-appgw-v1
 * @description Permissive Network Security Group for Azure Application Gateway subnets.
 *              Builds on Azure's default NSG behavior and adds only the platform rules
 *              required for Application Gateway v2 to function without hindering the user.
 *
 * @see Application Gateway infrastructure configuration:
 *      https://learn.microsoft.com/azure/application-gateway/configuration-infrastructure
 */

// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location for the NSG')
param location string = resourceGroup().location

@description('Name of the NSG')
param nsgName string = 'nsg-appgw'


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.network/networksecuritygroups
resource nsgAppGw 'Microsoft.Network/networkSecurityGroups@2025-01-01' = {
  name: nsgName
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowGatewayManagerInbound'
        properties: {
          description: 'Allow Azure infrastructure communication'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '65200-65535'
          sourceAddressPrefix: 'GatewayManager'
          destinationAddressPrefix: '*'
          access: 'Allow'
          priority: 100
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowHTTPSInbound'
        properties: {
          description: 'Allow HTTPS listener traffic to Application Gateway'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
          access: 'Allow'
          priority: 110
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowAzureLoadBalancerInbound'
        properties: {
          description: 'Allow Azure Load Balancer health probes'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: 'AzureLoadBalancer'
          destinationAddressPrefix: '*'
          access: 'Allow'
          priority: 120
          direction: 'Inbound'
        }
      }
    ]
  }
}

// ------------------------------
//    OUTPUTS
// ------------------------------

output nsgId string = nsgAppGw.id
output nsgName string = nsgAppGw.name
