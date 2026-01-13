#!/bin/bash
# Run comprehensive Python code quality checks (linting and testing)
#
# This script executes both pylint linting and pytest testing in sequence,
# providing a complete code quality assessment. It's the recommended way
# to validate Python code changes before committing.
#
# Usage:
#   ./check_python.sh              # Run with default settings
#   ./check_python.sh --show-report  # Include detailed pylint report
#   ./check_python.sh samples      # Only lint the samples folder

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SHOW_REPORT=""
TARGET="${1:-infrastructure samples setup shared tests}"

PYLINT_SCORE=""

# Parse arguments
if [ "$1" = "--show-report" ]; then
    SHOW_REPORT="--show-report"
    TARGET="infrastructure samples setup shared tests"
elif [ "$2" = "--show-report" ]; then
    SHOW_REPORT="--show-report"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         Python Code Quality Check                         ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""


# ------------------------------
#    STEP 1: RUN PYLINT
# ------------------------------

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 1/2: Running Pylint"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

set +e
bash "$SCRIPT_DIR/run_pylint.sh" "$TARGET" $SHOW_REPORT
LINT_EXIT_CODE=$?
set -e

# Extract pylint score from the latest report, if available
PYLINT_LATEST_TEXT="$SCRIPT_DIR/pylint/reports/latest.txt"
if [ -f "$PYLINT_LATEST_TEXT" ]; then
    PYLINT_SCORE=$(grep -Eo 'rated at [0-9]+(\.[0-9]+)?/10' "$PYLINT_LATEST_TEXT" | head -n 1 | awk '{print $3}')
fi

echo ""


# ------------------------------
#    STEP 2: RUN TESTS
# ------------------------------

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 2/2: Running Tests"
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
#    FINAL SUMMARY
# ------------------------------

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         Final Results                                     ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Determine Pylint status
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

# Display results with proper alignment
echo "Pylint   : $LINT_STATUS"
if [ -n "$PYLINT_SCORE" ]; then
    echo "             ($PYLINT_SCORE)"
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
    printf "            • Total  : %5d\n" "$TOTAL_TESTS"
    printf "            • Passed : %5d (%6.2f%%)\n" "$PASSED_TESTS" "$PASSED_PERCENT"
    printf "            • Failed : %5d (%6.2f%%)\n" "$FAILED_TESTS" "$FAILED_PERCENT"
fi

# Display code coverage
if [ -n "$COVERAGE_PERCENT" ]; then
    echo "Coverage : 📊 ${COVERAGE_PERCENT}"
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

if [ $OVERALL_EXIT_CODE -eq 0 ]; then
    echo "🎉 All checks passed! Code is ready to commit."
else
    echo "⚠️  Some checks did not pass. Please review and fix issues."
fi

echo ""
exit $OVERALL_EXIT_CODE
