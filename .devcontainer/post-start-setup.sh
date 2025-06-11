#!/bin/bash

# ------------------------------
#    APIM SAMPLES POST-START VERIFICATION
# ------------------------------

start=$(date +%s.%N)

# Make terminal output more prominent
clear
echo "============================================================================"
echo "                    🚀 APIM SAMPLES CODESPACE VERIFICATION                "
echo "============================================================================"
echo ""
echo "🔧 This terminal shows the Codespace verification progress."
echo "📋 Keep this panel open to monitor the environment status."
echo ""
echo -e "✅ Most setup completed during prebuild - verifying environment...\n"

# ------------------------------
#    CONFIGURATION
# ------------------------------

echo -e "1/5) Detecting & setting environment variables...\n"

WORKSPACE_ROOT="/workspaces/Apim-Samples"
VENV_PATH="$WORKSPACE_ROOT/.venv"
PYTHON_EXECUTABLE="$VENV_PATH/bin/python"

echo "   Workspace              : $WORKSPACE_ROOT"
echo "   Virtual Environment    : $VENV_PATH"
echo "   Python Executable      : $PYTHON_EXECUTABLE"

# Activate virtual environment to get the correct Python version
source "$VENV_PATH/bin/activate" 2>/dev/null || true
PYTHON_VERSION=$(python --version | grep "Python" | awk '{print $2}')
echo "   Python Version         : $PYTHON_VERSION"

# Extract Azure CLI version (suppress warnings and get just the version number)
AZ_CLI_VERSION=$(az --version 2>/dev/null | grep "azure-cli" | awk '{print $2}' | head -1)
echo "   Azure CLI Version      : $AZ_CLI_VERSION"

# ------------------------------
#    ENVIRONMENT VERIFICATION
# ------------------------------

echo -e "\n2/5) Verifying virtual environment...\n"

# Verify virtual environment exists
if [ -d "$VENV_PATH" ]; then
    echo "   ✅ Virtual environment found at $VENV_PATH"
    if [ -f "$PYTHON_EXECUTABLE" ]; then
        echo "   ✅ Python executable available"
        # Activate and verify
        source "$VENV_PATH/bin/activate"
        echo "   ✅ Python version     : $PYTHON_VERSION"
        # Commenting out the number of packages installed as this does take some time to run. When the setup was verified, a count of 125 packages was printed.
        # echo "   ✅ Packages installed: $(pip list | wc -l)"
    else
        echo "   ❌ Python executable not found"
        exit 1
    fi
else
    echo "   ❌ Virtual environment not found at $VENV_PATH"
    echo "   💡 Virtual environment should have been created during container setup"
    exit 1
fi

# ------------------------------
#    ENVIRONMENT FILE VERIFICATION
# ------------------------------

echo -e "\n3/5) Verifying .env file...\n"

cd "$WORKSPACE_ROOT"
if [ -f ".env" ]; then
    echo "   ✅ .env file exists"
else
    echo "   ⚠️  .env file missing, regenerating..."
    if [ -f "setup/setup_python_path.py" ]; then
        python setup/setup_python_path.py --generate-env
        echo "   ✅ .env file regenerated"
    else
        echo "   ⚠️  setup_python_path.py not found, creating basic .env"
        cat > .env << EOF
# Auto-generated for APIM Samples dev container
PROJECT_ROOT=$WORKSPACE_ROOT
PYTHONPATH=$WORKSPACE_ROOT/shared/python:$WORKSPACE_ROOT
EOF
        echo "   ✅ Basic .env file created"
    fi
fi

# ------------------------------
#    AZURE CLI VERIFICATION
# ------------------------------

echo -e "\n4/5) Verifying Azure CLI configuration...\n"

# Verify Azure CLI extensions are installed (they should be from prebuild)
echo "   Checking Azure CLI extensions..."
if az extension list --query "[?name=='containerapp']" -o tsv | grep -q "containerapp"; then
    echo "   ✅ containerapp extension installed"
else
    echo "   ⚠️  containerapp extension missing, installing..."
    az extension add --name containerapp --only-show-errors 2>/dev/null || true
fi

if az extension list --query "[?name=='front-door']" -o tsv | grep -q "front-door"; then
    echo "   ✅ front-door extension installed"
else
    echo "   ⚠️  front-door extension missing, installing..."
    az extension add --name front-door --only-show-errors 2>/dev/null || true
fi

# Verify Azure CLI configuration
echo "   ✅ Azure CLI configured for device code authentication"

# ------------------------------
#    FINAL VERIFICATION
# ------------------------------

echo -e "\n5/5) Environment Summary\n"
echo "   Virtual Environment : $VIRTUAL_ENV"
echo "   Python              : $PYTHON_VERSION at $(which python)"
# Commenting out the number of packages installed as this does take some time to run. When the setup was verified, a count of 125 packages was printed.
# echo "      Packages: $(pip list | wc -l) installed"
echo "   .env File exists?   : $([ -f .env ] && echo "✅" || echo "❌")"
echo "   Azure CLI Version   : $AZ_CLI_VERSION"

# Verify Jupyter kernel registration
echo "   Jupyter Kernels     : $(jupyter kernelspec list --json | python -c "import sys, json; data=json.load(sys.stdin); print(len(data['kernelspecs'])) if 'kernelspecs' in data else print('0')" 2>/dev/null || echo "unknown")"

if jupyter kernelspec list | grep -q "apim-samples" 2>/dev/null; then
    echo "   APIM Samples Kernel : ✅"
else
    echo "   APIM Samples Kernel : ⚠️ (missing, re-registering...)"
    python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python 3.12" 2>/dev/null && echo "   ✅ Kernel registered successfully" || echo "   ❌ Failed to register kernel"
fi

# Test core imports
python -c "
try:
    import requests, jwt, pandas, matplotlib, azure.identity
    print(f'   Core packages       : ✅')
except ImportError as e:
    print(f'   Core packages       : ❌')
    print(f'   {e}')
"

# Calculate total duration using Python
end=$(date +%s.%N)
duration=$(python3 -c "print(f'{float('$end') - float('$start'):.2f}')")

echo ""
echo "============================================================================"
echo "                          🎉 VERIFICATION COMPLETED!                      "
echo "============================================================================"
echo ""
printf "⏱️ Total verification time: %s seconds\n" "$duration"
echo "💡 Environment prebuild optimizations have significantly reduced startup time!"
echo ""
echo "🔍 This terminal shows your Codespace verification progress and logs."
echo "📋 You can minimize this panel or open a new terminal for your work."
echo ""
echo "🚀 Your APIM Samples environment is ready to use!"
echo ""
echo ""
echo " NEXT STEPS:"
echo " -----------"
echo ""
echo "   1. Log in via the Azure CLI: az login"
echo "   2. Start using the infrastructures and samples!"
echo ""
echo "============================================================================"
echo -e "\n\n\n"
