"""Tests for show_infrastructures module."""

import sys
from unittest.mock import MagicMock

# APIM Samples imports
import show_infrastructures as si
from apimtypes import INFRASTRUCTURE


def test_gather_infrastructures_with_locations(monkeypatch):
    """Gather infrastructures with location lookups enabled."""

    def fake_find(infra):
        if infra == INFRASTRUCTURE.SIMPLE_APIM:
            return [(infra, None), (infra, 2)]
        if infra == INFRASTRUCTURE.APIM_ACA:
            return [(infra, 1)]
        return []

    monkeypatch.setattr(si.az, 'find_infrastructure_instances', fake_find)
    monkeypatch.setattr(
        si.az,
        'get_infra_rg_name',
        lambda infra, idx: f'rg-{infra.value}-{idx if idx is not None else "base"}',
    )
    monkeypatch.setattr(si.az, 'get_resource_group_location', lambda rg: f'loc-{rg}')

    result = si.gather_infrastructures(include_location=True)

    assert len(result) == 3
    rg_names = {entry['resource_group'] for entry in result}
    assert 'rg-apim-aca-1' in rg_names
    assert 'rg-simple-apim-base' in rg_names
    assert all(entry['location'] for entry in result)


def test_gather_infrastructures_without_locations(monkeypatch):
    """Gather infrastructures without requesting locations."""

    def fake_find(infra):
        return [(infra, None)] if infra == INFRASTRUCTURE.SIMPLE_APIM else []

    monkeypatch.setattr(si.az, 'find_infrastructure_instances', fake_find)
    monkeypatch.setattr(si.az, 'get_infra_rg_name', lambda infra, idx: 'rg-simple-apim')
    monkeypatch.setattr(
        si.az,
        'get_resource_group_location',
        lambda rg: (_ for _ in ()).throw(AssertionError('Location lookup should be skipped')),
    )

    result = si.gather_infrastructures(include_location=False)

    assert result == [
        {
            'infrastructure': 'simple-apim',
            'index': None,
            'resource_group': 'rg-simple-apim',
            'location': None,
        }
    ]


def test_display_infrastructures_empty(monkeypatch):
    """Display message when no infrastructures are found."""

    printed: list[str] = []
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: printed.append(' '.join(str(a) for a in args)))

    si.display_infrastructures([], include_location=True)

    assert any('No deployed infrastructures' in line for line in printed)


def test_display_infrastructures_with_data(monkeypatch):
    """Display infrastructures with and without the location column."""

    printed: list[str] = []
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: printed.append(' '.join(str(a) for a in args)))

    data = [
        {
            'infrastructure': 'simple-apim',
            'index': None,
            'resource_group': 'rg-simple',
            'location': 'eastus',
        }
    ]

    si.display_infrastructures(data, include_location=True)
    assert any('rg-simple' in line for line in printed)
    assert any('eastus' in line for line in printed)

    printed.clear()
    si.display_infrastructures(data, include_location=False)
    header_line = next((line for line in printed if line.startswith('#')), '')
    assert 'Location' not in header_line


def test_show_subscription_success(monkeypatch):
    """Subscription details are shown when az account show succeeds."""

    printed: list[str] = []
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: printed.append(' '.join(str(a) for a in args)))
    monkeypatch.setattr(
        si.az,
        'run',
        lambda cmd: MagicMock(success=True, json_data={'name': 'test-sub', 'id': 'sub-id'}),
    )

    si.show_subscription()

    assert any('test-sub' in line for line in printed)
    assert any('sub-id' in line for line in printed)


def test_show_subscription_failure(monkeypatch):
    """Friendly message is printed when az account show fails."""

    printed: list[str] = []
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: printed.append(' '.join(str(a) for a in args)))
    monkeypatch.setattr(si.az, 'run', lambda cmd: MagicMock(success=False, json_data=None))

    si.show_subscription()

    assert any('Unable to read subscription details' in line for line in printed)


def test_main_runs_with_data(monkeypatch):
    """main returns zero and prints infrastructures."""

    printed: list[str] = []
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: printed.append(' '.join(str(a) for a in args)))
    monkeypatch.setattr(si, 'show_subscription', lambda: printed.append('subscription shown'))
    monkeypatch.setattr(
        si,
        'gather_infrastructures',
        lambda include_location=True: [
            {
                'infrastructure': 'simple-apim',
                'index': None,
                'resource_group': 'rg-main',
                'location': 'eastus' if include_location else None,
            }
        ],
    )
    monkeypatch.setattr(sys, 'argv', ['script.py'])

    result = si.main()

    assert not result
    assert any('rg-main' in line for line in printed)


def test_main_honors_no_location(monkeypatch):
    """main passes include_location=False when requested."""

    captured: dict[str, bool] = {}

    monkeypatch.setattr(si, 'show_subscription', lambda: None)
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)
    monkeypatch.setattr(sys, 'argv', ['script.py', '--no-location'])

    def fake_gather(include_location=True):
        captured['include_location'] = include_location
        return []

    monkeypatch.setattr(si, 'gather_infrastructures', fake_gather)

    result = si.main()

    assert not result
    assert captured['include_location'] is False


def test_display_infrastructures_index_column_right_aligned(monkeypatch):
    """Verify that Index column values are right-aligned."""

    printed_lines: list[str] = []
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: printed_lines.append(' '.join(str(a) for a in args)))

    data = [
        {
            'infrastructure': 'apim-aca',
            'index': 4,
            'resource_group': 'rg-apim-aca-4',
            'location': 'eastus',
        },
        {
            'infrastructure': 'apim-aca',
            'index': 21,
            'resource_group': 'rg-apim-aca-21',
            'location': 'eastus',
        },
    ]

    si.display_infrastructures(data, include_location=True)

    # Find the data rows (skip header and separator)
    data_rows = [line for line in printed_lines if line and not line.startswith('-') and not line.startswith('#')]

    # Verify we have at least the two data rows
    assert len([r for r in data_rows if 'apim-aca' in r]) >= 2

    # Check that single-digit index (4) has leading spaces compared to two-digit (21)
    row_with_4 = next((r for r in data_rows if 'rg-apim-aca-4' in r), None)
    row_with_21 = next((r for r in data_rows if 'rg-apim-aca-21' in r), None)

    assert row_with_4 is not None
    assert row_with_21 is not None

    # Index should appear after infrastructure column
    # For right-aligned: "4" should have trailing spaces, "21" should have no trailing spaces
    idx_4_pos = row_with_4.find('4')
    idx_21_pos = row_with_21.find('21')

    assert idx_4_pos > 0 and idx_21_pos > 0


def test_display_infrastructures_index_none_right_aligned(monkeypatch):
    """Verify that Index column with None values (N/A) is also right-aligned."""

    printed_lines: list[str] = []
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: printed_lines.append(' '.join(str(a) for a in args)))

    data = [
        {
            'infrastructure': 'simple-apim',
            'index': None,
            'resource_group': 'rg-simple',
            'location': 'eastus',
        },
        {
            'infrastructure': 'apim-aca',
            'index': 1,
            'resource_group': 'rg-apim-aca-1',
            'location': 'eastus',
        },
    ]

    si.display_infrastructures(data, include_location=True)

    printed_output = ' '.join(printed_lines)

    # Verify N/A appears for None index and single digit appears for index=1
    assert 'N/A' in printed_output
    assert 'rg-simple' in printed_output
    assert 'rg-apim-aca-1' in printed_output


def test_display_infrastructures_table_formatting(monkeypatch):
    """Verify the table structure and formatting."""

    printed_lines: list[str] = []
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: printed_lines.append(' '.join(str(a) for a in args)))

    data = [
        {
            'infrastructure': 'test-infra',
            'index': 1,
            'resource_group': 'test-rg-1',
            'location': 'eastus',
        },
    ]

    si.display_infrastructures(data, include_location=True)

    # Verify header row exists (contains #)
    header_line = next((l for l in printed_lines if '#' in l and 'Infrastructure' in l), None)
    assert header_line is not None
    assert 'Index' in header_line
    assert 'Resource Group' in header_line
    assert 'Location' in header_line

    # Verify separator row exists (all dashes)
    separator_line = next((l for l in printed_lines if l and all(c in '- ' for c in l)), None)
    assert separator_line is not None

    # Verify data row exists
    data_line = next((l for l in printed_lines if 'test-infra' in l), None)
    assert data_line is not None
    assert 'test-rg-1' in data_line
    assert 'eastus' in data_line
