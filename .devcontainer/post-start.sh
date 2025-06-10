#!/bin/bash

# ------------------------------
#    POST-START VERIFICATION
# ------------------------------

echo ""
echo ""
echo ""
echo "🚀 APIM Samples environment starting..."

# Check if this is a prebuild-created environment
if [ -f ".devcontainer/.prebuild-complete" ]; then
    echo "✅ Detected prebuild environment - skipping heavy setup"
    PREBUILD_ENV=true
else
    echo "⚠️ No prebuild detected - running full setup"
    PREBUILD_ENV=false
fi

# ------------------------------
#    INTERACTIVE AZURE SETUP
# ------------------------------

if [ "$PREBUILD_ENV" = "false" ]; then
    echo "🔧 Running full setup (no prebuild detected)..."
    bash .devcontainer/setup.sh
else
    echo "🔧 Running Azure CLI interactive configuration..."
    
    # Only run the interactive Azure configuration part
    if [ -t 0 ] && [ -t 1 ]; then
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
fi

# ------------------------------
#    QUICK VERIFICATION
# ------------------------------

echo " ✅ Verifying Python environment..."
python --version

echo ""
echo " ✅ Verifying Azure CLI..."
az --version | head -1

echo ""
echo " ✅ Verifying Python packages..."
python -c "import requests, jwt; print('✅ Core packages available')" || echo "⚠️ Some packages may need reinstalling"

echo ""
echo " ✅ Running environment verification..."
python .devcontainer/verify-setup.py

echo ""
echo " 🎉 APIM Samples environment is ready!"
echo ""

# ------------------------------
#    NEXT STEPS GUIDANCE
# ------------------------------

echo "📋 Next steps:"
echo ""
if [ -f ".devcontainer/devcontainer.json" ] && grep -q '"mounts"' .devcontainer/devcontainer.json; then
    echo " ✅ Azure CLI config mounting detected - your authentication should be available"
    echo ""
    echo "1. Verify Azure access and ensure correct tenant/subscription: az account show"
    echo "2. If needed, switch tenant: az login --tenant <your-tenant-id-or-domain>"
    echo "3. If needed, set subscription: az account set --subscription <your-subscription-id-or-name>"
    echo "4. Execute shared/jupyter/verify-az-account.ipynb to verify your Azure setup"
else
    echo ""
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
echo ""
echo " 🎉 ALL DONE!"
echo ""