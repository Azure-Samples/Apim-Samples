# This script uninstalls all versions of Az.Accounts and Az.Storage, then installs the latest versions.
# It is intended to resolve module version conflicts for Azure PowerShell deployments.
# Run this script in a new PowerShell session with administrator privileges.

Write-Host "Uninstalling all versions of Az.Accounts and Az.Storage..."

$modules = @('Az.Accounts', 'Az.Storage')
foreach ($module in $modules) {
    Get-InstalledModule -Name $module -AllVersions -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "Uninstalling $($_.Name) v$($_.Version)"
        Uninstall-Module -Name $_.Name -RequiredVersion $_.Version -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Installing latest Az.Accounts and Az.Storage modules..."
Install-Module -Name Az.Accounts -Force
Install-Module -Name Az.Storage -Force

Write-Host "Updating Az module (if installed)..."
Update-Module -Name Az -Force -ErrorAction SilentlyContinue

Write-Host "All done! Please open a new PowerShell session before running your deployment again."
