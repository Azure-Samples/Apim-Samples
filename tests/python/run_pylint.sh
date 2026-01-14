#!/bin/bash
# Run pylint on the Apim-Samples project with comprehensive reporting

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TARGET="${1:-infrastructure samples setup shared}"
REPORT_DIR="$SCRIPT_DIR/pylint/reports"
PYLINT_RC="$REPO_ROOT/.pylintrc"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Set UTF-8 encoding for Python and console output
export PYTHONIOENCODING=utf-8
export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Ensure report directory exists
mkdir -p "$REPORT_DIR"

echo ""
echo "🔍 Running pylint analysis..."
echo ""
echo "   Target            : $TARGET"
echo "   Reports           : $REPORT_DIR"
echo "   Working Directory : $REPO_ROOT"
echo ""

# Run pylint with multiple output formats
JSON_REPORT="$REPORT_DIR/pylint_${TIMESTAMP}.json"
TEXT_REPORT="$REPORT_DIR/pylint_${TIMESTAMP}.txt"
LATEST_JSON="$REPORT_DIR/latest.json"
LATEST_TEXT="$REPORT_DIR/latest.txt"

# Change to repository root and execute pylint (allow non-zero exit for reporting)
cd "$REPO_ROOT"
set +e
pylint --rcfile "$PYLINT_RC" \
    --output-format=json:"$JSON_REPORT",colorized,text:"$TEXT_REPORT" \
    $TARGET
EXIT_CODE=$?
set -e

# Create symlinks to latest reports
if [ -f "$JSON_REPORT" ]; then
    cp "$JSON_REPORT" "$LATEST_JSON"
    cp "$TEXT_REPORT" "$LATEST_TEXT"
fi

# Display summary
echo ""
echo "📊 Pylint Summary"
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "   Exit code: $EXIT_CODE ✅"
else
    echo "   Exit code: $EXIT_CODE ⚠️"
fi
echo "   JSON report       : $JSON_REPORT"
echo "   Text report       : $TEXT_REPORT"

# Parse and display top issues from JSON
if [ -f "$JSON_REPORT" ] && command -v jq &> /dev/null; then
    echo ""
    echo "🔝 Top 10 Issues:"
    jq -r 'group_by(.symbol) | map({symbol: .[0].symbol, msgid: .[0]."message-id", msg: .[0].message, count: length}) | sort_by(-.count) | limit(10; .[]) | "   [\(.count | tostring | tonumber)] \(.symbol) (\(.msgid))\n        \(.msg)"' "$JSON_REPORT"
elif [ -f "$JSON_REPORT" ]; then
    ISSUE_COUNT=$(grep -c '"symbol"' "$JSON_REPORT" || true)
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
