/**
 * @module nsg-apim-strict-v1
 * @description Strict Network Security Group for Azure API Management in VNet mode.
 *              Supports inbound traffic from Application Gateway, Azure Front Door (via Private Link), or both.
 *              Inbound rules (management, load balancer, deny all) always apply.
 *              App Gateway and Front Door inbound rules are conditionally included via parameters.
 *              Outbound rules are conditionally included based on the VNet mode and APIM SKU:
 *              - Storage and Key Vault are required for all tiers (injection and integration alike).
 *              - SQL and Monitor are additionally required for classic VNet-injection tiers (Developer, Premium).
 */

// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location for the NSG')
param location string = resourceGroup().location

@description('Name of the NSG')
param nsgName string = 'nsg-apim-strict'

@description('APIM subnet prefix for destination filtering')
param apimSubnetPrefix string

@description('Whether to allow inbound HTTPS traffic from an Application Gateway subnet')
param allowAppGateway bool = false

@description('Application Gateway subnet prefix for source filtering (required when allowAppGateway is true)')
param appgwSubnetPrefix string = ''

@description('Whether to allow inbound HTTPS traffic from Azure Front Door Backend service tag (via Private Link)')
param allowFrontDoorBackend bool = false

@description('APIM SKU name. Classic tiers (Developer, Premium) with injection require additional outbound NSG rules for SQL and Monitor.')
param apimSku string

@allowed([
  'injection'
  'integration'
])
@description('VNet mode for the APIM instance. Classic tiers with injection require SQL and Monitor outbound rules beyond the baseline Storage and Key Vault rules.')
param vnetMode string

import {nsgsr_denyAllInbound} from './nsg_rules.bicep'

// ------------------------------
//    CONSTANTS
// ------------------------------

var CLASSIC_SKUS = ['Developer', 'Premium']

// ------------------------------
//    VARIABLES
// ------------------------------

var isClassicInjection = vnetMode == 'injection' && contains(CLASSIC_SKUS, apimSku)

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
      allowAppGateway && !empty(appgwSubnetPrefix) ? [
        {
          name: 'AllowAppGatewayToApim'
          properties: {
            description: 'Allow inbound HTTPS traffic from Application Gateway to APIM'
            protocol: 'Tcp'
            sourcePortRange: '*'
            destinationPortRange: '443'
            sourceAddressPrefix: appgwSubnetPrefix
            destinationAddressPrefix: apimSubnetPrefix
            access: 'Allow'
            priority: 120
            direction: 'Inbound'
          }
        }
      ] : [],
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
            priority: 130
            direction: 'Inbound'
          }
        }
      ] : [],
      [
        nsgsr_denyAllInbound
      ],
      [
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
          name: 'AllowApimToKeyVault'
          properties: {
            description: 'Allow APIM to reach Azure Key Vault for core service functionality'
            protocol: 'Tcp'
            sourcePortRange: '*'
            destinationPortRange: '443'
            sourceAddressPrefix: 'VirtualNetwork'
            destinationAddressPrefix: 'AzureKeyVault'
            access: 'Allow'
            priority: 110
            direction: 'Outbound'
          }
        }
      ],
      isClassicInjection ? [
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
      ] : []
    )
  }
}

// ------------------------------
//    OUTPUTS
// ------------------------------

output nsgId string = nsgApim.id
output nsgName string = nsgApim.name
