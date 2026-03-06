#!/bin/bash
# Run ruff on the Apim-Samples project with comprehensive reporting

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TARGET="${1:-infrastructure samples setup shared}"
REPORT_DIR="$SCRIPT_DIR/ruff/reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Set UTF-8 encoding for Python and console output
export PYTHONIOENCODING=utf-8
export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Ensure report directory exists
mkdir -p "$REPORT_DIR"

echo ""
echo "🔍 Running ruff analysis..."
echo ""
echo "   Target            : $TARGET"
echo "   Reports           : $REPORT_DIR"
echo "   Working Directory : $REPO_ROOT"
echo ""

# Run ruff with multiple output formats
TEXT_REPORT="$REPORT_DIR/ruff_${TIMESTAMP}.txt"
JSON_REPORT="$REPORT_DIR/ruff_${TIMESTAMP}.json"
LATEST_TEXT="$REPORT_DIR/latest.txt"
LATEST_JSON="$REPORT_DIR/latest.json"

# Change to repository root and execute ruff (allow non-zero exit for reporting)
cd "$REPO_ROOT"
set +e
# shellcheck disable=SC2086
ruff check $TARGET 2>&1 | tee "$TEXT_REPORT"
EXIT_CODE=${PIPESTATUS[0]}
# shellcheck disable=SC2086
ruff check --output-format json $TARGET > "$JSON_REPORT" 2>/dev/null || true
set -e

# Copy to latest reports
if [ -f "$TEXT_REPORT" ]; then
    cp "$TEXT_REPORT" "$LATEST_TEXT"
fi
if [ -f "$JSON_REPORT" ]; then
    cp "$JSON_REPORT" "$LATEST_JSON"
fi

# Display summary
echo ""
echo "📊 Ruff Summary"
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "   Exit code: $EXIT_CODE ✅"
else
    echo "   Exit code: $EXIT_CODE ⚠️"
fi
echo "   Text report : $TEXT_REPORT"
echo "   JSON report : $JSON_REPORT"

# Parse and display top issues from JSON
if [ -f "$JSON_REPORT" ] && command -v jq &> /dev/null; then
    ISSUE_COUNT=$(jq 'length' "$JSON_REPORT" 2>/dev/null || echo "0")
    echo ""
    if [ "$ISSUE_COUNT" -eq 0 ]; then
        echo "✅ No issues found!"
    else
        echo "   $ISSUE_COUNT issue(s) found."
        echo ""
        echo "🔝 Top 10 Issues:"
        jq -r 'group_by(.code) | map({code: .[0].code, message: .[0].message, count: length}) | sort_by(-.count) | limit(10; .[]) | "   [\(.count | tostring)] \(.code)\n        \(.message)"' "$JSON_REPORT"
    fi
elif [ -f "$JSON_REPORT" ]; then
    ISSUE_COUNT=$(grep -c '"code"' "$JSON_REPORT" || true)
    echo ""
    if [ "$ISSUE_COUNT" -eq 0 ]; then
        echo "✅ No issues found!"
    else
        echo "   $ISSUE_COUNT issue(s) found. Install jq for detailed summary."
    fi
fi

# Optionally show full report
if [ "${2}" = "--show-report" ] && [ -f "$TEXT_REPORT" ]; then
    echo ""
    echo "📄 Full Report:"
    cat "$TEXT_REPORT"
fi

echo ""
exit $EXIT_CODE
