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
param privateEndpointSubnetName string = 'snet-pe'

@description('The address prefixes for the VNet.')
param vnetAddressPrefixes array = [ '10.0.0.0/16' ]

@description('The address prefix for the APIM subnet.')
param apimSubnetPrefix string = '10.0.1.0/24'

@description('The address prefix for the ACA subnet. Requires a /23 or larger subnet for Consumption workloads.')
param acaSubnetPrefix string = '10.0.2.0/23'

@description('The address prefix for the Application Gateway subnet.')
param appgwSubnetPrefix string = '10.0.4.0/24'

@description('The address prefix for the Private Endpoint subnet.')
param privateEndpointSubnetPrefix string = '10.0.5.0/24'

// API Management
param apimName string = 'apim-${resourceSuffix}'
param apimSku string
param apis array = []
param policyFragments array = []

@description('Set to true to make APIM publicly accessible. If false, APIM will be deployed into a VNet subnet for egress only.')
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


// ------------------------------
//    VARIABLES
// ------------------------------

var azureRoles = loadJsonContent('../../shared/azure-roles.json')


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

// 3. Storage Account for NSG Flow Logs
module storageFlowLogsModule '../../shared/bicep/modules/vnet/v1/storage-flowlogs.bicep' = {
  name: 'storageFlowLogsModule'
  params: {
    location: location
    resourceSuffix: resourceSuffix
  }
}

// 4. Virtual Network and Subnets
resource nsgDefault 'Microsoft.Network/networkSecurityGroups@2025-01-01' = {
  name: 'nsg-default'
  location: location
}

// App Gateway needs a specific NSG
resource nsgAppGw 'Microsoft.Network/networkSecurityGroups@2025-01-01' = {
  name: 'nsg-appgw'
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
          description: 'Allow HTTPS traffic from internet'
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

// NSG for APIM with Private Link from Application Gateway
module nsgApimModule '../../shared/bicep/modules/vnet/v1/nsg-apim-pe.bicep' = {
  name: 'nsgApimModule'
  params: {
    location: location
    nsgName: 'nsg-apim'
    apimSubnetPrefix: apimSubnetPrefix
    allowAppGateway: true
    appgwSubnetPrefix: appgwSubnetPrefix
  }
}

// NSG for Container Apps - only allow traffic from APIM
module nsgAcaModule '../../shared/bicep/modules/vnet/v1/nsg-aca.bicep' = if (useACA) {
  name: 'nsgAcaModule'
  params: {
    location: location
    nsgName: 'nsg-aca'
    acaSubnetPrefix: acaSubnetPrefix
    apimSubnetPrefix: apimSubnetPrefix
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
            id: nsgApimModule.outputs.nsgId
          }
          delegations: [
            {
              name: 'Microsoft.Web/serverFarms'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ]
        }
      }
      // ACA Subnet
      {
        name: acaSubnetName
        properties: {
          addressPrefix: acaSubnetPrefix
          networkSecurityGroup: {
            id: useACA ? nsgAcaModule.outputs.nsgId : nsgDefault.id
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
      // Private Endpoint Subnet
      {
        name: privateEndpointSubnetName
        properties: {
          addressPrefix: privateEndpointSubnetPrefix
          networkSecurityGroup: {
            id: nsgDefault.id
          }
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

var apimSubnetResourceId  = '${vnetModule.outputs.vnetId}/subnets/${apimSubnetName}'
var acaSubnetResourceId   = '${vnetModule.outputs.vnetId}/subnets/${acaSubnetName}'
var appgwSubnetResourceId = '${vnetModule.outputs.vnetId}/subnets/${appgwSubnetName}'
var peSubnetResourceId    = '${vnetModule.outputs.vnetId}/subnets/${privateEndpointSubnetName}'

// 5. NSG Flow Logs and Traffic Analytics

// NSG Flow Logs for Application Gateway
module nsgFlowLogsAppGwModule '../../shared/bicep/modules/vnet/v1/nsg-flow-logs.bicep' = {
  name: 'nsgFlowLogsAppGwModule'
  params: {
    location: location
    flowLogName: 'fl-nsg-appgw-${resourceSuffix}'
    nsgResourceId: nsgAppGw.id
    storageAccountResourceId: storageFlowLogsModule.outputs.storageAccountId
    logAnalyticsWorkspaceResourceId: lawId
    retentionDays: 7
    enableTrafficAnalytics: true
  }
}

// NSG Flow Logs for APIM
module nsgFlowLogsApimModule '../../shared/bicep/modules/vnet/v1/nsg-flow-logs.bicep' = {
  name: 'nsgFlowLogsApimModule'
  params: {
    location: location
    flowLogName: 'fl-nsg-apim-${resourceSuffix}'
    nsgResourceId: nsgApimModule.outputs.nsgId
    storageAccountResourceId: storageFlowLogsModule.outputs.storageAccountId
    logAnalyticsWorkspaceResourceId: lawId
    retentionDays: 7
    enableTrafficAnalytics: true
  }
}

// NSG Flow Logs for ACA
module nsgFlowLogsAcaModule '../../shared/bicep/modules/vnet/v1/nsg-flow-logs.bicep' = if (useACA) {
  name: 'nsgFlowLogsAcaModule'
  params: {
    location: location
    flowLogName: 'fl-nsg-aca-${resourceSuffix}'
    nsgResourceId: nsgAcaModule.outputs.nsgId
    storageAccountResourceId: storageFlowLogsModule.outputs.storageAccountId
    logAnalyticsWorkspaceResourceId: lawId
    retentionDays: 7
    enableTrafficAnalytics: true
  }
}

// 6. User Assigned Managed Identity
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/managed-identity/user-assigned-identity
module uamiModule 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.2' = {
  name: 'uamiModule'
  params: {
    name: uamiName
    location: location
  }
}

// 7. Key Vault
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

// 8. Public IP for Application Gateway
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

// 9. WAF Policy for Application Gateway
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

// 10. Azure Container App Environment (ACAE)
module acaEnvModule '../../shared/bicep/modules/aca/v1/environment.bicep' = if (useACA) {
  name: 'acaEnvModule'
  params: {
    name: 'cae-${resourceSuffix}'
    logAnalyticsWorkspaceCustomerId: lawModule.outputs.customerId
    logAnalyticsWorkspaceSharedKey: lawModule.outputs.clientSecret
    subnetResourceId: acaSubnetResourceId
  }
}

// 11. Azure Container Apps (ACA) for Mock Web API
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

// 12. API Management
module apimModule '../../shared/bicep/modules/apim/v1/apim.bicep' = {
  name: 'apimModule'
  params: {
    apimName: apimName
    apimSku: apimSku
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    apimSubnetResourceId: apimSubnetResourceId
    publicAccess: apimPublicAccess
    globalPolicyXml: revealBackendApiInfo ? loadTextContent('../../shared/apim-policies/all-apis-reveal-backend.xml') : loadTextContent('../../shared/apim-policies/all-apis.xml')
  }
}

// 13. APIM Policy Fragments
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

// 14. APIM Backends for ACA
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

// 15. APIM APIs
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

// 16. Private Endpoint for APIM
// https://learn.microsoft.com/azure/templates/microsoft.network/privateendpoints
resource apimPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: 'pe-apim-${resourceSuffix}'
  location: location
  properties: {
    subnet: {
      id: peSubnetResourceId
    }
    privateLinkServiceConnections: [
      {
        name: 'apim-connection'
        properties: {
          privateLinkServiceId: apimModule.outputs.id
          groupIds: [
            'Gateway'
          ]
        }
      }
    ]
  }
}

// 17. Private DNS Zone Group for APIM Private Endpoint
// https://learn.microsoft.com/azure/templates/microsoft.network/privateendpoints/privatednszoneegroups
resource apimPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  name: 'apim-dns-zone-group'
  parent: apimPrivateEndpoint
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-azure-api-net'
        properties: {
          privateDnsZoneId: apimDnsPrivateLinkModule.outputs.privateDnsZoneId
        }
      }
    ]
  }
}

// 18. APIM Private DNS Zone, VNet Link
module apimDnsPrivateLinkModule '../../shared/bicep/modules/dns/v1/dns-private-link.bicep' = {
  name: 'apimDnsPrivateLinkModule'
  params: {
    dnsZoneName: 'privatelink.azure-api.net'
    vnetId: vnetModule.outputs.vnetId
    vnetLinkName: 'link-apim'
    enableDnsZoneGroup: false
    dnsZoneGroupName: 'dnsZoneGroup-apim'
    dnsZoneConfigName: 'config-apim'
  }
}

// 19. ACA Private DNS Zone
module acaDnsPrivateZoneModule '../../shared/bicep/modules/dns/v1/aca-dns-private-zone.bicep' = if (useACA) {
  name: 'acaDnsPrivateZoneModule'
  params: {
    acaEnvironmentRandomSubdomain: acaEnvModule!.outputs.environmentRandomSubdomain
    acaEnvironmentStaticIp: acaEnvModule!.outputs.environmentStaticIp
    vnetId: vnetModule.outputs.vnetId
  }
}

// 20. Application Gateway
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/network/application-gateway
module appgwModule 'br/public:avm/res/network/application-gateway:0.7.2' = {
  name: 'appgwModule'
  params: {
    name: appgwName
    location: location
    sku: 'WAF_v2'
    firewallPolicyResourceId: wafPolicy.id
    enableHttp2: true
    // Create only one instance (default is 2) for cost savings. Adjust accordingly for production workloads (use scaling, minimum instances, no maximum instances, etc.).
    capacity: 1
    // Use minimal AZs (1) for cost savings. Adjust accordingly for production workloads.
    // Setting to 1 availability zone yields the following Azure Advisor message:
    // High Impact - Deploy your Application Gateway across Availability Zones
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
              fqdn: '${apimName}.azure-api.net'
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
          pickHostNameFromBackendAddress: true
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
output apimPrivateEndpointId string = apimPrivateEndpoint.id
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
