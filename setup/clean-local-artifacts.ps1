#!/usr/bin/env pwsh

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
$RepoRoot  = Split-Path -Path $ScriptDir -Parent

Write-Host ""
Write-Host "Cleaning local artifacts..." -ForegroundColor Cyan
Write-Host ""

# ── Directories ───────────────────────────────────────────────────────────────

$dirPatterns = @('.pytest_cache', '.ruff_cache', '__pycache__', 'htmlcov', 'build', 'dist', '.eggs')

foreach ($pattern in $dirPatterns) {
    Get-ChildItem -Path $RepoRoot -Recurse -Force -Directory -Filter $pattern -ErrorAction SilentlyContinue |
        ForEach-Object {
            Write-Host "  Removing $($_.FullName)"
            Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
}

# *.egg-info directories (filter does not match mid-name wildcards, so use Where-Object)
Get-ChildItem -Path $RepoRoot -Recurse -Force -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like '*.egg-info' } |
    ForEach-Object {
        Write-Host "  Removing $($_.FullName)"
        Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }

# ── Files ─────────────────────────────────────────────────────────────────────

$filePatterns = @('.coverage', '*.pyc', '*.pyo', '*.tmp', '*.temp')

foreach ($pattern in $filePatterns) {
    Get-ChildItem -Path $RepoRoot -Recurse -Force -File -Filter $pattern -ErrorAction SilentlyContinue |
        ForEach-Object {
            Write-Host "  Removing $($_.FullName)"
            Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue
        }
}

# .coverage.* files (dot-prefixed names are not matched by -Filter alone)
Get-ChildItem -Path $RepoRoot -Recurse -Force -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like '.coverage.*' } |
    ForEach-Object {
        Write-Host "  Removing $($_.FullName)"
        Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue
    }

# ── Done ──────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "Done. Note: .env was intentionally left in place." -ForegroundColor Green
Write-Host ""
