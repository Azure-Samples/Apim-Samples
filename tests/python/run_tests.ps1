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
	$env:COVERAGE_FILE = (Join-Path $RepoRoot ".coverage")
	# Since we have many tests, we omit the verbosity (-v). We also show the top 3 test durations that run slower than 0.1s as that is often an indicator of missing or faulty mocks.
	pytest --color=yes --durations=3 --durations-min=0.1 --cov --cov-config=tests/python/.coveragerc --cov-report=html:tests/python/htmlcov --cov-report=xml:coverage.xml --cov-report=json:coverage.json tests/python/

	# Display coverage summary
	Write-Host "`nCoverage Summary:" -ForegroundColor Green
	coverage report --skip-covered

	Write-Host "`n✅ Coverage reports generated:" -ForegroundColor Green
	Write-Host "   - HTML: tests/python/htmlcov/index.html" -ForegroundColor Cyan
	Write-Host "   - XML: coverage.xml (for VS Code)" -ForegroundColor Cyan
	Write-Host "   - JSON: coverage.json" -ForegroundColor Cyan
}
finally {
	Pop-Location
}
