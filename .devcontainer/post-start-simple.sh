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
VENV_PATH="$WORKSPACE_ROOT/.venv"
PYTHON_EXECUTABLE="$VENV_PATH/bin/python"

echo -e "📋 Configuration:\n"
echo "   Workspace: $WORKSPACE_ROOT"
echo "   Virtual Environment: $VENV_PATH"
echo "   Python Executable: $PYTHON_EXECUTABLE"
echo ""

# ------------------------------
#    ENVIRONMENT VERIFICATION
# ------------------------------

echo -e "1/5) Verifying virtual environment...\n"

if [ -d "$VENV_PATH" ]; then
    echo "   ✅ Virtual environment found at $VENV_PATH"
    if [ -f "$PYTHON_EXECUTABLE" ]; then
        echo "   ✅ Python executable available"
        # Activate and verify
        source "$VENV_PATH/bin/activate"
        echo "   ✅ Python version: $(python --version)"
        echo "   ✅ Packages installed: $(pip list | wc -l)"
    else
        echo "   ❌ Python executable not found"
        exit 1
    fi
else
    echo "   ❌ Virtual environment not found"
    exit 1
fi

# ------------------------------
#    GENERATE .ENV FILE
# ------------------------------

echo -e "\n2/5) Generating .env file...\n"

cd "$WORKSPACE_ROOT"
if [ -f "setup/setup_python_path.py" ]; then
    python setup/setup_python_path.py --generate-env
    echo "   ✅ .env file updated"
else
    echo "   ⚠️  setup_python_path.py not found, creating basic .env"
    cat > .env << EOF
# Auto-generated for APIM Samples dev container
PROJECT_ROOT=$WORKSPACE_ROOT
PYTHONPATH=$WORKSPACE_ROOT/shared/python:$WORKSPACE_ROOT
EOF
fi

# ------------------------------
#    AZURE CLI SETUP
# ------------------------------

echo -e "\n3/5) Configuring Azure CLI...\n"

az config set core.login_experience_v2=off 2>/dev/null || true
az extension add --name containerapp --only-show-errors 2>/dev/null || true
az extension add --name front-door --only-show-errors 2>/dev/null || true
echo "   ✅ Azure CLI configured"

# ------------------------------
#    WORKSPACE SETTINGS
# ------------------------------

echo -e "\n4/5) Ensuring workspace settings...\n"

mkdir -p .vscode
if [ ! -f ".vscode/settings.json" ]; then
    cat > .vscode/settings.json << 'EOF'
{
  "python.analysis.extraPaths": [
    "/workspaces/Apim-Samples/shared/python"
  ]
}
EOF
    echo "   ✅ Created .vscode/settings.json"
else
    echo "   ✅ .vscode/settings.json exists"
fi

# ------------------------------
#    FINAL VERIFICATION
# ------------------------------

echo -e "\n5/5) Final verification...\n"

echo "   📊 Environment Summary:"
echo "      Python: $(python --version) at $(which python)"
echo "      Virtual Environment: $VIRTUAL_ENV"
echo "      Packages: $(pip list | wc -l) installed"
echo "      .env File: $([ -f .env ] && echo "✅" || echo "❌")"
echo "      Azure CLI: $(az --version | head -1)"

# Test core imports
python -c "
try:
    import requests, jwt, pandas, matplotlib, azure.identity
    print('   ✅ Core packages working')
except ImportError as e:
    print(f'   ❌ Package issue: {e}')
"

echo ""
echo "🎉 Environment ready!"
echo ""
echo "💡 The virtual environment is at: $VENV_PATH"
echo "💡 It should be auto-selected in VS Code"
echo "💡 All packages are pre-installed and ready to use"
echo ""
