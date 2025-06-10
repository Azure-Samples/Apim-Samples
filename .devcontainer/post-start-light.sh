#!/bin/bash

# ------------------------------
#    QUICK POST-START SETUP
# ------------------------------

echo ""
echo -e "🚀 APIM Samples environment starting...\n"

# ------------------------------
#    MINIMAL SETUP TASKS
# ------------------------------

echo -e "Running minimal post-start configuration...\n"

# Configure Azure CLI (quick)
echo -e "1) Configuring Azure CLI...\n"
az config set core.login_experience_v2=off 2>/dev/null || true

# Install Azure CLI extensions if not already present
echo -e "2) Checking Azure CLI extensions...\n"
az extension add --name containerapp --only-show-errors 2>/dev/null || true
az extension add --name front-door --only-show-errors 2>/dev/null || true

# Create workspace settings if they don't exist
echo "3) Ensuring workspace configuration..."
mkdir -p .vscode

if [ ! -f ".vscode/settings.json" ]; then
    cat > .vscode/settings.json << 'EOF'
{
  "python.terminal.activateEnvironment": true,
  "python.defaultInterpreterPath": "~/.venv/bin/python",
  "python.analysis.extraPaths": [
    "/workspaces/Apim-Samples/shared/python"
  ],
  "jupyter.kernels.filter": [
    {
      "path": "~/.venv/bin/python",
      "type": "pythonEnvironment"
    }
  ],
  "files.associations": {
    "*.bicep": "bicep"
  },
  "python.envFile": "${workspaceFolder}/.env"
}
EOF
fi

# ------------------------------
#    VERIFICATION
# ------------------------------

echo ""
echo -e "4) Verifying environment...\n"
echo "Python version: $(python --version)"
echo "Virtual environment: $VIRTUAL_ENV"
echo "Python location: $(which python)"
echo "Packages available: $(pip list | wc -l) packages"

echo ""
echo -e "5) Quick package verification...\n"
python -c "import requests, jwt, pandas, matplotlib; print('✅ Core packages ready')" || echo "⚠️ Some packages may need attention"

echo ""
echo -e "6) Azure CLI version: $(az --version | head -1)\n"

echo ""
echo "🎉 Environment ready for development!"
echo ""

# ------------------------------
#    GUIDANCE
# ------------------------------

echo "📋 Quick start:"
echo "  • Virtual environment is pre-activated"
echo "  • All packages are pre-installed"
echo "  • Ready to run notebooks and scripts immediately"
echo ""
echo "💡 To verify your Azure setup:"
echo "  1. Run      : az login"
echo "  2. Execute  : shared/jupyter/verify-az-account.ipynb"
echo ""
