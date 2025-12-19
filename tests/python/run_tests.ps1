#!/usr/bin/env pwsh

# PowerShell script to run pytest with coverage.
# This script can be run from any working directory.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Set UTF-8 encoding for console output to properly display Unicode characters
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\.."))

# Set Python to use UTF-8 and unbuffered output
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"

Push-Location $RepoRoot
try {
	$env:COVERAGE_FILE = (Join-Path $RepoRoot "tests/python/.coverage")
	pytest -v --color=yes --cov=shared/python --cov-config=tests/python/.coveragerc --cov-report=html:tests/python/htmlcov tests/python/
}
finally {
	Pop-Location
}
