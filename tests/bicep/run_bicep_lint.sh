#!/usr/bin/env bash
# Lint all Bicep files in the repository.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [ "$#" -gt 0 ]; then
  SEARCH_ROOTS=("$@")
else
  SEARCH_ROOTS=("infrastructure" "samples" "shared")
fi
DEFAULT_SEARCH_ROOTS=("infrastructure" "samples" "shared")

get_bicep_executable() {
  if command -v bicep >/dev/null 2>&1; then
    command -v bicep
    return 0
  fi

  local candidates=("$HOME/.azure/bin/bicep" "$HOME/.azure/bin/bicep.exe")
  local candidate
  for candidate in "${candidates[@]}"; do
    if [ -x "$candidate" ] || [ -f "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  if ! command -v az >/dev/null 2>&1; then
    return 1
  fi

  # Ask Azure CLI to provision/validate the Bicep binary once, then use it directly.
  az bicep version >/dev/null || return 1

  for candidate in "${candidates[@]}"; do
    if [ -x "$candidate" ] || [ -f "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

BICEP_EXECUTABLE="$(get_bicep_executable)"
if [ -z "$BICEP_EXECUTABLE" ]; then
  echo ""
  echo "Bicep CLI is required to lint Bicep files."
  echo ""
  exit 1
fi

get_lint_patterns() {
  local roots=("$@")
  local matches_default=1
  local i

  if [ ${#roots[@]} -ne ${#DEFAULT_SEARCH_ROOTS[@]} ]; then
    matches_default=0
  else
    for i in "${!DEFAULT_SEARCH_ROOTS[@]}"; do
      local normalized_root="${roots[$i]%/}"
      normalized_root="${normalized_root%\\}"
      if [ "$normalized_root" != "${DEFAULT_SEARCH_ROOTS[$i]}" ]; then
        matches_default=0
        break
      fi
    done
  fi

  if [ $matches_default -eq 1 ]; then
    printf '%s\n' '**/*.bicep'
    return 0
  fi

  local root
  for root in "${roots[@]}"; do
    root="${root%/}"
    root="${root%\\}"
    printf '%s\n' "$root/**/*.bicep"
  done
}

FILES=()
for root in "${SEARCH_ROOTS[@]}"; do
  if [ -d "$REPO_ROOT/$root" ]; then
    while IFS= read -r file; do
      FILES+=("$file")
    done < <(find "$REPO_ROOT/$root" -type f -name '*.bicep' | sort)
  fi
done

if [ ${#FILES[@]} -eq 0 ]; then
  echo ""
  echo "No Bicep files found to lint."
  echo ""
  exit 0
fi

echo ""
echo "Running Bicep lint across the repository..."
echo ""
echo "Files     : ${#FILES[@]}"
echo "Bicep CLI : $BICEP_EXECUTABLE"
echo ""

FAILED_FILES=()
while IFS= read -r pattern; do
  echo ">>> $BICEP_EXECUTABLE lint --pattern $pattern"
  if ! "$BICEP_EXECUTABLE" lint --pattern "$pattern"; then
    FAILED_FILES+=("$pattern")
  fi
  echo ""
done < <(get_lint_patterns "${SEARCH_ROOTS[@]}")

if [ ${#FAILED_FILES[@]} -eq 0 ]; then
  echo "All Bicep files passed linting."
  exit 0
fi

echo "Bicep lint failed for pattern(s):"
for failed_file in "${FAILED_FILES[@]}"; do
  echo "  - $failed_file"
done

exit 1
