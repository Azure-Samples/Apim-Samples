/**
 * @module storage-account-flowlogs-v1
 * @description Storage Account for NSG Flow Logs
 */

// ------------------------------
//    PARAMETERS
// ------------------------------

@description('Location for the storage account')
param location string = resourceGroup().location

@description('The unique suffix to append')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

@description('Storage account name (must be globally unique, 3-24 chars, lowercase alphanumeric)')
@minLength(3)
@maxLength(24)
param storageAccountName string = 'stflowlogs${take(resourceSuffix, 13)}'

@description('Storage account SKU')
@allowed([
  'Standard_LRS'
  'Standard_GRS'
  'Standard_RAGRS'
  'Standard_ZRS'
])
param skuName string = 'Standard_LRS'

// ------------------------------
//    RESOURCES
// ------------------------------

// https://learn.microsoft.com/azure/templates/microsoft.storage/storageaccounts
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: skuName
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
    encryption: {
      services: {
        blob: {
          enabled: true
        }
        file: {
          enabled: true
        }
      }
      keySource: 'Microsoft.Storage'
    }
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
  }
}

// ------------------------------
//    OUTPUTS
// ------------------------------

output storageAccountId string = storageAccount.id
output storageAccountName string = storageAccount.name
