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

export COVERAGE_FILE="tests/python/.coverage"
pytest -v --color=yes --cov=shared/python --cov-config=tests/python/.coveragerc --cov-report=html:tests/python/htmlcov --cov-report=json tests/python/

# Generate coverage.json for VS Code visualization
echo ""
echo "Generating coverage.json for VS Code..."
coverage json

# Display coverage summary
echo ""
echo "Coverage Summary:"
coverage report --skip-covered
