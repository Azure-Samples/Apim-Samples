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

        & $exe @cmdArgs 2>&1 | Write-Host
        $exitCode = $LASTEXITCODE
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
    print(json.dumps(info, indent=2))
except Exception as exc:  # pylint: disable=broad-except
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


while ($true) {
    Write-Host ""
    Write-Host "APIM Samples Developer CLI" -ForegroundColor Cyan
    Write-Host "==========================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Setup" -ForegroundColor Yellow
    Write-Host "  1) Complete environment setup"
    Write-Host "  2) Verify local setup"
    Write-Host ""
    Write-Host "Verify" -ForegroundColor Yellow
    Write-Host "  3) Show Azure account info"
    Write-Host "  4) Show soft-deleted resources"
    Write-Host "  5) Show all deployed infrastructures"
    Write-Host ""
    Write-Host "Tests" -ForegroundColor Yellow
    Write-Host "  6) Run pylint"
    Write-Host "  7) Run tests"
    Write-Host "  8) Run full Python checks (most statistics)"
    Write-Host ""
    Write-Host "Misc" -ForegroundColor Yellow
    Write-Host "  0) Exit"
    Write-Host ""
    $choice = Read-Host "Select an option"

    switch ($choice) {
        '1' {
            Invoke-Cmd (Get-Python) "$RepoRoot/setup/local_setup.py" "--complete-setup" | Out-Null
        }
        '2' {
            Invoke-Cmd (Get-Python) "$RepoRoot/setup/verify_local_setup.py" | Out-Null
        }
        '3' {
            Show-AccountInfo
        }
        '4' {
            Invoke-Cmd (Get-Python) "$RepoRoot/shared/python/show_soft_deleted_resources.py" | Out-Null
        }
        '5' {
            Invoke-Cmd (Get-Python) "$RepoRoot/shared/python/show_infrastructures.py" | Out-Null
        }
        '6' {
            Invoke-Cmd "$RepoRoot/tests/python/run_pylint.ps1" | Out-Null
        }
        '7' {
            Invoke-Cmd "$RepoRoot/tests/python/run_tests.ps1" | Out-Null
        }
        '8' {
            Invoke-Cmd "$RepoRoot/tests/python/check_python.ps1" | Out-Null
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
