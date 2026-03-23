#!/usr/bin/env bash

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "${SCRIPT_DIR}")"

echo ""
echo "Cleaning local artifacts..."
echo ""

# ── Directories ───────────────────────────────────────────────────────────────

for pattern in '.pytest_cache' '.ruff_cache' '__pycache__' 'htmlcov' 'build' 'dist' '.eggs'; do
    while IFS= read -r -d $'\0' dir; do
        echo "  Removing $dir"
        rm -rf "$dir"
    done < <(find "${REPO_ROOT}" -type d -name "$pattern" -print0 2>/dev/null)
done

# *.egg-info directories
while IFS= read -r -d $'\0' dir; do
    echo "  Removing $dir"
    rm -rf "$dir"
done < <(find "${REPO_ROOT}" -type d -name '*.egg-info' -print0 2>/dev/null)

# ── Files ─────────────────────────────────────────────────────────────────────

for pattern in '*.pyc' '*.pyo' '*.tmp' '*.temp' '.coverage'; do
    while IFS= read -r -d $'\0' f; do
        echo "  Removing $f"
        rm -f "$f"
    done < <(find "${REPO_ROOT}" -type f -name "$pattern" -print0 2>/dev/null)
done

# .coverage.* files
while IFS= read -r -d $'\0' f; do
    echo "  Removing $f"
    rm -f "$f"
done < <(find "${REPO_ROOT}" -type f -name '.coverage.*' -print0 2>/dev/null)

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "Done. Note: .env was intentionally left in place."
echo ""
