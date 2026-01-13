#!/usr/bin/env python3
"""
Unified verification script for APIM Samples environments (local and devcontainer).

This script verifies that the environment is configured correctly and always
emits a suggested fix for any failed check. Checks include:
- Virtual environment is active
- Required packages are installed
- Shared modules can be imported
- Azure CLI is installed
- Azure Bicep is installed
- Azure login context is present
- Required Azure resource providers are registered
- Jupyter kernel is registered
- VS Code settings are configured

Run after setup (local or devcontainer) to ensure everything is working.
"""

import sys
import subprocess
import os
import io
import json
import shutil
from pathlib import Path

# Configure UTF-8 encoding for console output
if sys.stdout.encoding != 'utf-8':  # pragma: no cover
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def print_status(message, success=True, fix="", skipped=False):
    """Print status message with optional fix guidance."""
    if skipped:
        color = "33"  # Yellow for skipped
        icon = "⚠️ "
        status_text = "SKIPPED"
    else:
        color = "32" if success else "31"  # Green for success, red for failure
        icon = "✅" if success else "❌"
        status_text = "PASS" if success else "FAIL"
    print(f"{icon} \033[1;{color}m{status_text}: {message}\033[0m")
    if fix:
        if skipped:
            print(f"   ℹ️  Note: {fix}")
        elif not success:
            print(f"   👉 Fix: {fix}")


def print_section(title):
    """Print section header."""
    print(f"\n📋 {title}")
    print("-" * (len(title) + 3))


def check_virtual_environment():
    """Check if we're running in the correct virtual environment."""
    venv_path = Path.cwd() / ".venv"
    if not venv_path.exists():
        return False, "Create it: uv venv && uv sync (then activate: source .venv/bin/activate or .venv\\Scripts\\activate on Windows)"

    current_python = Path(sys.executable)
    expected_venv_python = venv_path / ("Scripts" if os.name == 'nt' else "bin") / "python"

    if not str(current_python).startswith(str(venv_path)):
        return False, f"Activate it: source {expected_venv_python.parent}/activate"

    return True, ""


def check_required_packages():
    """Check if required packages are installed."""
    required_packages = [
        ("requests", "requests"),
        ("ipykernel", "ipykernel"),
        ("jupyter", "jupyter"),
        ("python-dotenv", "dotenv"),
    ]

    missing = []
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(package_name)

    if missing:
        return False, f"Install missing packages: uv sync (missing: {', '.join(missing)})"

    return True, ""


def check_shared_modules():
    """Check if shared modules can be imported."""
    try:
        project_root = Path(__file__).parent.parent
        shared_python_path = project_root / "shared" / "python"

        if str(shared_python_path) not in sys.path:  # pragma: no cover
            sys.path.insert(0, str(shared_python_path))

        __import__("utils")
        __import__("apimtypes")
        __import__("authfactory")
        __import__("apimrequests")

        return True, ""
    except ImportError as exc:
        return False, f"Regenerate env and PYTHONPATH: python setup/local_setup.py --generate-env (detail: {exc})"


def check_jupyter_kernel():
    """Check if the Jupyter kernel is registered."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "jupyter", "kernelspec", "list"],
            capture_output=True,
            text=True,
            check=True,
        )

        if "python-venv" in result.stdout or "Python (.venv)" in result.stdout:
            return True, ""

        if "python3" in result.stdout:
            return True, ""

        return False, "Register kernel: python -m ipykernel install --user --name=python-venv --display-name='Python (.venv)'"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False, "Install Jupyter tooling: uv add --dev jupyter && uv sync"


def check_vscode_settings():
    """Check if VS Code settings are configured."""
    vscode_settings = Path.cwd() / ".vscode" / "settings.json"

    if not vscode_settings.exists():
        return False, "Run: python setup/local_setup.py --complete-setup (missing .vscode/settings.json)"

    try:
        with open(vscode_settings, "r", encoding="utf-8") as handle:
            content = handle.read()

        checks = [
            ("python.defaultInterpreterPath", ".venv"),
            ("python.envFile", ".env"),
            ("python.terminal.activateEnvironment", "true"),
            ("python.testing.pytestEnabled", "true"),
        ]

        missing = []
        for setting_key, expected_value in checks:
            if setting_key not in content or expected_value not in content:
                missing.append(setting_key)

        if missing:
            return False, f"Regenerate VS Code settings: python setup/local_setup.py --complete-setup (missing: {', '.join(missing)})"

        return True, ""
    except Exception as exc:  # pylint: disable=broad-except
        return False, f"Could not read VS Code settings: {exc}"


def check_env_file():
    """Check if .env file exists and has correct configuration."""
    env_file = Path.cwd() / ".env"

    if not env_file.exists():
        return False, "Generate it: python setup/local_setup.py --generate-env"

    try:
        with open(env_file, "r", encoding="utf-8") as handle:
            content = handle.read()

        if "PYTHONPATH=" in content and "PROJECT_ROOT=" in content:
            return True, ""

        return False, "Regenerate .env: python setup/local_setup.py --generate-env"
    except Exception as exc:  # pylint: disable=broad-except
        return False, f"Could not read .env file: {exc}"


def _az_path():
    return shutil.which("az") or shutil.which("az.cmd") or shutil.which("az.bat")


def check_azure_cli():
    """Check if Azure CLI is installed."""
    az_path = _az_path()
    if not az_path:
        return False, "Install Azure CLI: https://learn.microsoft.com/cli/azure/install-azure-cli"

    try:
        result = subprocess.run([az_path, "--version"], capture_output=True, text=True, check=True)
        version_line = (result.stdout.splitlines() or ["unknown version"])[0].strip()
        version = version_line.split()[-1] if version_line else "unknown"
        return True, f"Azure CLI {version} detected"
    except subprocess.CalledProcessError:
        return False, "Reinstall Azure CLI: https://learn.microsoft.com/cli/azure/install-azure-cli"


def check_bicep_cli():
    """Check if Azure Bicep CLI is installed."""
    az_path = _az_path()
    if not az_path:
        return False, "Install Azure CLI first: https://learn.microsoft.com/cli/azure/install-azure-cli"

    try:
        result = subprocess.run([az_path, "bicep", "version"], capture_output=True, text=True, check=True)
        version_line = (result.stdout.splitlines() or ["unknown version"])[0].strip()
        version = "unknown"
        if "version" in version_line.lower():
            parts = version_line.split()
            for index, part in enumerate(parts):
                if part.lower() == "version" and index + 1 < len(parts):
                    version = parts[index + 1]
                    break
        return True, f"Bicep {version} detected"
    except subprocess.CalledProcessError:
        return False, "Install Bicep: az bicep install"


def check_azure_login():
    """Check if the user is logged in to Azure."""
    az_path = _az_path()
    if not az_path:
        return False, "Install Azure CLI: https://learn.microsoft.com/cli/azure/install-azure-cli"

    try:
        result = subprocess.run(
            [az_path, "account", "show", "--output", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
        account = json.loads(result.stdout)
        name = account.get("name", "unknown")
        tenant = account.get("tenantId", "unknown")
        subscription = account.get("id", "unknown")
        return True, f"Logged in (sub: {name}, id: {subscription}, tenant: {tenant})"
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return False, "Log in and set subscription: az login --tenant <tenant-id> && az account set --subscription <subscription-id>"


def check_azure_providers():
    """Check if required Azure resource providers are registered in the current subscription."""
    az_path = _az_path()
    if not az_path:
        return False, "Install Azure CLI: https://learn.microsoft.com/cli/azure/install-azure-cli"

    required_providers = [
        "Microsoft.ApiManagement",
        "Microsoft.App",
        "Microsoft.Authorization",
        "Microsoft.CognitiveServices",
        "Microsoft.ContainerRegistry",
        "Microsoft.KeyVault",
        "Microsoft.Maps",
        "Microsoft.ManagedIdentity",
        "Microsoft.Network",
        "Microsoft.OperationalInsights",
        "Microsoft.Resources",
        "Microsoft.Storage",
    ]

    try:
        result = subprocess.run(
            [az_path, "provider", "list", "--query", "[].namespace", "-o", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
        registered_providers = sorted(set(json.loads(result.stdout)))

        missing_providers = [p for p in required_providers if p not in registered_providers]

        if not missing_providers:
            return True, ""

        fix_cmds = ", ".join([f"az provider register -n {provider}" for provider in missing_providers])
        return False, f"Register missing providers: {fix_cmds}"
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return False, "Log in then retry: az login --tenant <tenant> && az account set --subscription <subscription>"


def main():
    """Run all verification checks."""
    print("🔍 APIM Samples Local Environment Verification")
    print("=" * 50)

    checks = [
        ("Virtual Environment", check_virtual_environment),
        ("Required Packages", check_required_packages),
        ("Shared Modules", check_shared_modules),
        ("Environment File", check_env_file),
        ("Azure CLI", check_azure_cli),
        ("Azure Bicep", check_bicep_cli),
        ("Azure Login", check_azure_login),
        ("Azure Providers", check_azure_providers),
        ("Jupyter Kernel", check_jupyter_kernel),
        ("VS Code Settings", check_vscode_settings),
    ]

    results = []
    azure_login_passed = False

    for check_name, check_function in checks:
        # Skip Azure Providers check if Azure Login failed
        if check_name == "Azure Providers" and not azure_login_passed:
            print_section(check_name)
            print_status(
                check_name,
                success=True,
                fix="A successful Azure login must be detected prior to running this check",
                skipped=True
            )
            results.append((check_name, None, "Skipped because Azure login is required"))
            continue

        print_section(check_name)
        passed, fix = check_function()
        print_status(check_name, passed, fix)
        results.append((check_name, passed, fix))

        # Track if Azure Login passed for conditional Azure Providers check
        if check_name == "Azure Login":
            azure_login_passed = passed

    print_section("Summary")
    passed_count = sum(1 for _, ok, _ in results if ok is True)
    skipped_count = sum(1 for _, ok, _ in results if ok is None)
    total = len(results)
    max_name_length = max(len(check_name) for check_name, _, _ in results)

    for check_name, ok, fix in results:
        padded_name = check_name.ljust(max_name_length + 1)
        if ok is None:
            # Skipped check
            print_status(padded_name, success=True, fix=fix, skipped=True)
        else:
            print_status(padded_name, ok, fix)

    active_checks = total - skipped_count
    print(f"\n📊 Overall: {passed_count}/{active_checks} checks passed", end="")
    if skipped_count > 0:
        print(f" ({skipped_count} skipped)", end="")
    print()

    if passed_count == active_checks:
        print("\n🎉 All checks passed! Your environment is ready for APIM Samples.")
        print("💡 You can now open any notebook and it should work seamlessly.")
    else:
        print("\n⚠️  Some checks failed. Run the suggested fixes above, or rerun:")
        print("   python setup/local_setup.py --complete-setup")
        print("   Then restart VS Code and run this verification again.")

    return passed_count == active_checks


if __name__ == '__main__':  # pragma: no cover
    sys.exit(0 if main() else 1)
