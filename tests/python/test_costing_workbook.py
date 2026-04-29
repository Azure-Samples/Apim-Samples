"""Regression tests for the costing workbook JSON structure."""

import json
from pathlib import Path

WORKBOOK_PATH = Path(__file__).resolve().parents[2] / 'samples' / 'costing' / 'costing.workbook.json'

EXPECTED_TABS = ['instructions', 'subscription', 'entraid', 'aigateway', 'byrequest']

EXPECTED_INSTRUCTIONS_ITEMS = [
    ('text - instructions-overview', 1),
    ('group - instructions-howtouse', 12),
    ('group - instructions-subscription', 12),
    ('group - instructions-entraid', 12),
    ('group - instructions-aigateway', 12),
    ('group - instructions-aigateway-pricing', 12),
    ('group - instructions-byrequest', 12),
]


def _load_workbook():
    return json.loads(WORKBOOK_PATH.read_text(encoding='utf-8'))


def test_costing_workbook_instructions_page_contains_expected_text_items():
    workbook = _load_workbook()

    instructions_group = next(item for item in workbook['items'] if item.get('name') == 'group - tab-1-instructions')

    assert instructions_group['conditionalVisibility']['parameterName'] == 'selectedTab'
    assert instructions_group['conditionalVisibility']['value'] == 'instructions'

    instructions_items = instructions_group['content']['items']
    item_names_and_types = [(item.get('name'), item.get('type')) for item in instructions_items]

    assert item_names_and_types == EXPECTED_INSTRUCTIONS_ITEMS

    # First item is the markdown overview text
    overview_item = instructions_items[0]
    assert overview_item['type'] == 1
    assert 'json' in overview_item['content']
    assert 'Instructions' in overview_item['content']['json']

    # All collapsible groups are collapsed by default with editable groupType
    for item in instructions_items[1:]:
        assert item['type'] == 12
        content = item['content']
        assert content['version'] == 'NotebookGroup/1.0'
        assert content['groupType'] == 'editable'
        assert content['expandable'] is True
        assert content['expanded'] is False
        assert content['title']
        # Each collapsible group wraps a single markdown text item
        assert len(content['items']) == 1
        assert content['items'][0]['type'] == 1
        assert 'json' in content['items'][0]['content']


def test_costing_workbook_tabs_include_instructions_first():
    workbook = _load_workbook()

    shared_parameters_group = next(item for item in workbook['items'] if item.get('name') == 'parameters - shared')
    selected_tab = next(parameter for parameter in shared_parameters_group['content']['parameters'] if parameter['name'] == 'selectedTab')
    tabs_item = next(item for item in workbook['items'] if item.get('name') == 'links - tabs')
    sub_targets = [link['subTarget'] for link in tabs_item['content']['links']]

    assert selected_tab['value'] == 'instructions'
    assert sub_targets == EXPECTED_TABS


def test_costing_workbook_shared_parameters_exist_once():
    workbook = _load_workbook()

    shared_parameters_group = next(item for item in workbook['items'] if item.get('name') == 'parameters - shared')
    parameters = shared_parameters_group['content']['parameters']
    parameter_names = [parameter['name'] for parameter in parameters]

    # Each shared parameter must be defined exactly once.
    for required_name in ('TimeRange', 'selectedTab', 'DateTimeFormat'):
        assert parameter_names.count(required_name) == 1, f'expected exactly one {required_name} parameter'
