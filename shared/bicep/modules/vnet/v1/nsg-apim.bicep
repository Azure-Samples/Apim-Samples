/**
 * @module nsg-apim-v1
 * @description Network Security Group for Azure API Management in VNet mode.
 *              Supports inbound traffic from Application Gateway, Azure Front Door (via Private Link), or both.
 *              Inbound rules (management, load balancer, deny all) always apply.
 *              App Gateway and Front Door inbound rules are conditionally included via parameters.
 *              Outbound rules are conditionally included based on the VNet mode and APIM SKU:
 *              - Storage and Key Vault are required for all tiers (injection and integration alike).
 *              - SQL and Monitor are additionally required for classic VNet-injection tiers (Developer, Premium).
 *
 * INBOUND NSG rule matrix (as of 03/02/2026):
 *   PE = Private Endpoint-backed inbound path.
 *   If allowAppGateway = Application Gateway scenario.
 *   If allowFrontDoorBackend = Azure Front Door via PE scenario.
 *
 *   SKU          | VNet Mode   | APIM Mgmt (3443) | Load Balancer (6390) | App Gateway (443)  | Front Door PE (443)      | Deny All
 *   -------------|-------------|------------------|----------------------|--------------------|--------------------------|---------
 *   Developer    | injection   | Yes              | Yes                  | If allowAppGateway | If allowFrontDoorBackend | Yes
 *   Basic        | (none)      |  -               |  -                   |  -                 |  -                       |  -
 *   Standard     | (none)      |  -               |  -                   |  -                 |  -                       |  -
 *   Premium      | injection   | Yes              | Yes                  | If allowAppGateway | If allowFrontDoorBackend | Yes
 *   Basicv2      | integration | Yes              | Yes                  | If allowAppGateway | If allowFrontDoorBackend | Yes
 *   Standardv2   | injection   | Yes              | Yes                  | If allowAppGateway | If allowFrontDoorBackend | Yes
 *   Standardv2   | integration | Yes              | Yes                  | If allowAppGateway | If allowFrontDoorBackend | Yes
 *   Premiumv2    | injection   | Yes              | Yes                  | If allowAppGateway | If allowFrontDoorBackend | Yes
 *   Premiumv2    | integration | Yes              | Yes                  | If allowAppGateway | If allowFrontDoorBackend | Yes
 *
 * OUTBOUND NSG rule matrix (as of 03/02/2026):
 *
 *   SKU          | VNet Mode   | Storage          | Key Vault            | SQL                | Monitor
 *   -------------|-------------|------------------|----------------------|--------------------|----------
 *   Developer    | injection   | Yes              | Yes                  | Yes                | Yes
 *   Basic        | (none)      |  -               |  -                   |  -                 |  -
 *   Standard     | (none)      |  -               |  -                   |  -                 |  -
 *   Premium      | injection   | Yes              | Yes                  | Yes                | Yes
 *   Basicv2      | integration | Yes              | Yes                  | No                 | No
 *   Standardv2   | injection   | Yes              | Yes                  | No                 | No
 *   Standardv2   | integration | Yes              | Yes                  | No                 | No
 *   Premiumv2    | injection   | Yes              | Yes                  | No                 | No
 *   Premiumv2    | integration | Yes              | Yes                  | No                 | No
 *
 * @see Classic tiers - required NSG rules for VNet injection:
 *      https://learn.microsoft.com/azure/api-management/api-management-using-with-internal-vnet#configure-nsg-rules
 * @see V2 tiers - VNet integration (outbound only, no specific NSG rules required):
 *      https://learn.microsoft.com/azure/api-management/integrate-vnet-outbound#network-security-group
 * @see V2 tiers - VNet injection (outbound rules for Storage and Key Vault, but not SQL or Monitor):
 *      https://learn.microsoft.com/azure/api-management/inject-vnet-v2#network-security-group
 * @see Comprehensive VNet reference (all tiers):
 *      https://learn.microsoft.com/azure/api-management/virtual-network-reference
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

// Import the deny all inbound rule
import {nsgsr_denyAllInbound} from './nsg_rules.bicep'


// ------------------------------
//    CONSTANTS
// ------------------------------

// Classic tiers that additionally require SQL and Monitor outbound rules when VNet-injected
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
      // INBOUND Security Rules
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
      // INBOUND: Application Gateway (conditional)
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
      // INBOUND: Azure Front Door Backend via Private Link (conditional)
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
      // OUTBOUND: Storage + Key Vault — required for all tiers (injection and integration)
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
      // OUTBOUND: SQL + Monitor — additionally required for classic VNet-injected tiers (Developer, Premium)
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
