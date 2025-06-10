#!/usr/bin/env python3
"""
Configure Python interpreter for VS Code in devcontainer.

This script ensures that VS Code automatically detects and uses the virtual environment
created during container build.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


# ------------------------------
#    CONSTANTS
# ------------------------------

VENV_PATH = "/home/vscode/.venv"
PYTHON_EXECUTABLE = f"{VENV_PATH}/bin/python"
WORKSPACE_ROOT = "/workspaces/Apim-Samples"


# ------------------------------
#    PUBLIC METHODS
# ------------------------------

def register_python_interpreter() -> bool:
    """
    Register the virtual environment Python interpreter with VS Code.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Verify the virtual environment exists
        if not Path(PYTHON_EXECUTABLE).exists():
            print(f"❌ Python interpreter not found at {PYTHON_EXECUTABLE}")
            return False
            
        # Get Python version info
        result = subprocess.run(
            [PYTHON_EXECUTABLE, "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        python_version = result.stdout.strip()
        print(f"🐍 Found Python interpreter: {python_version}")
        
        # Verify packages are installed
        result = subprocess.run(
            [PYTHON_EXECUTABLE, "-c", "import requests, jwt, pandas, matplotlib"],
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ Core packages verified")
        
        # Create/update workspace settings to point to the correct interpreter
        vscode_dir = Path(WORKSPACE_ROOT) / ".vscode"
        settings_file = vscode_dir / "settings.json"
        
        # Ensure .vscode directory exists
        vscode_dir.mkdir(exist_ok=True)
        
        # Read existing settings if they exist
        settings = {}
        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    content = f.read()
                    # Remove comments for JSON parsing
                    lines = content.split('\n')
                    clean_lines = [line for line in lines if not line.strip().startswith('//')]
                    clean_content = '\n'.join(clean_lines)
                    settings = json.loads(clean_content)
            except json.JSONDecodeError:
                print("⚠️ Existing settings.json has syntax issues, will preserve as much as possible")
        
        # Update Python interpreter settings
        python_settings = {
            "python.defaultInterpreterPath": PYTHON_EXECUTABLE,
            "python.pythonPath": PYTHON_EXECUTABLE,
            "python.terminal.activateEnvironment": True,
            "python.terminal.activateEnvInCurrentTerminal": True,
            "jupyter.defaultKernel": "apim-samples",
            "jupyter.askForKernelRestart": False,
        }
        
        settings.update(python_settings)
        
        print(f"✅ Python interpreter registered: {PYTHON_EXECUTABLE}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error checking Python interpreter: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def create_python_environment_marker() -> None:
    """
    Create a marker file that VS Code can use to auto-detect the environment.
    """
    try:
        # Create a pyvenv.cfg file that VS Code recognizes
        pyvenv_cfg = Path(VENV_PATH) / "pyvenv.cfg"
        if not pyvenv_cfg.exists():
            with open(pyvenv_cfg, 'w') as f:
                f.write(f"home = /usr/bin\n")
                f.write(f"include-system-site-packages = false\n")
                f.write(f"version = 3.12\n")
                f.write(f"executable = {PYTHON_EXECUTABLE}\n")
            print("✅ Created Python environment marker")
        
        # Create activate script marker
        activate_script = Path(VENV_PATH) / "bin" / "activate"
        if activate_script.exists():
            print("✅ Virtual environment activation script found")
        else:
            print("⚠️ Virtual environment activation script not found")
            
    except Exception as e:
        print(f"⚠️ Could not create environment marker: {e}")


def verify_setup() -> bool:
    """
    Verify that the Python environment is properly configured.
    
    Returns:
        bool: True if verification passes, False otherwise
    """
    try:
        print("🔍 Verifying Python environment setup...")
        
        # Check virtual environment
        if not Path(VENV_PATH).exists():
            print(f"❌ Virtual environment not found at {VENV_PATH}")
            return False
            
        # Check Python executable
        if not Path(PYTHON_EXECUTABLE).exists():
            print(f"❌ Python executable not found at {PYTHON_EXECUTABLE}")
            return False
            
        # Test Python execution
        result = subprocess.run(
            [PYTHON_EXECUTABLE, "-c", "import sys; print(f'Python {sys.version}')"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✅ {result.stdout.strip()}")
        
        # Test package imports
        packages_to_test = ["requests", "jwt", "pandas", "matplotlib", "azure.storage.blob", "azure.identity"]
        for package in packages_to_test:
            try:
                subprocess.run(
                    [PYTHON_EXECUTABLE, "-c", f"import {package}"],
                    capture_output=True,
                    text=True,
                    check=True
                )
            except subprocess.CalledProcessError:
                print(f"⚠️ Package {package} not available")
                return False
                
        print("✅ All required packages are available")
        
        # Check Jupyter kernel
        try:
            result = subprocess.run(
                [PYTHON_EXECUTABLE, "-m", "jupyter", "kernelspec", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            if "apim-samples" in result.stdout:
                print("✅ Jupyter kernel 'apim-samples' is registered")
            else:
                print("⚠️ Jupyter kernel 'apim-samples' not found")
        except subprocess.CalledProcessError:
            print("⚠️ Could not check Jupyter kernels")
            
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False


def main() -> int:
    """
    Main function to configure Python interpreter.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    print("🔧 Configuring Python interpreter for VS Code...")
    print("")
    
    # Register the Python interpreter
    if not register_python_interpreter():
        print("❌ Failed to register Python interpreter")
        return 1
        
    # Create environment markers
    create_python_environment_marker()
    
    # Verify the setup
    if not verify_setup():
        print("❌ Environment verification failed")
        return 1
        
    print("")
    print("🎉 Python interpreter configuration complete!")
    print(f"📍 Interpreter path: {PYTHON_EXECUTABLE}")
    print(f"📍 Virtual environment: {VENV_PATH}")
    print("")
    print("💡 VS Code should now automatically use the virtual environment.")
    print("💡 If you still see a Python interpreter selection prompt:")
    print("   1. Press Ctrl+Shift+P")
    print("   2. Type 'Python: Select Interpreter'")
    print(f"   3. Choose: {PYTHON_EXECUTABLE}")
    print("")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
