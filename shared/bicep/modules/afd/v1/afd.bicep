/**
 * @module fd-v1
 * @description This module defines the Azure Front Door (AFD) resources using Bicep.
 * It includes configurations for creating and managing an AFD instance.
 */


// ------------------------------
//    PARAMETERS
// ------------------------------

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('The name of the Front Door profile. Defaults to "afd-<resourceSuffix>".')
param afdName string = 'afd-${resourceSuffix}'

@description('The name of the Front Door endpoint. Defaults to "fde-<resourceSuffix>".')
param fdeName string = 'fde-${resourceSuffix}'

@description('The SKU to use when creating the Front Door profile.')
@allowed([
  'Premium_AzureFrontDoor'
])
param afdSku string = 'Premium_AzureFrontDoor'

@description('The name of the API Management instance. Defaults to "apim-<resourceSuffix>".')
param apimName string = 'apim-${resourceSuffix}'

@description('Log Analytics Workspace ID for diagnostic settings (optional)')
param logAnalyticsWorkspaceId string = ''


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// https://learn.microsoft.com/azure/templates/microsoft.cdn/profiles
resource frontDoorProfile 'Microsoft.Cdn/profiles@2025-04-15' = {
  name: afdName
  location: 'global'
  sku: {
    name: afdSku
  }
  dependsOn: [
    apimService // This explicit dependency is required to ensure that the APIM service is created before the Front Door profile.
  ]
}

// https://learn.microsoft.com/azure/templates/microsoft.cdn/profiles/afdendpoints
resource frontDoorEndpoint 'Microsoft.Cdn/profiles/afdEndpoints@2025-04-15' = {
  name: fdeName
  parent: frontDoorProfile
  location: 'global'
  properties: {
    enabledState: 'Enabled'
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.cdn/profiles/origingroups
resource frontDoorOriginGroup 'Microsoft.Cdn/profiles/originGroups@2025-04-15' = {
  name: 'OriginGroup'
  parent: frontDoorProfile
  properties: {
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
    }
    healthProbeSettings: {
      probePath: '/'
      probeRequestType: 'GET'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 60
    }
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.cdn/profiles/origingroups/origins
resource frontDoorOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2025-04-15' = {
  name: 'FrontDoorOrigin'
  parent: frontDoorOriginGroup
  properties: {
    hostName: replace(apimService.properties.gatewayUrl, 'https://', '')
    httpPort: 80
    httpsPort: 443
    originHostHeader: replace(apimService.properties.gatewayUrl, 'https://', '')
    priority: 1
    weight: 1000
    enabledState: 'Enabled'
    sharedPrivateLinkResource: {
      groupId: 'Gateway'
      privateLinkLocation: resourceGroup().location 
      requestMessage: 'Please validate PE connection'
      privateLink: {
        id: apimService.id
      }
    }
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.cdn/profiles/afdendpoints/routes
resource frontDoorRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2025-04-15' = {
  name: 'FrontDoorRoute'
  parent: frontDoorEndpoint
  dependsOn: [
    frontDoorOrigin // This explicit dependency is required to ensure that the origin group is not empty when the route is created.
  ]
  properties: {
    originGroup: {
      id: frontDoorOriginGroup.id
    }
    supportedProtocols: ['Http', 'Https']
    patternsToMatch: ['/*']
    forwardingProtocol: 'MatchRequest' // 'HttpsOnly'
    linkToDefaultDomain: 'Enabled'
    httpsRedirect: 'Enabled'
    originPath: '/'
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.network/frontdoorwebapplicationfirewallpolicies
resource wafPolicy 'Microsoft.Network/FrontDoorWebApplicationFirewallPolicies@2024-02-01' = {
  name: 'wafFrontDoor${resourceSuffix}'
  location: 'global'
  sku: {
    name: afdSku
  }
  properties: {
    policySettings: {
      enabledState: 'Enabled'
      mode: 'Detection'   // Set to 'Detection' rather than 'Prevention' INITIALLY, so that we can test the WAF rules without blocking traffic.
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetAction: 'Log'
          ruleSetType: 'Microsoft_DefaultRuleSet'
          ruleSetVersion: '2.1'
        }
        {
          ruleSetAction: 'Log'
          ruleSetType: 'Microsoft_BotManagerRuleSet'
          ruleSetVersion: '1.0'
        }
      ]
    }
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.cdn/profiles/securitypolicies
resource securityPolicy 'Microsoft.Cdn/profiles/securityPolicies@2025-04-15' = {
  parent: frontDoorProfile
  name: 'security-policy'
  properties: {
    parameters: {
      type: 'WebApplicationFirewall'
      wafPolicy: {
        id: wafPolicy.id
      }
      associations: [
        {
          domains: [
            {
              id: frontDoorEndpoint.id
            }
          ]
          patternsToMatch: [
            '/*'
          ]
        }
      ]
    }
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.insights/diagnosticsettings
resource frontDoorDiagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: 'afd-diagnostics'
  scope: frontDoorProfile
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}


// ------------------------------
//    OUTPUTS
// ------------------------------

output fdeHostName string = frontDoorEndpoint.properties.hostName
output fdeSecureUrl string = 'https://${frontDoorEndpoint.properties.hostName}'
