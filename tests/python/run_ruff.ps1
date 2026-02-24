#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run ruff on the Apim-Samples project with comprehensive reporting.

.DESCRIPTION
    Executes ruff with multiple output formats for better visibility:
    - Colorized console output
    - JSON report for automated processing
    - Text report for detailed analysis

.PARAMETER Target
    Path to analyze. Defaults to all Python files in infrastructure, samples, setup, and shared.

.PARAMETER ShowReport
    Display the full text report after completion.

.EXAMPLE
    .\run_ruff.ps1
    Run ruff on all repository Python files with default settings

.EXAMPLE
    .\run_ruff.ps1 -Target "../../samples" -ShowReport
    Run on samples folder and show detailed report
#>

param(
    [string]$Target = "infrastructure samples setup shared",
    [switch]$ShowReport
)

$ErrorActionPreference = "Continue"
$ScriptDir = $PSScriptRoot
$RepoRoot = Split-Path (Split-Path $ScriptDir -Parent) -Parent
$ReportDir = Join-Path $ScriptDir "ruff/reports"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Set UTF-8 encoding for Python and console output
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Ensure report directory exists
if (-not (Test-Path $ReportDir)) {
    New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
}

Write-Host "`n🔍 Running ruff analysis...`n" -ForegroundColor Cyan
Write-Host "   Target            : $Target" -ForegroundColor Gray
Write-Host "   Reports           : $ReportDir" -ForegroundColor Gray
Write-Host "   Working Directory : $RepoRoot`n" -ForegroundColor Gray

# Run ruff with multiple output formats
$TextReport = Join-Path $ReportDir "ruff_${Timestamp}.txt"
$JsonReport = Join-Path $ReportDir "ruff_${Timestamp}.json"
$LatestText = Join-Path $ReportDir "latest.txt"
$LatestJson = Join-Path $ReportDir "latest.json"

# Change to repository root and execute ruff
Push-Location $RepoRoot
try {
    ruff check $Target.Split(' ') `
        | Tee-Object -FilePath $TextReport
    $TextExitCode = $LASTEXITCODE

    ruff check --output-format json $Target.Split(' ') `
        | Tee-Object -FilePath $JsonReport | Out-Null
    $JsonExitCode = $LASTEXITCODE

    $ExitCode = if ($TextExitCode -ne 0) { $TextExitCode } else { $JsonExitCode }
} finally {
    Pop-Location
}

# Copy to latest reports
if (Test-Path $TextReport) {
    Copy-Item $TextReport $LatestText -Force
}
if (Test-Path $JsonReport) {
    Copy-Item $JsonReport $LatestJson -Force
}

# Display summary
Write-Host "`n📊 Ruff Summary`n" -ForegroundColor Cyan
Write-Host "   Exit code: $ExitCode" -ForegroundColor $(if ($ExitCode -eq 0) { "Green" } else { "Yellow" })
Write-Host "   Text report : $TextReport" -ForegroundColor Gray
Write-Host "   JSON report : $JsonReport" -ForegroundColor Gray

# Parse and display top issues from JSON
if (Test-Path $JsonReport) {
    $RawJson = Get-Content $JsonReport -Raw
    if ($RawJson -and $RawJson.Trim()) {
        $Issues = $RawJson | ConvertFrom-Json
        $GroupedIssues = $Issues | Group-Object -Property code | Sort-Object Count -Descending | Select-Object -First 10

        if ($GroupedIssues) {
            Write-Host "`n🔝 Top 10 Issues:" -ForegroundColor Cyan
            foreach ($Group in $GroupedIssues) {
                $Sample = $Issues | Where-Object { $_.code -eq $Group.Name } | Select-Object -First 1
                Write-Host "   [$($Group.Count.ToString().PadLeft(3))] " -NoNewline -ForegroundColor Yellow
                Write-Host "$($Group.Name)" -NoNewline -ForegroundColor White
                Write-Host " - $($Sample.message)" -ForegroundColor DarkGray
            }
        } else {
            Write-Host "`n✅ No issues found!" -ForegroundColor Green
        }
    }
}

# Show full report if requested
if ($ShowReport -and (Test-Path $TextReport)) {
    Write-Host "`n📄 Full Report:" -ForegroundColor Cyan
    Get-Content $TextReport
}

Write-Host ""
exit $ExitCode
