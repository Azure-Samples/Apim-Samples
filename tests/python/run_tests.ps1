#!/usr/bin/env pwsh

# PowerShell script to run pytest with coverage.
# This script can be run from any working directory.

$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\.."))

Push-Location $RepoRoot
try {
	$env:COVERAGE_FILE = (Join-Path $RepoRoot "tests/python/.coverage")
	pytest -v --cov=shared/python --cov-config=tests/python/.coveragerc --cov-report=html:tests/python/htmlcov tests/python/
}
finally {
	Pop-Location
}
