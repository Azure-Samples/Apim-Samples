#!/bin/bash

# ------------------------------
#    APIM SAMPLES POST-START SETUP
# ------------------------------

start=$(date +%s.%N)

echo ""
echo -e "🚀 APIM Samples environment starting...\n"

# ------------------------------
#    CONFIGURATION
# ------------------------------

echo -e "1/5) Setting environment variables...\n"

WORKSPACE_ROOT="/workspaces/Apim-Samples"
VENV_PATH="$WORKSPACE_ROOT/.venv"
PYTHON_EXECUTABLE="$VENV_PATH/bin/python"

echo "   Workspace              : $WORKSPACE_ROOT"
echo "   Virtual Environment    : $VENV_PATH"
echo "   Python Executable      : $PYTHON_EXECUTABLE"
echo ""

# ------------------------------
#    ENVIRONMENT VERIFICATION
# ------------------------------

echo -e "2/5) Verifying virtual environment...\n"

# Verify virtual environment exists
if [ -d "$VENV_PATH" ]; then
    echo "   ✅ Virtual environment found at $VENV_PATH"
    if [ -f "$PYTHON_EXECUTABLE" ]; then
        echo "   ✅ Python executable available"
        # Activate and verify
        source "$VENV_PATH/bin/activate"
        echo "   ✅ Python version: $(python --version)"
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
#    GENERATE .ENV FILE
# ------------------------------

echo -e "\n3/5) Verifying .env file...\n"

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

echo -e "\n4/5) Configuring Azure CLI...\n"

az config set core.login_experience_v2=off 2>/dev/null || true

# Install extensions used by infrastructure samples
# - containerapp: Required for infrastructure/apim-aca and infrastructure/afd-apim
# - front-door: Required for infrastructure/afd-apim and shared/python/utils.py
echo "   Installing containerapp extension..."
az extension add --name containerapp --only-show-errors 2>/dev/null || true
echo "   Installing front-door extension..."
az extension add --name front-door --only-show-errors 2>/dev/null || true
echo "   \n✅ Azure CLI configured"

# ------------------------------
#    FINAL VERIFICATION
# ------------------------------

echo -e "\n5/5) Environment Summary\n"
echo "      Virtual Environment : $VIRTUAL_ENV"
echo "      Python              : $(python --version) at $(which python)"
# Commenting out the number of packages installed as this does take some time to run. When the setup was verified, a count of 125 packages was printed.
# echo "      Packages: $(pip list | wc -l) installed"
echo "      .env File           : $([ -f .env ] && echo "✅" || echo "❌")"
echo "      Azure CLI           :"
echo "$(az --version | head -1)"

# Verify Jupyter kernel registration
echo "      Jupyter Kernels: $(jupyter kernelspec list --json | python -c "import sys, json; data=json.load(sys.stdin); print(len(data['kernelspecs'])) if 'kernelspecs' in data else print('0')" 2>/dev/null || echo "unknown")"
if jupyter kernelspec list | grep -q "apim-samples" 2>/dev/null; then
    echo "      APIM Samples Kernel: ✅"
else
    echo "      APIM Samples Kernel: ❌ (registering...)"
    python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python 3.12" 2>/dev/null && echo "      ✅ Kernel registered successfully" || echo "      ⚠️  Failed to register kernel"
fi

# Test core imports
python -c "
try:
    import requests, jwt, pandas, matplotlib, azure.identity
    print('   ✅ Core packages working')
except ImportError as e:
    print(f'   ❌ Package issue: {e}')
"

# Calculate total duration using Python
end=$(date +%s.%N)
duration=$(python3 -c "print(f'{float('$end') - float('$start'):.2f}')")
printf "   ⏱️  Total duration in %s seconds\n\n" "$duration"

echo "🎉 Environment ready!"
printf "⏱️  Total setup time: %s seconds\n" "$total_duration"
echo ""
echo "💡 The virtual environment is at: $VENV_PATH"
echo "💡 It should be auto-selected in VS Code"
echo "💡 All packages are pre-installed and ready to use"
echo ""
