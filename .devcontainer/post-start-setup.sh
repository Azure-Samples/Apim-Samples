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

echo -e "1/4) Verifying virtual environment...\n"

# Verify virtual environment exists
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
    echo "   ❌ Virtual environment not found at $VENV_PATH"
    echo "   💡 Virtual environment should have been created during container setup"
    exit 1
fi
    echo "   ❌ Virtual environment not found in workspace or home directory"
    echo "   🔍 Debug - checking available directories:"
# ------------------------------
#    GENERATE .ENV FILE
# ------------------------------

echo -e "\n2/4) Verifying .env file...\n"

cd "$WORKSPACE_ROOT"
if [ -f ".env" ]; then
    echo "   ✅ .env file exists"
else
    echo "   ⚠️  .env file missing, generating..."
    if [ -f "setup/setup_python_path.py" ]; then
        python setup/setup_python_path.py --generate-env
        echo "   ✅ .env file generated"
    else
        echo "   ⚠️  setup_python_path.py not found, creating basic .env"
        cat > .env << EOF
# Auto-generated for APIM Samples dev container
PROJECT_ROOT=$WORKSPACE_ROOT
PYTHONPATH=$WORKSPACE_ROOT/shared/python:$WORKSPACE_ROOT
EOF
    fi
fi

# ------------------------------
#    AZURE CLI SETUP
# ------------------------------

echo -e "\n3/4) Configuring Azure CLI...\n"

az config set core.login_experience_v2=off 2>/dev/null || true

# Install extensions used by infrastructure samples
# - containerapp: Required for infrastructure/apim-aca and infrastructure/afd-apim
# - front-door: Required for infrastructure/afd-apim and shared/python/utils.py
az extension add --name containerapp --only-show-errors 2>/dev/null || true
az extension add --name front-door --only-show-errors 2>/dev/null || true
echo "   ✅ Azure CLI configured"

# ------------------------------
#    FINAL VERIFICATION
# ------------------------------

echo -e "\n4/4) Final verification...\n"

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
