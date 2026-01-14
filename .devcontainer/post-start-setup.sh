#!/bin/bash

# ------------------------------
#    APIM SAMPLES INSTANT VERIFICATION
# ------------------------------

# Exit silently if not in devcontainer
if [ ! -d "/workspaces/Apim-Samples" ]; then
    echo ""
    echo "This script only runs as part of a devcontainer / Codespace."
    echo "Exiting."
    echo ""

    exit 0
fi

start=$(date +%s.%N)

# Ensure workspace scripts are executable (handles mounts without exec bit)
chmod +x .devcontainer/post-start-setup.sh start.sh start.ps1 setup/*.sh setup/*.ps1 tests/python/*.sh 2>/dev/null || true

# Make terminal output more prominent
clear
echo "============================================================================"
echo "                    🚀 APIM SAMPLES - INSTANT VERIFICATION                "
echo "============================================================================"
echo ""
echo "⚡ Running unified verification (setup/verify_local_setup.py)..."
echo ""

WORKSPACE_ROOT="/workspaces/Apim-Samples"

# Use venv python directly (uv manages the venv)
PY_CMD="$WORKSPACE_ROOT/.venv/bin/python"

# Fallback to system python if venv doesn't exist yet
if [ ! -x "$PY_CMD" ]; then
    if command -v python3 &> /dev/null; then
        PY_CMD=python3
    else
        PY_CMD=python
    fi
fi

cd "$WORKSPACE_ROOT" || exit 1

# Configure shell profile to auto-activate venv
BASHRC="${HOME}/.bashrc"

# Add venv activation to .bashrc if not already present
if [ -f "$BASHRC" ] && ! grep -q "activate.*\.venv" "$BASHRC" 2>/dev/null; then
    echo "" >> "$BASHRC"
    echo "# Auto-activate Python venv for APIM Samples" >> "$BASHRC"
    echo "if [ -f '$WORKSPACE_ROOT/.venv/bin/activate' ]; then" >> "$BASHRC"
    echo "    source '$WORKSPACE_ROOT/.venv/bin/activate'" >> "$BASHRC"
    echo "fi" >> "$BASHRC"
fi

"$PY_CMD" setup/verify_local_setup.py || true

# Open CODESPACES-QUICKSTART.md in preview mode with focus
if [ -f "$WORKSPACE_ROOT/.devcontainer/CODESPACES-QUICKSTART.md" ]; then
    code --reuse-window "$WORKSPACE_ROOT/.devcontainer/CODESPACES-QUICKSTART.md" --goto
fi

# Calculate total duration
end=$(date +%s.%N)
duration=$(python3 -c "print(f'{float('$end') - float('$start'):.1f}')" 2>/dev/null || echo "0.1")

echo ""
echo "============================================================================="
echo "                          ⚡ INSTANT VERIFICATION COMPLETE!                 "
echo "============================================================================="
echo ""
printf "⏱️  Verification time: %s seconds\n" "$duration"
echo ""
echo "🎉 Your APIM Samples environment is ready to use! Follow these steps:"
echo ""
echo "   1. Scroll up and review the verification results. We will log in below."
echo "   2. Wait until Codespace is ready. '(.venv)' prefix will appear when done."
echo "   3. Use 'Azure CLI Login' option in the Developer CLI: 'bash start.sh'."
echo ""
echo ""
echo "   If you experience any problems, please refer to the READMEs in the editor."
echo ""
echo "============================================================================="
echo -e "\n\n"
