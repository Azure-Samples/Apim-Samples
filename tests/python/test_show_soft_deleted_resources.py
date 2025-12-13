"""
Tests for show_soft_deleted_resources module.
"""

from unittest.mock import patch, MagicMock
from datetime import datetime
import pytest

# Import the module we're testing
import sys
from pathlib import Path

# Add shared/python to path
shared_python_path = Path(__file__).parent.parent.parent / 'shared' / 'python'
sys.path.insert(0, str(shared_python_path))

import show_soft_deleted_resources as sdr


# ------------------------------
#    HELPER FUNCTION TESTS
# ------------------------------

def test_parse_date_valid_iso_format():
    """Test parsing a valid ISO format date."""
    date_str = '2025-12-13T10:30:00Z'
    result = sdr.parse_date(date_str)
    assert result == '2025-12-13 10:30:00 UTC'


def test_parse_date_empty_string():
    """Test parsing an empty date string."""
    result = sdr.parse_date('')
    assert result == 'N/A'


def test_parse_date_invalid_format():
    """Test parsing an invalid date format returns original string."""
    date_str = 'invalid-date'
    result = sdr.parse_date(date_str)
    assert result == 'invalid-date'


# ------------------------------
#    GET DELETED RESOURCES TESTS
# ------------------------------

def test_get_deleted_apim_services_success():
    """Test successfully retrieving deleted APIM services."""
    mock_output = MagicMock()
    mock_output.success = True
    mock_output.is_json = True
    mock_output.json_data = [
        {'name': 'apim1', 'location': 'eastus'},
        {'name': 'apim2', 'location': 'westus'}
    ]

    with patch('show_soft_deleted_resources.az.run', return_value=mock_output):
        result = sdr.get_deleted_apim_services()

        assert len(result) == 2
        assert result[0]['name'] == 'apim1'
        assert result[1]['location'] == 'westus'


def test_get_deleted_apim_services_failure():
    """Test handling failure when retrieving deleted APIM services."""
    mock_output = MagicMock()
    mock_output.success = False
    mock_output.text = 'Error message'

    with patch('show_soft_deleted_resources.az.run', return_value=mock_output):
        with patch('builtins.print'):
            result = sdr.get_deleted_apim_services()

            assert result == []


def test_get_deleted_key_vaults_success():
    """Test successfully retrieving deleted Key Vaults."""
    mock_output = MagicMock()
    mock_output.success = True
    mock_output.is_json = True
    mock_output.json_data = [
        {'name': 'kv1', 'properties': {'location': 'eastus', 'purgeProtectionEnabled': False}},
        {'name': 'kv2', 'properties': {'location': 'westus', 'purgeProtectionEnabled': True}}
    ]

    with patch('show_soft_deleted_resources.az.run', return_value=mock_output):
        result = sdr.get_deleted_key_vaults()

        assert len(result) == 2
        assert result[0]['name'] == 'kv1'
        assert result[1]['properties']['purgeProtectionEnabled'] is True


def test_get_deleted_key_vaults_not_json():
    """Test handling non-JSON response when retrieving Key Vaults."""
    mock_output = MagicMock()
    mock_output.success = True
    mock_output.is_json = False

    with patch('show_soft_deleted_resources.az.run', return_value=mock_output):
        result = sdr.get_deleted_key_vaults()

        assert result == []


# ------------------------------
#    PURGE FUNCTION TESTS
# ------------------------------

def test_purge_apim_services_success():
    """Test successfully purging APIM services."""
    services = [
        {'name': 'apim1', 'location': 'eastus'},
        {'name': 'apim2', 'location': 'westus'}
    ]

    mock_output = MagicMock()
    mock_output.success = True

    with patch('show_soft_deleted_resources.az.run', return_value=mock_output):
        with patch('builtins.print'):
            result = sdr.purge_apim_services(services)

            assert result == 2


def test_purge_apim_services_empty_list():
    """Test purging with empty services list."""
    result = sdr.purge_apim_services([])
    assert result == 0


def test_purge_key_vaults_with_purge_protection():
    """Test purging Key Vaults where some have purge protection."""
    vaults = [
        {'name': 'kv1', 'properties': {'location': 'eastus', 'purgeProtectionEnabled': False}},
        {'name': 'kv2', 'properties': {'location': 'westus', 'purgeProtectionEnabled': True}}
    ]

    mock_output = MagicMock()
    mock_output.success = True

    with patch('show_soft_deleted_resources.az.run', return_value=mock_output):
        with patch('builtins.print'):
            success_count, skipped_count = sdr.purge_key_vaults(vaults)

            assert success_count == 1
            assert skipped_count == 1


def test_purge_key_vaults_all_protected():
    """Test purging Key Vaults when all have purge protection."""
    vaults = [
        {'name': 'kv1', 'properties': {'location': 'eastus', 'purgeProtectionEnabled': True}},
        {'name': 'kv2', 'properties': {'location': 'westus', 'purgeProtectionEnabled': True}}
    ]

    with patch('builtins.print'):
        success_count, skipped_count = sdr.purge_key_vaults(vaults)

        assert success_count == 0
        assert skipped_count == 2


# ------------------------------
#    CONFIRMATION TESTS
# ------------------------------

def test_confirm_purge_user_confirms():
    """Test user confirmation with correct input."""
    with patch('builtins.input', return_value='PURGE ALL'):
        with patch('builtins.print'):
            result = sdr.confirm_purge(1, 1, 0)

            assert result is True


def test_confirm_purge_user_cancels():
    """Test user cancellation with incorrect input."""
    with patch('builtins.input', return_value=''):
        with patch('builtins.print'):
            result = sdr.confirm_purge(1, 1, 0)

            assert result is False


def test_confirm_purge_keyboard_interrupt():
    """Test handling keyboard interrupt during confirmation."""
    with patch('builtins.input', side_effect=KeyboardInterrupt()):
        with patch('builtins.print'):
            result = sdr.confirm_purge(1, 1, 0)

            assert result is False


# ------------------------------
#    DISPLAY FUNCTION TESTS
# ------------------------------

def test_show_deleted_apim_services_with_data():
    """Test displaying APIM services with data."""
    services = [
        {
            'name': 'apim1',
            'location': 'eastus',
            'deletionDate': '2025-12-13T10:00:00Z',
            'scheduledPurgeDate': '2026-01-13T10:00:00Z',
            'serviceId': 'id123'
        }
    ]

    with patch('builtins.print') as mock_print:
        sdr.show_deleted_apim_services(services)

        # Verify print was called (checking specific output)
        assert mock_print.call_count > 0


def test_show_deleted_apim_services_empty():
    """Test displaying APIM services with no data."""
    with patch('builtins.print') as mock_print:
        sdr.show_deleted_apim_services([])

        # Should print "No soft-deleted API Management services found"
        call_args = [str(call) for call in mock_print.call_args_list]
        assert any('No soft-deleted' in str(arg) for arg in call_args)


def test_show_deleted_key_vaults_with_purge_protection():
    """Test displaying Key Vaults showing purge protection status."""
    vaults = [
        {
            'name': 'kv1',
            'properties': {
                'location': 'eastus',
                'deletionDate': '2025-12-13T10:00:00Z',
                'scheduledPurgeDate': '2026-01-13T10:00:00Z',
                'vaultId': 'vault-id-1',
                'purgeProtectionEnabled': True
            }
        }
    ]

    with patch('builtins.print') as mock_print:
        sdr.show_deleted_key_vaults(vaults)

        # Verify purge protection message was printed
        call_args = [str(call) for call in mock_print.call_args_list]
        assert any('PURGE PROTECTION' in str(arg) for arg in call_args)


# ------------------------------
#    EDGE CASES
# ------------------------------

def test_purge_key_vaults_missing_properties():
    """Test purging Key Vaults with missing properties field."""
    vaults = [
        {'name': 'kv1'},  # Missing properties
        {'name': 'kv2', 'properties': {}}  # Empty properties
    ]

    mock_output = MagicMock()
    mock_output.success = True

    with patch('show_soft_deleted_resources.az.run', return_value=mock_output):
        with patch('builtins.print'):
            success_count, skipped_count = sdr.purge_key_vaults(vaults)

            # Both should be treated as not protected
            assert success_count == 2
            assert skipped_count == 0


def test_parse_date_with_plus_offset():
    """Test parsing date with +00:00 offset."""
    date_str = '2025-12-13T10:30:00+00:00'
    result = sdr.parse_date(date_str)
    assert '2025-12-13' in result
    assert 'UTC' in result
