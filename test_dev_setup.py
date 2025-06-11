#!/usr/bin/env python3
"""
Test script to verify dev container setup is working correctly.
This script can be run to validate the environment after container setup.
"""

import sys
import os
import subprocess
from pathlib import Path

def test_python_environment():
    """Test that Python environment is correctly configured"""
    print("=== Python Environment Test ===")
    
    # Check Python version
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    
    # Check virtual environment
    venv_path = os.environ.get('VIRTUAL_ENV')
    if venv_path:
        print(f"Virtual environment: {venv_path}")
        expected_venv = "/workspaces/Apim-Samples/.venv"
        if venv_path == expected_venv:
            print("✅ Correct virtual environment active")
        else:
            print(f"⚠️  Expected {expected_venv}, got {venv_path}")
    else:
        print("❌ No virtual environment detected")
    
    print()

def test_package_imports():
    """Test that all required packages can be imported"""
    print("=== Package Import Test ===")
    
    packages_to_test = [
        'requests',
        'pandas', 
        'matplotlib',
        'jwt',
        'azure.identity',
        'azure.storage.blob',
        'pytest',
        'jupyter',
        'ipykernel'
    ]
    
    failed_imports = []
    for package in packages_to_test:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError as e:
            print(f"❌ {package}: {e}")
            failed_imports.append(package)
    
    if failed_imports:
        print(f"\n⚠️  Failed to import: {', '.join(failed_imports)}")
    else:
        print("\n✅ All packages imported successfully")
    
    print()

def test_workspace_structure():
    """Test that workspace structure is as expected"""
    print("=== Workspace Structure Test ===")
    
    workspace_root = Path("/workspaces/Apim-Samples")
    expected_paths = [
        workspace_root / ".venv",
        workspace_root / ".venv" / "bin" / "python",
        workspace_root / ".env",
        workspace_root / "requirements.txt",
        workspace_root / "shared" / "python",
        workspace_root / "setup" / "setup_python_path.py"
    ]
    
    for path in expected_paths:
        if path.exists():
            print(f"✅ {path}")
        else:
            print(f"❌ {path} (missing)")
    
    print()

def test_environment_variables():
    """Test that environment variables are correctly set"""
    print("=== Environment Variables Test ===")
    
    # Check PYTHONPATH
    pythonpath = os.environ.get('PYTHONPATH', '')
    print(f"PYTHONPATH: {pythonpath}")
    
    expected_paths = [
        "/workspaces/Apim-Samples/shared/python",
        "/workspaces/Apim-Samples"
    ]
    
    for expected_path in expected_paths:
        if expected_path in pythonpath:
            print(f"✅ {expected_path} in PYTHONPATH")
        else:
            print(f"⚠️  {expected_path} not in PYTHONPATH")
    
    # Check .env file
    env_file = Path("/workspaces/Apim-Samples/.env")
    if env_file.exists():
        print("✅ .env file exists")
        # Could read and validate contents here
    else:
        print("❌ .env file missing")
    
    print()

def test_azure_cli():
    """Test Azure CLI setup"""
    print("=== Azure CLI Test ===")
    
    try:
        # Check Azure CLI version
        result = subprocess.run(['az', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✅ {version_line}")
        else:
            print("❌ Azure CLI not working")
    except Exception as e:
        print(f"❌ Azure CLI error: {e}")
    
    # Check extensions
    try:
        result = subprocess.run(['az', 'extension', 'list'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            if 'containerapp' in result.stdout:
                print("✅ containerapp extension installed")
            else:
                print("⚠️  containerapp extension missing")
            
            if 'front-door' in result.stdout:
                print("✅ front-door extension installed")
            else:
                print("⚠️  front-door extension missing")
        else:
            print("⚠️  Could not check Azure CLI extensions")
    except Exception as e:
        print(f"⚠️  Azure CLI extension check error: {e}")
    
    print()

def main():
    """Run all tests"""
    print("🧪 Testing APIM Samples Dev Container Setup\n")
    
    test_python_environment()
    test_package_imports()
    test_workspace_structure()
    test_environment_variables()
    test_azure_cli()
    
    print("🎉 Test complete!")
    print("\nIf you see any ❌ or ⚠️  items above, the environment may need attention.")
    print("Otherwise, your dev container is ready for Azure APIM development!")

if __name__ == "__main__":
    main()
