#!/bin/bash

# ------------------------------
#    APIM SAMPLES POST-START SETUP
# ------------------------------

echo ""
echo -e "🚀 APIM Samples environment starting...\n"

# ------------------------------
#    CONFIGURATION
# ------------------------------

WORKSPACE_ROOT="/workspaces/Apim-Samples"
VENV_PATH="/home/vscode/.venv"
PYTHON_EXECUTABLE="$VENV_PATH/bin/python"

echo -e "📋 Configuration:\n"
echo "   Workspace           : $WORKSPACE_ROOT"
echo "   Virtual Environment : $VENV_PATH"
echo "   Python Executable   : $PYTHON_EXECUTABLE"
echo ""

# ------------------------------
#    ENVIRONMENT SETUP
# ------------------------------

echo -e "1) Setting up Python environment...\n"

# Ensure virtual environment is activated
if [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found at $VENV_PATH"
    exit 1
fi

# Generate .env file using the setup script
echo -e "\n2) Generating .env file...\n"

cd "$WORKSPACE_ROOT"
python setup/setup_python_path.py --generate-env

# Verify .env file was created
if [ -f "$WORKSPACE_ROOT/.env" ]; then
    echo "✅ .env file created successfully"
    echo "   Contents:"
    cat "$WORKSPACE_ROOT/.env" | sed 's/^/   /'
else
    echo "❌ Failed to create .env file"
fi

# ------------------------------
#    AZURE CLI SETUP
# ------------------------------

echo -e "\n3) Configuring Azure CLI...\n"

az config set core.login_experience_v2=off 2>/dev/null || true

# Install Azure CLI extensions if not already present
echo -e "4) Installing Azure CLI extensions...\n"

az extension add --name containerapp --only-show-errors 2>/dev/null || true
az extension add --name front-door --only-show-errors 2>/dev/null || true

# ------------------------------
#    WORKSPACE CONFIGURATION
# ------------------------------

echo -e "5) Configuring workspace settings...\n"

mkdir -p .vscode

# Create workspace settings that complement devcontainer.json
if [ ! -f ".vscode/settings.json" ]; then
    cat > .vscode/settings.json << 'EOF'
{
  "python.analysis.extraPaths": [
    "/workspaces/Apim-Samples/shared/python"
  ],
  "jupyter.kernels.filter": [
    {
      "path": "/home/vscode/.venv/bin/python",
      "type": "pythonEnvironment"
    }
  ]
}
EOF
    echo "✅ Created .vscode/settings.json"
else
    echo "✅ .vscode/settings.json already exists"
fi

# ------------------------------
#    VERIFICATION
# ------------------------------

echo -e "\n6) Verifying environment...\n"

echo "Python version: $(python --version)"
echo "Virtual environment: $VIRTUAL_ENV"
echo "Python location: $(which python)"
echo "Packages available: $(pip list | wc -l) packages"

echo -e "\n7) Testing core packages...\n"

python -c "
import sys
print(f'✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')

try:
    import requests, jwt, pandas, matplotlib
    print('✅ Core packages (requests, jwt, pandas, matplotlib)')
except ImportError as e:
    print(f'❌ Core packages: {e}')

try:
    import azure.storage.blob, azure.identity
    print('✅ Azure packages (storage.blob, identity)')
except ImportError as e:
    print(f'❌ Azure packages: {e}')

try:
    import jupyter, notebook
    print('✅ Jupyter packages')
except ImportError as e:
    print(f'❌ Jupyter packages: {e}')
"

echo -e "\n8) Azure CLI version: $(az --version | head -1)\n"

# ------------------------------
#    COMPLETION
# ------------------------------

echo "🎉 Environment setup complete!"
echo ""
echo "📋 Quick start:"
echo "  • Single virtual environment at: $VENV_PATH"
echo "  • All packages are pre-installed and verified"
echo "  • .env file configured with proper PYTHONPATH"
echo "  • VS Code Python extension configured"
echo "  • Ready to run notebooks and scripts immediately"
echo ""
echo "💡 To verify your Azure setup:"
echo "  1. Run      : az login"
echo "  2. Execute  : shared/jupyter/verify-az-account.ipynb"
echo ""
