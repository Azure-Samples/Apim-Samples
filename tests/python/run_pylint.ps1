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
    Path to analyze. Defaults to all Python files in infrastructure, samples, setup, shared, and tests.

.PARAMETER ShowReport
    Display the full text report after completion.

.EXAMPLE
    .\run_pylint.ps1
    Run pylint on all repository Python files with default settings

.EXAMPLE
    .\run_pylint.ps1 -Target "../../samples" -ShowReport
    Run on samples folder and show detailed report
#>

param(
    [string]$Target = "infrastructure samples setup shared tests",
    [switch]$ShowReport
)

$ErrorActionPreference = "Continue"
$ScriptDir = $PSScriptRoot
$RepoRoot = Split-Path (Split-Path $ScriptDir -Parent) -Parent
$ReportDir = Join-Path $ScriptDir "pylint/reports"
$PylintRc = Join-Path $RepoRoot ".pylintrc"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Set UTF-8 encoding for Python and console output
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Ensure report directory exists
if (-not (Test-Path $ReportDir)) {
    New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
}

Write-Host "`n🔍 Running pylint analysis...`n" -ForegroundColor Cyan
Write-Host "   Target            : $Target" -ForegroundColor Gray
Write-Host "   Reports           : $ReportDir" -ForegroundColor Gray
Write-Host "   Working Directory : $RepoRoot" -ForegroundColor Gray
Write-Host "   Pylint Config     : $PylintRc`n" -ForegroundColor Gray

# Run pylint with multiple output formats
$JsonReport = Join-Path $ReportDir "pylint_${Timestamp}.json"
$TextReport = Join-Path $ReportDir "pylint_${Timestamp}.txt"
$LatestJson = Join-Path $ReportDir "latest.json"
$LatestText = Join-Path $ReportDir "latest.txt"

$ReportDirRelative = [IO.Path]::GetRelativePath($RepoRoot, $ReportDir) -replace "\\", "/"
$JsonReportRelative = "$ReportDirRelative/pylint_${Timestamp}.json"
$TextReportRelative = "$ReportDirRelative/pylint_${Timestamp}.txt"

# Change to repository root and execute pylint
Push-Location $RepoRoot
try {
    pylint --rcfile "$PylintRc" `
        --output-format=json `
        $Target.Split(' ') `
        | Tee-Object -FilePath $JsonReport | Out-Null
    $JsonExitCode = $LASTEXITCODE

    pylint --rcfile "$PylintRc" `
        --output-format=text `
        $Target.Split(' ') `
        | Tee-Object -FilePath $TextReport
    $TextExitCode = $LASTEXITCODE

    $ExitCode = if ($JsonExitCode -ne 0) { $JsonExitCode } else { $TextExitCode }
} finally {
    Pop-Location
}

# Create symlinks to latest reports
if (Test-Path $JsonReport) {
    Copy-Item $JsonReport $LatestJson -Force
    Copy-Item $TextReport $LatestText -Force
}

# Display summary
Write-Host "`n📊 Pylint Summary`n" -ForegroundColor Cyan
Write-Host "   Exit code: $ExitCode" -ForegroundColor $(if ($ExitCode -eq 0) { "Green" } else { "Yellow" })
Write-Host "   JSON report       : $JsonReport" -ForegroundColor Gray
Write-Host "   Text report       : $TextReport" -ForegroundColor Gray

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
