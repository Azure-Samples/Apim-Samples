#!/bin/bash

# ------------------------------
#    APIM SAMPLES INSTANT VERIFICATION
# ------------------------------

# Exit silently if not in devcontainer
if [ ! -d "/workspaces/Apim-Samples" ]; then
    exit 0
fi

start=$(date +%s.%N)

# Ensure workspace scripts are executable (handles mounts without exec bit)
chmod +x .devcontainer/post-start-setup.sh start.sh start.ps1 setup/*.sh setup/*.ps1 2>/dev/null || true

# Make terminal output more prominent
clear
echo "============================================================================"
echo "                    🚀 APIM SAMPLES - INSTANT VERIFICATION                "
echo "============================================================================"
echo ""
echo "⚡ Running unified verification (setup/verify_local_setup.py)..."
echo ""

WORKSPACE_ROOT="/workspaces/Apim-Samples"
PY_CMD="$WORKSPACE_ROOT/.venv/bin/python"
[ -x "$PY_CMD" ] || PY_CMD=python

cd "$WORKSPACE_ROOT" || exit 1

"$PY_CMD" setup/verify_local_setup.py || true

# Open CODESPACES-QUICKSTART.md in preview mode with focus
if [ -f "$WORKSPACE_ROOT/.devcontainer/CODESPACES-QUICKSTART.md" ]; then
    code --reuse-window "$WORKSPACE_ROOT/.devcontainer/CODESPACES-QUICKSTART.md" --preview --goto
fi

# Calculate total duration
end=$(date +%s.%N)
duration=$(python3 -c "print(f'{float('$end') - float('$start'):.1f}')" 2>/dev/null || echo "0.1")

echo ""
echo "============================================================================"
echo "                          ⚡ INSTANT VERIFICATION COMPLETE!               "
echo "============================================================================"
echo ""
printf "⏱️  Verification time: %s seconds\n" "$duration"
echo ""
echo "🎉 Your APIM Samples environment is ready to use!"
echo -e "\n"
echo " Next Steps:"
echo ""
echo "   1. Scroll up and review the verification results."
echo "        --> Don't worry, it is expected that the Azure Login section failed."
echo ""
echo "   2. Wait until Codespace is ready (it may already be done!):"
echo "        - Watch progress indicators in status bar"
echo "        - Wait for all extensions to install"
echo "        --> ✅ (.venv) prefix will appear when you open a new terminal"
echo ""
echo "   3. Reuse this or open a new terminal, then log in via the Azure CLI"
echo "      command above."
echo "      See TROUBLESHOOTING.md in the root for details."
echo ""
echo "   4. Start with the '🚀 Getting Started' section in the root README.md"
echo "      The file is already open in the editor!"
echo ""
echo ""
echo " Optional:"
echo ""
echo "   Launch the APIM Samples Developer CLI via 'bash start.sh'"
echo ""
echo "============================================================================"
echo -e "\n\n"
