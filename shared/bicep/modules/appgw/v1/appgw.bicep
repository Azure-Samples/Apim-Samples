/**
 * @module appgw-v1
 * @description Minimal Azure Application Gateway (WAF_v2 capable) with a public frontend and a single backend pointing to APIM.
 * Frontend: HTTP on port 80 (no certs per requirement). Backend: HTTPS to APIM with health probe.
 */

// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Application Gateway name')
param appGatewayName string = 'ag-${resourceSuffix}'

@description('Subnet resource ID for the Application Gateway. Must be a dedicated subnet.')
param appGatewaySubnetResourceId string

@description('Backend hostname (FQDN) for APIM gateway. Example: apim-xyz.azure-api.net or apim-xyz.privatelink.azure-api.net')
param backendHostname string

@description('Health probe path for APIM. Defaults to status endpoint that requires no subscription key')
param probePath string = '/status-0123456789abcdef'

@description('Enable WAF. If false, Standard_v2 SKU is used. If true, WAF_v2 is used in Detection mode.')
param enableWaf bool = false

@description('Priority for the default request routing rule. Required from API version 2021-08-01 and later. Must be unique per rule and between 1 and 20000.')
param requestRoutingRulePriority int = 100

@description('Include an HTTP listener on port 80. Set to false to disable HTTP.')
param includeHttpListener bool = true

@description('Include an HTTPS listener on port 443. Requires sslCertKeyVaultSecretId or inline cert.')
param includeHttpsListener bool = false

@description('Key Vault secret ID of the PFX certificate to bind to the HTTPS listener. Example format: <vault uri>/secrets/<name>/<version> (use environment().suffixes.keyvaultDns to build URIs)')
@secure()
param sslCertKeyVaultSecretId string = ''

@description('Optional user-assigned identity resource ID to attach to the Application Gateway for Key Vault auth. If empty and includeHttpsListener is true, SystemAssigned identity is used.')
param userAssignedIdentityResourceId string = ''

// ------------------------------
//    VARIABLES
// ------------------------------

var pipName = 'pip-${appGatewayName}'
var useHttps = includeHttpsListener && !empty(sslCertKeyVaultSecretId)

// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.network/publicipaddresses
resource publicIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: pipName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.network/applicationgateways
resource appGateway 'Microsoft.Network/applicationGateways@2024-07-01' = {
  name: appGatewayName
  location: location
  properties: {
    sku: {
      name: enableWaf ? 'WAF_v2' : 'Standard_v2'
      tier: enableWaf ? 'WAF_v2' : 'Standard_v2'
      capacity: 1
    }
    gatewayIPConfigurations: [
      {
        name: 'appGatewayIpConfig'
        properties: {
          subnet: {
            id: appGatewaySubnetResourceId
          }
        }
      }
    ]
    frontendIPConfigurations: [
      {
        name: 'appGatewayFrontendIp'
        properties: {
          publicIPAddress: {
            id: publicIp.id
          }
        }
      }
    ]
    frontendPorts: union(
      includeHttpListener ? [
        {
          name: 'port-80'
          properties: {
            port: 80
          }
        }
      ] : [],
      useHttps ? [
        {
          name: 'port-443'
          properties: {
            port: 443
          }
        }
      ] : []
    )
    backendAddressPools: [
      {
        name: 'pool-apim'
        properties: {
          backendAddresses: [
            {
              fqdn: backendHostname
            }
          ]
        }
      }
    ]
    backendHttpSettingsCollection: [
      {
        name: 'bhs-https-apim'
        properties: {
          port: 443
          protocol: 'Https'
          pickHostNameFromBackendAddress: true
          requestTimeout: 30
          probe: {
            id: resourceId('Microsoft.Network/applicationGateways/probes', appGatewayName, 'probe-apim')
          }
        }
      }
    ]
    probes: [
      {
        name: 'probe-apim'
        properties: {
          protocol: 'Https'
          host: backendHostname
          path: probePath
          interval: 30
          timeout: 30
          unhealthyThreshold: 3
          pickHostNameFromBackendHttpSettings: false
          match: {
            body: ''
            statusCodes: [
              '200-399'
            ]
          }
        }
      }
    ]
    httpListeners: union(
      includeHttpListener ? [
        {
          name: 'listener-http'
          properties: {
            frontendIPConfiguration: {
              id: resourceId(
                'Microsoft.Network/applicationGateways/frontendIPConfigurations',
                appGatewayName,
                'appGatewayFrontendIp'
              )
            }
            frontendPort: {
              id: resourceId('Microsoft.Network/applicationGateways/frontendPorts', appGatewayName, 'port-80')
            }
            protocol: 'Http'
          }
        }
      ] : [],
      useHttps ? [
        {
          name: 'listener-https'
          properties: {
            frontendIPConfiguration: {
              id: resourceId(
                'Microsoft.Network/applicationGateways/frontendIPConfigurations',
                appGatewayName,
                'appGatewayFrontendIp'
              )
            }
            frontendPort: {
              id: resourceId('Microsoft.Network/applicationGateways/frontendPorts', appGatewayName, 'port-443')
            }
            protocol: 'Https'
            sslCertificate: {
              id: resourceId('Microsoft.Network/applicationGateways/sslCertificates', appGatewayName, 'sslcert-https')
            }
          }
        }
      ] : []
    )

    sslCertificates: useHttps ? [
      {
        name: 'sslcert-https'
        properties: {
          keyVaultSecretId: sslCertKeyVaultSecretId
        }
      }
    ] : []
    requestRoutingRules: [
      {
        name: 'rule-default'
        properties: {
          ruleType: 'Basic'
          priority: requestRoutingRulePriority
          httpListener: {
            id: resourceId(
              'Microsoft.Network/applicationGateways/httpListeners',
              appGatewayName,
              useHttps ? 'listener-https' : 'listener-http'
            )
          }
          backendAddressPool: {
            id: resourceId('Microsoft.Network/applicationGateways/backendAddressPools', appGatewayName, 'pool-apim')
          }
          backendHttpSettings: {
            id: resourceId(
              'Microsoft.Network/applicationGateways/backendHttpSettingsCollection',
              appGatewayName,
              'bhs-https-apim'
            )
          }
        }
      }
    ]
    webApplicationFirewallConfiguration: enableWaf
      ? {
          enabled: true
          firewallMode: 'Detection'
          ruleSetType: 'OWASP'
          ruleSetVersion: '3.2'
        }
      : null
  }
  identity: includeHttpsListener ? (!empty(userAssignedIdentityResourceId) ? {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityResourceId}': {}
    }
  } : {
    type: 'SystemAssigned'
  }) : null
}

// ------------------------------
//    OUTPUTS
// ------------------------------

output appGatewayId string = appGateway.id
output publicIpAddress string = publicIp.properties.ipAddress
output publicIpResourceId string = publicIp.id
output publicIpUrl string = useHttps ? 'https://${publicIp.properties.ipAddress}' : 'http://${publicIp.properties.ipAddress}'
