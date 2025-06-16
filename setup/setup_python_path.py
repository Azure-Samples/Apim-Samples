#!/usr/bin/env python3

"""
Cross-platform PYTHONPATH setup and Jupyter kernel registration for APIM Samples.

This script automatically detects the project root and configures PYTHONPATH
to include shared Python modules, and optionally registers a standardized
Jupyter kernel for consistent notebook experience. Cross-platform compatibility
is achieved by:
- Using pathlib.Path for all file operations (handles Windows/Unix path separators)
- Using absolute paths (eliminates relative path issues across platforms)
- Using UTF-8 encoding explicitly (ensures consistent file encoding)
- Using Python's sys.path for runtime PYTHONPATH configuration
- Registering consistent Jupyter kernel across local and dev container environments
"""

import sys
import subprocess
import os
from pathlib import Path  # Cross-platform path handling (Windows: \, Unix: /)


def get_project_root() -> Path:
    """
    Get the absolute path to the project root directory.
    
    Cross-platform strategy:
    - Uses pathlib.Path for consistent path operations across OS
    - Searches upward from script location to find project indicators
    - Returns absolute paths that work on Windows, macOS, and Linux
    
    Returns:
        Path: Absolute path to project root directory
    """

    # Start from script's parent directory (since we're in setup/ folder)
    # Path(__file__).resolve() gives absolute path, .parent.parent goes up two levels
    start_path = Path(__file__).resolve().parent.parent
    
    # Project root indicators - files that should exist at project root
    # These help identify the correct directory regardless of where script is run
    indicators = ['README.md', 'requirements.txt', 'bicepconfig.json']
    current_path = start_path
    
    # Walk up the directory tree until we find all indicators or reach filesystem root
    while current_path != current_path.parent:  # Stop at filesystem root
        # Check if all indicator files exist in current directory
        if all((current_path / indicator).exists() for indicator in indicators):
            return current_path
        current_path = current_path.parent
    
    # Fallback: if indicators not found, assume parent of script directory is project root
    # This handles cases where the project structure might be different
    return Path(__file__).resolve().parent.parent


def setup_python_path() -> None:
    """
    Add shared Python modules to PYTHONPATH for runtime import resolution.
    
    This modifies sys.path in the current Python session to enable imports
    from the shared/python directory. Cross-platform compatibility:
    - Uses pathlib for path construction (handles OS-specific separators)
    - Converts to string only when needed for sys.path compatibility
    - Uses sys.path.insert(0, ...) to prioritize our modules
    """

    project_root = get_project_root()
    # Use pathlib's / operator for cross-platform path joining
    shared_python_path = project_root / 'shared' / 'python'
    
    if shared_python_path.exists():
        # Convert Path object to string for sys.path compatibility
        shared_path_str = str(shared_python_path)
        
        # Check if path is already in sys.path to avoid duplicates
        if shared_path_str not in sys.path:
            # Insert at beginning to prioritize our modules over system modules
            sys.path.insert(0, shared_path_str)
            print(f"Added to PYTHONPATH: {shared_path_str}")


def generate_env_file() -> None:
    """
    Generate .env file with cross-platform absolute paths for VS Code integration.
      Creates a .env file that VS Code's Python extension reads to configure
    the Python environment. Cross-platform features:
    - Uses absolute paths (no relative path issues)
    - Explicit UTF-8 encoding (consistent across platforms)
    - pathlib handles path separators automatically (\\ on Windows, / on Unix)
    - Works with VS Code's python.envFile setting
    """
    
    project_root = get_project_root()
    shared_python_path = project_root / 'shared' / 'python'
    
    # Create .env file content with absolute paths
    # These paths will be automatically correct for the current platform
    env_content = f"""# Auto-generated PYTHONPATH for VS Code - Run 'python setup/setup_python_path.py' to regenerate
PROJECT_ROOT={project_root}
PYTHONPATH={shared_python_path}
"""
    
    env_file_path = project_root / '.env'
    
    # Use explicit UTF-8 encoding for cross-platform text file compatibility
    # This ensures the file reads correctly on all operating systems
    with open(env_file_path, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print()
    print(f"Generated .env file : {env_file_path}")
    print(f"PROJECT_ROOT        : {project_root}")
    print(f"PYTHONPATH          : {shared_python_path}\n")


def install_jupyter_kernel():
    """
    Install and register the standardized Jupyter kernel for APIM Samples.
    
    This creates a consistent kernel specification that matches the dev container
    setup, ensuring notebooks have the same kernel regardless of environment.
    """
    
    try:
        # Check if ipykernel is available
        subprocess.run([sys.executable, '-m', 'ipykernel', '--version'], 
                      check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Installing ipykernel...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'ipykernel'], 
                          check=True, capture_output=True, text=True)
            print("✅ ipykernel installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install ipykernel: {e}")
            return False
    
    # Register the kernel with standardized name and display name
    kernel_name = "apim-samples"
    display_name = "APIM Samples Python 3.12"
    
    try:
        # Install the kernel for the current user
        result = subprocess.run([
            sys.executable, '-m', 'ipykernel', 'install', 
            '--user', 
            f'--name={kernel_name}', 
            f'--display-name={display_name}'
        ], check=True, capture_output=True, text=True)
        
        print(f"✅ Jupyter kernel registered successfully:")
        print(f"   Name         : {kernel_name}")
        print(f"   Display Name : {display_name}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to register Jupyter kernel: {e}")
        if e.stderr:
            print(f"Error details: {e.stderr}")
        return False


def create_vscode_settings():
    """
    Create VS Code workspace settings to automatically use the APIM Samples kernel.
    
    This ensures that when users open notebooks, VS Code automatically selects
    the correct kernel without manual intervention.
    """
    
    project_root = get_project_root()
    vscode_dir = project_root / '.vscode'
    settings_file = vscode_dir / 'settings.json'
    
    # Create .vscode directory if it doesn't exist
    vscode_dir.mkdir(exist_ok=True)
    
    # Settings to update for kernel and Python configuration
    required_settings = {
        "python.defaultInterpreterPath": "./.venv/Scripts/python.exe" if os.name == 'nt' else "./.venv/bin/python",
        "python.pythonPath": "./.venv/Scripts/python.exe" if os.name == 'nt' else "./.venv/bin/python",
        "python.envFile": "${workspaceFolder}/.env",
        "jupyter.defaultKernel": "apim-samples",
        "jupyter.kernels.filter": [
            {
                "path": "apim-samples",
                "type": "pythonEnvironment"
            }
        ],
        "jupyter.kernels.excludePythonEnvironments": [
            "**/anaconda3/**",
            "**/conda/**",
            "**/miniconda3/**",
            "**/python3.*",
            "*/site-packages/*",
            "/bin/python",
            "/bin/python3", 
            "/opt/python/*/bin/python*",
            "/usr/bin/python",
            "/usr/bin/python3",
            "/usr/local/bin/python",
            "/usr/local/bin/python3",
            "python",
            "python3",
            "**/.venv/**/python*",
            "**/Scripts/python*",
            "**/bin/python*"
        ],
        "jupyter.kernels.trusted": [
            "./.venv/Scripts/python.exe" if os.name == 'nt' else "./.venv/bin/python"
        ],
        "jupyter.preferredKernelIdForNotebook": {
            "*.ipynb": "apim-samples"
        },
        "jupyter.kernels.changeKernelIdForNotebookEnabled": False,
        "notebook.defaultLanguage": "python",
        "notebook.kernelPickerType": "mru"
    }
    
    # For Windows, also set the default terminal profile
    if os.name == 'nt':
        required_settings["terminal.integrated.defaultProfile.windows"] = "PowerShell"
    
    # Check if settings.json already exists
    if settings_file.exists():
        try:
            # Read the existing settings file content as text first
            with open(settings_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Try to parse as JSON (will fail if it has comments)
            import json
            existing_settings = json.loads(content)
            
            # Merge required settings with existing ones
            existing_settings.update(required_settings)
            
            # Write back the merged settings
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(existing_settings, f, indent=4)
            
            print(f"✅ VS Code settings updated: {settings_file}")
            print("   - Existing settings preserved")
            print("   - Default kernel set to 'apim-samples'")
            print("   - Python interpreter configured for .venv")
            
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Existing settings.json has comments or formatting issues")
            print(f"   Please manually add these settings to preserve your existing configuration:")
            print(f"   - \"jupyter.defaultKernel\": \"apim-samples\"")
            print(f"   - \"python.defaultInterpreterPath\": \"{required_settings['python.defaultInterpreterPath']}\"")
            print(f"   - \"python.pythonPath\": \"{required_settings['python.pythonPath']}\"")
            return False
    else:
        # Create new settings file
        try:
            import json
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(required_settings, f, indent=4)
            
            print(f"✅ VS Code settings created: {settings_file}")
            print("   - Default kernel set to 'apim-samples'")
            print("   - Python interpreter configured for .venv")
        except (ImportError, IOError) as e:
            print(f"❌ Failed to create VS Code settings: {e}")
            return False
    
    return True


def validate_kernel_setup():
    """
    Validate that the APIM Samples kernel is properly registered and accessible.
    
    Returns:
        bool: True if kernel is properly configured, False otherwise
    """
    
    try:
        # Check if ipykernel is available
        result = subprocess.run([sys.executable, '-m', 'jupyter', 'kernelspec', 'list'], 
                              check=True, capture_output=True, text=True)
        
        # Check if our kernel is in the list
        if 'apim-samples' in result.stdout:
            print("✅ APIM Samples kernel found in kernelspec list")
            return True
        else:
            print("❌ APIM Samples kernel not found in kernelspec list")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to check kernel list: {e}")
        return False
    except FileNotFoundError:
        print("❌ Jupyter not found - please ensure Jupyter is installed")
        return False


def force_kernel_consistency():
    """
    Enforce kernel consistency by removing conflicting kernels and ensuring
    only the APIM Samples kernel is used for notebooks.
    """
    
    print("🔧 Enforcing kernel consistency...")
    
    # First, ensure our kernel is registered
    if not validate_kernel_setup():
        print("⚠️ Kernel not found, attempting to register...")
        if not install_jupyter_kernel():
            print("❌ Failed to register kernel - manual intervention required")
            return False
    
    # Update VS Code settings with strict kernel enforcement
    project_root = get_project_root()
    vscode_dir = project_root / '.vscode'
    settings_file = vscode_dir / 'settings.json'
    
    # Enhanced kernel settings that prevent VS Code from changing kernels
    strict_kernel_settings = {
        "jupyter.defaultKernel": "apim-samples",
        "jupyter.kernels.changeKernelIdForNotebookEnabled": False,
        "jupyter.kernels.filter": [
            {
                "path": "apim-samples", 
                "type": "pythonEnvironment"
            }
        ],
        "jupyter.preferredKernelIdForNotebook": {
            "*.ipynb": "apim-samples"
        },
        "jupyter.kernels.trusted": [
            "./.venv/Scripts/python.exe" if os.name == 'nt' else "./.venv/bin/python"
        ],
        # Prevent VS Code from auto-detecting other Python environments
        "jupyter.kernels.excludePythonEnvironments": [
            "**/anaconda3/**",
            "**/conda/**", 
            "**/miniconda3/**",
            "**/python3.*",
            "*/site-packages/*",
            "/bin/python",
            "/bin/python3",
            "/opt/python/*/bin/python*",
            "/usr/bin/python",
            "/usr/bin/python3", 
            "/usr/local/bin/python",
            "/usr/local/bin/python3",
            "python",
            "python3",
            "**/.venv/**/python*",
            "**/Scripts/python*",
            "**/bin/python*"
        ]
    }
    
    try:
        import json
        
        # Read existing settings or create new ones
        existing_settings = {}
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    existing_settings = json.load(f)
            except json.JSONDecodeError:
                print("⚠️ Existing settings.json has issues, creating new one")
        
        # Merge settings, with our strict kernel settings taking priority
        existing_settings.update(strict_kernel_settings)
        
        # Write updated settings
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(existing_settings, f, indent=4)
        
        print("✅ Strict kernel enforcement settings applied")
        return True
        
    except Exception as e:
        print(f"❌ Failed to update VS Code settings: {e}")
        return False


def setup_complete_environment():
    """
    Complete setup: generate .env file, register kernel, and configure VS Code.
    
    This provides a one-command setup that makes the local environment
    as easy to use as the dev container.
    """
    
    print("🚀 Setting up complete APIM Samples environment...\n")
    
    # Step 1: Generate .env file
    print("1. Generating .env file for Python path configuration...")
    generate_env_file()
    
    # Step 2: Register Jupyter kernel
    print("2. Registering standardized Jupyter kernel...")
    kernel_success = install_jupyter_kernel()
    
    # Step 3: Configure VS Code settings with strict kernel enforcement
    print("\n3. Configuring VS Code workspace settings...")
    vscode_success = create_vscode_settings()
    
    # Step 4: Enforce kernel consistency
    print("\n4. Enforcing kernel consistency for future reliability...")
    consistency_success = force_kernel_consistency()
    
    # Summary
    print("\n" + "="*50)
    print("📋 Setup Summary:")
    print(f"   ✅ Python path configuration: Complete")
    print(f"   {'✅' if kernel_success else '❌'} Jupyter kernel registration: {'Complete' if kernel_success else 'Failed'}")
    print(f"   {'✅' if vscode_success else '❌'} VS Code settings: {'Complete' if vscode_success else 'Failed'}")
    print(f"   {'✅' if consistency_success else '❌'} Kernel consistency enforcement: {'Complete' if consistency_success else 'Failed'}")
    
    if kernel_success and vscode_success and consistency_success:
        print("\n🎉 Setup complete! Your local environment now matches the dev container experience.")
        print("   • Notebooks will automatically use the 'APIM Samples Python 3.12' kernel")
        print("   • Python modules from shared/ directory are available")
        print("   • VS Code is configured for optimal workflow")
        print("   • Kernel selection is locked to prevent auto-changes")
        print("\n💡 Next steps:")
        print("   1. Restart VS Code to apply all settings")
        print("   2. Open any notebook - it should automatically use the correct kernel")
        print("   3. The kernel should remain consistent across all notebooks")
    else:
        print("\n⚠️  Setup completed with some issues. Check error messages above.")


def show_help():
    """
    Display comprehensive help information about the script's functionality and available options.
    """
    print("\n" + "="*80)
    print("                      APIM Samples Python Environment Setup")
    print("="*80)
    
    print("\nThis script configures the Python environment for APIM Samples development.")
    print("It handles PYTHONPATH setup, Jupyter kernel registration, and VS Code integration.")
    
    print("\nUSAGE:")
    print("  python setup/setup_python_path.py [OPTION]")
    
    print("\nOPTIONS:")
    print("  (no options)        Show this help information")
    print("  --run-only          Only modify current session's PYTHONPATH (basic setup)")
    print("  --generate-env      Generate .env file for VS Code and terminal integration")
    print("  --setup-kernel      Register the APIM Samples Jupyter kernel")
    print("  --setup-vscode      Configure VS Code settings for optimal workflow")
    print("  --complete-setup    Perform complete environment setup (recommended)")
    
    print("\nDETAILS:")
    print("  --run-only:")
    print("    • Modifies the current Python session's sys.path")
    print("    • Adds shared/python directory to PYTHONPATH")
    print("    • Changes are temporary (only for current session)")
    print("    • Use this for quick testing in the current terminal")
    
    print("\n  --generate-env:")
    print("    • Creates a .env file at project root")
    print("    • Sets PROJECT_ROOT and PYTHONPATH variables")
    print("    • Used by VS Code and can be sourced in shells")
    print("    • Ensures consistent paths across platforms")
    
    print("\n  --setup-kernel:")
    print("    • Registers a standardized Jupyter kernel named 'apim-samples'")
    print("    • Display name will be 'APIM Samples Python 3.12'")
    print("    • Ensures consistent notebook experience")
    print("    • Installs ipykernel if not already available")
    
    print("\n  --setup-vscode:")
    print("    • Creates/updates .vscode/settings.json")
    print("    • Configures Python interpreter, Jupyter settings")
    print("    • Sets default kernel for notebooks")
    print("    • Preserves existing VS Code settings")
    
    print("\n  --complete-setup:")
    print("    • Performs all of the above steps")
    print("    • Recommended for new development environments")
    print("    • Recreates dev container experience locally")
    
    print("\nEXAMPLES:")
    print("  # Show this help information:")
    print("  python setup/setup_python_path.py")
    print("\n  # Perform complete setup (recommended for new users):")
    print("  python setup/setup_python_path.py --complete-setup")
    print("\n  # Only generate the .env file:")
    print("  python setup/setup_python_path.py --generate-env")
    
    print("\nNOTES:")
    print("  • Running this script without options now displays this help screen")
    print("  • For basic PYTHONPATH setup, use the --run-only option")
    print("  • The --complete-setup option is recommended for new environments")
    print("  • Changes to .vscode/settings.json require restarting VS Code")
    print("="*80)


# Script entry point - handles command-line arguments
if __name__ == "__main__":
    # Parse command-line arguments for different setup modes
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--generate-env":
            # Legacy: just generate .env file
            generate_env_file()
        elif command == "--setup-kernel":
            # Just register the Jupyter kernel
            install_jupyter_kernel()
        elif command == "--setup-vscode":
            # Just configure VS Code settings
            create_vscode_settings()
        elif command == "--force-kernel":
            # Force kernel consistency and prevent changes
            force_kernel_consistency()
        elif command == "--complete-setup":
            # Full setup: everything needed for local development
            setup_complete_environment()
        elif command == "--run-only":
            # Only modify current session's PYTHONPATH
            setup_python_path()
        else:
            # Show help for unrecognized options
            show_help()
    else:
        # Default behavior: show help instead of modifying PYTHONPATH
        show_help()
