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

run_interactive_cmd() {
  echo ""
  echo ">>> $*"
  echo ""
  (cd "${REPO_ROOT}" && "$@")
  status=$?
  if [ "$status" -eq 0 ]; then
    return 0
  fi

  echo ""
  echo "Command exited with code $status"
  echo ""
  return $status
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
    (
      cd "${REPO_ROOT}" &&
        { [ -d .venv ] || uv venv; } &&
        "$(find_python)" setup/sync_dependencies.py >/dev/null 2>&1 || true
    )
  fi
}

pyrun() {
  if has_uv; then
    uv run --no-sync python "$@"
  else
    "$(find_python)" "$@"
  fi
}

read_menu_selection() {
  local prompt="$1"
  shift
  local choices=("$@")
  MENU_INPUT=''
  if [[ ! -t 0 ]]; then
    IFS= read -r -p "$prompt: " MENU_INPUT
    return $?
  fi

  printf '%s: ' "$prompt"
  local key normalized choice matches exact
  while true; do
    IFS= read -r -s -n 1 key || return 1
    case "$key" in
      ''|$'\r') printf '\n'; return 0 ;;
      $'\177'|$'\b')
        if [[ -n "$MENU_INPUT" ]]; then
          MENU_INPUT="${MENU_INPUT%?}"
          printf '\b \b'
        fi
        continue
        ;;
      [[:cntrl:]]) continue ;;
    esac

    MENU_INPUT+="$key"
    printf '%s' "$key"
    normalized="$(printf '%s' "$MENU_INPUT" | tr '[:upper:]' '[:lower:]')"
    matches=0
    exact=false
    for choice in "${choices[@]}"; do
      if [[ "$choice" == "$normalized"* ]]; then
        matches=$((matches + 1))
      fi
      if [[ "$choice" == "$normalized" ]]; then
        exact=true
      fi
    done
    if [[ "$matches" -eq 1 && "$exact" == true ]]; then
      printf '\n'
      return 0
    fi
  done
}

while true; do
  echo ""
  echo "APIM Samples Developer CLI"
  echo "=========================="
  echo ""
  echo "Setup"
  echo "  1) Complete environment setup"
  echo "  2) Azure CLI login"
  echo "  u) Install eligible uv dependencies from uv.lock"
  echo "  l) Upgrade to eligible uv dependencies & sync"
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
  echo "  d) Delete deployed infrastructures"
  echo "  c) Clean local artifacts (preserves .env)"
  echo ""
  echo "Misc"
  echo "  0) Exit"
  echo ""
  echo "Unique choices run immediately; press Enter for 1 (10 is also available)."
  read_menu_selection "Select an option" 0 1 2 3 4 5 6 7 8 9 10 u l p e w d c || break
  choice="$(printf '%s' "$MENU_INPUT" | tr '[:upper:]' '[:lower:]')"
  case "$choice" in
    1)
      if base_python=$("$(find_python)" -c 'import sys; print(sys._base_executable)'); then
        run_interactive_cmd "$base_python" "${REPO_ROOT}/setup/local_setup.py" --complete-setup
      else
        echo "Could not find a system Python to start setup."
      fi
      ;;
    2)
      echo ""
      read_menu_selection "Do you want to specify a tenant ID? (y/n)" y n || break
      use_tenant_id="$MENU_INPUT"
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
      run_cmd pyrun "${REPO_ROOT}/setup/verify_local_setup.py" --repair
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
    d)
      echo ""
      echo "Checking what is currently deployed. This discovery step does not delete any resources."
      run_interactive_cmd pyrun "${REPO_ROOT}/shared/python/cleanup_infrastructures.py"
      ;;
    u)
      if has_uv; then
        run_cmd "$(find_python)" "${REPO_ROOT}/setup/sync_dependencies.py"
      else
        echo ""
        echo "uv is not installed or not on PATH. Install uv first (see setup/README.md)."
        echo ""
      fi
      ;;
    l)
      if has_uv; then
        run_cmd "$(find_python)" "${REPO_ROOT}/setup/sync_dependencies.py" --upgrade
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
