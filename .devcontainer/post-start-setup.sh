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

# Note: CODESPACES-QUICKSTART.md opens automatically via workbench.editorAssociations
# in the devcontainer.json, configured to show in preview mode on first view

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
echo "   1. Open a new terminal and log in via the Azure CLI with either command."
echo "      See TROUBLESHOOTING.md in the root for details."
echo ""
echo "        - az login"
echo "        - az login --tenant <your-tenant-id>"
echo ""
echo "   2. Wait until Codespace is fully started (it's fairly quick):"
echo "        - Watch progress indicators in status bar"
echo "        - Wait for all extensions to install"
echo "        --> ✅ (.venv) prefix will appear when you open a new terminal"
echo ""
echo "   3. Start using the infrastructures and samples!"
echo "        - You may initially need to select the kernel (top-right above the"
echo "          Jupyter notebook). If so, select the '.venv' Python environment."
echo "        - To launch the APIM Samples Developer CLI, run: bash start.sh"
echo ""
echo "============================================================================"
echo -e "\n\n"
