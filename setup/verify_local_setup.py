#!/usr/bin/env python3
"""
Verification script for local APIM Samples environment setup.

This script verifies that the local environment is configured correctly:
- Virtual environment is active
- Required packages are installed
- Shared modules can be imported
- Jupyter kernel is registered
- VS Code settings are configured

Run this after completing the setup to ensure everything is working.
"""

import sys
import subprocess
import os
from pathlib import Path


def print_status(message, success=True):
    """Print status message with colored output."""
    color = "32" if success else "31"  # Green for success, red for failure
    icon = "✅" if success else "❌"
    print(f"{icon} \033[1;{color}m{message}\033[0m")


def print_section(title):
    """Print section header."""
    print(f"\n📋 {title}")
    print("-" * (len(title) + 3))


def check_virtual_environment():
    """Check if we're running in the correct virtual environment."""
    venv_path = Path.cwd() / ".venv"
    if not venv_path.exists():
        print_status("Virtual environment (.venv) not found", False)
        return False
    
    # Check if current Python executable is from the venv
    current_python = Path(sys.executable)
    expected_venv_python = venv_path / ("Scripts" if os.name == 'nt' else "bin") / "python"
    
    if not str(current_python).startswith(str(venv_path)):
        print_status(f"Not using virtual environment Python", False)
        print(f"   Current: {current_python}")
        print(f"   Expected: {expected_venv_python}")
        return False
    
    print_status("Virtual environment is active")
    return True


def check_required_packages():
    """Check if required packages are installed."""
    # List of (package_name, import_name) tuples
    required_packages = [
        ('requests', 'requests'),
        ('ipykernel', 'ipykernel'),
        ('jupyter', 'jupyter'),
        ('python-dotenv', 'dotenv')
    ]
    
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
            print_status(f"{package_name} is installed")
        except ImportError:
            print_status(f"{package_name} is missing", False)
            missing_packages.append(package_name)
    
    return len(missing_packages) == 0


def check_shared_modules():
    """Check if shared modules can be imported."""
    try:
        # Add project root to path
        project_root = Path(__file__).parent.parent
        shared_python_path = project_root / 'shared' / 'python'
        
        if str(shared_python_path) not in sys.path:
            sys.path.insert(0, str(shared_python_path))
        
        # Try importing shared modules
        import utils
        import apimtypes
        import authfactory
        import apimrequests
        
        print_status("All shared modules can be imported")
        return True
        
    except ImportError as e:
        print_status(f"Shared module import failed: {e}", False)
        return False


def check_jupyter_kernel():
    """Check if the APIM Samples Jupyter kernel is registered."""
    try:
        result = subprocess.run([
            sys.executable, '-m', 'jupyter', 'kernelspec', 'list'
        ], capture_output=True, text=True, check=True)
        
        if 'apim-samples' in result.stdout:
            print_status("APIM Samples Jupyter kernel is registered")
            return True
        else:
            print_status("APIM Samples Jupyter kernel not found", False)
            return False
            
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_status("Could not check Jupyter kernel registration", False)
        return False


def check_vscode_settings():
    """Check if VS Code settings are configured."""
    vscode_settings = Path.cwd() / '.vscode' / 'settings.json'
    
    if not vscode_settings.exists():
        print_status("VS Code settings.json not found", False)
        return False
    
    try:
        with open(vscode_settings, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for key settings (simple string search since the file may have comments)
        checks = [
            ('jupyter.defaultKernel', 'apim-samples'),
            ('python.defaultInterpreterPath', '.venv'),
            ('notebook.defaultLanguage', 'python')
        ]
        
        all_found = True
        for setting_key, expected_value in checks:
            if setting_key not in content or expected_value not in content:
                print_status(f"VS Code setting '{setting_key}' not properly configured", False)
                all_found = False
        
        if all_found:
            print_status("VS Code settings are configured correctly")
            return True
        else:
            return False
            
    except Exception as e:
        print_status(f"Could not read VS Code settings: {e}", False)
        return False


def check_env_file():
    """Check if .env file exists and has correct configuration."""
    env_file = Path.cwd() / '.env'
    
    if not env_file.exists():
        print_status(".env file not found", False)
        return False
    
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'PYTHONPATH=' in content and 'PROJECT_ROOT=' in content:
            print_status(".env file is configured correctly")
            return True
        else:
            print_status(".env file missing required configuration", False)
            return False
            
    except Exception as e:
        print_status(f"Could not read .env file: {e}", False)
        return False


def main():
    """Run all verification checks."""
    print("🔍 APIM Samples Local Environment Verification")
    print("=" * 50)
    
    checks = [
        ("Virtual Environment", check_virtual_environment),
        ("Required Packages", check_required_packages),
        ("Shared Modules", check_shared_modules),
        ("Environment File", check_env_file),
        ("Jupyter Kernel", check_jupyter_kernel),
        ("VS Code Settings", check_vscode_settings)
    ]
    
    results = []
    
    for check_name, check_function in checks:
        print_section(check_name)
        result = check_function()
        results.append((check_name, result))
      # Summary
    print_section("Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
      # Calculate the maximum check name length for alignment
    max_name_length = max(len(check_name) for check_name, _ in results)
    
    for check_name, result in results:
        padded_name = check_name.ljust(max_name_length + 1)
        print_status(f"{padded_name}: {'PASS' if result else 'FAIL'}", result)
    
    print(f"\n📊 Overall: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All checks passed! Your local environment is ready for APIM Samples.")
        print("💡 You can now open any notebook and it should work seamlessly.")
    else:
        print("\n⚠️  Some checks failed. Consider running the setup script:")
        print("   python setup/setup_python_path.py --complete-setup")
        print("   Then restart VS Code and run this verification again.")
    
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
