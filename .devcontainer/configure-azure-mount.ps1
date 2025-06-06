# Azure CLI Configuration Setup for APIM Samples Dev Container
# This PowerShell script provides an alternative to the Python configuration script

Write-Host "🚀 APIM Samples Dev Container Azure CLI Setup" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

Write-Host "🔧 Azure CLI Configuration Setup" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow

# Detect platform
$platform = "Windows"
Write-Host "Detected platform: $platform" -ForegroundColor Green

Write-Host "`nHow would you like to handle Azure CLI authentication?" -ForegroundColor White
Write-Host "1. Mount local Azure CLI config (preserves login between container rebuilds)" -ForegroundColor White
Write-Host "2. Use manual login inside container (az login each time)" -ForegroundColor White
Write-Host "3. Let me configure this manually later" -ForegroundColor White

do {
    $choice = Read-Host "`nEnter your choice (1-3)"
} while ($choice -notin @("1", "2", "3"))

# Path to devcontainer.json
$devcontainerPath = Join-Path $PSScriptRoot "devcontainer.json"
$backupPath = "$devcontainerPath.backup"

if (-not (Test-Path $devcontainerPath)) {
    Write-Host "❌ devcontainer.json not found at: $devcontainerPath" -ForegroundColor Red
    exit 1
}

# Create backup
try {
    Copy-Item $devcontainerPath $backupPath -Force
    Write-Host "✅ Backup created: $backupPath" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to create backup: $_" -ForegroundColor Red
    exit 1
}

# Read and parse devcontainer.json (simple approach for PowerShell)
try {
    $content = Get-Content $devcontainerPath -Raw | ConvertFrom-Json -Depth 10
    
    # Remove existing mounts if present
    if ($content.PSObject.Properties.Name -contains "mounts") {
        $content.PSObject.Properties.Remove("mounts")
    }
    
    switch ($choice) {
        "1" {
            # Add Windows mount configuration
            $mount = @{
                source = "`${localEnv:USERPROFILE}/.azure"
                target = "/home/vscode/.azure"
                type = "bind"
            }
            $content | Add-Member -MemberType NoteProperty -Name "mounts" -Value @($mount)
            Write-Host "✅ Configured Azure CLI mounting for Windows" -ForegroundColor Green
        }
        "2" {
            Write-Host "✅ Configured for manual Azure CLI login (az login)" -ForegroundColor Green
            Write-Host "   You'll need to run 'az login' after container startup" -ForegroundColor Yellow
        }
        "3" {
            Write-Host "✅ No automatic configuration applied" -ForegroundColor Green
            Write-Host "   You can manually edit .devcontainer/devcontainer.json later" -ForegroundColor Yellow
        }
    }
    
    # Save the updated configuration
    $content | ConvertTo-Json -Depth 10 | Set-Content $devcontainerPath -Encoding UTF8
    Write-Host "✅ devcontainer.json updated successfully" -ForegroundColor Green
    
} catch {
    Write-Host "❌ Failed to update devcontainer.json: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n🎉 Configuration completed successfully!" -ForegroundColor Green

switch ($choice) {
    "1" {
        Write-Host "`n📋 Next steps:" -ForegroundColor Cyan
        Write-Host "1. Rebuild your dev container" -ForegroundColor White
        Write-Host "2. Your local Azure CLI authentication will be available" -ForegroundColor White
    }
    "2" {
        Write-Host "`n📋 Next steps:" -ForegroundColor Cyan
        Write-Host "1. Start/rebuild your dev container" -ForegroundColor White
        Write-Host "2. Run 'az login' inside the container" -ForegroundColor White
    }
    "3" {
        Write-Host "`n📋 Next steps:" -ForegroundColor Cyan
        Write-Host "1. Edit .devcontainer/devcontainer.json manually if needed" -ForegroundColor White
        Write-Host "2. See the commented examples in the file" -ForegroundColor White
    }
}
