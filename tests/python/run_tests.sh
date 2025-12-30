#!/usr/bin/env bash

# Shell script to run pytest with coverage.
# This script can be run from any working directory.

set -euo pipefail

# Set UTF-8 encoding for Python and console output
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1
export LC_ALL=C.UTF-8
export LANG=C.UTF-8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${REPO_ROOT}"

export COVERAGE_FILE=".coverage"
pytest -v --color=yes --durations=3 --durations-min=0.1 --cov=shared/python --cov-config=tests/python/.coveragerc --cov-report=html:tests/python/htmlcov --cov-report=xml:coverage.xml --cov-report=json:coverage.json tests/python/

# Display coverage summary
echo ""
echo "Coverage Summary:"
coverage report --skip-covered

echo ""
echo "✅ Coverage reports generated:"
echo "   - HTML: htmlcov/index.html"
echo "   - XML: coverage.xml (for VS Code)"
echo "   - JSON: coverage.json"
