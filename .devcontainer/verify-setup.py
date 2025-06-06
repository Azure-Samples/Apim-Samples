#!/usr/bin/env python3
"""
Verification script for the APIM Samples dev container setup.
Run this script to verify that all dependencies are properly installed.
"""

import sys
import subprocess
import importlib.util

# ------------------------------
#    CONSTANTS
# ------------------------------

REQUIRED_PACKAGES = [
    'requests',
    'pandas',
    'matplotlib',
    'jwt',
    'pytest',
    'azure.storage.blob',
    'azure.identity',
    'jupyter',
    'ipykernel'
]

REQUIRED_COMMANDS = [
    'az',
    'python',
    'pip',
    'jupyter'
]

# ------------------------------
#    VERIFICATION FUNCTIONS
# ------------------------------

def check_python_packages():
    """Check if all required Python packages are installed."""
    print("🐍 Checking Python packages...")
    missing_packages = []
    
    for package in REQUIRED_PACKAGES:
        if importlib.util.find_spec(package) is None:
            missing_packages.append(package)
        else:
            print(f"  ✅ {package}")
    
    if missing_packages:
        print(f"  ❌ Missing packages: {', '.join(missing_packages)}")
        return False
    
    return True


def check_commands():
    """Check if required command-line tools are available."""
    print("\n🔧 Checking command-line tools...")
    missing_commands = []
    
    for command in REQUIRED_COMMANDS:
        try:
            subprocess.run([command, '--version'], 
                          capture_output=True, 
                          check=True, 
                          timeout=10)
            print(f"  ✅ {command}")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            missing_commands.append(command)
            print(f"  ❌ {command}")
    
    if missing_commands:
        print(f"  ❌ Missing commands: {', '.join(missing_commands)}")
        return False
    
    return True


def check_jupyter_kernel():
    """Check if the custom Jupyter kernel is installed."""
    print("\n📓 Checking Jupyter kernel...")
    try:
        result = subprocess.run(['jupyter', 'kernelspec', 'list'], 
                              capture_output=True, 
                              text=True, 
                              check=True,
                              timeout=10)
        
        if 'apim-samples' in result.stdout:
            print("  ✅ APIM Samples kernel found")
            return True
        else:
            print("  ❌ APIM Samples kernel not found")
            return False
            
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print("  ❌ Failed to check Jupyter kernels")
        return False


def check_azure_cli():
    """Check Azure CLI installation and extensions."""
    print("\n☁️ Checking Azure CLI...")
    try:
        # Check Azure CLI
        result = subprocess.run(['az', '--version'], 
                              capture_output=True, 
                              text=True, 
                              check=True,
                              timeout=10)
        
        print("  ✅ Azure CLI installed")
        
        # Check for useful extensions
        extensions = ['containerapp', 'front-door']
        for ext in extensions:
            if ext in result.stdout:
                print(f"  ✅ Extension {ext} installed")
            else:
                print(f"  ⚠️ Extension {ext} not found (optional)")
        
        return True
        
    except FileNotFoundError:
        print("  ❌ Azure CLI not found")
        return False
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print("  ❌ Azure CLI not working properly")
        return False


def main():
    """Main verification function."""
    print("🔍 Verifying APIM Samples dev container setup...\n")
    
    checks = [
        check_python_packages(),
        check_commands(),
        check_jupyter_kernel(),
        check_azure_cli()
    ]
    
    print("\n" + "="*50)
    
    if all(checks):
        print("🎉 All checks passed! Your dev container is ready to use.")
        print("\n📋 Next steps:")
        print("1. Configure Azure CLI: python .devcontainer/configure-azure-mount.py")
        print("2. Or manually sign in: az login")
        print("3. Execute shared/jupyter/verify-az-account.ipynb")
        print("4. If prompted, initialize the kernel according to the `Initialization` steps in the root README.md file")
        print("5. Explore the samples and infrastructure folders")
        return 0
    else:
        print("❌ Some checks failed. Please review the output above.")
        print("\n🔧 Try these troubleshooting steps:")
        print("1. Rebuild the container: Dev Containers: Rebuild Container")
        print("2. Manually run: pip install -r requirements.txt")
        print("3. Check the .devcontainer/README.md for more help")
        return 1


# ------------------------------
#    MAIN EXECUTION
# ------------------------------

if __name__ == "__main__":
    sys.exit(main())
