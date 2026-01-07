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
