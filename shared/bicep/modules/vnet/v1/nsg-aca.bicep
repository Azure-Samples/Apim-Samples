/**
 * @module nsg-aca-v1
 * @description Network Security Group for Azure Container Apps allowing traffic only from API Management
 */

// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location for the NSG')
param location string = resourceGroup().location

@description('Name of the NSG')
param nsgName string = 'nsg-aca'

@description('ACA subnet prefix for destination filtering')
param acaSubnetPrefix string

@description('APIM subnet prefix for source filtering')
param apimSubnetPrefix string

// Import the deny all inbound rule
import {nsgsr_denyAllInbound} from './nsg_rules.bicep'

// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.network/networksecuritygroups
resource nsgAca 'Microsoft.Network/networkSecurityGroups@2025-01-01' = {
  name: nsgName
  location: location
  properties: {
    securityRules: [
      // INBOUND Security Rules
      {
        name: 'AllowApimToAca'
        properties: {
          description: 'Allow inbound HTTPS traffic from APIM to Container Apps'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: apimSubnetPrefix
          destinationAddressPrefix: acaSubnetPrefix
          access: 'Allow'
          priority: 100
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowAzureLoadBalancerInbound'
        properties: {
          description: 'Allow Azure Load Balancer health probes for Container Apps'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: 'AzureLoadBalancer'
          destinationAddressPrefix: acaSubnetPrefix
          access: 'Allow'
          priority: 110
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowAcaControlPlane'
        properties: {
          description: 'Allow Container Apps control plane communication'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRanges: [
            '443'
            '4789'
            '5671'
            '5672'
          ]
          sourceAddressPrefix: 'MicrosoftContainerRegistry'
          destinationAddressPrefix: acaSubnetPrefix
          access: 'Allow'
          priority: 120
          direction: 'Inbound'
        }
      }
      nsgsr_denyAllInbound
      // OUTBOUND Security Rules
      {
        name: 'AllowAcaToInternet'
        properties: {
          description: 'Allow Container Apps to reach internet for container image pulls and other dependencies'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: acaSubnetPrefix
          destinationAddressPrefix: 'Internet'
          access: 'Allow'
          priority: 100
          direction: 'Outbound'
        }
      }
    ]
  }
}

// ------------------------------
//    OUTPUTS
// ------------------------------

output nsgId string = nsgAca.id
output nsgName string = nsgAca.name
