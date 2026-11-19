// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Foundry resource region with quota for every selected PAYG model.')
param location string

@description('Globally unique sample-owned Foundry account name; preserve it when upgrading.')
param accountName string

@description('Identical model deployment records for every account.')
param models array

@description('PAYG only; semantic pool labels never select a provisioned SKU.')
@allowed(['GlobalStandard', 'Standard'])
param modelSku string

@description('Existing gateway managed identity.')
param principalId string


// ------------------------------
//    VARIABLES
// ------------------------------

@description('Cognitive Services OpenAI User role.')
var openAiUserRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')


// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/accounts
resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: { name: 'S0' }
  properties: {
    allowProjectManagement: true
    customSubDomainName: accountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

// https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/accounts/deployments
// Serialize writes on each account to avoid RequestConflict.
@batchSize(1)
resource deployments 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = [for model in models: {
  parent: account
  name: model.deploymentName
  sku: {
    name: modelSku
    capacity: model.capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: model.name
      version: model.version
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}]

// https://learn.microsoft.com/azure/templates/microsoft.authorization/roleassignments
resource gatewayRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, principalId, openAiUserRole)
  scope: account
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: openAiUserRole
  }
}


// ------------------------------
//    OUTPUTS
// ------------------------------

// https://learn.microsoft.com/azure/foundry/foundry-models/how-to/create-model-deployments#use-the-model
@description('Published OpenAI inference base URL, not the generic multi-service endpoint.')
output endpoint string = account.properties.endpoints['Azure OpenAI Legacy API - Latest moniker']
output accountId string = account.id
output accountName string = account.name
