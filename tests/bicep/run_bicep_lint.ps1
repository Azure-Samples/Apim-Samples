#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Lint all Bicep files in the repository.

.DESCRIPTION
    Recursively finds every .bicep file under the standard source folders and
    lints them with the standalone Bicep CLI. The default repo-wide run uses a
    single recursive pattern to reduce process startup overhead.
#>

param(
    [string[]]$SearchRoots = @('infrastructure', 'samples', 'shared')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ScriptDir = $PSScriptRoot
$RepoRoot = Split-Path (Split-Path $ScriptDir -Parent) -Parent
$defaultSearchRoots = @('infrastructure', 'samples', 'shared')

function Get-BicepExecutable {
    $command = Get-Command bicep -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $homeDirectory = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
    $candidates = @(
        (Join-Path $homeDirectory '.azure/bin/bicep.exe'),
        (Join-Path $homeDirectory '.azure/bin/bicep')
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        return $null
    }

    # Ask Azure CLI to provision/validate the Bicep binary once, then use it directly.
    & az bicep version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

$bicepExecutable = Get-BicepExecutable

if (-not $bicepExecutable) {
    Write-Host ''
    Write-Host 'Bicep CLI is required to lint Bicep files.' -ForegroundColor Red
    Write-Host ''
    exit 1
}

function Get-LintPatterns {
    param(
        [string[]]$Roots,
        [string[]]$DefaultRoots
    )

    $normalizedRoots = @($Roots | ForEach-Object { $_.Trim().TrimEnd('/', '\') })
    $normalizedDefaults = @($DefaultRoots | ForEach-Object { $_.Trim().TrimEnd('/', '\') })

    $matchesDefaultSet = $normalizedRoots.Count -eq $normalizedDefaults.Count
    if ($matchesDefaultSet) {
        for ($i = 0; $i -lt $normalizedDefaults.Count; $i++) {
            if ($normalizedRoots[$i] -ne $normalizedDefaults[$i]) {
                $matchesDefaultSet = $false
                break
            }
        }
    }

    if ($matchesDefaultSet) {
        return @('**/*.bicep')
    }

    return @($normalizedRoots | ForEach-Object { ($_ -replace '\\', '/') + '/**/*.bicep' })
}

Push-Location $RepoRoot
try {
    $files = @(foreach ($root in $SearchRoots) {
        $fullRoot = Join-Path $RepoRoot $root
        if (Test-Path $fullRoot) {
            Get-ChildItem -Path $fullRoot -Recurse -File -Filter '*.bicep'
        }
    })

    $files = @($files | Sort-Object -Property FullName -Unique)

    if (-not $files) {
        Write-Host ''
        Write-Host 'No Bicep files found to lint.' -ForegroundColor Yellow
        Write-Host ''
        exit 0
    }

    Write-Host ''
    Write-Host 'Running Bicep lint across the repository...' -ForegroundColor Cyan
    Write-Host ''
    Write-Host "Files     : $($files.Count)" -ForegroundColor Gray
    Write-Host "Bicep CLI : $bicepExecutable" -ForegroundColor Gray
    Write-Host ''

    $patterns = Get-LintPatterns -Roots $SearchRoots -DefaultRoots $defaultSearchRoots
    $failedPatterns = @()

    foreach ($pattern in $patterns) {
        Write-Host ">>> $bicepExecutable lint --pattern $pattern" -ForegroundColor Cyan
        & $bicepExecutable lint --pattern $pattern
        if ($LASTEXITCODE -ne 0) {
            $failedPatterns += $pattern
        }
        Write-Host ''
    }
}
finally {
    Pop-Location
}

if ($failedPatterns.Count -eq 0) {
    Write-Host 'All Bicep files passed linting.' -ForegroundColor Green
    exit 0
}

Write-Host 'Bicep lint failed for pattern(s):' -ForegroundColor Yellow
foreach ($failedPattern in $failedPatterns) {
    Write-Host "  - $failedPattern" -ForegroundColor Yellow
}

exit 1
