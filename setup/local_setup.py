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

The script is idempotent and merges settings to preserve any existing
customizations in .env and .vscode/settings.json.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path  # Cross-platform path handling (Windows: \, Unix: /)


DEFAULT_PYTHON_ANALYSIS_EXCLUDE = [
    "**/node_modules",
    "**/__pycache__",
    ".git",
    "**/build",
    "env/**",
]

KERNEL_NAME = "python-venv"
KERNEL_DISPLAY_NAME = "Python (.venv)"


def _ensure_utf8_streams() -> None:
    """Ensure stdout/stderr use UTF-8 to avoid Windows cp1252 issues.

    On some Windows setups, the default console encoding is cp1252, which
    cannot encode many Unicode symbols (e.g., emoji). Reconfiguring the
    standard streams to UTF-8 prevents UnicodeEncodeError when printing.

    This is a safe no-op on platforms where UTF-8 is already the default.
    """

    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        # If reconfigure is unavailable or fails, fall back to env var.
        pass

    # Encourage UTF-8 for any child processes that honor PYTHONIOENCODING.
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


# Configure streams immediately on import so all prints are safe.
_ensure_utf8_streams()


def _venv_python_path() -> str:
    """Return the workspace-local virtualenv interpreter path (platform aware)."""

    return "./.venv/Scripts/python.exe" if os.name == "nt" else "./.venv/bin/python"


def check_azure_cli_installed():
    """Check if Azure CLI is installed."""
    az_path = shutil.which('az') or shutil.which('az.cmd') or shutil.which('az.bat')
    if not az_path:
        print("   ❌ Azure CLI is not installed. Please install from: https://learn.microsoft.com/cli/azure/install-azure-cli")
        return False
    try:
        subprocess.run([az_path, '--version'], capture_output=True, text=True, check=True)
        print("   ✅ Azure CLI is installed")
        return True
    except subprocess.CalledProcessError:
        print("   ❌ Azure CLI is not installed. Please install from: https://learn.microsoft.com/cli/azure/install-azure-cli")
        return False

def check_bicep_cli_installed():
    """Check if Azure Bicep CLI is installed."""
    az_path = shutil.which('az') or shutil.which('az.cmd') or shutil.which('az.bat')
    if not az_path:
        print("   ❌ Azure CLI is not installed. Please install from: https://learn.microsoft.com/cli/azure/install-azure-cli")
        return False

    try:
        subprocess.run([az_path, 'bicep', 'version'], capture_output=True, text=True, check=True)
        print("   ✅ Azure Bicep CLI is installed (via az bicep)")
        return True
    except subprocess.CalledProcessError:
        print("   ❌ Azure Bicep CLI is not installed. Install with: az bicep install")
        return False

def check_azure_providers_registered():
    """Check if required Azure resource providers are registered in the current subscription."""
    az_path = shutil.which('az') or shutil.which('az.cmd') or shutil.which('az.bat')
    if not az_path:
        print("   ❌ Azure CLI is not installed. Please install from: https://learn.microsoft.com/cli/azure/install-azure-cli")
        return False
    required_providers = [
        'Microsoft.ApiManagement',
        'Microsoft.App',
        'Microsoft.Authorization',
        'Microsoft.CognitiveServices',
        'Microsoft.ContainerRegistry',
        'Microsoft.KeyVault',
        'Microsoft.Maps',
        'Microsoft.ManagedIdentity',
        'Microsoft.Network',
        'Microsoft.OperationalInsights',
        'Microsoft.Resources',
        'Microsoft.Storage'
    ]

    try:
        # Get list of registered providers
        result = subprocess.run(
            [az_path, 'provider', 'list', '--query', '[].namespace', '-o', 'json'],
            capture_output=True,
            text=True,
            check=True
        )
        registered_providers = json.loads(result.stdout)

        missing_providers = [p for p in required_providers if p not in registered_providers]

        if not missing_providers:
            print("   ✅ All required Azure resource providers are registered")
            return True

        print(f"   ❌ Missing {len(missing_providers)} Azure provider(s):")
        for provider in missing_providers:
            print(f"      • {provider}")
        print("   Register with: az provider register -n <provider-namespace>")
        return False

    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        print("   ⚠️  Could not verify Azure provider registrations (Azure CLI may not be configured)")
        return False

def _normalize_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _merge_string_list(existing: object, required: list[str]) -> list[str]:
    """Merge lists while preserving order and avoiding duplicates.

    Required items come first, followed by any existing items.
    """

    existing_list = _normalize_string_list(existing)
    merged: list[str] = []

    for item in required:
        if item not in merged:
            merged.append(item)
    for item in existing_list:
        if item not in merged:
            merged.append(item)

    return merged


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

    env_file_path = project_root / '.env'

    existing_vars: dict[str, str] = {}
    if env_file_path.exists():
        try:
            for line in env_file_path.read_text(encoding='utf-8').splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                if '=' not in stripped:
                    continue
                key, value = stripped.split('=', 1)
                existing_vars[key.strip()] = value
        except OSError:
            existing_vars = {}

    # Keys we manage (and may default). If present already, keep the user's value.
    managed_keys = {
        'APIM_SAMPLES_CONSOLE_WIDTH': existing_vars.get('APIM_SAMPLES_CONSOLE_WIDTH', '180'),
        'APIM_SAMPLES_LOG_LEVEL': existing_vars.get('APIM_SAMPLES_LOG_LEVEL', 'INFO'),
        'PROJECT_ROOT': str(project_root),
        'PYTHONPATH': str(shared_python_path),
        'SPOTIFY_CLIENT_ID': existing_vars.get('SPOTIFY_CLIENT_ID', ''),
        'SPOTIFY_CLIENT_SECRET': existing_vars.get('SPOTIFY_CLIENT_SECRET', ''),
    }

    preserved_extras = {
        k: v for k, v in existing_vars.items() if k not in managed_keys
    }

    # Create .env file content with absolute paths
    # These paths will be automatically correct for the current platform
    lines: list[str] = [
        "# Auto-generated environment for VS Code and local tooling",
        "# Run 'python setup/local_setup.py --generate-env' to regenerate",
        "# Good to set console width to 220, 221 - whatever it takes",
        "",
        f"APIM_SAMPLES_CONSOLE_WIDTH={managed_keys['APIM_SAMPLES_CONSOLE_WIDTH']}",
        f"APIM_SAMPLES_LOG_LEVEL={managed_keys['APIM_SAMPLES_LOG_LEVEL']}",
        f"PROJECT_ROOT={managed_keys['PROJECT_ROOT']}",
        f"PYTHONPATH={managed_keys['PYTHONPATH']}",
        f"SPOTIFY_CLIENT_ID={managed_keys['SPOTIFY_CLIENT_ID']}",
        f"SPOTIFY_CLIENT_SECRET={managed_keys['SPOTIFY_CLIENT_SECRET']}",
    ]

    if preserved_extras:
        lines.extend(["", "# Preserved custom variables (not managed by the generator)"])
        for key in sorted(preserved_extras):
            lines.append(f"{key}={preserved_extras[key]}")

    env_content = "\n".join(lines) + "\n"

    # Use explicit UTF-8 encoding for cross-platform text file compatibility
    # This ensures the file reads correctly on all operating systems
    with open(env_file_path, 'w', encoding='utf-8') as f:
        f.write(env_content)

    print(f"\nSuccessfully generated .env file: {env_file_path}\n")


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

    kernel_name = KERNEL_NAME
    display_name = KERNEL_DISPLAY_NAME

    try:
        # Install the kernel for the current user
        subprocess.run([
            sys.executable, '-m', 'ipykernel', 'install',
            '--user',
            f'--name={kernel_name}',
            f'--display-name={display_name}'
        ], check=True, capture_output=True, text=True)

        print("✅ Jupyter kernel registered successfully:")
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
    Create VS Code workspace settings to prefer the standardized python-venv kernel.

    Settings are merged rather than overwritten so existing customizations stay intact.
    """

    project_root = get_project_root()
    vscode_dir = project_root / '.vscode'
    settings_file = vscode_dir / 'settings.json'

    # Create .vscode directory if it doesn't exist
    vscode_dir.mkdir(exist_ok=True)

    venv_python = _venv_python_path()

    # Settings to update for Python and notebook flow. Trusted kernels
    # are merged to avoid overwriting user customizations.
    required_settings = {
        "python.defaultInterpreterPath": venv_python,
        "python.envFile": "${workspaceFolder}/.env",
        "python.terminal.activateEnvironment": True,
        "python.terminal.activateEnvInCurrentTerminal": True,
        "python.testing.pytestEnabled": True,
        "python.linting.enabled": True,
        "python.linting.pylintEnabled": True,
        "jupyter.kernels.trusted": [venv_python],
    }

    # Check if settings.json already exists
    if settings_file.exists():
        try:
            # Read the existing settings file content as text first
            with open(settings_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Try to parse as JSON (will fail if it has comments)
            existing_settings = json.loads(content)
        except (json.JSONDecodeError, IOError):
            print("⚠️  Existing settings.json has comments or formatting issues; keeping your file untouched.")
            print("   Please manually merge these minimal settings:")
            for key, value in required_settings.items():
                print(f"   - {key}: {value}")
            return False

        merged_settings = existing_settings | required_settings
        merged_settings["python.analysis.exclude"] = _merge_string_list(
            existing_settings.get("python.analysis.exclude"),
            DEFAULT_PYTHON_ANALYSIS_EXCLUDE,
        )

        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(merged_settings, f, indent=4)

        print(f"✅ VS Code settings updated: {settings_file}")
        print("   - Existing settings preserved")
        print("   - Python interpreter set to .venv")
    else:
        # Create new settings file
        try:
            required_settings["python.analysis.exclude"] = DEFAULT_PYTHON_ANALYSIS_EXCLUDE

            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(required_settings, f, indent=4)

            print(f"✅ VS Code settings created: {settings_file}")
            print("   - Python interpreter configured for .venv")
        except (ImportError, IOError) as e:
            print(f"❌ Failed to create VS Code settings: {e}")
            return False

    return True


def validate_kernel_setup():
    """
    Validate that the standardized kernel is properly registered and accessible.

    Returns:
        bool: True if kernel is properly configured, False otherwise
    """

    try:
        # Check if ipykernel is available
        result = subprocess.run([sys.executable, '-m', 'jupyter', 'kernelspec', 'list'],
                              check=True, capture_output=True, text=True)

        # Check if our kernel is in the list
        if KERNEL_NAME in result.stdout:
            print(f"✅ {KERNEL_NAME} kernel found in kernelspec list")
            return True

        print(f"❌ {KERNEL_NAME} kernel not found in kernelspec list")
        return False

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to check kernel list: {e}")
        return False
    except FileNotFoundError:
        print("❌ Jupyter not found - please ensure Jupyter is installed")
        return False


def force_kernel_consistency():
    """
    Ensure the standardized kernel exists and trusted paths are set without
    overwriting user customization. This function is intentionally minimal to
    stay idempotent.
    """

    print("🔧 Enforcing kernel consistency...")

    if not validate_kernel_setup():
        print("⚠️ Kernel not found, attempting to register...")
        if not install_jupyter_kernel():
            print("❌ Failed to register kernel - manual intervention required")
            return False

    project_root = get_project_root()
    vscode_dir = project_root / '.vscode'
    settings_file = vscode_dir / 'settings.json'
    vscode_dir.mkdir(exist_ok=True)

    venv_python = _venv_python_path()

    try:
        existing_settings = {}
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    existing_settings = json.load(f)
            except json.JSONDecodeError:
                print("⚠️ Existing settings.json has issues; leaving it untouched.")
                return False

        merged_settings = existing_settings.copy()
        merged_settings["jupyter.kernels.trusted"] = _merge_string_list(
            existing_settings.get("jupyter.kernels.trusted"),
            [venv_python],
        )
        merged_settings["python.analysis.exclude"] = _merge_string_list(
            existing_settings.get("python.analysis.exclude"),
            DEFAULT_PYTHON_ANALYSIS_EXCLUDE,
        )

        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(merged_settings, f, indent=4)

        print("✅ Kernel trust refreshed without overriding user settings")
        return True

    except Exception as e:
        print(f"❌ Failed to update VS Code settings: {e}")
        return False


def setup_complete_environment():
    """
    Complete setup: check Azure prerequisites, generate .env file, register kernel, and configure VS Code.

    This provides a one-command setup that makes the local environment
    as easy to use as the dev container.
    """

    print("🚀 Setting up complete APIM Samples environment...\n")

    # Step 0: Check Azure prerequisites
    print("0. Checking Azure prerequisites...")
    azure_cli_ok = check_azure_cli_installed()
    bicep_ok = check_bicep_cli_installed()
    providers_ok = check_azure_providers_registered()

    if not (azure_cli_ok and bicep_ok and providers_ok):
        print("\n⚠️  Some Azure prerequisites are missing. Please address the issues above and re-run this script.")
        return

    # Step 1: Generate .env file
    print("\n1. Generating .env file for Python path configuration...")
    generate_env_file()

    # Step 2: Register Jupyter kernel
    print("2. Registering standardized Jupyter kernel...")
    kernel_success = install_jupyter_kernel()

    # Step 3: Configure VS Code settings with minimal, merged defaults
    print("\n3. Configuring VS Code workspace settings...")
    vscode_success = create_vscode_settings()

    # Step 4: Enforce kernel consistency
    print("\n4. Enforcing kernel consistency for future reliability...")
    consistency_success = force_kernel_consistency()

    # Summary
    print("\n" + "="*50)
    print("📋 Setup Summary:")
    print("   ✅ Azure CLI and Bicep: Available")
    print("   ✅ Azure resource providers: Registered")
    print("   ✅ Python path configuration: Complete")
    print(f"   {'✅' if kernel_success else '❌'} Jupyter kernel registration: {'Complete' if kernel_success else 'Failed'}")
    print(f"   {'✅' if vscode_success else '❌'} VS Code settings: {'Complete' if vscode_success else 'Failed'}")
    print(f"   {'✅' if consistency_success else '❌'} Kernel trust refresh: {'Complete' if consistency_success else 'Failed'}")

    if kernel_success and vscode_success and consistency_success:
        print("\n🎉 Setup complete! Your local environment now matches the dev container experience.")
        print(f"   • Notebooks can use the '{KERNEL_DISPLAY_NAME}' kernel")
        print("   • Python modules from shared/ directory are available")
        print("   • VS Code is configured for optimal workflow")
        print("   • User customizations are preserved across reruns")
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
    print("  python setup/local_setup.py [OPTION]")

    print("\nOPTIONS:")
    print("  (no options)        Show this help information")
    print("  --run-only          Only modify current session's PYTHONPATH (basic setup)")
    print("  --generate-env      Generate .env file for VS Code and terminal integration")
    print("  --setup-kernel      Register the standardized Jupyter kernel")
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
    print(f"    • Registers a standardized Jupyter kernel named '{KERNEL_NAME}'")
    print(f"    • Display name will be '{KERNEL_DISPLAY_NAME}'")
    print("    • Ensures consistent notebook experience")
    print("    • Installs ipykernel if not already available")

    print("\n  --setup-vscode:")
    print("    • Creates/updates .vscode/settings.json")
    print("    • Configures Python interpreter, linting, testing, and trusted kernels")
    print("    • Preserves existing VS Code settings by merging changes")

    print("\n  --complete-setup:")
    print("    • Performs all of the above steps")
    print("    • Recommended for new development environments")
    print("    • Recreates dev container experience locally")

    print("\nEXAMPLES:")
    print("  # Show this help information:")
    print("  python setup/local_setup.py")
    print("\n  # Perform complete setup (recommended for new users):")
    print("  python setup/local_setup.py --complete-setup")
    print("\n  # Only generate the .env file:")
    print("  python setup/local_setup.py --generate-env")

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
