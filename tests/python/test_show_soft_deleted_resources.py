"""Tests for show_soft_deleted_resources module."""

from unittest.mock import MagicMock, patch

# APIM Samples imports
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
    assert not result


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

        assert not success_count
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
            assert not skipped_count


def test_parse_date_with_plus_offset():
    """Test parsing date with +00:00 offset."""
    date_str = '2025-12-13T10:30:00+00:00'
    result = sdr.parse_date(date_str)
    assert '2025-12-13' in result
    assert 'UTC' in result

# ------------------------------
#    COMPREHENSIVE INTEGRATION TESTS
# ------------------------------

def test_main_no_resources_no_purge(monkeypatch):
    """Test main function with no soft-deleted resources."""
    def mock_get_apim():
        return []

    def mock_get_vaults():
        return []

    def mock_az_run(cmd, *a, **k):
        return MagicMock(success=True, json_data={'name': 'test-sub', 'id': 'sub-id'})

    monkeypatch.setattr('show_soft_deleted_resources.get_deleted_apim_services', mock_get_apim)
    monkeypatch.setattr('show_soft_deleted_resources.get_deleted_key_vaults', mock_get_vaults)
    monkeypatch.setattr('show_soft_deleted_resources.az.run', mock_az_run)
    monkeypatch.setattr('builtins.print', MagicMock())
    monkeypatch.setattr('sys.argv', ['script.py'])

    result = sdr.main()
    assert not result


def test_main_with_resources_show_only(monkeypatch):
    """Test main function showing resources without purge."""
    services = [{'name': 'apim-1', 'location': 'eastus', 'deletionDate': '2025-12-13T10:00:00Z', 'scheduledPurgeDate': '2026-01-13T10:00:00Z', 'serviceId': 'id-1'}]
    vaults = [{'name': 'vault-1', 'properties': {'location': 'eastus', 'deletionDate': '2025-12-13T10:00:00Z', 'scheduledPurgeDate': '2026-01-13T10:00:00Z', 'vaultId': 'vid-1', 'purgeProtectionEnabled': False}}]

    def mock_get_apim():
        return services

    def mock_get_vaults():
        return vaults

    def mock_az_run(cmd, *a, **k):
        return MagicMock(success=True, json_data={'name': 'test-sub', 'id': 'sub-id'})

    monkeypatch.setattr('show_soft_deleted_resources.get_deleted_apim_services', mock_get_apim)
    monkeypatch.setattr('show_soft_deleted_resources.get_deleted_key_vaults', mock_get_vaults)
    monkeypatch.setattr('show_soft_deleted_resources.az.run', mock_az_run)
    monkeypatch.setattr('builtins.print', MagicMock())
    monkeypatch.setattr('sys.argv', ['script.py'])

    result = sdr.main()
    assert not result


def test_main_with_purge_flag_confirmed(monkeypatch):
    """Test main with --purge flag and user confirms."""
    services = [{'name': 'apim-1', 'location': 'eastus', 'deletionDate': '2025-12-13T10:00:00Z', 'scheduledPurgeDate': '2026-01-13T10:00:00Z', 'serviceId': 'id-1'}]
    vaults = []

    def mock_get_apim():
        return services

    def mock_get_vaults():
        return vaults

    def mock_confirm_purge(a, b, c):
        return True

    def mock_purge_apim(s):
        return len(s)

    def mock_purge_kv(v):
        return (0, 0)

    def mock_az_run(cmd, *a, **k):
        return MagicMock(success=True, json_data={'name': 'test-sub', 'id': 'sub-id'})

    monkeypatch.setattr('show_soft_deleted_resources.get_deleted_apim_services', mock_get_apim)
    monkeypatch.setattr('show_soft_deleted_resources.get_deleted_key_vaults', mock_get_vaults)
    monkeypatch.setattr('show_soft_deleted_resources.confirm_purge', mock_confirm_purge)
    monkeypatch.setattr('show_soft_deleted_resources.purge_apim_services', mock_purge_apim)
    monkeypatch.setattr('show_soft_deleted_resources.purge_key_vaults', mock_purge_kv)
    monkeypatch.setattr('show_soft_deleted_resources.az.run', mock_az_run)
    monkeypatch.setattr('builtins.print', MagicMock())
    monkeypatch.setattr('sys.argv', ['script.py', '--purge'])

    result = sdr.main()
    assert not result


def test_main_with_purge_flag_not_confirmed(monkeypatch):
    """Test main with --purge flag but user cancels."""
    services = [{'name': 'apim-1', 'location': 'eastus', 'deletionDate': '2025-12-13T10:00:00Z', 'scheduledPurgeDate': '2026-01-13T10:00:00Z', 'serviceId': 'id-1'}]
    vaults = []

    def mock_get_apim():
        return services

    def mock_get_vaults():
        return vaults

    def mock_confirm_purge(a, b, c):
        return False

    def mock_az_run(cmd, *a, **k):
        return MagicMock(success=True, json_data={'name': 'test-sub', 'id': 'sub-id'})

    monkeypatch.setattr('show_soft_deleted_resources.get_deleted_apim_services', mock_get_apim)
    monkeypatch.setattr('show_soft_deleted_resources.get_deleted_key_vaults', mock_get_vaults)
    monkeypatch.setattr('show_soft_deleted_resources.confirm_purge', mock_confirm_purge)
    monkeypatch.setattr('show_soft_deleted_resources.az.run', mock_az_run)
    monkeypatch.setattr('builtins.print', MagicMock())
    monkeypatch.setattr('sys.argv', ['script.py', '--purge'])

    result = sdr.main()
    assert not result


def test_main_with_purge_and_yes_flags(monkeypatch):
    """Test main with both --purge and --yes flags (skip confirmation)."""
    services = [{'name': 'apim-1', 'location': 'eastus', 'deletionDate': '2025-12-13T10:00:00Z', 'scheduledPurgeDate': '2026-01-13T10:00:00Z', 'serviceId': 'id-1'}]
    vaults = []

    purge_apim_called = []
    purge_kv_called = []

    def track_purge_apim(s):
        purge_apim_called.append(True)
        return len(s)

    def track_purge_kv(v):
        purge_kv_called.append(True)
        return (0, 0)

    monkeypatch.setattr('show_soft_deleted_resources.get_deleted_apim_services', lambda: services)
    monkeypatch.setattr('show_soft_deleted_resources.get_deleted_key_vaults', lambda: vaults)
    monkeypatch.setattr('show_soft_deleted_resources.purge_apim_services', track_purge_apim)
    monkeypatch.setattr('show_soft_deleted_resources.purge_key_vaults', track_purge_kv)
    monkeypatch.setattr('show_soft_deleted_resources.az.run', lambda cmd, *a, **k: MagicMock(success=True, json_data={'name': 'test-sub', 'id': 'sub-id'}))
    monkeypatch.setattr('builtins.print', MagicMock())
    monkeypatch.setattr('sys.argv', ['script.py', '--purge', '--yes'])

    result = sdr.main()
    assert not result
    assert len(purge_apim_called) > 0
    assert len(purge_kv_called) > 0


def test_get_deleted_apim_services_empty():
    """Test get_deleted_apim_services with empty list response."""
    mock_output = MagicMock()
    mock_output.success = True
    mock_output.json_data = []

    with patch('show_soft_deleted_resources.az.run', return_value=mock_output):
        result = sdr.get_deleted_apim_services()
        assert result == []


def test_get_deleted_apim_services_non_json():
    """Test get_deleted_apim_services with non-JSON response."""
    mock_output = MagicMock()
    mock_output.success = True
    mock_output.json_data = None

    with patch('show_soft_deleted_resources.az.run', return_value=mock_output):
        result = sdr.get_deleted_apim_services()
        assert result == []


def test_get_deleted_key_vaults_empty():
    """Test get_deleted_key_vaults with empty list response."""
    mock_output = MagicMock()
    mock_output.success = True
    mock_output.json_data = []

    with patch('show_soft_deleted_resources.az.run', return_value=mock_output):
        result = sdr.get_deleted_key_vaults()
        assert result == []


def test_get_deleted_key_vaults_failure():
    """Test get_deleted_key_vaults failure handling."""
    mock_output = MagicMock()
    mock_output.success = False
    mock_output.text = 'Error retrieving vaults'

    with patch('show_soft_deleted_resources.az.run', return_value=mock_output):
        with patch('builtins.print'):
            result = sdr.get_deleted_key_vaults()
            assert result == []


def test_show_deleted_apim_services_multiple(monkeypatch):
    """Test show_deleted_apim_services with multiple services."""
    services = [
        {'name': 'apim-1', 'location': 'eastus', 'deletionDate': '2025-12-13T10:00:00Z', 'scheduledPurgeDate': '2026-01-13T10:00:00Z', 'serviceId': 'id-1'},
        {'name': 'apim-2', 'location': 'westus', 'deletionDate': '2025-12-12T10:00:00Z', 'scheduledPurgeDate': '2026-01-12T10:00:00Z', 'serviceId': 'id-2'},
        {'name': 'apim-3', 'location': 'northeurope', 'deletionDate': '2025-12-11T10:00:00Z', 'scheduledPurgeDate': '2026-01-11T10:00:00Z', 'serviceId': 'id-3'},
    ]

    print_calls = []
    monkeypatch.setattr('builtins.print', lambda *args, **k: print_calls.append(args))

    sdr.show_deleted_apim_services(services)

    output_text = ' '.join(str(c[0]) if c else '' for c in print_calls)
    assert 'apim-1' in output_text
    assert 'apim-2' in output_text
    assert 'apim-3' in output_text
    assert 'Found 3' in output_text


def test_show_deleted_key_vaults_multiple(monkeypatch):
    """Test show_deleted_key_vaults with multiple vaults."""
    vaults = [
        {'name': 'vault-1', 'properties': {'location': 'eastus', 'deletionDate': '2025-12-13T10:00:00Z', 'scheduledPurgeDate': '2026-01-13T10:00:00Z', 'vaultId': 'vid-1', 'purgeProtectionEnabled': False}},
        {'name': 'vault-2', 'properties': {'location': 'westus', 'deletionDate': '2025-12-12T10:00:00Z', 'scheduledPurgeDate': '2026-01-12T10:00:00Z', 'vaultId': 'vid-2', 'purgeProtectionEnabled': True}},
    ]

    print_calls = []
    monkeypatch.setattr('builtins.print', lambda *args, **k: print_calls.append(args))

    sdr.show_deleted_key_vaults(vaults)

    output_text = ' '.join(str(c[0]) if c else '' for c in print_calls)
    assert 'vault-1' in output_text
    assert 'vault-2' in output_text
    assert 'Found 2' in output_text


def test_purge_apim_services_partial_failure(monkeypatch):
    """Test purge_apim_services with some failures."""
    services = [
        {'name': 'apim-1', 'location': 'eastus'},
        {'name': 'apim-2', 'location': 'westus'},
        {'name': 'apim-3', 'location': 'northeurope'},
    ]

    call_count = [0]
    def mock_run(cmd, *args, **kwargs):
        output = MagicMock()
        output.success = call_count[0] != 1  # Second call fails
        call_count[0] += 1
        return output

    monkeypatch.setattr('show_soft_deleted_resources.az.run', mock_run)
    monkeypatch.setattr('builtins.print', MagicMock())

    result = sdr.purge_apim_services(services)
    assert result == 2  # Two succeeded


def test_purge_key_vaults_mixed_protection(monkeypatch):
    """Test purge_key_vaults with mixed purge protection settings."""
    vaults = [
        {'name': 'vault-1', 'properties': {'location': 'eastus', 'purgeProtectionEnabled': False}},
        {'name': 'vault-2', 'properties': {'location': 'westus', 'purgeProtectionEnabled': True}},
        {'name': 'vault-3', 'properties': {'location': 'northeurope', 'purgeProtectionEnabled': False}},
        {'name': 'vault-4', 'properties': {'location': 'southeastasia', 'purgeProtectionEnabled': True}},
    ]

    mock_output = MagicMock()
    mock_output.success = True

    monkeypatch.setattr('show_soft_deleted_resources.az.run', lambda cmd, *a, **k: mock_output)
    monkeypatch.setattr('builtins.print', MagicMock())

    success_count, skipped_count = sdr.purge_key_vaults(vaults)
    assert success_count == 2
    assert skipped_count == 2


def test_confirm_purge_with_protected_vaults(monkeypatch):
    """Test confirm_purge displays info about protected vaults."""
    print_calls = []
    monkeypatch.setattr('builtins.print', lambda *args, **k: print_calls.append(args))
    monkeypatch.setattr('builtins.input', lambda *args, **k: 'PURGE ALL')

    result = sdr.confirm_purge(1, 2, 1)
    assert result is True


def test_confirm_purge_eof_error(monkeypatch):
    """Test confirm_purge handles EOFError."""
    def raise_eof(*args, **kwargs):
        raise EOFError()
    monkeypatch.setattr('builtins.input', raise_eof)
    monkeypatch.setattr('builtins.print', MagicMock())

    result = sdr.confirm_purge(1, 1, 0)
    assert result is False


def test_parse_date_none_input():
    """Test parse_date with None input."""
    result = sdr.parse_date(None)
    assert result == 'N/A'


def test_parse_date_various_invalid_formats():
    """Test parse_date with various invalid formats."""
    test_cases = [
        'not-a-date',
        '2025/12/13',
        '13-12-2025',
        '2025-13-45T99:99:99Z',
        '',
    ]

    for test_input in test_cases:
        result = sdr.parse_date(test_input)
        if test_input:
            assert result == test_input  # Should return input as-is
        else:
            assert result == 'N/A'  # Empty string should return N/A
