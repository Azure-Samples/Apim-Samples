# Script to verify APIM managed identity has proper permissions on storage account
param(
    [Parameter(Mandatory=$true)]
    [string]$SubscriptionId,
    
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory=$true)]
    [string]$ApimServiceName,
    
    [Parameter(Mandatory=$true)]
    [string]$StorageAccountName
)

# Connect to Azure (assumes already logged in)
Set-AzContext -SubscriptionId $SubscriptionId

# Get APIM service managed identity
$apimService = Get-AzApiManagement -ResourceGroupName $ResourceGroupName -Name $ApimServiceName
$apimPrincipalId = $apimService.Identity.PrincipalId

Write-Host "APIM Service: $ApimServiceName"
Write-Host "APIM Principal ID: $apimPrincipalId"

# Get storage account
$storageAccount = Get-AzStorageAccount -ResourceGroupName $ResourceGroupName -Name $StorageAccountName
Write-Host "Storage Account: $StorageAccountName"
Write-Host "Storage Account ID: $($storageAccount.Id)"

# Check role assignments on storage account
$roleAssignments = Get-AzRoleAssignment -Scope $storageAccount.Id -ObjectId $apimPrincipalId
Write-Host "`nRole assignments for APIM service on storage account:"
$roleAssignments | ForEach-Object {
    Write-Host "  - Role: $($_.RoleDefinitionName)"
    Write-Host "    Principal: $($_.DisplayName)"
    Write-Host "    Scope: $($_.Scope)"
}

if ($roleAssignments.Count -eq 0) {
    Write-Warning "No role assignments found for APIM service on storage account!"
    Write-Host "`nYou may need to wait a few minutes for role assignment propagation."
} else {
    Write-Host "`nRole assignments look correct. If still getting 403 errors, wait a few minutes for propagation."
}

# Test blob access using REST API (similar to what APIM does)
try {
    Write-Host "`nTesting managed identity token acquisition..."
    
    # This would typically be done from within Azure (like APIM)
    Write-Host "Note: This test script runs from your local machine and cannot test managed identity tokens."
    Write-Host "The actual test needs to happen from within the APIM service itself."
    
} catch {
    Write-Error "Error testing access: $($_.Exception.Message)"
}
