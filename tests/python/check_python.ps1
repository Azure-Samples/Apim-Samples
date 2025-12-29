#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run comprehensive Python code quality checks (linting and testing).

.DESCRIPTION
    This script executes both pylint linting and pytest testing in sequence,
    providing a complete code quality assessment. It's the recommended way
    to validate Python code changes before committing.

    The script can be run from anywhere in the repository and will:
    - Execute pylint on all Python code with detailed reporting
    - Run the full test suite with coverage analysis
    - Display combined results and exit with appropriate status code

.PARAMETER ShowLintReport
    Display the full pylint text report after completion.

.PARAMETER Target
    Path to analyze for pylint. Defaults to all Python files in the repository.

.EXAMPLE
    .\check_python.ps1
    Run both linting and testing with default settings

.EXAMPLE
    .\check_python.ps1 -ShowLintReport
    Run checks and show detailed pylint report

.EXAMPLE
    .\check_python.ps1 -Target "samples"
    Run checks but only lint the samples folder
#>

param(
    [switch]$ShowLintReport,
    [string]$Target = "infrastructure samples setup shared tests"
)

$ErrorActionPreference = "Continue"
$ScriptDir = $PSScriptRoot

Write-Host ""
Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         Python Code Quality Check          ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""


# ------------------------------
#    STEP 1: RUN PYLINT
# ------------------------------

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "  Step 1/2: Running Pylint   " -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

$LintArgs = @{
    Target = $Target
}
if ($ShowLintReport) {
    $LintArgs.ShowReport = $true
}

& "$ScriptDir\run_pylint.ps1" @LintArgs
$LintExitCode = $LASTEXITCODE

Write-Host ""


# ------------------------------
#    STEP 2: RUN TESTS
# ------------------------------
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "  Step 2/2: Running Tests    " -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

# Capture test output and pass it through to console while also capturing it
$TestOutput = @()
& "$ScriptDir\run_tests.ps1" 2>&1 | Tee-Object -Variable TestOutput | Write-Host
$TestExitCode = $LASTEXITCODE

# Parse test results from captured output
$TotalTests = 0
$PassedTests = 0
$FailedTests = 0

foreach ($Line in $TestOutput) {
    $LineStr = $Line.ToString()
    # Look for pytest summary line like "908 passed, 9 failed in 26.76s"
    if ($LineStr -match '(\d+)\s+passed') {
        $PassedTests = [int]::Parse($matches[1])
    }
    if ($LineStr -match '(\d+)\s+failed') {
        $FailedTests = [int]::Parse($matches[1])
    }
}

$TotalTests = $PassedTests + $FailedTests

Write-Host ""


# ------------------------------
#    FINAL SUMMARY
# ------------------------------

Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         Final Results                      ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Determine statuses
$LintStatus = if ($LintExitCode -eq 0) { "✅ PASSED" } else { "⚠️  ISSUES FOUND" }
$TestStatus = if ($TestExitCode -eq 0) { "✅ PASSED" } else { "❌ FAILED" }

# Get pylint score
$PylintScore = $null
$LatestPylintText = Join-Path $ScriptDir "pylint/reports/latest.txt"
if (Test-Path $LatestPylintText) {
    $ScoreMatch = Select-String -Path $LatestPylintText -Pattern 'rated at (\d+(?:\.\d+)?/10)' | Select-Object -First 1
    if ($ScoreMatch -and $ScoreMatch.Matches.Count -gt 0) {
        $PylintScore = $ScoreMatch.Matches[0].Groups[1].Value
    }
}

# Set colors
$LintColor = if ($LintExitCode -eq 0) { "Green" } else { "Yellow" }
$TestColor = if ($TestExitCode -eq 0) { "Green" } else { "Red" }

# Calculate column widths for alignment
$LabelWidth = "Pylint :".Length  # 7
$Padding = " " * ($LabelWidth - 1)

# Display Pylint status with score
Write-Host "Pylint : " -NoNewline
Write-Host $LintStatus -ForegroundColor $LintColor -NoNewline
if ($PylintScore) {
    Write-Host " ($PylintScore)" -ForegroundColor Gray
} else {
    Write-Host ""
}

# Display Test status with counts
Write-Host "Tests  : " -NoNewline
Write-Host $TestStatus -ForegroundColor $TestColor

# Display test counts with right-aligned numbers
if ($TotalTests -gt 0) {
    # Calculate padding for right-alignment (max 5 digits)
    $TotalPadded = "{0,5}" -f $TotalTests
    $PassedPadded = "{0,5}" -f $PassedTests
    $FailedPadded = "{0,5}" -f $FailedTests

    Write-Host "          • Total  : $TotalPadded" -ForegroundColor Gray
    Write-Host "          • Passed : $PassedPadded" -ForegroundColor Gray
    Write-Host "          • Failed : $FailedPadded" -ForegroundColor Gray
}

Write-Host ""

# Determine overall exit code
$OverallExitCode = 0
if ($LintExitCode -ne 0) {
    $OverallExitCode = $LintExitCode
}
if ($TestExitCode -ne 0) {
    $OverallExitCode = $TestExitCode
}

if ($OverallExitCode -eq 0) {
    Write-Host "🎉 All checks passed! Code is ready to commit." -ForegroundColor Green
} else {
    Write-Host "⚠️  Some checks did not pass. Please review and fix issues." -ForegroundColor Yellow
}

Write-Host ""
exit $OverallExitCode
