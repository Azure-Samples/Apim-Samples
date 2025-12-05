#!/bin/bash
# Run pylint on the Apim-Samples project with comprehensive reporting

set -e

TARGET="${1:-../../infrastructure ../../samples ../../setup ../../shared ../../tests}"
REPORT_DIR="pylint/reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Ensure report directory exists
mkdir -p "$REPORT_DIR"

echo ""
echo "🔍 Running pylint analysis..."
echo "   Target:  All repository Python files"
echo "   Reports: $REPORT_DIR"
echo ""

# Run pylint with multiple output formats
JSON_REPORT="$REPORT_DIR/pylint_${TIMESTAMP}.json"
TEXT_REPORT="$REPORT_DIR/pylint_${TIMESTAMP}.txt"
LATEST_JSON="$REPORT_DIR/latest.json"
LATEST_TEXT="$REPORT_DIR/latest.txt"

# Execute pylint (allow non-zero exit for reporting)
set +e
pylint --rcfile .pylintrc \
    --output-format=json:"$JSON_REPORT",colorized,text:"$TEXT_REPORT" \
    "$TARGET"
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
if [ $EXIT_CODE -eq 0 ]; then
    echo "   Exit code: $EXIT_CODE ✅"
else
    echo "   Exit code: $EXIT_CODE ⚠️"
fi
echo "   JSON report: $JSON_REPORT"
echo "   Text report: $TEXT_REPORT"

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
