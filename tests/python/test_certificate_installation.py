"""
Unit tests for certificate installation functionality in certificate_installer.py
"""

import pytest
import tempfile
import platform
from unittest.mock import patch, Mock, MagicMock, mock_open
from pathlib import Path

import sys
sys.path.insert(0, '../../shared/python')

from certificate_installer import (
    install_certificate_for_infrastructure, 
    list_installed_apim_certificates,
    remove_all_apim_certificates,
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
        
    @patch('certificate_installer._get_key_vault_name')
    @patch('certificate_installer._download_certificate_from_key_vault')
    @patch('certificate_installer._install_certificate_to_trust_store')
    @patch('utils.get_infra_rg_name')
    def test_successful_installation_ag_apim_vnet(self, mock_rg_name, mock_install, mock_download, mock_kv_name):
        """Test successful certificate installation for AG_APIM_VNET"""
        # Setup mocks
        mock_rg_name.return_value = "apim-infra-ag-apim-vnet-1"
        mock_kv_name.return_value = "kv-test123"
        mock_download.return_value = b"CERT_DATA"
        mock_install.return_value = True
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is True
        mock_kv_name.assert_called_once_with("apim-infra-ag-apim-vnet-1")
        mock_download.assert_called_once_with("kv-test123", "ag-cert", "apim-infra-ag-apim-vnet-1")
        mock_install.assert_called_once_with(b"CERT_DATA", "apim-samples-apim-infra-ag-apim-vnet-1", INFRASTRUCTURE.AG_APIM_VNET, 1)
    
    @patch('certificate_installer._get_key_vault_name')
    @patch('certificate_installer._download_certificate_from_key_vault')
    @patch('certificate_installer._install_certificate_to_trust_store')
    @patch('utils.get_infra_rg_name')
    def test_successful_installation_ag_apim_pe(self, mock_rg_name, mock_install, mock_download, mock_kv_name):
        """Test successful certificate installation for AG_APIM_PE"""
        # Setup mocks
        mock_rg_name.return_value = "apim-infra-ag-apim-pe-20"
        mock_kv_name.return_value = "kv-test456"
        mock_download.return_value = b"CERT_DATA"
        mock_install.return_value = True
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_PE, 20)
        
        assert result is True
        mock_kv_name.assert_called_once_with("apim-infra-ag-apim-pe-20")
        mock_download.assert_called_once_with("kv-test456", "ag-cert", "apim-infra-ag-apim-pe-20")
        mock_install.assert_called_once_with(b"CERT_DATA", "apim-samples-apim-infra-ag-apim-pe-20", INFRASTRUCTURE.AG_APIM_PE, 20)

    @patch('certificate_installer._get_key_vault_name')
    def test_no_key_vault_found(self, mock_kv_name):
        """Test failure when no Key Vault is found"""
        mock_kv_name.return_value = None
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg")
        
        assert result is False

    @patch('certificate_installer._get_key_vault_name')
    @patch('certificate_installer._download_certificate_from_key_vault')
    def test_certificate_download_failure(self, mock_download, mock_kv_name):
        """Test failure when certificate download fails"""
        mock_kv_name.return_value = "kv-test123"
        mock_download.return_value = None
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg")
        
        assert result is False

    @patch('certificate_installer._get_key_vault_name')
    @patch('certificate_installer._download_certificate_from_key_vault')
    @patch('certificate_installer._install_certificate_to_trust_store')
    def test_certificate_install_failure(self, mock_install, mock_download, mock_kv_name):
        """Test failure when certificate installation fails"""
        mock_kv_name.return_value = "kv-test123"
        mock_download.return_value = b"CERT_DATA"
        mock_install.return_value = False
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg")
        
        assert result is False

    @patch('certificate_installer._get_key_vault_name')
    def test_exception_handling(self, mock_kv_name):
        """Test exception handling"""
        mock_kv_name.side_effect = Exception("Test exception")
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg")
        
        assert result is False


# ------------------------------
#    HELPER FUNCTION TESTS  
# ------------------------------






# ------------------------------
#    PLATFORM-SPECIFIC TESTS
# ------------------------------

class TestInstallCertificateToTrustStore:
    """Test platform-specific certificate installation routing"""
    
    @patch('platform.system')
    @patch('certificate_installer._install_certificate_windows')
    def test_windows_installation(self, mock_install_windows, mock_platform):
        """Test Windows certificate installation routing"""
        mock_platform.return_value = "Windows"
        mock_install_windows.return_value = True
        
        result = _install_certificate_to_trust_store(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is True
        mock_install_windows.assert_called_once_with(b"CERT_DATA", "test-cert")

    @patch('platform.system')
    @patch('certificate_installer._install_certificate_macos')
    def test_macos_installation(self, mock_install_macos, mock_platform):
        """Test macOS certificate installation routing"""
        mock_platform.return_value = "Darwin"
        mock_install_macos.return_value = True
        
        result = _install_certificate_to_trust_store(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is True
        mock_install_macos.assert_called_once_with(b"CERT_DATA", "test-cert")

    @patch('platform.system')
    @patch('certificate_installer._install_certificate_linux')
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
    @patch('certificate_installer._install_certificate_windows_powershell')
    @patch('os.unlink')
    def test_successful_powershell_installation(self, mock_unlink, mock_ps_install, mock_temp):
        """Test successful PowerShell installation"""
        mock_temp.return_value.__enter__.return_value.name = "C:\\temp\\test.pfx"
        mock_ps_install.return_value = True
        
        result = _install_certificate_windows(b"CERT_DATA", "test-cert")
        
        assert result is True
        mock_ps_install.assert_called_once_with("C:\\temp\\test.pfx")

    @patch('tempfile.NamedTemporaryFile')
    @patch('certificate_installer._install_certificate_windows_powershell')
    @patch('certificate_installer._install_certificate_windows_certutil')
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
    @patch('certificate_installer._install_certificate_windows_powershell')
    @patch('certificate_installer._install_certificate_windows_certutil')
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
    @patch('certificate_installer._list_certificates_windows')
    def test_list_certificates_windows(self, mock_list_windows, mock_platform):
        """Test listing certificates on Windows"""
        mock_platform.return_value = "Windows"
        
        list_installed_apim_certificates()
        
        mock_list_windows.assert_called_once()

    @patch('platform.system')
    @patch('certificate_installer._remove_certificates_macos')
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

    @patch('certificate_installer._get_key_vault_name')
    def test_early_exit_on_missing_keyvault(self, mock_kv_name):
        """Test early exit when Key Vault is not found"""
        mock_kv_name.return_value = None
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg")
        
        assert result is False
        # Should exit early without attempting download or installation


# ------------------------------
#    ERROR HANDLING TESTS
# ------------------------------

class TestErrorHandling:
    """Test comprehensive error handling"""
    
    @patch('certificate_installer._get_key_vault_name')
    def test_handles_unexpected_exceptions(self, mock_kv_name):
        """Test handling of unexpected exceptions"""
        mock_kv_name.side_effect = RuntimeError("Unexpected error")
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg")
        
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
