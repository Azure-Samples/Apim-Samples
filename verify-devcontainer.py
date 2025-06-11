#!/usr/bin/env python3
"""
APIM Samples Dev Container Verification Script
==============================================

This script verifies that the dev container is properly configured for
Azure API Management development work. It checks:

1. Python virtual environment setup
2. Required packages installation
3. Jupyter kernel configuration
4. VS Code integration
5. Environment file generation
6. Azure CLI setup

Run this script inside the dev container to verify everything is working.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*50}")
    print(f"🔍 {title}")
    print('='*50)

def check_mark(condition, success_msg, failure_msg):
    """Print a check mark or X based on condition."""
    if condition:
        print(f"✅ {success_msg}")
        return True
    else:
        print(f"❌ {failure_msg}")
        return False

def warning_mark(condition, success_msg, warning_msg):
    """Print a check mark or warning based on condition."""
    if condition:
        print(f"✅ {success_msg}")
        return True
    else:
        print(f"⚠️  {warning_msg}")
        return False

def main():
    print("🚀 APIM Samples Dev Container Verification")
    print("==========================================")
    
    issues = []
    
    # 1. Check Python environment
    print_section("Python Virtual Environment")
    
    # Check Python version
    python_version = sys.version_info
    if not check_mark(
        python_version.major == 3 and python_version.minor >= 10,
        f"Python {python_version.major}.{python_version.minor}.{python_version.micro}",
        f"Python version should be 3.10+ (got {python_version.major}.{python_version.minor}.{python_version.micro})"
    ):
        issues.append("Python version")
    
    # Check virtual environment
    venv_path = os.environ.get('VIRTUAL_ENV')
    expected_venv = '/workspaces/Apim-Samples/.venv'
    if not check_mark(
        venv_path and venv_path == expected_venv,
        f"Virtual environment: {venv_path}",
        f"Expected virtual environment at {expected_venv}, got {venv_path}"
    ):
        issues.append("Virtual environment path")
    
    # Check Python executable
    python_exe = sys.executable
    expected_python = '/workspaces/Apim-Samples/.venv/bin/python'
    if not warning_mark(
        expected_python in python_exe,
        f"Python executable: {python_exe}",
        f"Python executable should be in venv: {python_exe}"
    ):
        issues.append("Python executable location")
    
    # 2. Check required packages
    print_section("Required Packages")
    
    required_packages = [
        'requests', 'pandas', 'matplotlib', 'jwt', 'azure.identity', 
        'azure.storage.blob', 'pytest', 'jupyter', 'ipykernel'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (missing)")
            missing_packages.append(package)
    
    if missing_packages:
        issues.append(f"Missing packages: {', '.join(missing_packages)}")
    
    # 3. Check workspace structure
    print_section("Workspace Structure")
    
    workspace_files = [
        ('/workspaces/Apim-Samples/.venv', 'Virtual environment directory'),
        ('/workspaces/Apim-Samples/.env', 'Environment configuration file'),
        ('/workspaces/Apim-Samples/requirements.txt', 'Requirements file'),
        ('/workspaces/Apim-Samples/shared/python', 'Shared Python modules'),
        ('/workspaces/Apim-Samples/setup/setup_python_path.py', 'Setup script'),
    ]
    
    for file_path, description in workspace_files:
        if not check_mark(
            Path(file_path).exists(),
            f"{description}: {file_path}",
            f"{description} missing: {file_path}"
        ):
            issues.append(f"Missing {description}")
    
    # 4. Check PYTHONPATH
    print_section("Python Path Configuration")
    
    pythonpath = os.environ.get('PYTHONPATH', '')
    expected_paths = ['/workspaces/Apim-Samples/shared/python', '/workspaces/Apim-Samples']
    
    for path in expected_paths:
        if not warning_mark(
            path in pythonpath,
            f"PYTHONPATH includes: {path}",
            f"PYTHONPATH missing: {path}"
        ):
            issues.append(f"PYTHONPATH configuration")
    
    # 5. Check Jupyter kernel
    print_section("Jupyter Kernel Configuration")
    
    try:
        # List available kernels
        result = subprocess.run(['jupyter', 'kernelspec', 'list', '--json'], 
                              capture_output=True, text=True, check=True)
        kernels = json.loads(result.stdout)
        
        apim_kernel_found = False
        for kernel_name, kernel_info in kernels.get('kernelspecs', {}).items():
            if 'apim-samples' in kernel_name.lower():
                apim_kernel_found = True
                print(f"✅ APIM Samples kernel found: {kernel_name}")
                print(f"   Display name: {kernel_info.get('spec', {}).get('display_name', 'N/A')}")
                break
        
        if not apim_kernel_found:
            print("❌ APIM Samples Jupyter kernel not found")
            print("   Available kernels:", list(kernels.get('kernelspecs', {}).keys()))
            issues.append("Jupyter kernel registration")
            
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"❌ Error checking Jupyter kernels: {e}")
        issues.append("Jupyter kernel check failed")
    
    # 6. Check Azure CLI
    print_section("Azure CLI Configuration")
    
    try:
        result = subprocess.run(['az', '--version'], capture_output=True, text=True, check=True)
        az_version = result.stdout.split('\n')[0] if result.stdout else "Unknown"
        print(f"✅ Azure CLI: {az_version}")
        
        # Check for bicep extension
        result = subprocess.run(['az', 'extension', 'list'], capture_output=True, text=True, check=True)
        extensions = json.loads(result.stdout)
        bicep_installed = any(ext.get('name') == 'bicep' for ext in extensions)
        
        if not warning_mark(
            bicep_installed,
            "Bicep extension installed",
            "Bicep extension not installed (run: az extension add --name bicep)"
        ):
            pass  # Not critical
            
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"❌ Azure CLI error: {e}")
        issues.append("Azure CLI setup")
    
    # 7. Final summary
    print_section("Summary")
    
    if not issues:
        print("🎉 All checks passed! Your dev container is ready for Azure APIM development.")
        print("\nNext steps:")
        print("1. Open a Jupyter notebook and verify the kernel selection")
        print("2. Run 'az login' to authenticate with Azure")
        print("3. Start exploring the APIM samples!")
        return 0
    else:
        print(f"⚠️  Found {len(issues)} issue(s) that may need attention:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        print("\nPlease review the issues above and refer to the dev container documentation.")
        return 1

if __name__ == '__main__':
    exit(main())
