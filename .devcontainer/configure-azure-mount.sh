#!/bin/bash
# Azure CLI Configuration Setup for APIM Samples Dev Container
# Shell script alternative for Linux/macOS users

set -e

echo "🚀 APIM Samples Dev Container Azure CLI Setup"
echo "=================================================="

echo "🔧 Azure CLI Configuration Setup"
echo "========================================"

# Detect platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macOS"
    MOUNT_SOURCE="\${localEnv:HOME}/.azure"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="Linux"
    MOUNT_SOURCE="\${localEnv:HOME}/.azure"
else
    PLATFORM="Unix-like"
    MOUNT_SOURCE="\${localEnv:HOME}/.azure"
fi

echo "Detected platform: $PLATFORM"

echo ""
echo "How would you like to handle Azure CLI authentication?"
echo "1. Mount local Azure CLI config (preserves login between container rebuilds)"
echo "2. Use manual tenant-specific login inside container (requires explicit tenant/subscription setup each time)"
echo "3. Let me configure this manually later"

while true; do
    read -p $'\nEnter your choice (1-3): ' choice
    case $choice in
        [1-3]) break;;
        *) echo "❌ Invalid choice. Please enter 1, 2, or 3.";;
    esac
done

# Path to devcontainer.json
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEVCONTAINER_PATH="$SCRIPT_DIR/devcontainer.json"
BACKUP_PATH="$DEVCONTAINER_PATH.backup"

if [[ ! -f "$DEVCONTAINER_PATH" ]]; then
    echo "❌ devcontainer.json not found at: $DEVCONTAINER_PATH"
    exit 1
fi

# Create backup
if cp "$DEVCONTAINER_PATH" "$BACKUP_PATH"; then
    echo "✅ Backup created: $BACKUP_PATH"
else
    echo "❌ Failed to create backup"
    exit 1
fi

# Use Python to handle JSON manipulation (more reliable than jq which might not be installed)
python3 << EOF
import json
import sys

try:
    with open('$DEVCONTAINER_PATH', 'r') as f:
        content = f.read()
    
    # Simple comment removal for JSON parsing
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        if '//' in line and not ('"' in line and line.find('//') > line.find('"')):
            line = line[:line.find('//')]
        cleaned_lines.append(line)
    
    cleaned_content = '\n'.join(cleaned_lines)
    config = json.loads(cleaned_content)
    
    # Remove existing mounts if present
    if 'mounts' in config:
        del config['mounts']
    
    choice = '$choice'
    if choice == '1':
        # Add mount configuration
        mount_config = {
            "source": "$MOUNT_SOURCE",
            "target": "/home/vscode/.azure",
            "type": "bind"
        }
        config['mounts'] = [mount_config]
        print("✅ Configured Azure CLI mounting for $PLATFORM")
    elif choice == '2':
        print("✅ Configured for manual Azure CLI login with tenant/subscription specification")
        print("   You'll need to run tenant-specific login after container startup:")
        print("   az login --tenant <your-tenant-id-or-domain>")
        print("   az account set --subscription <your-subscription-id-or-name>")
        print("   az account show  # Verify your context")
    else:
        print("✅ No automatic configuration applied")
        print("   You can manually edit .devcontainer/devcontainer.json later")
    
    # Save updated configuration
    with open('$DEVCONTAINER_PATH', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✅ devcontainer.json updated successfully")

except Exception as e:
    print(f"❌ Failed to update devcontainer.json: {e}")
    sys.exit(1)
EOF

echo ""
echo "🎉 Configuration completed successfully!"

case $choice in
    1)
        echo ""
        echo "📋 Next steps:"
        echo "1. Rebuild your dev container"
        echo "2. Your local Azure CLI authentication will be available"
        ;;
    2)
        echo ""
        echo "📋 Next steps:"
        echo "1. Start/rebuild your dev container"
        echo "2. Sign in with tenant-specific authentication:"
        echo "   az login --tenant <your-tenant-id-or-domain>"
        echo "   az account set --subscription <your-subscription-id-or-name>"
        echo "   az account show  # Verify your context"
        ;;
    3)
        echo ""
        echo "📋 Next steps:"
        echo "1. Edit .devcontainer/devcontainer.json manually if needed"
        echo "2. See the documentation for examples"
        ;;
esac
