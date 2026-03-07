#!/bin/bash
# Run comprehensive code quality checks (Python linting, Python tests, Bicep linting)
#
# This script executes ruff linting, pytest testing, and Bicep linting in
# sequence, providing a complete code quality assessment across the repo.
# It is the recommended way to validate changes before committing.
#
# Usage:
#   ./check_python.sh              # Run with default settings
#   ./check_python.sh --show-report  # Include detailed ruff report
#   ./check_python.sh samples      # Only lint the samples folder

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SHOW_REPORT=""
TARGET="${1:-infrastructure samples setup shared}"

RUFF_ISSUE_COUNT=""

# Parse arguments
if [ "$1" = "--show-report" ]; then
    SHOW_REPORT="--show-report"
    TARGET="infrastructure samples setup shared"
elif [ "$2" = "--show-report" ]; then
    SHOW_REPORT="--show-report"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         Code Quality Check                                ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""


# ------------------------------
#    STEP 1: RUN RUFF
# ------------------------------

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 1/3: Running Ruff"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

set +e
bash "$SCRIPT_DIR/run_ruff.sh" "$TARGET" $SHOW_REPORT
LINT_EXIT_CODE=$?
set -e

# Extract ruff issue count from the latest JSON report, if available
RUFF_LATEST_JSON="$SCRIPT_DIR/ruff/reports/latest.json"
if [ -f "$RUFF_LATEST_JSON" ] && command -v jq &> /dev/null; then
    RUFF_ISSUE_COUNT=$(jq 'length' "$RUFF_LATEST_JSON" 2>/dev/null || echo "")
fi

echo ""


# ------------------------------
#    STEP 2: RUN TESTS
# ------------------------------

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 2/3: Running Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

set +e
TEST_OUTPUT=$(bash "$SCRIPT_DIR/run_tests.sh" 2>&1)
TEST_EXIT_CODE=$?
set -e

# Print the test output
echo "$TEST_OUTPUT"

# Parse test results from output
PASSED_TESTS=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ passed' | head -1 | grep -oE '[0-9]+' || echo "0")
FAILED_TESTS=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ failed' | head -1 | grep -oE '[0-9]+' || echo "0")
WARNING_COUNT=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ warning' | head -1 | grep -oE '[0-9]+' || echo "0")
TOTAL_TESTS=$((PASSED_TESTS + FAILED_TESTS))

# Parse coverage from pytest output (e.g., "TOTAL ... 95%")
COVERAGE_PERCENT=""
if echo "$TEST_OUTPUT" | grep -qE 'TOTAL\s+.*\s+\d+%'; then
    COVERAGE_PERCENT=$(echo "$TEST_OUTPUT" | grep -oE 'TOTAL\s+.*\s+(\d+)%' | grep -oE '[0-9]+%' | head -1)
fi

# Detect slow tests (>0.1s execution time)
SLOW_TESTS_FOUND=0
if echo "$TEST_OUTPUT" | grep -qE '[0-9]+\.[0-9]+s\s+call\s+'; then
    # Check each line with slow test pattern for times > 0.1
    while IFS= read -r line; do
        if [[ $line =~ ^([0-9]+\.[0-9]+)s\ +call ]]; then
            time="${BASH_REMATCH[1]}"
            # Use awk for floating point comparison instead of bc
            if awk "BEGIN {exit !($time > 0.1)}"; then
                SLOW_TESTS_FOUND=1
                break
            fi
        fi
    done <<< "$(echo "$TEST_OUTPUT" | grep -E '[0-9]+\.[0-9]+s\s+call\s+')"
fi

echo ""


# ------------------------------
#    STEP 3: RUN BICEP LINT
# ------------------------------

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 3/3: Running Bicep Lint"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

set +e
BICEP_OUTPUT=$(bash "$SCRIPT_DIR/../bicep/run_bicep_lint.sh" 2>&1)
BICEP_EXIT_CODE=$?
set -e

# Print the bicep output
echo "$BICEP_OUTPUT"

# Parse bicep file count from "Files     : N"
BICEP_FILE_COUNT=$(echo "$BICEP_OUTPUT" | grep -oE 'Files\s*:\s*[0-9]+' | grep -oE '[0-9]+' | head -1 || echo "")

echo ""


# ------------------------------
#    FINAL SUMMARY
# ------------------------------

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         Final Results                                     ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Determine Ruff status
if [ $LINT_EXIT_CODE -eq 0 ]; then
    LINT_STATUS="✅ PASSED"
else
    LINT_STATUS="⚠️  ISSUES FOUND" # leave two spaces after yellow triangle to display correctly
fi

# Determine Test status (must have zero failed tests AND zero exit code)
if [ $FAILED_TESTS -eq 0 ] && [ $TEST_EXIT_CODE -eq 0 ]; then
    TEST_STATUS="✅ PASSED"
else
    TEST_STATUS="❌ FAILED"
fi

# Determine Bicep status
if [ $BICEP_EXIT_CODE -eq 0 ]; then
    BICEP_STATUS="✅ PASSED"
else
    BICEP_STATUS="⚠️  ISSUES FOUND" # leave two spaces after yellow triangle to display correctly
fi

# Display results with proper alignment
echo "Ruff     : $LINT_STATUS"
if [ -n "$RUFF_ISSUE_COUNT" ]; then
    echo "             ($RUFF_ISSUE_COUNT issues)"
fi

if [ $FAILED_TESTS -eq 0 ] && [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "Tests    : $TEST_STATUS"
else
    echo -e "Tests    : \e[31m$TEST_STATUS\e[0m"  # Red color for failed tests
fi
if [ $TOTAL_TESTS -gt 0 ]; then
    # Calculate percentages using awk for floating point arithmetic
    PASSED_PERCENT=$(echo "$PASSED_TESTS $TOTAL_TESTS" | awk '{printf "%.2f", ($1 / $2 * 100)}')
    FAILED_PERCENT=$(echo "$FAILED_TESTS $TOTAL_TESTS" | awk '{printf "%.2f", ($1 / $2 * 100)}')

    # Right-align numbers with padding
    printf "            • Total    : %5d\n" "$TOTAL_TESTS"
    printf "            • Passed   : %5d (%6.2f%%)\n" "$PASSED_TESTS" "$PASSED_PERCENT"
    printf "            • Failed   : %5d (%6.2f%%)\n" "$FAILED_TESTS" "$FAILED_PERCENT"
    if [ "$WARNING_COUNT" -gt 0 ]; then
        WARNING_PERCENT=$(echo "$WARNING_COUNT $TOTAL_TESTS" | awk '{printf "%.2f", ($1 / $2 * 100)}')
        printf "            \e[33m• Warnings : %5d (%6.2f%%)\e[0m\n" "$WARNING_COUNT" "$WARNING_PERCENT"
    fi
fi

# Display code coverage
if [ -n "$COVERAGE_PERCENT" ]; then
    echo "Coverage : 📊 ${COVERAGE_PERCENT}"
fi

# Display Bicep status with file count
if [ $BICEP_EXIT_CODE -eq 0 ]; then
    echo "Bicep    : $BICEP_STATUS"
else
    echo -e "Bicep    : \e[33m$BICEP_STATUS\e[0m"  # Yellow color for issues
fi
if [ -n "$BICEP_FILE_COUNT" ]; then
    echo "             ($BICEP_FILE_COUNT files)"
fi

# Display slow tests warning if detected
if [ $SLOW_TESTS_FOUND -eq 1 ]; then
    echo ""
    echo "⚠️  SLOW TESTS DETECTED (> 0.1s). Please review slowest durations in test summary." | sed 's/^/\e[33m/;s/$/\e[0m/'  # Yellow color
fi

echo ""

# Determine overall exit code
OVERALL_EXIT_CODE=0
if [ $LINT_EXIT_CODE -ne 0 ]; then
    OVERALL_EXIT_CODE=$LINT_EXIT_CODE
fi
if [ $TEST_EXIT_CODE -ne 0 ] || [ $FAILED_TESTS -ne 0 ]; then
    OVERALL_EXIT_CODE=$TEST_EXIT_CODE
    if [ $OVERALL_EXIT_CODE -eq 0 ]; then
        OVERALL_EXIT_CODE=1
    fi
fi
if [ $BICEP_EXIT_CODE -ne 0 ]; then
    OVERALL_EXIT_CODE=$BICEP_EXIT_CODE
fi

if [ $OVERALL_EXIT_CODE -eq 0 ]; then
    echo "🎉 All checks passed! Code is ready to commit."
else
    echo "⚠️  Some checks did not pass. Please review and fix issues."
fi

echo ""
exit $OVERALL_EXIT_CODE
