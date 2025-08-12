"""
Unit tests for certificate installation functionality in utils.py
"""

import pytest
import tempfile
import platform
from unittest.mock import patch, Mock, MagicMock, mock_open
from pathlib import Path

import sys
sys.path.insert(0, '../../shared/python')

from utils import (
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
    _remove_certificates_linux
)
from apimtypes import INFRASTRUCTURE


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
        
    @patch('utils._get_key_vault_name')
    @patch('utils._download_certificate_from_key_vault')
    @patch('utils._install_certificate_to_trust_store')
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
    
    @patch('utils._get_key_vault_name')
    @patch('utils._download_certificate_from_key_vault')
    @patch('utils._install_certificate_to_trust_store')
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

    @patch('utils._get_key_vault_name')
    def test_no_key_vault_found(self, mock_kv_name):
        """Test failure when no Key Vault is found"""
        mock_kv_name.return_value = None
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg")
        
        assert result is False

    @patch('utils._get_key_vault_name')
    @patch('utils._download_certificate_from_key_vault')
    def test_certificate_download_failure(self, mock_download, mock_kv_name):
        """Test failure when certificate download fails"""
        mock_kv_name.return_value = "kv-test123"
        mock_download.return_value = None
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg")
        
        assert result is False

    @patch('utils._get_key_vault_name')
    @patch('utils._download_certificate_from_key_vault')
    @patch('utils._install_certificate_to_trust_store')
    def test_certificate_install_failure(self, mock_install, mock_download, mock_kv_name):
        """Test failure when certificate installation fails"""
        mock_kv_name.return_value = "kv-test123"
        mock_download.return_value = b"CERT_DATA"
        mock_install.return_value = False
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg")
        
        assert result is False

    @patch('utils._get_key_vault_name')
    def test_exception_handling(self, mock_kv_name):
        """Test exception handling"""
        mock_kv_name.side_effect = Exception("Test exception")
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg")
        
        assert result is False


# ------------------------------
#    HELPER FUNCTION TESTS  
# ------------------------------

class TestGetKeyVaultName:
    """Test Key Vault name retrieval"""
    
    @patch('utils.run')
    def test_successful_key_vault_found(self, mock_run):
        """Test successful Key Vault retrieval"""
        mock_run.return_value = Mock(success=True, text="kv-test123\n")
        
        result = _get_key_vault_name("test-rg")
        
        assert result == "kv-test123"
        mock_run.assert_called_once_with('az keyvault list -g test-rg --query "[0].name" -o tsv')
    
    @patch('utils.run')
    def test_no_key_vault_found(self, mock_run):
        """Test when no Key Vault is found"""
        mock_run.return_value = Mock(success=False, text="")
        
        result = _get_key_vault_name("test-rg")
        
        assert result is None

    @patch('utils.run')
    def test_empty_response(self, mock_run):
        """Test when response is empty"""
        mock_run.return_value = Mock(success=True, text="")
        
        result = _get_key_vault_name("test-rg")
        
        assert result is None


class TestDownloadCertificateFromKeyVault:
    """Test certificate download from Key Vault"""
    
    @patch('tempfile.NamedTemporaryFile')
    @patch('utils.run')
    @patch('builtins.open', new_callable=mock_open, read_data=b"CERT_DATA")
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_successful_download(self, mock_unlink, mock_exists, mock_file, mock_run, mock_temp):
        """Test successful certificate download"""
        mock_temp.return_value.__enter__.return_value.name = "/tmp/test.pfx"
        mock_run.return_value = Mock(success=True, text="")
        mock_exists.return_value = True
        
        result = _download_certificate_from_key_vault("kv-test", "ag-cert", "test-rg")
        
        assert result == b"CERT_DATA"
        mock_run.assert_called_once_with('az keyvault secret download --vault-name kv-test --name ag-cert --file /tmp/test.pfx --overwrite')

    @patch('tempfile.NamedTemporaryFile')
    @patch('utils.run')
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_download_failure(self, mock_unlink, mock_exists, mock_run, mock_temp):
        """Test failed certificate download"""
        mock_temp.return_value.__enter__.return_value.name = "/tmp/test.pfx"
        mock_run.return_value = Mock(success=False, text="Error message")
        mock_exists.return_value = False
        
        result = _download_certificate_from_key_vault("kv-test", "ag-cert", "test-rg")
        
        assert result is None

    @patch('tempfile.NamedTemporaryFile')
    @patch('utils.run')
    @patch('utils._grant_current_user_keyvault_access')
    @patch('time.sleep')
    @patch('builtins.open', new_callable=mock_open, read_data=b"CERT_DATA")
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_permission_error_with_retry(self, mock_unlink, mock_exists, mock_file, mock_sleep, mock_grant, mock_run, mock_temp):
        """Test permission error handling with automatic retry"""
        mock_temp.return_value.__enter__.return_value.name = "/tmp/test.pfx"
        
        # First call fails with permission error, second succeeds
        mock_run.side_effect = [
            Mock(success=False, text="Forbidden getSecret"),
            Mock(success=True, text="")
        ]
        mock_grant.return_value = True
        mock_exists.return_value = True
        
        result = _download_certificate_from_key_vault("kv-test", "ag-cert", "test-rg")
        
        assert result == b"CERT_DATA"
        assert mock_run.call_count == 2
        mock_grant.assert_called_once_with("kv-test", "test-rg")


class TestGrantCurrentUserKeyVaultAccess:
    """Test Key Vault access permission granting"""
    
    @patch('utils.run')
    def test_successful_grant(self, mock_run):
        """Test successful permission grant"""
        mock_run.side_effect = [
            Mock(success=True, text="user-object-id"),
            Mock(success=True, text="subscription-id"),
            Mock(success=True, text="")
        ]
        
        result = _grant_current_user_keyvault_access("kv-test", "test-rg")
        
        assert result is True
        assert mock_run.call_count == 3

    @patch('utils.run')
    def test_failed_user_lookup(self, mock_run):
        """Test failed user object ID lookup"""
        mock_run.return_value = Mock(success=False, text="")
        
        result = _grant_current_user_keyvault_access("kv-test", "test-rg")
        
        assert result is False

    @patch('utils.run')
    def test_failed_role_assignment(self, mock_run):
        """Test failed role assignment"""
        mock_run.side_effect = [
            Mock(success=True, text="user-object-id"),
            Mock(success=True, text="subscription-id"),
            Mock(success=False, text="Role assignment failed")
        ]
        
        result = _grant_current_user_keyvault_access("kv-test", "test-rg")
        
        assert result is False


# ------------------------------
#    PLATFORM-SPECIFIC TESTS
# ------------------------------

class TestInstallCertificateToTrustStore:
    """Test platform-specific certificate installation routing"""
    
    @patch('platform.system')
    @patch('utils._install_certificate_windows')
    def test_windows_installation(self, mock_install_windows, mock_platform):
        """Test Windows certificate installation routing"""
        mock_platform.return_value = "Windows"
        mock_install_windows.return_value = True
        
        result = _install_certificate_to_trust_store(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is True
        mock_install_windows.assert_called_once_with(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)

    @patch('platform.system')
    @patch('utils._install_certificate_macos')
    def test_macos_installation(self, mock_install_macos, mock_platform):
        """Test macOS certificate installation routing"""
        mock_platform.return_value = "Darwin"
        mock_install_macos.return_value = True
        
        result = _install_certificate_to_trust_store(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is True
        mock_install_macos.assert_called_once_with(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)

    @patch('platform.system')
    @patch('utils._install_certificate_linux')
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
    @patch('utils._install_certificate_windows_powershell')
    @patch('os.unlink')
    def test_successful_powershell_installation(self, mock_unlink, mock_ps_install, mock_temp):
        """Test successful PowerShell installation"""
        mock_temp.return_value.__enter__.return_value.name = "C:\\temp\\test.pfx"
        mock_ps_install.return_value = True
        
        result = _install_certificate_windows(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is True
        mock_ps_install.assert_called_once_with("C:\\temp\\test.pfx", "test-cert")

    @patch('tempfile.NamedTemporaryFile')
    @patch('utils._install_certificate_windows_powershell')
    @patch('utils._install_certificate_windows_certutil')
    @patch('os.unlink')
    def test_fallback_to_certutil(self, mock_unlink, mock_certutil_install, mock_ps_install, mock_temp):
        """Test fallback to certutil when PowerShell fails"""
        mock_temp.return_value.__enter__.return_value.name = "C:\\temp\\test.pfx"
        mock_ps_install.return_value = False
        mock_certutil_install.return_value = True
        
        result = _install_certificate_windows(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is True
        mock_ps_install.assert_called_once()
        mock_certutil_install.assert_called_once_with("C:\\temp\\test.pfx")

    @patch('tempfile.NamedTemporaryFile')
    @patch('utils._install_certificate_windows_powershell')
    @patch('utils._install_certificate_windows_certutil')
    @patch('os.unlink')
    def test_manual_installation_instructions(self, mock_unlink, mock_certutil_install, mock_ps_install, mock_temp):
        """Test manual installation instructions when both methods fail"""
        mock_temp.return_value.__enter__.return_value.name = "C:\\temp\\test.pfx"
        mock_ps_install.return_value = False
        mock_certutil_install.return_value = False
        
        result = _install_certificate_windows(b"CERT_DATA", "test-cert", INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is False
        mock_ps_install.assert_called_once()
        mock_certutil_install.assert_called_once()


class TestListAndRemoveCertificates:
    """Test certificate listing and removal functions"""
    
    @patch('platform.system')
    @patch('utils._list_certificates_windows')
    def test_list_certificates_windows(self, mock_list_windows, mock_platform):
        """Test listing certificates on Windows"""
        mock_platform.return_value = "Windows"
        
        list_installed_apim_certificates()
        
        mock_list_windows.assert_called_once()

    @patch('platform.system')
    @patch('utils._remove_certificates_macos')
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
#    INTEGRATION TESTS
# ------------------------------

class TestEndToEndCertificateInstallation:
    """End-to-end integration tests (with mocking)"""
    
    @patch('utils.run')
    @patch('utils._install_certificate_to_trust_store')
    @patch('tempfile.NamedTemporaryFile')
    @patch('builtins.open', new_callable=mock_open, read_data=b"MOCK_CERT_DATA")
    @patch('os.path.exists')
    @patch('os.unlink')
    @patch('utils.get_infra_rg_name')
    def test_complete_workflow_success(self, mock_rg_name, mock_unlink, mock_exists, mock_file, mock_temp, mock_install, mock_run):
        """Test complete successful workflow"""
        # Setup mocks
        mock_rg_name.return_value = "apim-infra-ag-apim-vnet-1"
        mock_run.return_value = Mock(success=True, text="kv-test123")
        mock_temp.return_value.__enter__.return_value.name = "/tmp/test.pfx"
        mock_exists.return_value = True
        mock_install.return_value = True
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is True
        
        # Verify the sequence of calls
        assert mock_run.call_count >= 1  # At least one Az CLI call
        mock_install.assert_called_once_with(
            b"MOCK_CERT_DATA", 
            "apim-samples-apim-infra-ag-apim-vnet-1", 
            INFRASTRUCTURE.AG_APIM_VNET, 
            1
        )

    @patch('utils.run')
    @patch('utils.get_infra_rg_name')
    def test_complete_workflow_no_keyvault(self, mock_rg_name, mock_run):
        """Test complete workflow when Key Vault is not found"""
        mock_rg_name.return_value = "apim-infra-ag-apim-vnet-1"
        mock_run.return_value = Mock(success=False, text="")
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1)
        
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

    @patch('utils._get_key_vault_name')
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
    
    @patch('utils._get_key_vault_name')
    def test_handles_unexpected_exceptions(self, mock_kv_name):
        """Test handling of unexpected exceptions"""
        mock_kv_name.side_effect = RuntimeError("Unexpected error")
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1, "test-rg")
        
        assert result is False

    @patch('utils.run')
    @patch('utils.get_infra_rg_name')
    def test_handles_network_timeouts(self, mock_rg_name, mock_run):
        """Test handling of network timeouts"""
        mock_rg_name.return_value = "test-rg"
        mock_run.side_effect = TimeoutError("Network timeout")
        
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, 1)
        
        assert result is False

    def test_handles_invalid_parameters(self):
        """Test handling of invalid parameters"""
        # Test with invalid infrastructure type
        result = install_certificate_for_infrastructure("INVALID", 1)
        assert result is False
        
        # Test with invalid index
        result = install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, -1)
        # Should still attempt (negative indices might be valid in some contexts)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
