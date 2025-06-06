#!/usr/bin/env python3
"""
Interactive Azure CLI configuration setup for dev container.
This script helps users configure Azure CLI authentication mounting based on their platform.
"""
import json
import os
import platform
import sys
from pathlib import Path

# ------------------------------
#    CONSTANTS
# ------------------------------

DEVCONTAINER_JSON_PATH = Path(__file__).parent / "devcontainer.json"
BACKUP_SUFFIX = ".backup"

MOUNT_CONFIGS = {
    "windows": {
        "source": "${localEnv:USERPROFILE}/.azure",
        "target": "/home/vscode/.azure",
        "type": "bind"
    },
    "unix": {
        "source": "${localEnv:HOME}/.azure", 
        "target": "/home/vscode/.azure",
        "type": "bind"
    }
}

# ------------------------------
#    UTILITY FUNCTIONS
# ------------------------------

def detect_platform() -> str:
    """Detect the current platform."""
    system = platform.system().lower()
    
    if system == "windows":
        return "windows"
    elif system in ["linux", "darwin"]:
        return "unix"
    else:
        return "unknown"


def get_user_choice() -> str:
    """Get user's preference for Azure CLI configuration."""
    # Add visual separation and emphasis
    print("\n" + "=" * 60)
    print("Azure CLI Authentication Setup")
    print("=" * 60)
    
    detected_platform = detect_platform()
    if detected_platform != "unknown":
        platform_name = "Windows" if detected_platform == "windows" else "macOS/Linux"
        print(f"\nDetected platform: {platform_name}")
    
    print("\nHow would you like to handle Azure CLI authentication?")
    print("\n   1. Mount local Azure CLI config")
    print("      - Preserves login between container rebuilds")
    print("      - Uses your existing tenant-specific 'az login' from host machine")
    print("      - Best for: Personal development with stable logins")
    print("\n   2. Use manual login inside container [RECOMMENDED]") 
    print("      - Run tenant-specific 'az login' each time container starts")
    print("      - More secure, fresh authentication each session")
    print("      - Best for: Shared environments, GitHub Codespaces")
    print("\n   3. Let me configure this manually later")
    print("      - No changes made to devcontainer.json")
    print("      - You can edit the configuration files yourself")
    
    # Check if we're in a non-interactive environment (like GitHub Codespaces automation)
    if not sys.stdin.isatty() or os.environ.get('CODESPACES') == 'true':
        print("\nNon-interactive environment detected (GitHub Codespaces).")
        print("Automatically selecting option 2 (manual login) as the most reliable choice.")
        print("You can reconfigure later by running this script manually.")
        return "2"
    
    print("\nWaiting for your input...")
    
    while True:
        try:
            choice = input("\nEnter your choice (1-3) [default: 2]: ").strip()
            
            # Default to option 2 if no input provided
            if not choice:
                choice = "2"
            
            if choice in ["1", "2", "3"]:
                return choice
            
            print("Invalid choice. Please enter 1, 2, or 3.")
        except (EOFError, KeyboardInterrupt):
            # Handle non-interactive scenarios gracefully
            print("\nInput not available. Defaulting to option 2 (manual login).")
            return "2"


def backup_devcontainer_json() -> bool:
    """Create a backup of the current devcontainer.json file."""
    try:
        backup_path = DEVCONTAINER_JSON_PATH.with_suffix(DEVCONTAINER_JSON_PATH.suffix + BACKUP_SUFFIX)
        
        if DEVCONTAINER_JSON_PATH.exists():
            with open(DEVCONTAINER_JSON_PATH, 'r', encoding='utf-8') as src:
                content = src.read()
            
            with open(backup_path, 'w', encoding='utf-8') as dst:
                dst.write(content)
            
            print(f"✅ Backup created: {backup_path}")
            return True
        else:
            print("❌ devcontainer.json not found")
            return False
            
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return False


def load_devcontainer_json() -> dict:
    """Load and parse the devcontainer.json file."""
    try:
        with open(DEVCONTAINER_JSON_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove comments for JSON parsing (simple approach)
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove line comments but preserve strings
            if '//' in line:
                # Simple check - this could be improved for complex cases
                if not ('"' in line and line.find('//') > line.find('"')):
                    line = line[:line.find('//')]
            cleaned_lines.append(line)
        
        cleaned_content = '\n'.join(cleaned_lines)
        return json.loads(cleaned_content)
        
    except Exception as e:
        print(f"❌ Failed to load devcontainer.json: {e}")
        return {}


def save_devcontainer_json(config: dict) -> bool:
    """Save the updated devcontainer.json file."""
    try:
        with open(DEVCONTAINER_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        print("✅ devcontainer.json updated successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to save devcontainer.json: {e}")
        return False


def configure_azure_mount(choice: str) -> bool:
    """Configure Azure CLI mounting based on user choice."""
    if not backup_devcontainer_json():
        return False
    
    config = load_devcontainer_json()
    if not config:
        return False
    
    # Initialize mounts array if it doesn't exist
    if "mounts" not in config:
        config["mounts"] = []
    
    # Remove existing Azure CLI mounts (preserve other mounts)
    existing_mounts = config["mounts"]
    non_azure_mounts = []
    
    for mount in existing_mounts:
        if isinstance(mount, dict):
            # Check if this is an Azure CLI mount by looking at the target path
            target = mount.get("target", "")
            if not target.endswith("/.azure"):
                non_azure_mounts.append(mount)
        else:
            # Keep non-dict mounts as-is
            non_azure_mounts.append(mount)
    
    config["mounts"] = non_azure_mounts
    
    if choice == "1":  # Mount local Azure CLI config
        detected_platform = detect_platform()
        
        if detected_platform == "unknown":
            print("\n🤔 Platform detection failed. Please choose:")
            print("1. Windows")
            print("2. macOS/Linux")
            
            while True:
                platform_choice = input("Enter platform choice (1-2): ").strip()
                if platform_choice == "1":
                    detected_platform = "windows"
                    break
                elif platform_choice == "2":
                    detected_platform = "unix"
                    break
                else:
                    print("❌ Invalid choice. Please enter 1 or 2.")
          # Add mount configuration
        mount_config = MOUNT_CONFIGS[detected_platform]
        config["mounts"].append(mount_config)
        
        platform_name = "Windows" if detected_platform == "windows" else "macOS/Linux"
        print("✅ Configured Azure CLI mounting for {platform_name}")
        
    elif choice == "2":  # Manual login
        print("✅ Configured for manual Azure CLI login with tenant/subscription specification")
        print("   You'll need to run tenant-specific login after container startup:")
        print("   az login --tenant <your-tenant-id-or-domain>")
        print("   az account set --subscription <your-subscription-id-or-name>")
        print("   az account show  # Verify your context")
        print("   (Removed any existing Azure CLI mounts)")
        
    elif choice == "3":  # Manual configuration
        print("✅ No automatic configuration applied")
        print("   You can manually edit .devcontainer/devcontainer.json later")
    
    return save_devcontainer_json(config)


# ------------------------------
#    MAIN EXECUTION
# ------------------------------

def main() -> int:
    """Main execution function."""
    # Check if this is being called during initial setup
    is_initial_setup = os.environ.get('APIM_SAMPLES_INITIAL_SETUP', '').lower() == 'true'
    
    # Visual presentation
    print("\n" + "=" * 60)
    if is_initial_setup:
        print("APIM Samples Dev Container - Initial Azure CLI Setup")
        print("This is part of the automated dev container setup process.")
    else:
        print("APIM Samples Dev Container Azure CLI Setup")
    print("=" * 60)
    
    if not DEVCONTAINER_JSON_PATH.exists():
        print(f"\ndevcontainer.json not found at: {DEVCONTAINER_JSON_PATH}")
        return 1
    
    choice = get_user_choice()
    
    if configure_azure_mount(choice):
        print("\n" + "=" * 40)
        print("Configuration completed successfully!")
        print("=" * 40)
        
        if choice == "1":
            print("\nNext steps:")
            if is_initial_setup:
                print("1. The setup script will complete automatically")
                print("2. Exit this container when setup finishes")
                print("3. Rebuild your dev container to apply the mount configuration")
                print("4. Your local Azure CLI authentication will be available after rebuild")
            else:
                print("1. Rebuild your dev container")
                print("2. Your local Azure CLI authentication will be available")
        elif choice == "2":
            print("\nNext steps:")
            if is_initial_setup:
                print("1. The setup script will complete automatically")
                print("2. Sign in with tenant-specific authentication when setup finishes:")
                print("   az login --tenant <your-tenant-id-or-domain>")
                print("   az account set --subscription <your-subscription-id-or-name>")
                print("   az account show  # Verify your context")
            else:
                print("1. Start/rebuild your dev container")
                print("2. Sign in with tenant-specific authentication inside the container:")
                print("   az login --tenant <your-tenant-id-or-domain>")
                print("   az account set --subscription <your-subscription-id-or-name>")
                print("   az account show  # Verify your context")
        else:
            print("\nNext steps:")
            print("1. Edit .devcontainer/devcontainer.json manually if needed")
            print("2. See the commented examples in the file")
        
        return 0
    else:
        print("\nConfiguration failed. Check the error messages above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
