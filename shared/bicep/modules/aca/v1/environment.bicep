/**
 * @module environment-v1
 * @description This module defines the Azure Container App Environment resources using Bicep.
 */


// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Name of the Container App Environment. Defaults to "cae-<resourceSuffix>".')
param name string = 'cae-${resourceSuffix}'

@description('Log Analytics Workspace Customer ID (required for diagnostics)')
param logAnalyticsWorkspaceCustomerId string

@secure()
@description('Log Analytics Workspace Shared Key')
param logAnalyticsWorkspaceSharedKey string

@description('Resource ID of the subnet for ACA environment. If not provided, ACA will be public.')
param subnetResourceId string = ''

@description('Whether to create an internal VNet for the ACA environment. Defaults to true.')
param internalVnet bool = true


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.app/managedenvironments
#disable-next-line BCP081
resource acaEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: name
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspaceCustomerId
        sharedKey: logAnalyticsWorkspaceSharedKey
      }
    }
    // There is an issues with cutting off public network access. 2025-02-02-preview does not work:
    // https://learn.microsoft.com/azure/templates/microsoft.app/change-log/managedenvironments#2025-02-02-preview
    // Hard-code cutting off public access as we are using a VNet. 
    //publicNetworkAccess: 'Disabled'
    vnetConfiguration: !empty(subnetResourceId) ? {
      infrastructureSubnetId: subnetResourceId
      // If internal is true for the ACA environment, the container apps cannot be accessed from outside the VNet (or container app environment - more on that in the container app bicep)
      internal: internalVnet
    } : null
    workloadProfiles: [
      {
        // Stick with hard-coded Consumption to not overcomplicate and to keep costs down
        name: 'Consumption'
        workloadProfileType: 'Consumption'        
      }
    ]
  }
}


// ------------------------------
//    OUTPUTS
// ------------------------------

output environmentId string = acaEnvironment.id
output environmentName string = acaEnvironment.name
output environmentDefaultDomain string = acaEnvironment.properties.defaultDomain
output internalVnet bool = !empty(acaEnvironment.properties.vnetConfiguration) && acaEnvironment.properties.vnetConfiguration.internal
output environmentRandomSubdomain string = join(take(split(acaEnvironment.properties.defaultDomain, '.'), 1), '.')
output environmentStaticIp string = acaEnvironment.properties.staticIp
