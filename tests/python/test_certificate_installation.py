"""
Unit tests for certificate installation functionality in certificate.py
"""

import pytest
import tempfile
import platform
from unittest.mock import patch, Mock, MagicMock, mock_open
from pathlib import Path

import sys
sys.path.insert(0, '../../shared/python')

from certificate import (
    install_certificate_for_infrastructure, 
    list_installed_apim_certificates,
    remove_all_apim_certificates,
    ensure_apim_samples_root_ca_auto,
    ensure_apim_samples_root_ca,
    get_root_ca_paths,
    upload_root_ca_for_infrastructure,
    upload_root_ca_to_key_vault,
    _get_key_vault_name,
    _download_certificate_from_key_vault,
    _grant_current_user_keyvault_access,
    _install_certificate_to_trust_store,
    _install_certificate_windows,
    _install_certificate_macos,
    _install_certificate_linux,
    _list_certificates_windows,
    _list_certificates_macos,
    _list_certificates_linux,
    _remove_certificates_windows,
    _remove_certificates_macos,
    _remove_certificates_linux,
    _is_root_ca_installed,
    _is_root_ca_installed_windows,
    _is_root_ca_installed_macos,
    _is_root_ca_installed_linux,
    _create_root_ca,
    _install_root_ca,
    _install_root_ca_windows,
    _install_root_ca_macos,
    _install_root_ca_linux,
    _is_certificate_ca_signed,
    INFRASTRUCTURE
)
from utils import get_infra_rg_name, run


# ------------------------------
#    FIXTURE SETUP
# ------------------------------

@pytest.fixture
def mock_cert_data():
    """Mock certificate data"""
    return b"MOCK_CERTIFICATE_DATA"


@pytest.fixture  
def mock_resource_group():
    """Mock resource group name"""
    return "apim-infra-ag-apim-vnet-1"


@pytest.fixture
def mock_key_vault_name():
    """Mock Key Vault name"""
    return "kv-mockkeyvault123"


# ------------------------------
#    MAIN FUNCTION TESTS
# ------------------------------

class TestInstallCertificateForInfrastructure:
    """Test the main certificate installation function"""
    
    def test_unsupported_infrastructure_type(self):
        """Test that unsupported infrastructure types are rejected"""
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.SIMPLE_APIM, 1)
        assert result is False
        
    @patch('certificate._get_key_vault_name')
    @patch('certificate._download_certificate_from_key_vault')
    @patch('certificate._install_certificate_to_trust_store')
    @patch('certificate.ensure_apim_samples_root_ca')
    @patch('certificate.upload_root_ca_to_key_vault')
    @patch('certificate._is_certificate_ca_signed')
    @patch('utils.get_infra_rg_name')
    def test_successful_installation_ag_apim_vnet(self, mock_rg_name, mock_ca_signed, mock_upload_ca, mock_ensure_ca, mock_install, mock_download, mock_kv_name):
        """Test successful certificate installation for AG_APIM_VNET"""
        # Setup mocks
        mock_rg_name.return_value = "apim-infra-ag-apim-vnet-1"
        mock_kv_name.return_value = "kv-test123"
        mock_ensure_ca.return_value = True
        mock_upload_ca.return_value = True
        mock_download.return_value = b"CERT_DATA"
        mock_ca_signed.return_value = True
        mock_install.return_value = True
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, interactive=False)
        
        assert result is True
        # _get_key_vault_name is called twice: once for upload and once for download
        assert mock_kv_name.call_count == 2
        mock_download.assert_called_once_with("kv-test123", "ag-cert", "apim-infra-ag-apim-vnet-1")
    
    @patch('certificate._get_key_vault_name')
    @patch('certificate._download_certificate_from_key_vault')
    @patch('certificate._install_certificate_to_trust_store')
    @patch('certificate.ensure_apim_samples_root_ca')
    @patch('certificate.upload_root_ca_to_key_vault')
    @patch('certificate._is_certificate_ca_signed')
    @patch('utils.get_infra_rg_name')
    def test_successful_installation_ag_apim_pe(self, mock_rg_name, mock_ca_signed, mock_upload_ca, mock_ensure_ca, mock_install, mock_download, mock_kv_name):
        """Test successful certificate installation for AG_APIM_PE"""
        # Setup mocks
        mock_rg_name.return_value = "apim-infra-ag-apim-pe-20"
        mock_kv_name.return_value = "kv-test456"
        mock_ensure_ca.return_value = True
        mock_upload_ca.return_value = True
        mock_download.return_value = b"CERT_DATA"
        mock_ca_signed.return_value = True
        mock_install.return_value = True
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_PE, 20, interactive=False)
        
        assert result is True
        # _get_key_vault_name is called twice: once for upload and once for download  
        assert mock_kv_name.call_count == 2
        mock_download.assert_called_once_with("kv-test456", "ag-cert", "apim-infra-ag-apim-pe-20")

    @patch('certificate._get_key_vault_name')
    def test_no_key_vault_found(self, mock_kv_name):
        """Test failure when no Key Vault is found"""
        mock_kv_name.return_value = None
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg", interactive=False)
        
        assert result is False

    @patch('certificate._get_key_vault_name')
    @patch('certificate._download_certificate_from_key_vault')
    def test_certificate_download_failure(self, mock_download, mock_kv_name):
        """Test failure when certificate download fails"""
        mock_kv_name.return_value = "kv-test123"
        mock_download.return_value = None
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg", interactive=False)
        
        assert result is False

    @patch('certificate._get_key_vault_name')
    @patch('certificate._download_certificate_from_key_vault')
    @patch('certificate._install_certificate_to_trust_store')
    def test_certificate_install_failure(self, mock_install, mock_download, mock_kv_name):
        """Test failure when certificate installation fails"""
        mock_kv_name.return_value = "kv-test123"
        mock_download.return_value = b"CERT_DATA"
        mock_install.return_value = False
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg", interactive=False)
        
        assert result is False

    @patch('certificate._get_key_vault_name')
    def test_exception_handling(self, mock_kv_name):
        """Test exception handling"""
        mock_kv_name.side_effect = Exception("Test exception")
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg", interactive=False)
        
        assert result is False


# ------------------------------
#    HELPER FUNCTION TESTS  
# ------------------------------

class TestRootCAFunctionality:
    """Test Root CA management functions"""

    @patch('certificate.get_root_ca_paths')
    def test_get_root_ca_paths(self, mock_get_paths):
        """Test get_root_ca_paths returns correct paths"""
        from pathlib import Path
        mock_ca_dir = Path.home() / ".apim-samples" / "root-ca"
        mock_cert_path = mock_ca_dir / "apim-samples-root-ca.crt"
        mock_key_path = mock_ca_dir / "apim-samples-root-ca.key"
        
        mock_get_paths.return_value = (mock_ca_dir, mock_cert_path, mock_key_path)
        
        ca_dir, cert_path, key_path = get_root_ca_paths()
        
        assert ca_dir == mock_ca_dir
        assert cert_path == mock_cert_path
        assert key_path == mock_key_path

    @patch('platform.system')
    @patch('certificate._is_root_ca_installed_windows')
    def test_is_root_ca_installed_windows(self, mock_windows_check, mock_platform):
        """Test Root CA installation check on Windows"""
        mock_platform.return_value = "Windows"
        mock_windows_check.return_value = True
        
        result = _is_root_ca_installed()
        
        assert result is True
        mock_windows_check.assert_called_once()

    @patch('platform.system')
    @patch('certificate._is_root_ca_installed_macos')
    def test_is_root_ca_installed_macos(self, mock_macos_check, mock_platform):
        """Test Root CA installation check on macOS"""
        mock_platform.return_value = "Darwin"
        mock_macos_check.return_value = False
        
        result = _is_root_ca_installed()
        
        assert result is False
        mock_macos_check.assert_called_once()

    @patch('platform.system')
    @patch('certificate._is_root_ca_installed_linux')
    def test_is_root_ca_installed_linux(self, mock_linux_check, mock_platform):
        """Test Root CA installation check on Linux"""
        mock_platform.return_value = "Linux"
        mock_linux_check.return_value = True
        
        result = _is_root_ca_installed()
        
        assert result is True
        mock_linux_check.assert_called_once()

    @patch('subprocess.run')
    def test_is_root_ca_installed_windows_with_friendly_name(self, mock_subprocess):
        """Test Windows Root CA detection with friendly name"""
        # Mock certutil output containing the friendly name
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
Cert Hash(sha1): 1234567890abcdef
  FriendlyName: APIM Samples Root Certificate
  Subject: CN=APIM Samples Root Certificate, OU=Development, O=APIM Samples
        """
        mock_subprocess.return_value = mock_result
        
        result = _is_root_ca_installed_windows()
        
        assert result is True
        mock_subprocess.assert_called_once()

    @patch('subprocess.run')
    def test_is_root_ca_installed_windows_with_legacy_name(self, mock_subprocess):
        """Test Windows Root CA detection with legacy subject name"""
        # Mock certutil output containing the legacy name
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
Cert Hash(sha1): 1234567890abcdef
  Subject: CN=apim-samples, OU=Development, O=APIM Samples
        """
        mock_subprocess.return_value = mock_result
        
        result = _is_root_ca_installed_windows()
        
        assert result is True

    @patch('subprocess.run')
    def test_is_root_ca_installed_windows_not_found(self, mock_subprocess):
        """Test Windows Root CA detection when not found"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "No matching certificates found"
        mock_subprocess.return_value = mock_result
        
        result = _is_root_ca_installed_windows()
        
        assert result is False

    @patch('certificate.get_root_ca_paths')
    @patch('certificate._is_root_ca_installed')
    @patch('certificate.check_openssl_availability')
    @patch('certificate._create_root_ca')
    @patch('certificate._install_root_ca')
    def test_ensure_apim_samples_root_ca_auto_existing_files(self, mock_install, mock_create, mock_openssl, mock_installed, mock_paths):
        """Test automatic Root CA setup with existing local files"""
        from pathlib import Path
        from unittest.mock import MagicMock
        
        # Mock existing certificate files
        mock_cert_path = MagicMock()
        mock_cert_path.exists.return_value = True
        mock_key_path = MagicMock() 
        mock_key_path.exists.return_value = True
        mock_paths.return_value = (Path("/mock"), mock_cert_path, mock_key_path)
        
        mock_installed.return_value = True
        
        result = ensure_apim_samples_root_ca_auto()
        
        assert result is True
        mock_create.assert_not_called()  # Should not create new files
        mock_install.assert_not_called()  # Should not install again

    @patch('certificate.get_root_ca_paths')
    @patch('certificate._is_root_ca_installed')
    @patch('certificate.check_openssl_availability')
    @patch('certificate._create_root_ca')
    @patch('certificate._install_root_ca')
    def test_ensure_apim_samples_root_ca_auto_missing_files_but_installed(self, mock_install, mock_create, mock_openssl, mock_installed, mock_paths):
        """Test automatic Root CA setup with missing files but installed in store"""
        from pathlib import Path
        from unittest.mock import MagicMock
        
        # Mock missing certificate files
        mock_cert_path = MagicMock()
        mock_cert_path.exists.return_value = False
        mock_key_path = MagicMock() 
        mock_key_path.exists.return_value = False
        mock_paths.return_value = (Path("/mock"), mock_cert_path, mock_key_path)
        
        mock_installed.return_value = True
        mock_openssl.return_value = True
        mock_create.return_value = True
        mock_install.return_value = True
        
        result = ensure_apim_samples_root_ca_auto()
        
        assert result is True
        mock_create.assert_called_once()  # Should recreate files
        mock_install.assert_called_once()  # Should install new certificate

    @patch('certificate.get_root_ca_paths')
    @patch('certificate._is_root_ca_installed')
    @patch('certificate.check_openssl_availability')
    def test_ensure_apim_samples_root_ca_auto_no_openssl(self, mock_openssl, mock_installed, mock_paths):
        """Test automatic Root CA setup when OpenSSL is not available"""
        from pathlib import Path
        from unittest.mock import MagicMock
        
        # Mock missing certificate files
        mock_cert_path = MagicMock()
        mock_cert_path.exists.return_value = False
        mock_key_path = MagicMock() 
        mock_key_path.exists.return_value = False
        mock_paths.return_value = (Path("/mock"), mock_cert_path, mock_key_path)
        
        mock_installed.return_value = False
        mock_openssl.return_value = False
        
        result = ensure_apim_samples_root_ca_auto()
        
        assert result is False

    @patch('certificate._get_key_vault_name')
    @patch('certificate.upload_root_ca_to_key_vault')
    @patch('utils.get_infra_rg_name')
    def test_upload_root_ca_for_infrastructure_success(self, mock_rg_name, mock_upload, mock_kv_name):
        """Test successful Root CA upload to Key Vault"""
        mock_rg_name.return_value = "apim-infra-ag-apim-pe-20"
        mock_kv_name.return_value = "kv-test123"
        mock_upload.return_value = True
        
        result = upload_root_ca_for_infrastructure(INFRASTRUCTURE.AG_APIM_PE, 20)
        
        assert result is True
        mock_upload.assert_called_once_with("kv-test123")

    @patch('certificate._get_key_vault_name')
    @patch('utils.get_infra_rg_name')
    def test_upload_root_ca_for_infrastructure_no_key_vault(self, mock_rg_name, mock_kv_name):
        """Test Root CA upload when no Key Vault is found"""
        mock_rg_name.return_value = "apim-infra-ag-apim-pe-20"
        mock_kv_name.return_value = None
        
        result = upload_root_ca_for_infrastructure(INFRASTRUCTURE.AG_APIM_PE, 20)
        
        assert result is False

    @patch('certificate.get_root_ca_paths')
    @patch('tempfile.NamedTemporaryFile')
    @patch('subprocess.run')
    @patch('utils.run')
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_upload_root_ca_to_key_vault_success(self, mock_unlink, mock_exists, mock_run_cmd, mock_subprocess, mock_temp, mock_paths):
        """Test successful Root CA upload to specific Key Vault"""
        from pathlib import Path
        from unittest.mock import MagicMock
        
        # Mock certificate files exist
        mock_cert_path = MagicMock()
        mock_cert_path.exists.return_value = True
        mock_key_path = MagicMock() 
        mock_key_path.exists.return_value = True
        mock_paths.return_value = (Path("/mock"), mock_cert_path, mock_key_path)
        
        # Mock temporary file
        mock_temp_context = MagicMock()
        mock_temp_context.name = "/tmp/test.pfx"
        mock_temp.return_value.__enter__.return_value = mock_temp_context
        
        # Mock OpenSSL success
        mock_openssl_result = Mock()
        mock_openssl_result.returncode = 0
        mock_subprocess.return_value = mock_openssl_result
        
        # Mock Azure CLI success
        mock_az_result = Mock()
        mock_az_result.success = True
        mock_run_cmd.return_value = mock_az_result
        
        mock_exists.return_value = True
        
        result = upload_root_ca_to_key_vault("kv-test123")
        
        assert result is True
        mock_subprocess.assert_called_once()  # OpenSSL pkcs12 creation
        mock_run_cmd.assert_called_once()  # Azure CLI certificate import


# ------------------------------
#    PLATFORM-SPECIFIC TESTS
# ------------------------------

class TestInstallCertificateToTrustStore:
    """Test platform-specific certificate installation routing"""
    
    @patch('platform.system')
    @patch('certificate._install_certificate_windows')
    def test_windows_installation(self, mock_install_windows, mock_platform):
        """Test Windows certificate installation routing"""
        mock_platform.return_value = "Windows"
        mock_install_windows.return_value = True
        
        result = _install_certificate_to_trust_store(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is True
        mock_install_windows.assert_called_once_with(b"CERT_DATA", "test-cert")

    @patch('platform.system')
    @patch('certificate._install_certificate_macos')
    def test_macos_installation(self, mock_install_macos, mock_platform):
        """Test macOS certificate installation routing"""
        mock_platform.return_value = "Darwin"
        mock_install_macos.return_value = True
        
        result = _install_certificate_to_trust_store(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is True
        mock_install_macos.assert_called_once_with(b"CERT_DATA", "test-cert")

    @patch('platform.system')
    @patch('certificate._install_certificate_linux')
    def test_linux_installation(self, mock_install_linux, mock_platform):
        """Test Linux certificate installation routing"""
        mock_platform.return_value = "Linux"
        mock_install_linux.return_value = True
        
        result = _install_certificate_to_trust_store(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is True
        mock_install_linux.assert_called_once_with(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)

    @patch('platform.system')
    def test_unsupported_platform(self, mock_platform):
        """Test unsupported platform handling"""
        mock_platform.return_value = "FreeBSD"
        
        result = _install_certificate_to_trust_store(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is False


class TestWindowsCertificateInstallation:
    """Test Windows-specific certificate installation"""
    
    @patch('tempfile.NamedTemporaryFile')
    @patch('certificate._install_certificate_windows_powershell')
    @patch('os.unlink')
    def test_successful_powershell_installation(self, mock_unlink, mock_ps_install, mock_temp):
        """Test successful PowerShell installation"""
        mock_temp.return_value.__enter__.return_value.name = "C:\\temp\\test.pfx"
        mock_ps_install.return_value = True
        
        result = _install_certificate_windows(b"CERT_DATA", "test-cert")
        
        assert result is True
        mock_ps_install.assert_called_once_with("C:\\temp\\test.pfx")

    @patch('tempfile.NamedTemporaryFile')
    @patch('certificate._install_certificate_windows_powershell')
    @patch('certificate._install_certificate_windows_certutil')
    @patch('os.unlink')
    def test_fallback_to_certutil(self, mock_unlink, mock_certutil_install, mock_ps_install, mock_temp):
        """Test fallback to certutil when PowerShell fails"""
        mock_temp.return_value.__enter__.return_value.name = "C:\\temp\\test.pfx"
        mock_ps_install.return_value = False
        mock_certutil_install.return_value = True
        
        result = _install_certificate_windows(b"CERT_DATA", "test-cert")
        
        assert result is True
        mock_ps_install.assert_called_once()
        mock_certutil_install.assert_called_once_with("C:\\temp\\test.pfx")

    @patch('tempfile.NamedTemporaryFile')
    @patch('certificate._install_certificate_windows_powershell')
    @patch('certificate._install_certificate_windows_certutil')
    @patch('os.unlink')
    def test_manual_installation_instructions(self, mock_unlink, mock_certutil_install, mock_ps_install, mock_temp):
        """Test manual installation instructions when both methods fail"""
        mock_temp.return_value.__enter__.return_value.name = "C:\\temp\\test.pfx"
        mock_ps_install.return_value = False
        mock_certutil_install.return_value = False
        
        result = _install_certificate_windows(b"CERT_DATA", "test-cert")
        
        assert result is False
        mock_ps_install.assert_called_once()
        mock_certutil_install.assert_called_once()


class TestListAndRemoveCertificates:
    """Test certificate listing and removal functions"""
    
    @patch('platform.system')
    @patch('certificate._list_certificates_windows')
    def test_list_certificates_windows(self, mock_list_windows, mock_platform):
        """Test listing certificates on Windows"""
        mock_platform.return_value = "Windows"
        
        list_installed_apim_certificates()
        
        mock_list_windows.assert_called_once()

    @patch('platform.system')
    @patch('certificate._remove_certificates_macos')
    def test_remove_certificates_macos(self, mock_remove_macos, mock_platform):
        """Test removing certificates on macOS"""
        mock_platform.return_value = "Darwin"
        mock_remove_macos.return_value = True
        
        result = remove_all_apim_certificates()
        
        assert result is True
        mock_remove_macos.assert_called_once()

    @patch('platform.system')
    def test_unsupported_platform_list(self, mock_platform):
        """Test listing certificates on unsupported platform"""
        mock_platform.return_value = "FreeBSD"
        
        # Should not raise an exception
        list_installed_apim_certificates()

    @patch('platform.system')
    def test_unsupported_platform_remove(self, mock_platform):
        """Test removing certificates on unsupported platform"""
        mock_platform.return_value = "FreeBSD"
        
        result = remove_all_apim_certificates()
        
        assert result is False




# ------------------------------
#    PERFORMANCE TESTS
# ------------------------------

class TestPerformance:
    """Test performance characteristics"""
    
    def test_function_calls_minimal_external_dependencies(self):
        """Test that invalid input fails quickly without external calls"""
        # This should fail immediately without making Azure CLI calls
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.SIMPLE_APIM, 1)
        
        assert result is False
        # Test should complete very quickly (< 0.1 seconds typically)

    @patch('certificate._get_key_vault_name')
    def test_early_exit_on_missing_keyvault(self, mock_kv_name):
        """Test early exit when Key Vault is not found"""
        mock_kv_name.return_value = None
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg", interactive=False)
        
        assert result is False
        # Should exit early without attempting download or installation


# ------------------------------
#    ERROR HANDLING TESTS
# ------------------------------

class TestErrorHandling:
    """Test comprehensive error handling"""
    
    @patch('certificate._get_key_vault_name')
    def test_handles_unexpected_exceptions(self, mock_kv_name):
        """Test handling of unexpected exceptions"""
        mock_kv_name.side_effect = RuntimeError("Unexpected error")
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg", interactive=False)
        
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
