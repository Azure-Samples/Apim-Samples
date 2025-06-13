#!/bin/bash

# ------------------------------
#    APIM SAMPLES INSTANT VERIFICATION
# ------------------------------

start=$(date +%s.%N)

# Make terminal output more prominent
clear
echo "============================================================================"
echo "                    🚀 APIM SAMPLES - INSTANT VERIFICATION                "
echo "============================================================================"
echo ""
echo "⚡ All heavy setup was completed during prebuild - verifying environment..."
echo ""

# ------------------------------
#    LIGHTNING FAST VERIFICATION
# ------------------------------

WORKSPACE_ROOT="/workspaces/Apim-Samples"
VENV_PATH="$WORKSPACE_ROOT/.venv"

echo -e "Environment Status:\n"

# Ultra-fast file system checks (no command execution)
if [ -d "$VENV_PATH" ]; then
    echo "   ✅ Virtual environment"
else
    echo "   ❌ Virtual environment missing"
fi

if [ -f "$WORKSPACE_ROOT/.env" ]; then
    echo "   ✅ Environment file"
else
    echo "   ❌ Environment file missing"
fi

# Quick command availability checks (fast)
if command -v az >/dev/null 2>&1; then
    echo "   ✅ Azure CLI"
else
    echo "   ❌ Azure CLI missing"
fi

if command -v python >/dev/null 2>&1; then
    echo "   ✅ Python"
else
    echo "   ❌ Python missing"
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
echo "   1. Open a new terminal and log in via the Azure CLI: az login"
echo "   2. Briefly wait until Codespace is fully started."
echo "   3. Start using the infrastructures and samples!"
echo ""
echo "============================================================================"
echo -e "\n\n"
