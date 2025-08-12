// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

// Networking names and ranges
@description('The name of the VNet.')
param vnetName string = 'vnet-${resourceSuffix}'
param appGwSubnetName string = 'snet-appgw'
param peSubnetName string = 'snet-pe'

@description('The address prefixes for the VNet.')
param vnetAddressPrefixes array = [ '10.30.0.0/16' ]

@description('The address prefix for the Application Gateway subnet (dedicated).')
param appGwSubnetPrefix string = '10.30.1.0/24'

@description('The address prefix for the Private Endpoint subnet.')
param peSubnetPrefix string = '10.30.2.0/24'

// API Management
param apimName string = 'apim-${resourceSuffix}'
param apimSku string = 'Developer'
param apis array = []
param policyFragments array = []

// Key Vault RBAC helper (optional): objectId and principalType of the principal creating the deployment
@description('Optional: Object ID of the principal running the deployment (user or service principal). When provided, it will be granted the Key Vault Certificates Officer role to allow creating the self-signed certificate.')
param kvCertificateCreatorObjectId string = ''

@description('Optional: Principal type for kvCertificateCreatorObjectId. Allowed values: User or ServicePrincipal.')
@allowed([ 'User', 'ServicePrincipal' ])
param kvCertificateCreatorPrincipalType string = 'User'

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

// 3. NSGs for subnets
resource nsgAppGw 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-appgw'
  location: location
  properties: {
    // NSG rules required for Application Gateway v2 infrastructure
    // Ref: https://learn.microsoft.com/azure/application-gateway/configuration-infrastructure#network-security-groups
    securityRules: [
      {
        name: 'Allow-GatewayManager-Inbound'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRanges: [ '65200-65535' ]
          sourceAddressPrefix: 'GatewayManager'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'Allow-AzureLoadBalancer-Inbound'
        properties: {
          priority: 101
          direction: 'Inbound'
          access: 'Allow'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: 'AzureLoadBalancer'
          destinationAddressPrefix: '*'
        }
      }
      // HTTPS listener only
      {
        name: 'Allow-HTTPS-From-Internet'
        properties: {
          priority: 200
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: 'Internet'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

// 3.1 User Assigned Managed Identity for App Gateway to access Key Vault
resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'uami-ag-${resourceSuffix}'
  location: location
}

// 3.2 Key Vault to store self-signed cert
var kvName = 'kv-${resourceSuffix}'
resource keyVault 'Microsoft.KeyVault/vaults@2024-04-01-preview' = {
  name: kvName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

// 3.3 RBAC: assign Key Vault Secrets User to UAMI
resource kvRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().id, keyVault.id, uami.name, '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// 3.3.2 RBAC: assign Key Vault Certificates Officer to UAMI for deployment script
resource kvCertificatesRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().id, keyVault.id, uami.name, 'a4417e6f-fecd-4de8-b567-7b0420556985') // Key Vault Certificates Officer
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a4417e6f-fecd-4de8-b567-7b0420556985')
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// 3.3.1 RBAC (optional): assign Key Vault Certificates Officer to the deploying principal to allow certificate creation
// Role: Key Vault Certificates Officer (a4417e6f-fecd-4de8-b567-7b0420556985)
resource kvCertCreatorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(kvCertificateCreatorObjectId)) {
  name: guid(subscription().id, keyVault.id, kvCertificateCreatorObjectId, 'a4417e6f-fecd-4de8-b567-7b0420556985')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a4417e6f-fecd-4de8-b567-7b0420556985')
    principalId: kvCertificateCreatorObjectId
    principalType: kvCertificateCreatorPrincipalType
  }
}

// 3.4 Create a self-signed certificate using deployment script (more reliable than direct ARM resource)
resource kvCertScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'create-ag-cert'
  location: location
  kind: 'AzurePowerShell'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uami.id}': {}
    }
  }
  dependsOn: [
    kvRoleAssignment
    kvCertificatesRoleAssignment
    kvCertCreatorRoleAssignment
  ]
  properties: {
    azPowerShellVersion: '11.0'
    timeout: 'PT10M'
    retentionInterval: 'P1D'
    environmentVariables: [
      {
        name: 'KEYVAULT_NAME'
        value: keyVault.name
      }
      {
        name: 'CERT_NAME'
        value: 'ag-cert'
      }
    ]
    scriptContent: '''
      $ErrorActionPreference = 'Stop'
      
      # Connect using the managed identity
      Connect-AzAccount -Identity
      
      # Set the subscription context
      $context = Get-AzContext
      Write-Output "Connected as: $($context.Account.Id)"
      
      # Check if certificate already exists and is completed
      try {
        $existingCert = Get-AzKeyVaultCertificate -VaultName $env:KEYVAULT_NAME -Name $env:CERT_NAME -ErrorAction SilentlyContinue
        if ($existingCert -and $existingCert.Enabled -and $existingCert.SecretId) {
          Write-Output "Certificate already exists and is usable: $($existingCert.Id)"
          Write-Output "Certificate thumbprint: $($existingCert.Thumbprint)"
          Write-Output "Certificate secret ID: $($existingCert.SecretId)"
          $DeploymentScriptOutputs = @{
            secretId = $existingCert.SecretId
            certificateId = $existingCert.Id
            thumbprint = $existingCert.Thumbprint
          }
          return
        }
        elseif ($existingCert) {
          Write-Output "Found existing certificate but it may be incomplete. Status: $($existingCert.Status). Will remove and recreate."
          Remove-AzKeyVaultCertificate -VaultName $env:KEYVAULT_NAME -Name $env:CERT_NAME -Force -Confirm:$false
          Start-Sleep -Seconds 15
        }
      }
      catch {
        Write-Output "No existing certificate found."
      }
      
      # Check for and purge any deleted certificates
      try {
        Write-Output "Checking for deleted certificates..."
        $deletedCerts = Get-AzKeyVaultCertificate -VaultName $env:KEYVAULT_NAME -InRemovedState -ErrorAction SilentlyContinue
        
        if ($deletedCerts) {
          $deletedCert = $deletedCerts | Where-Object { $_.Name -eq $env:CERT_NAME }
          if ($deletedCert) {
            Write-Output "Found deleted certificate '$env:CERT_NAME'. Purging..."
            Remove-AzKeyVaultCertificate -VaultName $env:KEYVAULT_NAME -Name $env:CERT_NAME -InRemovedState -Force -Confirm:$false
            Write-Output "Waiting for purge to complete..."
            Start-Sleep -Seconds 30
          }
        }
      }
      catch {
        Write-Output "No deleted certificates found or error checking: $($_.Exception.Message)"
      }
      
      # Create self-signed certificate using OpenSSL (available in Linux deployment script environment)
      Write-Output "Creating self-signed certificate using OpenSSL..."
      
      # Create the certificate using OpenSSL commands
      $keyPath = "/tmp/apim.key"
      $certPath = "/tmp/apim.crt"
      $pfxPath = "/tmp/apim.pfx"
      $password = "TempPassword123!"
      
      # Generate private key
      $keyResult = Invoke-Expression "openssl genrsa -out $keyPath 2048 2>&1"
      Write-Output "Private key generation result: $keyResult"
      
      # Create certificate signing request and self-signed certificate
      $certResult = Invoke-Expression "openssl req -new -x509 -key $keyPath -out $certPath -days 365 -subj '/CN=apim-samples-${resourceGroup().name}' 2>&1"
      Write-Output "Certificate creation result: $certResult"
      
      # Convert to PFX format
      $pfxResult = Invoke-Expression "openssl pkcs12 -export -out $pfxPath -inkey $keyPath -in $certPath -password pass:$password 2>&1"
      Write-Output "PFX conversion result: $pfxResult"
      
      # Import to Key Vault
      Write-Output "Importing certificate to Key Vault..."
      $securePassword = ConvertTo-SecureString -String $password -Force -AsPlainText
      $importedCert = Import-AzKeyVaultCertificate -VaultName $env:KEYVAULT_NAME -Name $env:CERT_NAME -FilePath $pfxPath -Password $securePassword
      
      # Clean up temporary files
      Remove-Item -Path $keyPath -Force -ErrorAction SilentlyContinue
      Remove-Item -Path $certPath -Force -ErrorAction SilentlyContinue
      Remove-Item -Path $pfxPath -Force -ErrorAction SilentlyContinue
      
      # Verify the imported certificate
      $finalCert = Get-AzKeyVaultCertificate -VaultName $env:KEYVAULT_NAME -Name $env:CERT_NAME
      
      if (-not $finalCert -or -not $finalCert.SecretId) {
        throw "Certificate import failed or SecretId is missing"
      }
      
      Write-Output "Certificate successfully imported to Key Vault!"
      Write-Output "Certificate ID: $($finalCert.Id)"
      Write-Output "Secret ID: $($finalCert.SecretId)"
      Write-Output "Thumbprint: $($finalCert.Thumbprint)"
      
      # Output the results
      $DeploymentScriptOutputs = @{
        secretId = $finalCert.SecretId
        certificateId = $finalCert.Id
        thumbprint = $finalCert.Thumbprint
      }
    '''
  }
}

// Use certificate's secretId from deployment script output
var sslSecretId = kvCertScript.properties.outputs.secretId

resource nsgPe 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-pe'
  location: location
}

// 4. Virtual Network and subnets
module vnetModule '../../shared/bicep/modules/vnet/v1/vnet.bicep' = {
  name: 'vnetModule'
  params: {
    vnetName: vnetName
    vnetAddressPrefixes: vnetAddressPrefixes
    subnets: [
      // App Gateway Subnet (dedicated)
      {
        name: appGwSubnetName
        properties: {
          addressPrefix: appGwSubnetPrefix
          networkSecurityGroup: {
            id: nsgAppGw.id
          }
        }
      }
      // Private Endpoint Subnet (no delegation; recommended Disable Network Policies)
      {
        name: peSubnetName
        properties: {
          addressPrefix: peSubnetPrefix
          networkSecurityGroup: {
            id: nsgPe.id
          }
          privateEndpointNetworkPolicies: 'Disabled'
          privateLinkServiceNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

var appGwSubnetResourceId = resourceId(resourceGroup().name, 'Microsoft.Network/virtualNetworks/subnets', vnetName, appGwSubnetName)
var peSubnetResourceId   = resourceId(resourceGroup().name, 'Microsoft.Network/virtualNetworks/subnets', vnetName, peSubnetName)

// 5. APIM (public access enabled, no VNet injection; Private Endpoint used for inbound traffic)
module apimModule '../../shared/bicep/modules/apim/v1/apim.bicep' = {
  name: 'apimModule'
  params: {
    apimName: apimName
    apimSku: apimSku
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    publicAccess: true
    // No apimSubnetResourceId provided here; we're using Private Endpoint instead
    globalPolicyXml: loadTextContent('../../shared/apim-policies/all-apis.xml')
  }
}

// 6. Private Endpoint for APIM (gateway)
module peModule '../../shared/bicep/modules/private-endpoint/v1/private-endpoint.bicep' = {
  name: 'apimPrivateEndpoint'
  params: {
    privateEndpointName: 'pe-${resourceSuffix}-apim'
    subnetResourceId: peSubnetResourceId
    targetResourceId: apimModule.outputs.id
  groupIds: [ 'Gateway' ]
    privateDnsZoneName: 'privatelink.azure-api.net'
    vnetId: vnetModule.outputs.vnetId
    vnetLinkName: 'link-apim'
    dnsZoneGroupName: 'dnsZoneGroup-apim'
    dnsZoneConfigName: 'config-apim'
  }
}

// 7. Application Gateway backend to APIM Private Link FQDN
// Note: APIM gateway Private Link hostnames resolve under privatelink.azure-api.net to a private IP.
// We can use the public hostname and rely on DNS override in VNet, or explicitly point to privatelink FQDN.
var apimGatewayHostname = '${apimName}.privatelink.azure-api.net'

module appGwModule '../../shared/bicep/modules/appgw/v1/appgw.bicep' = {
  name: 'appGwModule'
  params: {
    appGatewayName: 'ag-${resourceSuffix}'
    appGatewaySubnetResourceId: appGwSubnetResourceId
    backendHostname: apimGatewayHostname
  enableWaf: false
  requestRoutingRulePriority: 100
  includeHttpListener: false
  includeHttpsListener: true
  sslCertKeyVaultSecretId: sslSecretId
  userAssignedIdentityResourceId: uami.id
  }
}

// 8. APIM Policy Fragments
module policyFragmentModule '../../shared/bicep/modules/apim/v1/policy-fragment.bicep' = [for pf in policyFragments: {
  name: 'pf-${pf.name}'
  params: {
    apimName: apimName
    policyFragmentName: pf.name
    policyFragmentDescription: pf.description
    policyFragmentValue: pf.policyXml
  }
  dependsOn: [
    apimModule
  ]
}]

// 9. APIM APIs
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: if(length(apis) > 0) {
  name: 'api-${api.name}'
  params: {
    apimName: apimName
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    api: api
  }
  dependsOn: [
    apimModule
  ]
}]

// ------------------
//    MARK: OUTPUTS
// ------------------

output applicationInsightsAppId string = appInsightsModule.outputs.appId
output applicationInsightsName string = appInsightsModule.outputs.applicationInsightsName
output logAnalyticsWorkspaceId string = lawModule.outputs.customerId
output apimServiceId string = apimModule.outputs.id
output apimServiceName string = apimModule.outputs.name
output apimResourceGatewayURL string = apimModule.outputs.gatewayUrl
output privateEndpointId string = peModule.outputs.privateEndpointId
output appGatewayId string = appGwModule.outputs.appGatewayId
output appGatewayPublicIp string = appGwModule.outputs.publicIpAddress
output appGatewayUrl string = appGwModule.outputs.publicIpUrl

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
