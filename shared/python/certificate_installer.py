"""
Certificate installation and management module for APIM Samples.

This module provides functionality for:
- Installing certificates for Application Gateway infrastructures
- Managing APIM Samples Root CA
- Platform-specific certificate installation (Windows, macOS, Linux)
- Certificate validation and verification
"""

import base64
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from apimtypes import INFRASTRUCTURE
from utils import (
    get_infra_rg_name, 
    print_error, 
    print_info, 
    print_message, 
    print_ok, 
    print_success, 
    print_warning,
    run
)


# ------------------------------
#    CERTIFICATE INSTALLATION
# ------------------------------

def install_certificate_for_infrastructure(infrastructure_type: INFRASTRUCTURE, index: int, resource_group_name: Optional[str] = None) -> bool:
    """
    Install the certificate for a specific Application Gateway infrastructure using CA-based approach.
    
    Args:
        infrastructure_type (INFRASTRUCTURE): The infrastructure type (AG_APIM_VNET or AG_APIM_PE)
        index (int): The infrastructure index number
        resource_group_name (Optional[str]): Optional resource group name. If not provided, will be generated from infrastructure type and index.
        
    Returns:
        bool: True if certificate was installed successfully, False otherwise
    """
    
    if infrastructure_type not in [INFRASTRUCTURE.AG_APIM_VNET, INFRASTRUCTURE.AG_APIM_PE]:
        print_error(f"Certificate installation is only supported for Application Gateway infrastructures. Got: {infrastructure_type}")
        return False
        
    # Generate resource group name if not provided
    if not resource_group_name:
        resource_group_name = get_infra_rg_name(infrastructure_type, index)
    
    print_info(f"Installing certificate for {infrastructure_type.value} infrastructure (index {index})")
    print_info(f"Resource Group: {resource_group_name}")
    print_info("")
    
    # Step 1: Ensure Root CA exists and is installed
    print_info("🔍 Step 1: Checking Root CA...")
    if not ensure_apim_samples_root_ca():
        print_warning("❌ Root CA setup failed or was cancelled.")
        print_info("   Falling back to individual certificate installation...")
        return _install_individual_certificate(infrastructure_type, index, resource_group_name)
    
    print_ok("✅ Root CA is ready!")
    
    # Step 2: Check if infrastructure exists and upload Root CA to its Key Vault
    print_info("🔍 Step 2: Uploading Root CA to infrastructure Key Vault...")
    try:
        # Find the Key Vault in the resource group
        key_vault_name = _get_key_vault_name(resource_group_name)
        if not key_vault_name:
            print_error("No Key Vault found in the resource group")
            print_info("   This usually means the infrastructure hasn't been deployed yet.")
            print_info("   Please deploy the infrastructure first, then run this certificate installation.")
            return False
        
        # Upload Root CA to Key Vault for future deployments
        upload_success = upload_root_ca_to_key_vault(key_vault_name)
        if upload_success:
            print_ok("✅ Root CA uploaded to Key Vault!")
            print_info("   Future infrastructure deployments will use CA-signed certificates")
        else:
            print_warning("⚠️  Failed to upload Root CA to Key Vault")
            print_info("   Existing certificate will still work, but future deployments may use self-signed certificates")
        
        print_info("")
        
        # Step 3: Download and install certificate (with user prompting for self-signed)
        print_info("🔍 Step 3: Downloading and installing infrastructure certificate...")
        return _download_and_install_certificate(resource_group_name, infrastructure_type, index, "ag-cert", user_prompt=True)
            
    except Exception as e:
        print_error(f"Certificate installation failed: {str(e)}")
        return False


def list_installed_apim_certificates() -> None:
    """
    List all APIM-Samples certificates installed in the local trust store.
    """
    
    print_info("Listing installed APIM-Samples certificates...")
    
    try:
        system = platform.system().lower()
        
        if system == "windows":
            _list_certificates_windows()
        elif system == "darwin":  # macOS
            _list_certificates_macos()
        elif system == "linux":
            _list_certificates_linux()
        else:
            print_warning(f"Certificate listing not implemented for {system}")
            
    except Exception as e:
        print_error(f"Failed to list certificates: {str(e)}")


def remove_all_apim_certificates() -> bool:
    """
    Remove all APIM-Samples certificates from the local trust store.
    
    Returns:
        bool: True if all certificates were removed successfully, False otherwise
    """
    
    print_warning("Removing all APIM-Samples certificates from local trust store...")
    
    try:
        system = platform.system().lower()
        
        if system == "windows":
            return _remove_certificates_windows()
        elif system == "darwin":  # macOS
            return _remove_certificates_macos()
        elif system == "linux":
            return _remove_certificates_linux()
        else:
            print_warning(f"Certificate removal not implemented for {system}")
            return False
            
    except Exception as e:
        print_error(f"Failed to remove certificates: {str(e)}")
        return False


# ------------------------------
#    PRIVATE CERTIFICATE HELPERS
# ------------------------------

def _download_and_install_certificate(resource_group_name: str, infrastructure_type: INFRASTRUCTURE, index: int, cert_name: str = "ag-cert", user_prompt: bool = False) -> bool:
    """
    Common helper function to download and install a certificate from Key Vault.
    
    Args:
        resource_group_name (str): The resource group name
        infrastructure_type (INFRASTRUCTURE): The infrastructure type
        index (int): The infrastructure index
        cert_name (str): Name of the certificate in Key Vault (default: "ag-cert")
        user_prompt (bool): Whether to prompt user before installing self-signed certificates
        
    Returns:
        bool: True if certificate was downloaded and installed successfully, False otherwise
    """
    
    try:
        # Find and download certificate
        key_vault_name = _get_key_vault_name(resource_group_name)
        if not key_vault_name:
            return False
        
        cert_data = _download_certificate_from_key_vault(key_vault_name, cert_name, resource_group_name)
        if not cert_data:
            return False
        
        # If user prompt is requested, check if certificate is CA-signed
        if user_prompt:
            is_ca_signed = _is_certificate_ca_signed(cert_data)
            if is_ca_signed:
                print_ok("✅ Certificate is already CA-signed by APIM Samples Root CA!")
                print_info("   No additional installation needed - your browser should trust it automatically.")
                return True
            else:
                print_warning("⚠️  Certificate appears to be self-signed (created with old template)")
                print_info("   This means your infrastructure was deployed before the CA-based certificates were implemented.")
                print_info("   The certificate will still work, but you may see SSL warnings.")
                print_info("")
                print_info("💡 To get CA-signed certificates:")
                print_info("   1. The Root CA has been uploaded to your Key Vault")
                print_info("   2. Redeploy your infrastructure to get a CA-signed certificate")
                print_info("   3. Or continue with the current self-signed certificate")
                print_info("")
                
                try:
                    user_choice = input("🤔 Do you want to install the self-signed certificate now? (y/N): ").strip().lower()
                    if user_choice not in ['y', 'yes']:
                        print_info("❌ Certificate installation cancelled.")
                        return False
                    print_info("   Installing self-signed certificate...")
                except (KeyboardInterrupt, EOFError):
                    print_info("\n❌ Certificate installation cancelled by user.")
                    return False
        
        # Install certificate
        cert_display_name = "apim-samples" if not resource_group_name else f"apim-samples-{resource_group_name}"
        success = _install_certificate_to_trust_store(cert_data, cert_display_name, infrastructure_type, index)
        
        if success:
            print_ok("✅ Certificate installation completed!", blank_above=True)
            print_info("   Your browser should now trust the infrastructure endpoint")
            print_info("   You may need to restart your browser for changes to take effect")
        else:
            print_error("❌ Certificate installation failed", blank_above=True)
            print_info("")
            print_info("🔧 Troubleshooting:")
            print_info("   • Ensure OpenSSL is installed on your system")
            print_info("   • Check that you have permission to modify trust store") 
            print_info("   • Try running the cell again")
            print_info("   • Check the detailed output above for specific error messages")
    
        return success
        
    except Exception as e:
        print_error(f"Certificate download and installation failed: {str(e)}")
        return False


def _get_key_vault_name(resource_group_name: str) -> Optional[str]:
    """Get the Key Vault name from the resource group."""
    
    print_message("Looking for Key Vault in resource group...")
    
    output = run(f'az keyvault list -g {resource_group_name} --query "[0].name" -o tsv')
    
    if output.success and output.text.strip():
        key_vault_name = output.text.strip()
        print_ok(f"Found Key Vault: {key_vault_name}")
        return key_vault_name
    
    return None


def _download_certificate_from_key_vault(key_vault_name: str, cert_name: str, resource_group_name: str) -> Optional[bytes]:
    """Download certificate data from Key Vault."""
    
    print_message(f"Downloading certificate '{cert_name}' from Key Vault...")
    
    # Download the certificate as PFX
    with tempfile.NamedTemporaryFile(suffix='.pfx', delete=False) as temp_file:
        temp_path = temp_file.name
        
    try:
        output = run(f'az keyvault secret download --vault-name {key_vault_name} --name {cert_name} --file {temp_path} --overwrite')
        
        if output.success and os.path.exists(temp_path):
            with open(temp_path, 'rb') as f:
                cert_data = f.read()
            print_ok(f"Certificate downloaded ({len(cert_data)} bytes)")
            return cert_data
        else:
            # Check if this is a permission error
            if "Forbidden" in output.text and "getSecret" in output.text:
                print_warning("❌ Permission denied accessing Key Vault")
                print_info("   Attempting to grant current user access...")
                
                if _grant_current_user_keyvault_access(key_vault_name, resource_group_name):
                    print_info("   ⏳ Waiting for permission propagation (30 seconds)...")
                    time.sleep(30)
                    
                    # Retry the download
                    retry_output = run(f'az keyvault secret download --vault-name {key_vault_name} --name {cert_name} --file {temp_path} --overwrite')
                    if retry_output.success and os.path.exists(temp_path):
                        with open(temp_path, 'rb') as f:
                            cert_data = f.read()
                        print_ok(f"Certificate downloaded after permission grant ({len(cert_data)} bytes)")
                        return cert_data
                    else:
                        print_error("Failed to download certificate even after granting access")
                        return None
                else:
                    print_error("Failed to grant Key Vault access and download certificate")
                    return None
            else:
                print_error(f"Failed to download certificate: {output.text}")
            return None
            
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def _grant_current_user_keyvault_access(key_vault_name: str, resource_group_name: str) -> bool:
    """Grant the current Azure CLI user access to Key Vault secrets."""
    
    try:
        # Get current user's object ID
        user_output = run('az ad signed-in-user show --query id -o tsv')
        if not user_output.success:
            return False
            
        user_object_id = user_output.text.strip()
        
        # Get subscription ID
        sub_output = run('az account show --query id -o tsv')
        if not sub_output.success:
            return False
            
        subscription_id = sub_output.text.strip()
        
        # Construct the Key Vault scope
        scope = f"/subscriptions/{subscription_id}/resourcegroups/{resource_group_name}/providers/Microsoft.KeyVault/vaults/{key_vault_name}"
        
        # Grant Key Vault Secrets User role
        role_output = run(f'az role assignment create --assignee "{user_object_id}" --role "Key Vault Secrets User" --scope "{scope}"')
        
        if role_output.success:
            print_ok("Successfully granted Key Vault Secrets User access to current user")
            return True
        else:
            print_warning("Failed to grant automatic access (you may need Owner/Contributor permissions)")
            return False
            
    except Exception as e:
        print_warning(f"Failed to grant automatic access: {str(e)}")
        return False


def _install_certificate_to_trust_store(cert_data: bytes, display_name: str, infrastructure_type: INFRASTRUCTURE, index: int) -> bool:
    """Install certificate to the platform-specific trust store."""
    
    system = platform.system().lower()
    
    print_message(f"Installing certificate to {system} trust store...")
    print_message(f"Certificate name: {display_name}")
    
    if system == "windows":
        return _install_certificate_windows(cert_data, display_name)
    elif system == "darwin":  # macOS
        return _install_certificate_macos(cert_data, display_name)
    elif system == "linux":
        return _install_certificate_linux(cert_data, display_name, infrastructure_type, index)
    else:
        print_error(f"Certificate installation not supported on {system}")
        return False


def _install_certificate_windows(cert_data: bytes, display_name: str) -> bool:
    """Install certificate on Windows using multiple methods."""
    
    with tempfile.NamedTemporaryFile(suffix='.pfx', delete=False) as temp_file:
        temp_file.write(cert_data)
        temp_path = temp_file.name
        
    try:
        # Method 1: Try PowerShell with current user store (no admin required)
        powershell_success = _install_certificate_windows_powershell(temp_path)
        if powershell_success:
            return True
            
        # Method 2: Try certutil with user store (no admin required)
        certutil_success = _install_certificate_windows_certutil(temp_path)
        if certutil_success:
            return True
            
        # Method 3: Provide manual instructions
        print_warning("Automatic installation failed. Manual installation required.")
        print_info("To install the certificate manually:")
        print_info(f"1. Navigate to: {temp_path}")
        print_info("2. Double-click the certificate file")
        print_info("3. Click 'Install Certificate...'")
        print_info("4. Select 'Current User' (no admin required)")
        print_info("5. Choose 'Place all certificates in the following store'")
        print_info("6. Click 'Browse' and select 'Trusted Root Certification Authorities'")
        print_info("7. Click 'OK' and 'Finish'")
        print_info(f"8. Password when prompted: TempPassword123!")
        
        # Don't delete the temp file so user can install manually
        print_info(f"Certificate file saved at: {temp_path}")
        return False
        
    except Exception as e:
        print_error(f"Certificate installation error: {str(e)}")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return False


def _install_certificate_windows_powershell(temp_path: str) -> bool:
    """Try installing certificate using PowerShell (current user store)."""
    
    try:
        # PowerShell command to import to current user's trusted root store
        ps_script = f'''
        try {{
            $cert = Import-PfxCertificate -FilePath "{temp_path}" -CertStoreLocation "Cert:\\CurrentUser\\Root" -Password (ConvertTo-SecureString "TempPassword123!" -AsPlainText -Force)
            if ($cert) {{
                Write-Host "SUCCESS: Certificate imported with thumbprint: $($cert.Thumbprint)"
                exit 0
            }} else {{
                Write-Host "FAILED: Certificate import returned null"
                exit 1
            }}
        }} catch {{
            Write-Host "ERROR: $($_.Exception.Message)"
            exit 1
        }}
        '''
        
        result = subprocess.run(['powershell', '-Command', ps_script], capture_output=True, text=True)
        
        if result.returncode == 0 and "SUCCESS:" in result.stdout:
            print_ok("Certificate installed to Windows trusted root store (PowerShell)")
            return True
        else:
            print_message(f"PowerShell method failed: {result.stdout} {result.stderr}")
            return False
            
    except Exception as e:
        print_message(f"PowerShell method error: {str(e)}")
        return False


def _install_certificate_windows_certutil(temp_path: str) -> bool:
    """Try installing certificate using certutil (current user store)."""
    
    try:
        # Use certutil to install to current user store
        cmd = f'certutil -f -user -p "TempPassword123!" -importpfx Root "{temp_path}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print_ok("Certificate installed to Windows trusted root store (certutil)")
            return True
        else:
            print_message(f"Certutil method failed: {result.stdout} {result.stderr}")
            return False
            
    except Exception as e:
        print_message(f"Certutil method error: {str(e)}")
        return False


def _install_certificate_macos(cert_data: bytes, display_name: str) -> bool:
    """Install certificate on macOS using security command."""
    
    with tempfile.NamedTemporaryFile(suffix='.pfx', delete=False) as temp_file:
        temp_file.write(cert_data)
        temp_path = temp_file.name
        
    try:
        # Extract certificate from PFX first
        cert_path = temp_path.replace('.pfx', '.crt')
        
        # Extract certificate using openssl
        extract_cmd = f'openssl pkcs12 -in "{temp_path}" -clcerts -nokeys -out "{cert_path}" -passin pass:TempPassword123!'
        extract_result = subprocess.run(extract_cmd, shell=True, capture_output=True, text=True)
        
        if extract_result.returncode != 0:
            print_error(f"Failed to extract certificate: {extract_result.stderr}")
            return False
            
        # Install the certificate to system keychain
        install_cmd = f'sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "{cert_path}"'
        install_result = subprocess.run(install_cmd, shell=True, capture_output=True, text=True)
        
        if install_result.returncode == 0:
            print_ok("Certificate installed to macOS system keychain")
            return True
        else:
            print_error(f"Failed to install certificate: {install_result.stderr}")
            return False
            
    finally:
        for path in [temp_path, temp_path.replace('.pfx', '.crt')]:
            if os.path.exists(path):
                os.unlink(path)


def _install_certificate_linux(cert_data: bytes, display_name: str, infrastructure_type: INFRASTRUCTURE, index: int) -> bool:
    """Install certificate on Linux."""
    
    # Linux certificate installation varies by distribution
    # For now, we'll save to a common location and provide instructions
    
    cert_dir = Path.home() / ".local" / "share" / "ca-certificates" / "apim-samples"
    cert_dir.mkdir(parents=True, exist_ok=True)
    
    cert_filename = f"{infrastructure_type.value}-{index}.crt"
    cert_path = cert_dir / cert_filename
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.pfx', delete=False) as temp_file:
            temp_file.write(cert_data)
            temp_path = temp_file.name
            
        # Extract certificate from PFX
        extract_cmd = f'openssl pkcs12 -in "{temp_path}" -clcerts -nokeys -out "{cert_path}" -passin pass:TempPassword123!'
        extract_result = subprocess.run(extract_cmd, shell=True, capture_output=True, text=True)
        
        if extract_result.returncode == 0:
            print_ok(f"Certificate saved to {cert_path}")
            print_info("To trust this certificate system-wide on Linux:")
            print_info(f"  sudo cp '{cert_path}' /usr/local/share/ca-certificates/")
            print_info("  sudo update-ca-certificates")
            return True
        else:
            print_error(f"Failed to extract certificate: {extract_result.stderr}")
            return False
            
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def _list_certificates_windows() -> None:
    """List APIM certificates on Windows."""
    
    cmd = f'certutil -store Root | findstr /C:"apim-samples"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0 and result.stdout.strip():
        print_ok("Found APIM-Samples certificates:")
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                print_info(f"  {line.strip()}")
    else:
        print_info("No APIM-Samples certificates found")


def _list_certificates_macos() -> None:
    """List APIM certificates on macOS."""
    
    cmd = f'security find-certificate -c "apim-samples" /Library/Keychains/System.keychain'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0 and result.stdout.strip():
        print_ok("Found APIM-Samples certificates in system keychain")
        # Parse and display certificate info
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if line.strip():
                print_info(f"  {line.strip()}")
    else:
        print_info("No APIM-Samples certificates found")


def _list_certificates_linux() -> None:
    """List APIM certificates on Linux."""
    
    cert_dir = Path.home() / ".local" / "share" / "ca-certificates" / "apim-samples"
    
    if cert_dir.exists():
        cert_files = list(cert_dir.glob("*.crt"))
        if cert_files:
            print_ok("Found APIM-Samples certificates:")
            for cert_file in cert_files:
                print_info(f"  {cert_file}")
        else:
            print_info("No APIM-Samples certificates found")
    else:
        print_info("No APIM-Samples certificates directory found")


def _remove_certificates_windows() -> bool:
    """Remove APIM certificates from Windows."""
    
    # This is complex on Windows as we need to identify specific certificates
    # For now, provide instructions
    print_warning("To remove APIM-Samples certificates on Windows:")
    print_info("1. Run 'certmgr.msc' as administrator")
    print_info("2. Navigate to Trusted Root Certification Authorities > Certificates")
    print_info(f"3. Look for certificates containing 'apim-samples'")
    print_info("4. Right-click and delete each one")
    return True


def _remove_certificates_macos() -> bool:
    """Remove APIM certificates from macOS."""
    
    cmd = f'sudo security delete-certificate -c "apim-samples" /Library/Keychains/System.keychain'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print_ok("APIM-Samples certificates removed from macOS system keychain")
        return True
    else:
        print_warning("No APIM-Samples certificates found to remove (or removal failed)")
        return False


def _remove_certificates_linux() -> bool:
    """Remove APIM certificates from Linux."""
    
    cert_dir = Path.home() / ".local" / "share" / "ca-certificates" / "apim-samples"
    
    if cert_dir.exists():
        shutil.rmtree(cert_dir)
        print_ok("APIM-Samples certificates directory removed")
        return True
    else:
        print_info("No APIM-Samples certificates directory found")
        return True


# ------------------------------
#    ROOT CA MANAGEMENT
# ------------------------------

def check_openssl_availability() -> bool:
    """
    Check if OpenSSL is available on the system.
    
    Returns:
        bool: True if OpenSSL is available, False otherwise
    """
    
    try:
        result = subprocess.run(['openssl', 'version'], capture_output=True, text=True)
        if result.returncode == 0:
            return True
        else:
            return False
    except FileNotFoundError:
        return False


def ensure_apim_samples_root_ca() -> bool:
    """
    Ensure the APIM Samples Root CA exists and is installed in the local trust store.
    
    This function:
    1. Checks if the root CA already exists locally and in the trust store
    2. If not, prompts the user for permission to create and install it
    3. Creates the root CA certificate and private key
    4. Installs the root CA in the local trust store
    
    Returns:
        bool: True if the root CA is available and trusted, False otherwise
    """
    
    print_info("🔍 Checking for APIM Samples Root CA...")
    
    # Check if root CA already exists and is trusted
    if _is_root_ca_installed():
        print_ok("✅ APIM Samples Root CA is already installed and trusted!")
        return True
    
    # Check if OpenSSL is available
    if not check_openssl_availability():
        print_error("❌ OpenSSL is not available on this system")
        print_info("   Please install OpenSSL to use CA-signed certificates")
        print_info("   Windows: Download from https://slproweb.com/products/Win32OpenSSL.html")
        print_info("   macOS: brew install openssl")
        print_info("   Linux: sudo apt-get install openssl (or equivalent for your distribution)")
        print_info("")
        print_warning("❌ Root CA creation cancelled. Certificate installation will use individual certificates.")
        return False
    
    # Prompt user for permission to create and install root CA
    print_warning("⚠️  APIM Samples Root CA not found")
    print_info("")
    print_info("📋 What is a Root CA and why do we need it?")
    print_info("   • A Root Certificate Authority (CA) is a trusted certificate that can sign other certificates")
    print_info("   • Instead of trusting each individual infrastructure certificate separately,")
    print_info("     you only need to trust our Root CA once")
    print_info("   • All infrastructure certificates will be signed by this Root CA")
    print_info("   • This provides better security and easier management")
    print_info("")
    print_info("🔒 Security Notes:")
    print_info("   • The Root CA will only be used for APIM Samples development/testing")
    print_info("   • It will be stored locally on your machine only")
    print_info("   • It will NOT be shared or uploaded anywhere")
    print_info("   • You can remove it anytime using the provided functions")
    print_info("")
    print_info("📝 What will happen:")
    print_info("   1. Create a Root CA certificate and private key")
    print_info("   2. Install the Root CA in your system's trust store")
    print_info("   3. Future infrastructure certificates will be signed by this Root CA")
    print_info("")
    
    try:
        user_consent = input("🤔 Do you want to create and install the APIM Samples Root CA? (Y/n): ").strip().lower()
        if user_consent in ['', 'y', 'yes']:
            print_info("✅ User granted permission to create Root CA")
        else:
            print_warning("❌ Root CA creation cancelled. Certificate installation will use individual certificates.")
            return False
    except (KeyboardInterrupt, EOFError):
        print_warning("❌ Root CA creation cancelled. Certificate installation will use individual certificates.")
        return False
    
    # Create and install root CA
    if _create_root_ca() and _install_root_ca():
        print_success("🎉 APIM Samples Root CA created and installed successfully!")
        print_info("   All future infrastructure certificates will be automatically trusted")
        return True
    else:
        print_error("❌ Failed to create or install Root CA")
        return False


def get_root_ca_paths() -> tuple[Path, Path, Path]:
    """
    Get the standard paths for Root CA files.
    
    Returns:
        tuple: (ca_directory, certificate_path, private_key_path)
    """
    
    ca_dir = Path.home() / ".apim-samples" / "root-ca"
    cert_path = ca_dir / "apim-samples-root-ca.crt"
    key_path = ca_dir / "apim-samples-root-ca.key"
    
    return ca_dir, cert_path, key_path


def _is_root_ca_installed() -> bool:
    """Check if the APIM Samples Root CA is installed in the trust store."""
    
    # First check if the CA files exist locally
    ca_dir, cert_path, key_path = get_root_ca_paths()
    if not cert_path.exists() or not key_path.exists():
        return False
    
    # Then check if it's installed in the trust store
    system = platform.system().lower()
    
    try:
        if system == "windows":
            return _is_root_ca_installed_windows()
        elif system == "darwin":  # macOS
            return _is_root_ca_installed_macos()
        elif system == "linux":
            return _is_root_ca_installed_linux()
        else:
            print_warning(f"Root CA installation check not implemented for {system}")
            return False
    except Exception as e:
        print_warning(f"Error checking Root CA installation: {str(e)}")
        return False


def _create_root_ca() -> bool:
    """Create the APIM Samples Root CA certificate and private key."""
    
    ca_dir, cert_path, key_path = get_root_ca_paths()
    
    try:
        # Create directory
        ca_dir.mkdir(parents=True, exist_ok=True)
        
        # Create root CA private key (4096 bits for better security)
        print_info("📝 Creating Root CA private key...")
        key_result = subprocess.run([
            'openssl', 'genrsa', '-out', str(key_path), '4096'
        ], capture_output=True, text=True)
        
        if key_result.returncode != 0:
            print_error(f"Failed to create private key: {key_result.stderr}")
            return False
        
        # Create root CA certificate (valid for 10 years)
        print_info("📝 Creating Root CA certificate...")
        cert_result = subprocess.run([
            'openssl', 'req', '-new', '-x509',
            '-key', str(key_path),
            '-out', str(cert_path),
            '-days', '3650',
            '-subj', '/C=US/ST=Development/L=Local/O=APIM Samples/OU=Development/CN=apim-samples'
        ], capture_output=True, text=True)
        
        if cert_result.returncode != 0:
            print_error(f"Failed to create certificate: {cert_result.stderr}")
            return False
        
        print_ok("✅ Root CA certificate and private key created successfully!")
        print_info(f"   Certificate: {cert_path}")
        print_info(f"   Private Key: {key_path}")
        
        return True
        
    except Exception as e:
        print_error(f"Failed to create Root CA: {str(e)}")
        return False


def _install_root_ca() -> bool:
    """Install the APIM Samples Root CA in the platform-specific trust store."""
    
    ca_dir, cert_path, key_path = get_root_ca_paths()
    
    if not cert_path.exists():
        print_error("Root CA certificate not found")
        return False
    
    system = platform.system().lower()
    print_info(f"📝 Installing Root CA in {system} trust store...")
    
    try:
        if system == "windows":
            return _install_root_ca_windows(cert_path)
        elif system == "darwin":  # macOS
            return _install_root_ca_macos(cert_path)
        elif system == "linux":
            return _install_root_ca_linux(cert_path)
        else:
            print_error(f"Root CA installation not supported on {system}")
            return False
    except Exception as e:
        print_error(f"Failed to install Root CA: {str(e)}")
        return False


def create_ca_signed_certificate(common_name: str, output_pfx_path: str, pfx_password: str = "TempPassword123!") -> bool:
    """
    Create a certificate signed by the APIM Samples Root CA.
    
    Args:
        common_name (str): The common name (CN) for the certificate
        output_pfx_path (str): Path where to save the PFX file
        pfx_password (str): Password for the PFX file
        
    Returns:
        bool: True if certificate was created successfully, False otherwise
    """
    
    ca_dir, ca_cert_path, ca_key_path = get_root_ca_paths()
    
    if not ca_cert_path.exists() or not ca_key_path.exists():
        print_error("Root CA not found. Please run ensure_apim_samples_root_ca() first.")
        return False
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            # Generate private key for the certificate
            cert_key_path = temp_dir_path / "cert.key"
            key_result = subprocess.run([
                'openssl', 'genrsa', '-out', str(cert_key_path), '2048'
            ], capture_output=True, text=True)
            
            if key_result.returncode != 0:
                print_error(f"Failed to create certificate private key: {key_result.stderr}")
                return False
            
            # Create certificate signing request (CSR)
            csr_path = temp_dir_path / "cert.csr"
            csr_result = subprocess.run([
                'openssl', 'req', '-new',
                '-key', str(cert_key_path),
                '-out', str(csr_path),
                '-subj', f'/C=US/ST=Development/L=Local/O=APIM Samples/OU=Development/CN={common_name}'
            ], capture_output=True, text=True)
            
            if csr_result.returncode != 0:
                print_error(f"Failed to create CSR: {csr_result.stderr}")
                return False
            
            # Sign the certificate with the Root CA
            cert_path = temp_dir_path / "cert.crt"
            sign_result = subprocess.run([
                'openssl', 'x509', '-req',
                '-in', str(csr_path),
                '-CA', str(ca_cert_path),
                '-CAkey', str(ca_key_path),
                '-CAcreateserial',
                '-out', str(cert_path),
                '-days', '365',
                '-extensions', 'v3_req'
            ], capture_output=True, text=True)
            
            if sign_result.returncode != 0:
                print_error(f"Failed to sign certificate: {sign_result.stderr}")
                return False
            
            # Create PFX file
            pfx_result = subprocess.run([
                'openssl', 'pkcs12', '-export',
                '-out', output_pfx_path,
                '-inkey', str(cert_key_path),
                '-in', str(cert_path),
                '-certfile', str(ca_cert_path),
                '-passout', f'pass:{pfx_password}'
            ], capture_output=True, text=True)
            
            if pfx_result.returncode != 0:
                print_error(f"Failed to create PFX: {pfx_result.stderr}")
                return False
            
            print_ok(f"✅ CA-signed certificate created: {output_pfx_path}")
            return True
            
    except Exception as e:
        print_error(f"Failed to create CA-signed certificate: {str(e)}")
        return False


# ------------------------------
#    PLATFORM-SPECIFIC ROOT CA HELPERS
# ------------------------------

def _is_root_ca_installed_windows() -> bool:
    """Check if Root CA is installed on Windows."""
    
    try:
        cmd = 'certutil -store Root | findstr /C:"apim-samples"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0 and "apim-samples" in result.stdout
    except Exception:
        return False


def _is_root_ca_installed_macos() -> bool:
    """Check if Root CA is installed on macOS."""
    
    try:
        cmd = ['security', 'find-certificate', '-c', 'apim-samples', '/Library/Keychains/System.keychain']
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


def _is_root_ca_installed_linux() -> bool:
    """Check if Root CA is installed on Linux."""
    
    # This is simplified - in reality, Linux CA installation varies by distribution
    # For now, we'll just check if the CA file exists in our local directory
    ca_dir, cert_path, key_path = get_root_ca_paths()
    return cert_path.exists() and key_path.exists()


def _install_root_ca_windows(cert_path: Path) -> bool:
    """Install Root CA on Windows."""
    
    try:
        # Try PowerShell method first (works with current user store)
        ps_script = f'''
        try {{
            $cert = Import-Certificate -FilePath "{cert_path}" -CertStoreLocation "Cert:\\CurrentUser\\Root"
            if ($cert) {{
                Write-Host "SUCCESS: Root CA imported with thumbprint: $($cert.Thumbprint)"
                exit 0
            }} else {{
                Write-Host "FAILED: Root CA import returned null"
                exit 1
            }}
        }} catch {{
            Write-Host "ERROR: $($_.Exception.Message)"
            exit 1
        }}
        '''
        
        result = subprocess.run(['powershell', '-Command', ps_script], capture_output=True, text=True)
        
        if result.returncode == 0 and "SUCCESS:" in result.stdout:
            print_ok("✅ Root CA installed to Windows trusted root store")
            return True
        else:
            print_error(f"Failed to install Root CA: {result.stdout} {result.stderr}")
            return False
            
    except Exception as e:
        print_error(f"Failed to install Root CA on Windows: {str(e)}")
        return False


def _install_root_ca_macos(cert_path: Path) -> bool:
    """Install Root CA on macOS."""
    
    try:
        cmd = ['sudo', 'security', 'add-trusted-cert', '-d', '-r', 'trustRoot', 
               '-k', '/Library/Keychains/System.keychain', str(cert_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print_ok("✅ Root CA installed to macOS system keychain")
            return True
        else:
            print_error(f"Failed to install Root CA: {result.stderr}")
            return False
            
    except Exception as e:
        print_error(f"Failed to install Root CA on macOS: {str(e)}")
        return False


def _install_root_ca_linux(cert_path: Path) -> bool:
    """Install Root CA on Linux."""
    
    try:
        # Copy to system CA directory
        system_ca_path = Path("/usr/local/share/ca-certificates/apim-samples-root-ca.crt")
        
        # Try to copy with sudo
        copy_result = subprocess.run(['sudo', 'cp', str(cert_path), str(system_ca_path)], 
                                   capture_output=True, text=True)
        
        if copy_result.returncode == 0:
            # Update CA certificates
            update_result = subprocess.run(['sudo', 'update-ca-certificates'], 
                                         capture_output=True, text=True)
            
            if update_result.returncode == 0:
                print_ok("✅ Root CA installed to Linux system CA store")
                return True
            else:
                print_error(f"Failed to update CA certificates: {update_result.stderr}")
                return False
        else:
            print_error(f"Failed to copy Root CA to system directory: {copy_result.stderr}")
            return False
            
    except Exception as e:
        print_error(f"Failed to install Root CA on Linux: {str(e)}")
        return False


def upload_root_ca_to_key_vault(key_vault_name: str) -> bool:
    """
    Upload the Root CA certificate to a Key Vault for infrastructure deployments.
    
    Args:
        key_vault_name (str): Name of the Key Vault to upload to
        
    Returns:
        bool: True if upload was successful, False otherwise
    """
    
    ca_dir, cert_path, key_path = get_root_ca_paths()
    
    if not cert_path.exists():
        print_error("Root CA certificate not found")
        return False
    
    try:
        print_info(f"Uploading Root CA to Key Vault '{key_vault_name}'...")
        
        # Upload certificate
        cert_result = run(f'az keyvault certificate import --vault-name {key_vault_name} --name "apim-samples-root-ca" --file "{cert_path}"')
        
        if cert_result.success:
            print_ok("✅ Root CA certificate uploaded to Key Vault")
            return True
        else:
            print_error(f"Failed to upload Root CA: {cert_result.text}")
            return False
            
    except Exception as e:
        print_error(f"Failed to upload Root CA to Key Vault: {str(e)}")
        return False


def _is_certificate_ca_signed(cert_data: bytes) -> bool:
    """
    Check if a certificate is signed by the APIM Samples Root CA.
    
    Args:
        cert_data (bytes): The certificate data (PFX format)
        
    Returns:
        bool: True if certificate is signed by APIM Samples Root CA, False otherwise
    """
    
    try:
        # Extract certificate from PFX
        with tempfile.NamedTemporaryFile(suffix='.pfx', delete=False) as temp_pfx:
            temp_pfx.write(cert_data)
            temp_pfx_path = temp_pfx.name
        
        with tempfile.NamedTemporaryFile(suffix='.crt', delete=False) as temp_cert:
            temp_cert_path = temp_cert.name
        
        # Extract certificate using openssl
        extract_result = subprocess.run([
            'openssl', 'pkcs12', '-in', temp_pfx_path, '-clcerts', '-nokeys', 
            '-out', temp_cert_path, '-passin', 'pass:TempPassword123!'
        ], capture_output=True, text=True)
        
        if extract_result.returncode != 0:
            print_warning("Could not extract certificate for verification")
            return False
        
        # Check the issuer
        issuer_result = subprocess.run([
            'openssl', 'x509', '-in', temp_cert_path, '-noout', '-issuer'
        ], capture_output=True, text=True)
        
        if issuer_result.returncode == 0:
            issuer = issuer_result.stdout.strip()
            # Check if issued by our Root CA
            return "apim-samples" in issuer.lower()
        
        return False
        
    except Exception as e:
        print_warning(f"Could not verify certificate signature: {str(e)}")
        return False
    finally:
        # Clean up temp files
        for path in [temp_pfx_path, temp_cert_path]:
            if 'path' in locals() and os.path.exists(path):
                os.unlink(path)


def _install_individual_certificate(infrastructure_type: INFRASTRUCTURE, index: int, resource_group_name: str) -> bool:
    """
    Fallback method to install individual infrastructure certificate.
    
    Args:
        infrastructure_type (INFRASTRUCTURE): The infrastructure type
        index (int): The infrastructure index
        resource_group_name (str): The resource group name
        
    Returns:
        bool: True if certificate was installed successfully, False otherwise
    """
    
    print_info("🔐 Starting certificate installation process...")
    return _download_and_install_certificate(resource_group_name, infrastructure_type, index, "ag-cert", user_prompt=False)
