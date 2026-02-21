/**
 * @module nsg-apim-pe-v1
 * @description Network Security Group for Azure API Management with Private Link from Front Door or Application Gateway
 */

// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location for the NSG')
param location string = resourceGroup().location

@description('Name of the NSG')
param nsgName string = 'nsg-apim'

@description('APIM subnet prefix for destination filtering')
param apimSubnetPrefix string

@description('Whether to allow traffic from Azure Front Door Backend service tag')
param allowFrontDoorBackend bool = false

@description('Whether to allow traffic from Application Gateway subnet')
param allowAppGateway bool = false

@description('Application Gateway subnet prefix for source filtering (required if allowAppGateway is true)')
param appgwSubnetPrefix string = ''

// Import the deny all inbound rule
import {nsgsr_denyAllInbound} from './nsg_rules.bicep'

// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.network/networksecuritygroups
resource nsgApim 'Microsoft.Network/networkSecurityGroups@2025-01-01' = {
  name: nsgName
  location: location
  properties: {
    securityRules: concat(
      [
        // INBOUND Security Rules
        {
          name: 'AllowApimManagement'
          properties: {
            description: 'Allow Management endpoint for Azure portal and PowerShell traffic'
            protocol: 'Tcp'
            sourcePortRange: '*'
            destinationPortRange: '3443'
            sourceAddressPrefix: 'ApiManagement'
            destinationAddressPrefix: 'VirtualNetwork'
            access: 'Allow'
            priority: 100
            direction: 'Inbound'
          }
        }
        {
          name: 'AllowAzureLoadBalancerInbound'
          properties: {
            description: 'Allow Azure Load Balancer health probes'
            protocol: 'Tcp'
            sourcePortRange: '*'
            destinationPortRange: '6390'
            sourceAddressPrefix: 'AzureLoadBalancer'
            destinationAddressPrefix: apimSubnetPrefix
            access: 'Allow'
            priority: 110
            direction: 'Inbound'
          }
        }
      ],
      allowFrontDoorBackend ? [
        {
          name: 'AllowFrontDoorBackendToApim'
          properties: {
            description: 'Allow inbound HTTPS traffic from Azure Front Door Backend to APIM via Private Link'
            protocol: 'Tcp'
            sourcePortRange: '*'
            destinationPortRange: '443'
            sourceAddressPrefix: 'AzureFrontDoor.Backend'
            destinationAddressPrefix: apimSubnetPrefix
            access: 'Allow'
            priority: 120
            direction: 'Inbound'
          }
        }
      ] : [],
      allowAppGateway && !empty(appgwSubnetPrefix) ? [
        {
          name: 'AllowAppGatewayToApim'
          properties: {
            description: 'Allow inbound HTTPS traffic from Application Gateway to APIM via Private Link'
            protocol: 'Tcp'
            sourcePortRange: '*'
            destinationPortRange: '443'
            sourceAddressPrefix: appgwSubnetPrefix
            destinationAddressPrefix: apimSubnetPrefix
            access: 'Allow'
            priority: 130
            direction: 'Inbound'
          }
        }
      ] : [],
      [
        nsgsr_denyAllInbound
        // OUTBOUND Security Rules
        {
          name: 'AllowApimToStorage'
          properties: {
            description: 'Allow APIM to reach Azure Storage for core service functionality'
            protocol: 'Tcp'
            sourcePortRange: '*'
            destinationPortRange: '443'
            sourceAddressPrefix: 'VirtualNetwork'
            destinationAddressPrefix: 'Storage'
            access: 'Allow'
            priority: 100
            direction: 'Outbound'
          }
        }
        {
          name: 'AllowApimToSql'
          properties: {
            description: 'Allow APIM to reach Azure SQL for core service functionality'
            protocol: 'Tcp'
          sourcePortRange: '*'
            destinationPortRange: '1433'
            sourceAddressPrefix: 'VirtualNetwork'
            destinationAddressPrefix: 'Sql'
            access: 'Allow'
            priority: 110
            direction: 'Outbound'
          }
        }
        {
          name: 'AllowApimToKeyVault'
          properties: {
            description: 'Allow APIM to reach Azure Key Vault for core service functionality'
            protocol: 'Tcp'
            sourcePortRange: '*'
            destinationPortRange: '443'
            sourceAddressPrefix: 'VirtualNetwork'
            destinationAddressPrefix: 'AzureKeyVault'
            access: 'Allow'
            priority: 120
            direction: 'Outbound'
          }
        }
        {
          name: 'AllowApimToMonitor'
          properties: {
            description: 'Allow APIM to reach Azure Monitor for diagnostics logs, metrics, and Application Insights'
            protocol: 'Tcp'
            sourcePortRange: '*'
            destinationPortRanges: [
              '1886'
              '443'
            ]
            sourceAddressPrefix: 'VirtualNetwork'
            destinationAddressPrefix: 'AzureMonitor'
            access: 'Allow'
            priority: 130
            direction: 'Outbound'
          }
        }
      ]
    )
  }
}

// ------------------------------
//    OUTPUTS
// ------------------------------

output nsgId string = nsgApim.id
output nsgName string = nsgApim.name
