#!/usr/bin/env bash

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

find_python() {
  if [ -x "${REPO_ROOT}/.venv/Scripts/python.exe" ]; then
    echo "${REPO_ROOT}/.venv/Scripts/python.exe"
  elif [ -x "${REPO_ROOT}/.venv/bin/python" ]; then
    echo "${REPO_ROOT}/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3"
  else
    echo "python"
  fi
}

run_cmd() {
  echo ""
  echo ">>> $*"
  echo ""
  output=""
  if output=$(cd "${REPO_ROOT}" && "$@" 2>&1); then
    if [ -n "$output" ]; then
      printf '%s\n' "$output"
    fi
    return 0
  else
    status=$?
    if [ -n "$output" ]; then
      printf '%s\n' "$output"
    else
      echo "No output was returned from the command."
    fi
    echo ""
    echo "Command exited with code $status"
    echo ""
    return $status
  fi
}

show_account() {
  local py
  py=$(find_python)
  (cd "${REPO_ROOT}" && "$py" - <<'PY'
from pathlib import Path
import json
import sys
import os

root = Path(os.getcwd())
shared = root / "shared" / "python"
if str(shared) not in sys.path:
    sys.path.insert(0, str(shared))
try:
    import azure_resources as az
    info = az.get_account_info()
except Exception as exc:  # noqa: BLE001
    print(f"Failed to read Azure account info: {exc}")
PY
  )
}


has_uv() {
  command -v uv >/dev/null 2>&1
}

ensure_uv_env() {
  if has_uv; then
    (cd "${REPO_ROOT}" && { [ -d .venv ] || uv venv; } && uv sync >/dev/null 2>&1 || true)
  fi
}

pyrun() {
  if has_uv; then
    uv run python "$@"
  else
    "$(find_python)" "$@"
  fi
}

while true; do
  echo ""
  echo "APIM Samples Developer CLI"
  echo "=========================="
  echo ""
  echo "Setup"
  echo "  1) Complete environment setup"
  echo "  2) Azure CLI login"
  echo "  u) Update & sync uv dependencies (refresh uv.lock)"
  echo ""
  echo "Verify"
  echo "  3) Verify local setup"
  echo "  4) Show Azure account info"
  echo "  5) Show soft-deleted resources"
  echo "  6) Show all deployed infrastructures"
  echo ""
  echo "Tests"
  echo "  7) Run python ruff"
  echo "  8) Run python tests (shows detailed test results)"
  echo "  9) Run Bicep lint"
  echo " 10) Run full checks (most statistics)"
  echo ""
  echo "Presentation"
  echo "  p) Serve & view presentation (auto-opens browser)"
  echo "  e) Export presentation as self-contained HTML"
  echo "  w) Serve & view GitHub Pages website (auto-opens browser)"
  echo ""
  echo "Cleanup"
  echo "  c) Clean local artifacts (preserves .env)"
  echo ""
  echo "Misc"
  echo "  0) Exit"
  echo ""
  read -rp "Select an option: " choice
  case "$choice" in
    1)
      run_cmd pyrun "${REPO_ROOT}/setup/local_setup.py" --complete-setup
      ;;
    2)
      echo ""
      read -rp "Do you want to specify a tenant ID? (y/n): " use_tenant_id
      if [ "$use_tenant_id" = "y" ] || [ "$use_tenant_id" = "Y" ]; then
        read -rp "Enter tenant ID: " tenant_id
        if [ -n "$tenant_id" ]; then
          echo ""
          echo ">>> az login --tenant $tenant_id"
          echo ""
          exec az login --tenant "$tenant_id" <&1
        else
          echo "Tenant ID is required."
        fi
      else
        echo ""
        echo ">>> az login"
        echo ""
        exec az login <&1
      fi
      ;;
    3)
      run_cmd pyrun "${REPO_ROOT}/setup/verify_local_setup.py"
      ;;
    4)
      show_account
      ;;
    5)
      run_cmd pyrun "${REPO_ROOT}/shared/python/show_soft_deleted_resources.py"
      ;;
    6)
      run_cmd pyrun "${REPO_ROOT}/shared/python/show_infrastructures.py"
      ;;
    7)
      run_cmd bash "${REPO_ROOT}/tests/python/run_ruff.sh"
      ;;
    8)
      run_cmd bash "${REPO_ROOT}/tests/python/run_tests.sh"
      ;;
    9)
      run_cmd bash "${REPO_ROOT}/tests/bicep/run_bicep_lint.sh"
      ;;
    10)
      run_cmd bash "${REPO_ROOT}/tests/python/check_python.sh"
      ;;
    p)
      run_cmd pyrun "${REPO_ROOT}/setup/serve_presentation.py"
      ;;
    e)
      run_cmd pyrun "${REPO_ROOT}/setup/export_presentation.py"
      ;;
    w)
      run_cmd pyrun "${REPO_ROOT}/setup/serve_website.py"
      ;;
    c)
      run_cmd bash "${REPO_ROOT}/setup/clean-local-artifacts.sh"
      ;;
    u)
      if has_uv; then
        if run_cmd uv lock --upgrade; then
          run_cmd uv sync
        fi
      else
        echo ""
        echo "uv is not installed or not on PATH. Install uv first (see setup/README.md)."
        echo ""
      fi
      ;;
    0)
      echo ""
      echo "Goodbye!"
      echo ""
      exit 0
      ;;
    *)
      echo "Invalid option. Please try again."
      ;;
  esac
done
