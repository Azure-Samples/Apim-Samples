// ------------------
//    IMPORTS
// ------------------

import {nsgsr_denyAllInbound} from '../../shared/bicep/modules/vnet/v1/nsg_rules.bicep'


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
param appgwSubnetName string = 'snet-appgw'

@description('The address prefixes for the VNet.')
param vnetAddressPrefixes array = [ '10.0.0.0/16' ]

@description('The address prefix for the APIM subnet.')
param apimSubnetPrefix string = '10.0.1.0/24'

@description('The address prefix for the ACA subnet. Requires a /23 or larger subnet for Consumption workloads.')
param acaSubnetPrefix string = '10.0.2.0/23'

@description('The address prefix for the Application Gateway subnet.')
param appgwSubnetPrefix string = '10.0.4.0/24'

// API Management
param apimName string = 'apim-${resourceSuffix}'
param apimSku string
param apis array = []
param policyFragments array = []

@description('APIM public access. Must be true during initial creation (Azure limitation). Can be disabled post-deployment.')
param apimPublicAccess bool = true

@description('Reveals the backend API information. Defaults to true. *** WARNING: This will expose backend API information to the caller - For learning & testing only! ***')
param revealBackendApiInfo bool = true

// Container Apps
param acaName string = 'aca-${resourceSuffix}'
param useACA bool = false

// Application Gateway
param appgwName string = 'appgw-${resourceSuffix}'
param keyVaultName string = 'kv-${resourceSuffix}'
param uamiName string = 'uami-${resourceSuffix}'

param setCurrentUserAsKeyVaultAdmin bool = false
param currentUserId string = ''

// ------------------
//    CONSTANTS
// ------------------

var IMG_HELLO_WORLD = 'simonkurtzmsft/helloworld:latest'
var IMG_MOCK_WEB_API = 'simonkurtzmsft/mockwebapi:1.0.0-alpha.1'
var CERT_NAME = 'appgw-cert'
var DOMAIN_NAME = 'api.apim-samples.contoso.com'
var APIM_V1_SKUS = ['Developer', 'Basic', 'Standard', 'Premium']
var APIM_V2_SKUS = ['BasicV2', 'StandardV2', 'PremiumV2']


// ------------------------------
//    VARIABLES
// ------------------------------

var azureRoles = loadJsonContent('../../shared/azure-roles.json')

// ------------------
//    FUNCTIONS
// ------------------

func is_apim_sku_v1(apimSku string) bool => contains(APIM_V1_SKUS, apimSku)
func is_apim_sku_v2(apimSku string) bool => contains(APIM_V2_SKUS, apimSku)

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

// 3. Network Watcher (required for NSG flow logs)
module networkWatcherModule '../../shared/bicep/modules/network-watcher/v1/network-watcher.bicep' = {
  name: 'networkWatcherModule'
  params: {
    location: location
  }
}

// 4. Virtual Network and Subnets
// https://learn.microsoft.com/azure/templates/microsoft.network/networksecuritygroups
resource nsgDefault 'Microsoft.Network/networkSecurityGroups@2025-01-01' = {
  name: 'nsg-default'
  location: location
  dependsOn: [
    networkWatcherModule
  ]
}

// App Gateway needs a specific NSG
// https://learn.microsoft.com/azure/templates/microsoft.network/networksecuritygroups
resource nsgAppGw 'Microsoft.Network/networkSecurityGroups@2025-01-01' = {
  name: 'nsg-appgw'
  location: location
  dependsOn: [
    networkWatcherModule
  ]
  properties: {
    securityRules: [
      {
        name: 'AllowGatewayManagerInbound'
        properties: {
          description: 'Allow Azure infrastructure communication'
          protocol: 'TCP'
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
          description: 'Allow HTTPS traffic'
          protocol: 'TCP'
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
          description: 'Allow Azure Load Balancer'
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

// APIM V1 needs a specific NSG: https://learn.microsoft.com/en-us/azure/api-management/api-management-using-with-internal-vnet#configure-nsg-rules
// https://learn.microsoft.com/azure/templates/microsoft.network/networksecuritygroups
resource nsgApimV1 'Microsoft.Network/networkSecurityGroups@2025-01-01' = if (is_apim_sku_v1(apimSku)) {
// resource nsgApimV1 'Microsoft.Network/networkSecurityGroups@2025-01-01' = {
  name: 'nsg-apim'
  location: location
  dependsOn: [
    networkWatcherModule
  ]
  properties: {
    securityRules: [
      // INBOUND Security Rules
      {
        name: 'AllowApimInbound'
        properties: {
          description: 'Allow Management endpoint for Azure portal and Powershell traffic'
          protocol: 'TCP'
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
          description: 'Allow Azure Load Balancer'
          protocol: 'TCP'
          sourcePortRange: '*'
          destinationPortRange: '6390'
          sourceAddressPrefix: 'AzureLoadBalancer'
          destinationAddressPrefix: apimSubnetPrefix
          access: 'Allow'
          priority: 110
          direction: 'Inbound'
        }
      }
      // Limit ingress to traffic from App Gateway subnet, forcing both internal and external traffic to traverse App Gateway
      {
        name: 'AllowAppGatewayToApim'
        properties: {
          description: 'Allows inbound App Gateway traffic to APIM'
          protocol: 'TCP'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: appgwSubnetPrefix
          destinationAddressPrefix: apimSubnetPrefix
          access: 'Allow'
          priority: 120
          direction: 'Inbound'
        }
      }
      nsgsr_denyAllInbound
      // OUTBOUND Security Rules
      {
        name: 'AllowApimToStorage'
        properties: {
          description: 'Allow APIM to reach Azure Storage endpoints for core service functionality (i.e. pull binaries to provision units, etc.)'
          protocol: 'TCP'
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
          description: 'Allow APIM to reach Azure SQL endpoints for core service functionality'
          protocol: 'TCP'
          sourcePortRange: '*'
          destinationPortRange: '1433'
          sourceAddressPrefix: 'VirtualNetwork'
          destinationAddressPrefix: 'SQL'
          access: 'Allow'
          priority: 110
          direction: 'Outbound'
        }
      }
      {
        name: 'AllowApimToKeyVault'
        properties: {
          description: 'Allow APIM to reach Azure Key Vault endpoints for core service functionality'
          protocol: 'TCP'
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
          description: 'Allow APIM to reach Azure Monitor to publish diagnostics logs, metrics, resource health, and application insights'
          protocol: 'TCP'
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
            id: is_apim_sku_v1(apimSku) ? nsgApimV1.id : nsgDefault.id
          }
          // Delegations need to be conditional. If using V1 SKU (Developer), then we cannot delegate the subnet, so we need to check for V2.
          delegations: is_apim_sku_v2(apimSku) ? [
            {
              name: 'Microsoft.Web/serverFarms'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ] : []
        }
      }
      // ACA Subnet
      {
        name: acaSubnetName
        properties: {
          addressPrefix: acaSubnetPrefix
          networkSecurityGroup: {
            id: nsgDefault.id
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
      // App Gateway Subnet
      {
        name: appgwSubnetName
        properties: {
          addressPrefix: appgwSubnetPrefix
          networkSecurityGroup: {
            id: nsgAppGw.id
          }
        }
      }
    ]
  }
}

var apimSubnetResourceId  = '${vnetModule.outputs.vnetId}/subnets/${apimSubnetName}'
var acaSubnetResourceId   = '${vnetModule.outputs.vnetId}/subnets/${acaSubnetName}'
var appgwSubnetResourceId = '${vnetModule.outputs.vnetId}/subnets/${appgwSubnetName}'

// 5. User Assigned Managed Identity
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/managed-identity/user-assigned-identity
module uamiModule 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.2' = {
  name: 'uamiModule'
  params: {
    name: uamiName
    location: location
  }
}

// 6. Key Vault
// https://learn.microsoft.com/azure/templates/microsoft.keyvault/vaults
// This assignment is helpful for testing to allow you to examine and administer the Key Vault. Adjust accordingly for real workloads!
var keyVaultAdminRoleAssignment = setCurrentUserAsKeyVaultAdmin && !empty(currentUserId) ? [
  {
    roleDefinitionIdOrName: azureRoles.KeyVaultAdministrator
    principalId: currentUserId
    principalType: 'User'
  }
] : []

var keyVaultServiceRoleAssignments = [
  {
    // Key Vault Certificate User (for App Gateway to read certificates)
    roleDefinitionIdOrName: azureRoles.KeyVaultCertificateUser
    principalId: uamiModule.outputs.principalId
    principalType: 'ServicePrincipal'
  }
]

// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/key-vault/vault
module keyVaultModule 'br/public:avm/res/key-vault/vault:0.13.3' = {
  name: 'keyVaultModule'
  params: {
    name: keyVaultName
    location: location
    sku: 'standard'
    enableRbacAuthorization: true
    enablePurgeProtection: false  // Disabled for learning/testing scenarios to facilitate resource cleanup. Set to true in production!
    roleAssignments: concat(keyVaultAdminRoleAssignment, keyVaultServiceRoleAssignments)
  }
}

// 7. Public IP for Application Gateway
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/network/public-ip-address
module appgwPipModule 'br/public:avm/res/network/public-ip-address:0.9.1' = {
  name: 'appgwPipModule'
  params: {
    name: 'pip-${appgwName}'
    location: location
    publicIPAllocationMethod: 'Static'
    skuName: 'Standard'
    skuTier: 'Regional'
  }
}

// 8. WAF Policy for Application Gateway
// https://learn.microsoft.com/azure/templates/microsoft.network/applicationgatewaywebapplicationfirewallpolicies
resource wafPolicy 'Microsoft.Network/ApplicationGatewayWebApplicationFirewallPolicies@2025-01-01' = {
  name: 'waf-${resourceSuffix}'
  location: location
  properties: {
    customRules: []
    policySettings: {
      requestBodyCheck: true
      maxRequestBodySizeInKb: 128
      fileUploadLimitInMb: 100
      state: 'Enabled'
      mode: 'Detection'  // Use 'Prevention' in production
    }
    managedRules: {
      managedRuleSets: [
        {
          // Ruleset is defined here: https://github.com/Azure/azure-cli/pull/31289/files
          ruleSetType: 'Microsoft_DefaultRuleSet'
          ruleSetVersion: '2.1'
        }
      ]
    }
  }
}

// 9. Azure Container App Environment (ACAE)
module acaEnvModule '../../shared/bicep/modules/aca/v1/environment.bicep' = if (useACA) {
  name: 'acaEnvModule'
  params: {
    name: 'cae-${resourceSuffix}'
    logAnalyticsWorkspaceCustomerId: lawModule.outputs.customerId
    logAnalyticsWorkspaceSharedKey: lawModule.outputs.clientSecret
    subnetResourceId: acaSubnetResourceId
  }
}

// 10. Azure Container Apps (ACA) for Mock Web API
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

// 11. API Management (VNet Internal)
module apimModule '../../shared/bicep/modules/apim/v1/apim.bicep' = {
  name: 'apimModule'
  params: {
    apimName: apimName
    apimSku: apimSku
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    apimSubnetResourceId: apimSubnetResourceId
    publicAccess: apimPublicAccess
    apimVirtualNetworkType: 'Internal'
    globalPolicyXml: revealBackendApiInfo ? loadTextContent('../../shared/apim-policies/all-apis-reveal-backend.xml') : loadTextContent('../../shared/apim-policies/all-apis.xml')
  }
}

// 12. APIM Policy Fragments
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

// 13. APIM Backends for ACA
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

// 14. APIM APIs
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

// 15. Application Gateway
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/network/application-gateway
module appgwModule 'br/public:avm/res/network/application-gateway:0.7.2' = {
  name: 'appgwModule'
  params: {
    name: appgwName
    location: location
    sku: 'WAF_v2'
    firewallPolicyResourceId: wafPolicy.id
    enableHttp2: true
    capacity: 1
    availabilityZones: [
      1
    ]
    gatewayIPConfigurations: [
      {
        name: 'appGatewayIpConfig'
        properties: {
          subnet: {
            id: appgwSubnetResourceId
          }
        }
      }
    ]
    frontendIPConfigurations: [
      {
        name: 'appGatewayFrontendPublicIP'
        properties: {
          publicIPAddress: {
            id: appgwPipModule.outputs.resourceId
          }
        }
      }
    ]
    frontendPorts: [
      {
        name: 'port_443'
        properties: {
          port: 443
        }
      }
    ]
    sslCertificates: [
      {
        name: CERT_NAME
        properties: {
          keyVaultSecretId: '${keyVaultModule.outputs.uri}secrets/${CERT_NAME}'
        }
      }
    ]
    managedIdentities: {
      userAssignedResourceIds: [
        uamiModule.outputs.resourceId
      ]
    }
    backendAddressPools: [
      {
        name: 'apim-backend-pool'
        properties: {
          backendAddresses: [
            {
              ipAddress: apimModule.outputs.privateIpAddresses[0]
            }
          ]
        }
      }
    ]
    backendHttpSettingsCollection: [
      {
        name: 'apim-https-settings'
        properties: {
          port: 443
          protocol: 'Https'
          cookieBasedAffinity: 'Disabled'
          pickHostNameFromBackendAddress: false
          hostName: '${apimName}.azure-api.net'
          requestTimeout: 20
          probe: {
            id: resourceId('Microsoft.Network/applicationGateways/probes', appgwName, 'apim-probe')
          }
        }
      }
    ]
    httpListeners: [
      {
        name: 'https-listener'
        properties: {
          frontendIPConfiguration: {
            id: resourceId('Microsoft.Network/applicationGateways/frontendIPConfigurations', appgwName, 'appGatewayFrontendPublicIP')
          }
          frontendPort: {
            id: resourceId('Microsoft.Network/applicationGateways/frontendPorts', appgwName, 'port_443')
          }
          protocol: 'Https'
          sslCertificate: {
            id: resourceId('Microsoft.Network/applicationGateways/sslCertificates', appgwName, CERT_NAME)
          }
          hostName: DOMAIN_NAME
        }
      }
    ]
    requestRoutingRules: [
      {
        name: 'rule-1'
        properties: {
          ruleType: 'Basic'
          httpListener: {
            id: resourceId('Microsoft.Network/applicationGateways/httpListeners', appgwName, 'https-listener')
          }
          backendAddressPool: {
            id: resourceId('Microsoft.Network/applicationGateways/backendAddressPools', appgwName, 'apim-backend-pool')
          }
          backendHttpSettings: {
            id: resourceId('Microsoft.Network/applicationGateways/backendHttpSettingsCollection', appgwName, 'apim-https-settings')
          }
          priority: 100
        }
      }
    ]
    probes: [
      {
        name: 'apim-probe'
        properties: {
          protocol: 'Https'
          path: '/status-0123456789abcdef'
          interval: 30
          timeout: 30
          unhealthyThreshold: 3
          pickHostNameFromBackendHttpSettings: true
        }
      }
    ]
  }
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
output appGatewayName string = appgwModule.outputs.name
output appGatewayDomainName string = DOMAIN_NAME
output appGatewayFrontendUrl string = 'https://${DOMAIN_NAME}'
output appgwPublicIpAddress string = appgwPipModule.outputs.ipAddress

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
