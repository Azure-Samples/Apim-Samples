#!/bin/bash

# ------------------------------
#    DEVCONTAINER SETUP SCRIPT
# ------------------------------

set -e

echo "🚀 Setting up APIM Samples development environment..."

# ------------------------------
#    PYTHON ENVIRONMENT SETUP
# ------------------------------

echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Ensure pytest and coverage tools are available
pip install pytest pytest-cov coverage

echo "🔧 Setting up Python path configuration..."
python setup/setup_python_path.py --generate-env

# ------------------------------
#    AZURE CLI SETUP
# ------------------------------

echo "☁️ Configuring Azure CLI..."
# Set Azure CLI to use device code flow by default in codespaces/containers
az config set core.login_experience_v2=off 2>/dev/null || true

# Install additional Azure CLI extensions that might be useful
echo "📥 Installing Azure CLI extensions..."
az extension add --name containerapp --only-show-errors 2>/dev/null || true
az extension add --name front-door --only-show-errors 2>/dev/null || true

# ------------------------------
#    INTERACTIVE AZURE CONFIGURATION
# ------------------------------

echo ""
echo "🔧 Azure CLI Authentication Setup"
echo "================================="
echo ""
echo "To make working with Azure easier, you can configure how Azure CLI authentication works."
echo "This only needs to be done once during initial setup."
echo ""

# Check if we're in an interactive terminal
if [ -t 0 ] && [ -t 1 ]; then
    echo "Running interactive Azure CLI configuration..."
    export APIM_SAMPLES_INITIAL_SETUP=true
    python3 .devcontainer/configure-azure-mount.py
    unset APIM_SAMPLES_INITIAL_SETUP
    
    echo ""
    echo "⚠️  IMPORTANT: If you chose to mount Azure CLI config, you'll need to:"
    echo "   1. Exit this container"
    echo "   2. Rebuild the dev container to apply the mount configuration"
    echo "   3. The container will restart with your Azure CLI authentication available"
    echo ""
else
    echo "⚠️  Non-interactive environment detected."
    echo "   You can run the Azure CLI configuration later with:"
    echo "   python3 .devcontainer/configure-azure-mount.py"
    echo ""
fi

# ------------------------------
#    JUPYTER SETUP
# ------------------------------

echo "📓 Setting up Jupyter environment..."
# Install Jupyter kernel (with error handling)
if python -c "import ipykernel" 2>/dev/null; then
    python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python" || echo "⚠️ Warning: Failed to install Jupyter kernel, but continuing..."
else
    echo "⚠️ Warning: ipykernel not found. Installing it now..."
    pip install ipykernel
    python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python" || echo "⚠️ Warning: Failed to install Jupyter kernel, but continuing..."
fi

# ------------------------------
#    WORKSPACE CONFIGURATION
# ------------------------------

echo "🛠️ Configuring workspace settings..."

# Create .vscode directory if it doesn't exist
mkdir -p .vscode

# Create settings.json for the workspace
cat > .vscode/settings.json << 'EOF'
{
  "python.terminal.activateEnvironment": true,
  "python.defaultInterpreterPath": "/usr/local/bin/python",
  "jupyter.kernels.filter": [
    {
      "path": "/usr/local/bin/python",
      "type": "pythonEnvironment"
    }
  ],
  "files.associations": {
    "*.bicep": "bicep"
  },
  "python.envFile": "${workspaceFolder}/.env"
}
EOF

# ------------------------------
#    FINAL VERIFICATION
# ------------------------------

echo "✅ Verifying installation..."

echo "Python version:"
python --version

echo "Azure CLI version:"
az --version | head -1

echo "Pip packages installed:"
pip list | grep -E "(requests|pandas|matplotlib|pytest|azure|jwt|jupyter|ipykernel)"

echo "Jupyter kernels available:"
jupyter kernelspec list 2>/dev/null || echo "⚠️ Jupyter kernels could not be listed"

echo "🎉 Development environment setup complete!"

echo "🔍 Running final verification..."
python .devcontainer/verify-setup.py

echo ""
echo "📋 Next steps:"
if [ -f ".devcontainer/devcontainer.json" ] && grep -q '"mounts"' .devcontainer/devcontainer.json; then
    echo "✅ Azure CLI config mounting detected - your authentication should be available"
    echo "1. Verify Azure access and ensure correct tenant/subscription: az account show"
    echo "2. If needed, switch tenant: az login --tenant <your-tenant-id-or-domain>"
    echo "3. If needed, set subscription: az account set --subscription <your-subscription-id-or-name>"
    echo "4. Execute shared/jupyter/verify-az-account.ipynb to verify your Azure setup"
else
    echo "1. Sign in to your specific Azure tenant: az login --tenant <your-tenant-id-or-domain>"
    echo "2. Set your target subscription: az account set --subscription <your-subscription-id-or-name>"
    echo "3. Verify your context: az account show"
    echo "4. Execute shared/jupyter/verify-az-account.ipynb to verify your Azure setup"
fi
echo "5. Navigate to any infrastructure folder and run the create.ipynb notebook"
echo "6. Explore the samples in the samples/ directory"
echo ""
echo "💡 Tip: The Python path has been configured to include shared/python modules automatically."
echo "🔧 To reconfigure Azure CLI authentication, run: python3 .devcontainer/configure-azure-mount.py"
