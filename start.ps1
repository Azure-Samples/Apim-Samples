#!/usr/bin/env pwsh

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Set UTF-8 encoding for console output to properly display Unicode characters
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Enable ANSI escape sequence support in PowerShell 7+
$PSVersionTable.PSVersion.Major -ge 7 | Out-Null
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $env:TERM = "xterm-256color"
}

$ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
$RepoRoot = $ScriptDir

function Get-Python {
    $venvWin = Join-Path $RepoRoot ".venv/Scripts/python.exe"
    $venvNix = Join-Path $RepoRoot ".venv/bin/python"
    if (Test-Path $venvWin) { return $venvWin }
    if (Test-Path $venvNix) { return $venvNix }
    if (Get-Command python3 -ErrorAction SilentlyContinue) { return "python3" }
    return "python"
}

function Invoke-Cmd {
    $flatArgs = @()
    foreach ($a in $args) {
        if ($a -is [System.Collections.IEnumerable] -and -not ($a -is [string])) {
            $flatArgs += $a
        } else {
            $flatArgs += $a
        }
    }

    Write-Host "`n>>> $($flatArgs -join ' ')`n" -ForegroundColor Cyan
    Push-Location $RepoRoot
    try {
        if ($flatArgs.Count -eq 0) {
            throw "No command specified"
        }

        $exe = $flatArgs[0]
        $cmdArgs = @()

        if ($flatArgs.Count -gt 1) {
            $cmdArgs = @($flatArgs[1..($flatArgs.Count - 1)])
        }

        $global:LASTEXITCODE = 0
            # Send command stdout directly to the host so menu callers can ignore the
            # boolean return value without swallowing the child command output.
            & $exe @cmdArgs | Out-Host
        $commandSucceeded = $?
        $exitCode = if ($commandSucceeded) { $LASTEXITCODE } else { [Math]::Max($LASTEXITCODE, 1) }
    }
    catch {
        Write-Host ""
        Write-Host "Command failed: $_" -ForegroundColor Red
        Write-Host ""
        return $false
    }
    finally {
        Pop-Location
    }

    if ($exitCode -ne 0) {
        Write-Host ""
        Write-Host "Command exited with code $exitCode" -ForegroundColor Yellow
        Write-Host ""
        return $false
    }

    return $true
}

function Show-AccountInfo {
    $python = Get-Python
    $code = @"
from pathlib import Path
import json
import sys
import os

root = Path(os.getcwd())
shared = root / "shared" / "python"
if str(shared) not in sys.path:
    sys.path.insert(0, str(shared))
try:
    import azure_resources as az
    info = az.get_account_info()
except Exception as exc:  # noqa: BLE001
    print(f"Failed to read Azure account info: {exc}")
"@
    Push-Location $RepoRoot
    try {
        & $python -c $code
    }
    finally {
        Pop-Location
    }
}

function Test-Uv {
    return [bool](Get-Command uv -ErrorAction SilentlyContinue)
}

function PyRun {
    param(
        [Parameter(ValueFromRemainingArguments=$true)]
        [string[]] $Args
    )
    if (Test-Uv) {
        Invoke-Cmd "uv" (@("run", "python") + $Args)
    } else {
        Invoke-Cmd (Get-Python) $Args
    }
}

while ($true) {
    Write-Host ""
    Write-Host "APIM Samples Developer CLI" -ForegroundColor Cyan
    Write-Host "==========================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Setup" -ForegroundColor Yellow
    Write-Host "  1) Complete environment setup"
    Write-Host "  2) Azure CLI login"
    Write-Host "  u) Update & sync uv dependencies (refresh uv.lock)"
    Write-Host ""
    Write-Host "Verify" -ForegroundColor Yellow
    Write-Host "  3) Verify local setup"
    Write-Host "  4) Show Azure account info"
    Write-Host "  5) Show soft-deleted resources"
    Write-Host "  6) Show all deployed infrastructures"
    Write-Host ""
    Write-Host "Tests" -ForegroundColor Yellow
    Write-Host "  7) Run python ruff"
    Write-Host "  8) Run python tests (shows detailed test results)"
    Write-Host "  9) Run Bicep lint"
    Write-Host " 10) Run full checks (most statistics)"
    Write-Host ""
    Write-Host "Presentation" -ForegroundColor Yellow
    Write-Host "  p) Serve & view presentation (auto-opens browser)"
    Write-Host "  e) Export presentation as self-contained HTML"
    Write-Host "  w) Serve & view GitHub Pages website (auto-opens browser)"
    Write-Host ""
    Write-Host "Cleanup" -ForegroundColor Yellow
    Write-Host "  c) Clean local artifacts (preserves .env)"
    Write-Host ""
    Write-Host "Misc" -ForegroundColor Yellow
    Write-Host "  0) Exit"
    Write-Host ""
    $choice = Read-Host "Select an option"

    switch ($choice) {
        '1' {
            $null = PyRun "$RepoRoot/setup/local_setup.py" "--complete-setup"
        }
        '2' {
            Write-Host ""
            $useTenantId = Read-Host "Do you want to specify a tenant ID? (y/n)"
            if ($useTenantId -eq 'y' -or $useTenantId -eq 'Y') {
                $tenantId = Read-Host "Enter tenant ID"
                if ($tenantId) {
                    $cmd = "az login --tenant $tenantId"
                    Write-Host "`n>>> $cmd`n" -ForegroundColor Cyan
                    & az login --tenant $tenantId
                } else {
                    Write-Host "Tenant ID is required." -ForegroundColor Red
                }
            } else {
                $cmd = "az login"
                Write-Host "`n>>> $cmd`n" -ForegroundColor Cyan
                & az login
            }
        }
        '3' {
            $null = PyRun "$RepoRoot/setup/verify_local_setup.py"
        }
        '4' {
            Show-AccountInfo
        }
        '5' {
            $null = PyRun "$RepoRoot/shared/python/show_soft_deleted_resources.py"
        }
        '6' {
            $null = PyRun "$RepoRoot/shared/python/show_infrastructures.py"
        }
        '7' {
            $null = Invoke-Cmd "$RepoRoot/tests/python/run_ruff.ps1"
        }
        '8' {
            $null = Invoke-Cmd "$RepoRoot/tests/python/run_tests.ps1"
        }
        '9' {
            $null = Invoke-Cmd "$RepoRoot/tests/bicep/run_bicep_lint.ps1"
        }
        '10' {
            $null = Invoke-Cmd "$RepoRoot/tests/python/check_python.ps1"
        }
        'p' {
            $null = PyRun "$RepoRoot/setup/serve_presentation.py"
        }
        'e' {
            $null = PyRun "$RepoRoot/setup/export_presentation.py"
        }
        'w' {
            $null = PyRun "$RepoRoot/setup/serve_website.py"
        }
        'c' {
            $null = Invoke-Cmd "$RepoRoot/setup/clean-local-artifacts.ps1"
        }
        'u' {
            if (Test-Uv) {
                $lockOk = Invoke-Cmd "uv" @("lock", "--upgrade")
                if ($lockOk) {
                    $null = Invoke-Cmd "uv" @("sync")
                }
            } else {
                Write-Host ""
                Write-Host "uv is not installed or not on PATH. Install uv first (see setup/README.md)." -ForegroundColor Red
                Write-Host ""
            }
        }
        '0' {
            Write-Host ""
            Write-Host "Goodbye!" -ForegroundColor Green
            Write-Host ""
            exit 0
        }
        Default {
            Write-Host "Invalid option. Please try again." -ForegroundColor Red
        }
    }
}
