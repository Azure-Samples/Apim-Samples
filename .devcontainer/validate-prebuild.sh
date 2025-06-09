#!/bin/bash

# ------------------------------
#    PREBUILD VALIDATION SCRIPT
# ------------------------------

echo "🔍 Validating prebuild configuration..."

# Check if prebuild marker exists
if [ -f ".devcontainer/.prebuild-complete" ]; then
    echo "✅ Prebuild marker found"
    echo "   Created: $(cat .devcontainer/.prebuild-complete)"
else
    echo "❌ No prebuild marker found"
    echo "   This indicates the environment was not created from a prebuild"
fi

echo ""
echo "📊 Environment Status:"
echo "====================="

# Check Python installation
if command -v python &> /dev/null; then
    echo "✅ Python: $(python --version)"
else
    echo "❌ Python: Not found"
fi

# Check Azure CLI
if command -v az &> /dev/null; then
    echo "✅ Azure CLI: $(az --version | head -1)"
else
    echo "❌ Azure CLI: Not found"
fi

# Check key Python packages
echo ""
echo "📦 Python Packages:"
echo "=================="
packages=("requests" "jwt" "pandas" "matplotlib" "pytest" "azure-cli" "jupyter" "ipykernel")

for pkg in "${packages[@]}"; do
    if python -c "import ${pkg//-/_}" &> /dev/null; then
        version=$(pip show "$pkg" 2>/dev/null | grep Version | cut -d' ' -f2)
        echo "✅ $pkg: $version"
    else
        echo "❌ $pkg: Not installed"
    fi
done

echo ""
echo "🔧 Configuration Files:"
echo "======================"

# Check for key configuration files
files=(".env" ".vscode/settings.json" "requirements.txt")

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file: Found"
    else
        echo "❌ $file: Missing"
    fi
done

echo ""
echo "🎯 Recommendations:"
echo "=================="

if [ ! -f ".devcontainer/.prebuild-complete" ]; then
    echo "💡 Consider using GitHub Codespaces prebuilds for faster startup"
    echo "   Learn more: https://docs.github.com/en/codespaces/prebuilding-your-codespaces"
fi

echo "💡 Run 'python .devcontainer/verify-setup.py' for detailed environment verification"
echo "💡 Run 'python3 .devcontainer/configure-azure-mount.py' to configure Azure CLI authentication"
