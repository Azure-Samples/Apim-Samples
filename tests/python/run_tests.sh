#!/usr/bin/env bash

# Shell script to run pytest with coverage.
# This script can be run from any working directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${REPO_ROOT}"

export COVERAGE_FILE="tests/python/.coverage"
pytest -v --cov=shared/python --cov-config=tests/python/.coveragerc --cov-report=html:tests/python/htmlcov tests/python/
