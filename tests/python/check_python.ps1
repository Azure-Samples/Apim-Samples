#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run comprehensive Python code quality checks (linting and testing).

.DESCRIPTION
    This script executes both ruff linting and pytest testing in sequence,
    providing a complete code quality assessment. It's the recommended way
    to validate Python code changes before committing.

    The script can be run from anywhere in the repository and will:
    - Execute ruff on all Python code with detailed reporting
    - Run the full test suite with coverage analysis
    - Display combined results and exit with appropriate status code

.PARAMETER ShowLintReport
    Display the full ruff text report after completion.

.PARAMETER Target
    Path to analyze for ruff. Defaults to all Python files in the repository.

.EXAMPLE
    .\check_python.ps1
    Run both linting and testing with default settings

.EXAMPLE
    .\check_python.ps1 -ShowLintReport
    Run checks and show detailed ruff report

.EXAMPLE
    .\check_python.ps1 -Target "samples"
    Run checks but only lint the samples folder
#>

param(
    [switch]$ShowLintReport,
    [string]$Target = "infrastructure samples setup shared"
)

$ErrorActionPreference = "Continue"
$ScriptDir = $PSScriptRoot

Write-Host ""
Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         Python Code Quality Check          ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""


# ------------------------------
#    STEP 1: RUN RUFF
# ------------------------------

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "  Step 1/2: Running Ruff    " -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

$LintArgs = @{
    Target = $Target
}
if ($ShowLintReport) {
    $LintArgs.ShowReport = $true
}

& "$ScriptDir\run_ruff.ps1" @LintArgs
$LintExitCode = $LASTEXITCODE

Write-Host ""


# ------------------------------
#    STEP 2: RUN TESTS
# ------------------------------
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "  Step 2/2: Running Tests   " -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
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

# Parse coverage from coverage.json
$CoveragePercent = $null
$CoverageJsonPath = Join-Path $ScriptDir "..\..\coverage.json"
if (Test-Path $CoverageJsonPath) {
    try {
        $CoverageData = Get-Content $CoverageJsonPath -Raw | ConvertFrom-Json
        if ($CoverageData.totals -and $CoverageData.totals.percent_covered) {
            $CoveragePercent = $CoverageData.totals.percent_covered
        }
    }
    catch {
        # Silently continue if coverage parsing fails
    }
}

# Fallback: Parse coverage from pytest output (e.g., "TOTAL ... 95%")
if ($CoveragePercent -eq $null) {
    foreach ($Line in $TestOutput) {
        $LineStr = $Line.ToString()
        if ($LineStr -match 'TOTAL\s+.*\s+(\d+)%') {
            $CoveragePercent = [int]::Parse($matches[1])
            break
        }
    }
}

# Detect slow tests (>0.1s execution time)
$SlowTestsFound = $false
foreach ($Line in $TestOutput) {
    $LineStr = $Line.ToString()
    # Match lines like "1.23s call test_file.py::test_name"
    if ($LineStr -match '(\d+\.\d+)s\s+call\s+') {
        $time = [double]::Parse($matches[1])
        if ($time -gt 0.1) {
            $SlowTestsFound = $true
            break
        }
    }
}

Write-Host ""


# ------------------------------
#    FINAL SUMMARY
# ------------------------------

Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         Final Results                      ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Determine statuses - tests need both 0 failures AND 0 exit code
$LintStatus = if ($LintExitCode -eq 0) { "✅ PASSED" } else { "⚠️  ISSUES FOUND" } # leave two spaces after yellow triangle to display correctly
$TestStatus = if ($FailedTests -eq 0 -and $TestExitCode -eq 0) { "✅ PASSED" } else { "❌ FAILED" }

# Get ruff issue count
$RuffIssueCount = $null
$LatestRuffJson = Join-Path $ScriptDir "ruff/reports/latest.json"

if (Test-Path $LatestRuffJson) {
    try {
        $RawJson = Get-Content $LatestRuffJson -Raw
        if ($RawJson -and $RawJson.Trim()) {
            $Issues = $RawJson | ConvertFrom-Json
            if ($null -eq $Issues) {
                $RuffIssueCount = 0
            }
            elseif ($Issues -is [System.Array]) {
                $RuffIssueCount = $Issues.Count
            }
            else {
                $RuffIssueCount = 1
            }
        }
    }
    catch {
        $RuffIssueCount = $null
    }
}

# Set colors
$LintColor = if ($LintExitCode -eq 0) { "Green" } else { "Yellow" }
$TestColor = if ($FailedTests -eq 0 -and $TestExitCode -eq 0) { "Green" } else { "Red" }

# Display Ruff status with issue count
Write-Host "Ruff     : " -NoNewline
Write-Host $LintStatus -ForegroundColor $LintColor -NoNewline
if ($RuffIssueCount -ne $null) {
    $IssueLabel = if ($RuffIssueCount -eq 1) { "1 issue" } else { "$RuffIssueCount issues" }
    Write-Host " (" -ForegroundColor Gray -NoNewline
    Write-Host $IssueLabel -ForegroundColor Gray -NoNewline
    Write-Host ")" -ForegroundColor Gray
} else {
    Write-Host ""
}

# Display Test status with counts
Write-Host "Tests    : " -NoNewline
Write-Host $TestStatus -ForegroundColor $TestColor

# Display test counts with right-aligned numbers and percentages
if ($TotalTests -gt 0) {
    # Calculate padding for right-alignment (max 5 digits)
    $TotalPadded = "{0,5}" -f $TotalTests
    $PassedPadded = "{0,5}" -f $PassedTests
    $FailedPadded = "{0,5}" -f $FailedTests

    # Calculate percentages
    $PassedPercent = ($PassedTests / $TotalTests * 100)
    $FailedPercent = ($FailedTests / $TotalTests * 100)
    $PassedPercentStr = "{0,6:F2}" -f $PassedPercent
    $FailedPercentStr = "{0,6:F2}" -f $FailedPercent

    Write-Host "            • Total  : $TotalPadded" -ForegroundColor Gray
    Write-Host "            • Passed : $PassedPadded (" -ForegroundColor Gray -NoNewline
    Write-Host $PassedPercentStr -ForegroundColor Gray -NoNewline
    Write-Host "%)" -ForegroundColor Gray
    Write-Host "            • Failed : $FailedPadded (" -ForegroundColor Gray -NoNewline
    Write-Host $FailedPercentStr -ForegroundColor Gray -NoNewline
    Write-Host "%)" -ForegroundColor Gray
}

# Display code coverage
if ($CoveragePercent -ne $null) {
    Write-Host "Coverage : " -NoNewline
    Write-Host "📊 " -NoNewline
    Write-Host ("{0:F2}" -f $CoveragePercent) -ForegroundColor Cyan -NoNewline
    Write-Host "%" -ForegroundColor Cyan
}

# Display slow tests warning if detected
if ($SlowTestsFound) {
    Write-Host ""
    Write-Host "⚠️  SLOW TESTS DETECTED (> 0.1s). Please review slowest durations in test summary." -ForegroundColor Yellow
}

Write-Host ""

# Determine overall exit code - require both 0 failed tests AND exit code 0 for test success
$OverallExitCode = 0
if ($LintExitCode -ne 0) {
    $OverallExitCode = $LintExitCode
}
# Tests must have both 0 failures AND 0 exit code to pass
if ($FailedTests -ne 0 -or $TestExitCode -ne 0) {
    $OverallExitCode = if ($TestExitCode -ne 0) { $TestExitCode } else { 1 }
}

if ($OverallExitCode -eq 0) {
    Write-Host "🎉 All checks passed! Code is ready to commit." -ForegroundColor Green
} else {
    Write-Host "⚠️  Some checks did not pass. Please review and fix issues." -ForegroundColor Yellow
}

Write-Host ""
exit $OverallExitCode
