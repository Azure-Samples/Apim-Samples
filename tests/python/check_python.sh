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
"$SCRIPT_DIR/run_pylint.sh" "$TARGET" $SHOW_REPORT
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
TEST_OUTPUT=$("$SCRIPT_DIR/run_tests.sh" 2>&1)
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
    LINT_STATUS="⚠️  ISSUES FOUND"
fi

# Determine Test status
if [ $TEST_EXIT_CODE -eq 0 ]; then
    TEST_STATUS="✅ PASSED"
else
    TEST_STATUS="❌ FAILED"
fi

# Display results with proper alignment
echo "Pylint   : $LINT_STATUS"
if [ -n "$PYLINT_SCORE" ]; then
    echo "             ($PYLINT_SCORE)"
fi

echo "Tests    : $TEST_STATUS"
if [ $TOTAL_TESTS -gt 0 ]; then
    # Calculate percentages (using bc for floating point)
    PASSED_PERCENT=$(echo "scale=2; $PASSED_TESTS / $TOTAL_TESTS * 100" | bc)
    FAILED_PERCENT=$(echo "scale=2; $FAILED_TESTS / $TOTAL_TESTS * 100" | bc)

    # Right-align numbers with padding
    printf "            • Total  : %5d\n" "$TOTAL_TESTS"
    printf "            • Passed : %5d (% 6.2f%%)\n" "$PASSED_TESTS" "$PASSED_PERCENT"
    printf "            • Failed : %5d (% 6.2f%%)\n" "$FAILED_TESTS" "$FAILED_PERCENT"
fi

# Display code coverage
if [ -n "$COVERAGE_PERCENT" ]; then
    echo "Coverage : 📊 ${COVERAGE_PERCENT}"
fi

echo ""

# Determine overall exit code
OVERALL_EXIT_CODE=0
if [ $LINT_EXIT_CODE -ne 0 ]; then
    OVERALL_EXIT_CODE=$LINT_EXIT_CODE
fi
if [ $TEST_EXIT_CODE -ne 0 ]; then
    OVERALL_EXIT_CODE=$TEST_EXIT_CODE
fi

if [ $OVERALL_EXIT_CODE -eq 0 ]; then
    echo "🎉 All checks passed! Code is ready to commit."
else
    echo "⚠️  Some checks did not pass. Please review and fix issues."
fi

echo ""
exit $OVERALL_EXIT_CODE
