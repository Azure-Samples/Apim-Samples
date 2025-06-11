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
step1_start=$(date +%s.%N)

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

step1_end=$(date +%s.%N)
step1_duration=$(echo "$step1_end - $step1_start" | bc -l)
printf "   ⏱️  Step 1 completed in %.2f seconds\n\n" "$step1_duration"

# ------------------------------
#    GENERATE .ENV FILE
# ------------------------------

echo -e "2/4) Verifying .env file...\n"
step2_start=$(date +%s.%N)

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

step2_end=$(date +%s.%N)
step2_duration=$(echo "$step2_end - $step2_start" | bc -l)
printf "   ⏱️  Step 2 completed in %.2f seconds\n\n" "$step2_duration"

# ------------------------------
#    AZURE CLI SETUP
# ------------------------------

echo -e "3/4) Configuring Azure CLI...\n"
step3_start=$(date +%s.%N)

az config set core.login_experience_v2=off 2>/dev/null || true

# Install extensions used by infrastructure samples
# - containerapp: Required for infrastructure/apim-aca and infrastructure/afd-apim
# - front-door: Required for infrastructure/afd-apim and shared/python/utils.py
az extension add --name containerapp --only-show-errors 2>/dev/null || true
az extension add --name front-door --only-show-errors 2>/dev/null || true
echo "   ✅ Azure CLI configured"

step3_end=$(date +%s.%N)
step3_duration=$(echo "$step3_end - $step3_start" | bc -l)
printf "   ⏱️  Step 3 completed in %.2f seconds\n\n" "$step3_duration"

# ------------------------------
#    FINAL VERIFICATION
# ------------------------------

echo -e "4/4) Final verification...\n"
step4_start=$(date +%s.%N)

echo "   📊 Environment Summary:"
echo "      Python: $(python --version) at $(which python)"
echo "      Virtual Environment: $VIRTUAL_ENV"
echo "      Packages: $(pip list | wc -l) installed"
echo "      .env File: $([ -f .env ] && echo "✅" || echo "❌")"
echo "      Azure CLI: $(az --version | head -1)"

# Verify Jupyter kernel registration
echo "      Jupyter Kernels: $(jupyter kernelspec list --json | python -c "import sys, json; data=json.load(sys.stdin); print(len(data['kernelspecs'])) if 'kernelspecs' in data else print('0')" 2>/dev/null || echo "unknown")"
if jupyter kernelspec list | grep -q "apim-samples" 2>/dev/null; then
    echo "      APIM Samples Kernel: ✅"
else
    echo "      APIM Samples Kernel: ❌ (registering...)"
    python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python 3.12" 2>/dev/null || echo "      ⚠️  Failed to register kernel"
fi

# Test core imports
python -c "
try:
    import requests, jwt, pandas, matplotlib, azure.identity
    print('   ✅ Core packages working')
except ImportError as e:
    print(f'   ❌ Package issue: {e}')
"

step4_end=$(date +%s.%N)
step4_duration=$(echo "$step4_end - $step4_start" | bc -l)
printf "   ⏱️  Step 4 completed in %.2f seconds\n\n" "$step4_duration"

# Calculate total duration
total_duration=$(echo "$step1_duration + $step2_duration + $step3_duration + $step4_duration" | bc -l)

echo "🎉 Environment ready!"
printf "⏱️  Total setup time: %.2f seconds\n" "$total_duration"
echo ""
echo "💡 The virtual environment is at: $VENV_PATH"
echo "💡 It should be auto-selected in VS Code"
echo "💡 All packages are pre-installed and ready to use"
echo ""
