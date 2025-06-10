#!/bin/bash

# ------------------------------
#    QUICK POST-START SETUP
# ------------------------------

echo ""
echo "🚀 APIM Samples environment starting..."
echo ""

# ------------------------------
#    MINIMAL SETUP TASKS
# ------------------------------

echo "🔧 Running minimal post-start configuration..."

# Set up Python path configuration (lightweight)
if [ -f "setup/setup_python_path.py" ]; then
    python setup/setup_python_path.py --generate-env || echo "⚠️ Python path setup skipped"
fi

# Configure Azure CLI (quick)
echo "☁️ Configuring Azure CLI..."
az config set core.login_experience_v2=off 2>/dev/null || true

# Install Azure CLI extensions if not already present
echo "📥 Checking Azure CLI extensions..."
az extension add --name containerapp --only-show-errors 2>/dev/null || true
az extension add --name front-door --only-show-errors 2>/dev/null || true

# Set up Jupyter kernel if needed
echo "📓 Ensuring Jupyter kernel is available..."
python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python" 2>/dev/null || echo "⚠️ Jupyter kernel already configured"

# Create workspace settings if they don't exist
echo "🛠️ Ensuring workspace configuration..."
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
echo "✅ Verifying environment..."
echo "Python version: $(python --version)"
echo "Virtual environment: $VIRTUAL_ENV"
echo "Python location: $(which python)"
echo "Packages available: $(pip list | wc -l) packages"

echo ""
echo "✅ Quick package verification..."
python -c "import requests, jwt, pandas, matplotlib; print('✅ Core packages ready')" || echo "⚠️ Some packages may need attention"

echo ""
echo "✅ Azure CLI version: $(az --version | head -1)"

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
echo "  1. Run: az login"
echo "  2. Execute: shared/jupyter/verify-az-account.ipynb"
echo ""
