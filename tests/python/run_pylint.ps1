#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run pylint on the Apim-Samples project with comprehensive reporting.

.DESCRIPTION
    Executes pylint with multiple output formats for better visibility:
    - Colorized console output
    - JSON report for automated processing
    - Text report for detailed analysis
    - Statistics summary

.PARAMETER Target
    Path to analyze. Defaults to all Python files in shared/python.

.PARAMETER ShowReport
    Display the full text report after completion.

.EXAMPLE
    .\run_pylint.ps1
    Run pylint on shared/python with default settings

.EXAMPLE
    .\run_pylint.ps1 -Target "../../samples" -ShowReport
    Run on samples folder and show detailed report
#>

param(
    [string]$Target = "../../shared/python",
    [switch]$ShowReport
)

$ErrorActionPreference = "Continue"
$ReportDir = "pylint/reports"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Ensure report directory exists
if (-not (Test-Path $ReportDir)) {
    New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
}

Write-Host "`n🔍 Running pylint analysis..." -ForegroundColor Cyan
Write-Host "   Target:  $Target" -ForegroundColor Gray
Write-Host "   Reports: $ReportDir`n" -ForegroundColor Gray

# Run pylint with multiple output formats
$JsonReport = "$ReportDir/pylint_${Timestamp}.json"
$TextReport = "$ReportDir/pylint_${Timestamp}.txt"
$LatestJson = "$ReportDir/latest.json"
$LatestText = "$ReportDir/latest.txt"

# Execute pylint
pylint --rcfile .pylintrc `
    --output-format=json:$JsonReport,colorized,text:$TextReport `
    $Target

$ExitCode = $LASTEXITCODE

# Create symlinks to latest reports
if (Test-Path $JsonReport) {
    Copy-Item $JsonReport $LatestJson -Force
    Copy-Item $TextReport $LatestText -Force
}

# Display summary
Write-Host "`n📊 Pylint Summary" -ForegroundColor Cyan
Write-Host "   Exit code: $ExitCode" -ForegroundColor $(if ($ExitCode -eq 0) { "Green" } else { "Yellow" })
Write-Host "   JSON report: $JsonReport" -ForegroundColor Gray
Write-Host "   Text report: $TextReport" -ForegroundColor Gray

# Parse and display top issues from JSON
if (Test-Path $JsonReport) {
    $Issues = Get-Content $JsonReport | ConvertFrom-Json
    $GroupedIssues = $Issues | Group-Object -Property symbol | Sort-Object Count -Descending | Select-Object -First 10
    
    if ($GroupedIssues) {
        Write-Host "`n🔝 Top 10 Issues:" -ForegroundColor Cyan
        foreach ($Group in $GroupedIssues) {
            $Sample = $Issues | Where-Object { $_.symbol -eq $Group.Name } | Select-Object -First 1
            Write-Host "   [$($Group.Count.ToString().PadLeft(3))] " -NoNewline -ForegroundColor Yellow
            Write-Host "$($Group.Name) " -NoNewline -ForegroundColor White
            Write-Host "($($Sample.'message-id'))" -ForegroundColor Gray
            Write-Host "        $($Sample.message)" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "`n✅ No issues found!" -ForegroundColor Green
    }
}

# Show full report if requested
if ($ShowReport -and (Test-Path $TextReport)) {
    Write-Host "`n📄 Full Report:" -ForegroundColor Cyan
    Get-Content $TextReport
}

Write-Host ""
exit $ExitCode
