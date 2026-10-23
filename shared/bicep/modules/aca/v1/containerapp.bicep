/**
 * @module containerapp-v1
 * @description This module defines the Azure Container App resources using Bicep.
 */


// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Name of the Container App. Defaults to "ca-<resourceSuffix>".')
param name string = 'ca-${resourceSuffix}'

@description('Container image to deploy')
param containerImage string

@description('Container app environment resource id')
param environmentId string

@description('Container app CPU (vCPU)')
param cpu string = '0.25'

@description('Container app memory (GiB), e.g. "0.5Gi"')
param memory string = '0.5Gi'

@description('Ingress external port')
param ingressPort int = 8080

@description('Enable public ingress')
param ingressExternal bool = true

@secure()
@description('Secure configuration object containing the Container Apps secrets array.')
param secretConfiguration object = {}

@description('Container environment variables, including secretRef entries.')
param environmentVariables array = []

@description('Optional user-assigned managed identity resource ID.')
param userAssignedIdentityId string = ''

@description('HTTP health probes for the container.')
param probes array = []

@minValue(0)
@description('Minimum number of replicas.')
param minReplicas int = 1

@minValue(1)
@description('Maximum number of replicas.')
param maxReplicas int = 3


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.app/containerapps
#disable-next-line BCP081
resource containerApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: name
  location: location
  identity: empty(userAssignedIdentityId) ? null : {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: secretConfiguration.?secrets ?? []
      ingress: {
        external: ingressExternal
        targetPort: ingressPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [] // No ACR needed
    }
    template: {
      containers: [
        {
          name: name
          image: containerImage
          env: environmentVariables
          probes: probes
          resources: {
            cpu: json(cpu)  // Convert string to JSON, which is bizarre, but required for this "int"
            memory: memory
          }
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}


// ------------------------------
//    OUTPUTS
// ------------------------------

output containerAppName string = containerApp.name
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
