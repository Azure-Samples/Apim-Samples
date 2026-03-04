/**
 * @module nsg-appgw-strict-v1
 * @description Strict Network Security Group for Azure Application Gateway subnets.
 *              Includes the required inbound rules for GatewayManager, HTTPS listener traffic,
 *              Azure Load Balancer probes, and a final deny-all inbound rule.
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
param nsgName string = 'nsg-appgw-strict'

// Import the deny all inbound rule
import {nsgsr_denyAllInbound} from './nsg_rules.bicep'


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
      nsgsr_denyAllInbound
    ]
  }
}

// ------------------------------
//    OUTPUTS
// ------------------------------

output nsgId string = nsgAppGw.id
output nsgName string = nsgAppGw.name
