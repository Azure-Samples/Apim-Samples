#!/usr/bin/env sh
# This script uninstalls all versions of Az.Accounts and Az.Storage PowerShell modules and installs the latest versions.
# It is intended for use on Linux or macOS systems with PowerShell Core (pwsh) installed.
# Run this script with: sh ./setup/fix-az-modules.sh

# Check for pwsh
if ! command -v pwsh >/dev/null 2>&1; then
  echo "PowerShell Core (pwsh) is not installed. Please install it first: https://learn.microsoft.com/powershell/scripting/install/installing-powershell"
  exit 1
fi

# Run PowerShell commands to clean up and install modules
pwsh -NoProfile -Command "\
  Write-Host 'Uninstalling all versions of Az.Accounts and Az.Storage...'; \
  $modules = @('Az.Accounts', 'Az.Storage'); \
  foreach ($module in $modules) { \
    Get-InstalledModule -Name $module -AllVersions -ErrorAction SilentlyContinue | ForEach-Object { \
      Write-Host \"Uninstalling $($_.Name) v$($_.Version)\"; \
      Uninstall-Module -Name $_.Name -RequiredVersion $_.Version -Force -ErrorAction SilentlyContinue; \
    } \
  }; \
  Write-Host 'Installing latest Az.Accounts and Az.Storage modules...'; \
  Install-Module -Name Az.Accounts -Force; \
  Install-Module -Name Az.Storage -Force; \
  Write-Host 'Updating Az module (if installed)...'; \
  Update-Module -Name Az -Force -ErrorAction SilentlyContinue; \
  Write-Host 'All done! Please open a new PowerShell session before running your deployment again.' \
"
