"""Unit tests for the HTML report builder."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

# APIM Samples imports
from htmlreport import HtmlList, HtmlReport, HtmlSuccess, HtmlText, HtmlWarning


def test_html_report_writes_self_contained_content(tmp_path: Path) -> None:
    """Render escaped metrics, tables, figures, and links into one portable file."""
    report = HtmlReport('Inference <Report>', 'A clean run summary')
    figure = MagicMock()
    figure.savefig.side_effect = lambda buffer, **_: buffer.write(b'png bytes')

    report.add_metrics('Tests', {'Passed': 5, 'Result': 'Passed', 'Success rate': '100.0%', 'Detail': '<ok>'})
    report.add_success_callout('All <good>', 'Every request returned HTTP 200.')
    report.add_info_callout('Lab <note>', 'Capacity is intentionally low.')
    report.add_table(
        HtmlText('Rows for gpt-5.1', ('gpt-5.1',)),
        ['Status', 'Name', 'Value'],
        [
            [
                HtmlSuccess('All requests returned HTTP 200'),
                HtmlText('P1: route-a\nP2: route-b', ('P1', 'P2'), True),
                HtmlList(('One <item>.', 'Two.')),
            ]
        ],
        HtmlText('Bold <caption> then plain text.', ('Bold <caption>',)),
        column_widths=['10%', '50%', '40%'],
    )
    report.add_table('Warnings', ['Status'], [[HtmlWarning('Some requests returned non-200 responses')]])
    report.add_metrics('Neutral tests', {'Result': 'Passed', 'Success rate': '100.0%'}, highlight_success=False)
    report.add_figure('Route graph', figure, 'Embedded output')
    report.add_links('Explore', {'Workbook': 'https://portal.azure.com/example'})
    output_path = report.write(tmp_path / 'report.html')
    document = output_path.read_text(encoding='utf-8')

    assert output_path == (tmp_path / 'report.html').resolve()
    assert '<title>Inference &lt;Report&gt;</title>' in document
    assert '&lt;ok&gt;' in document
    assert document.count('class="metric metric-success"') == 2
    assert '.metric-success { background: #146c43; border-left-color: #0a3622; color: #ffffff; }' in document
    assert 'class="status-callout status-success" role="status"' in document
    assert '.status-success { background: #146c43; border: 2px solid #0a3622; color: #ffffff; }' in document
    assert '<span class="status-icon" aria-hidden="true">&#10003;</span>' in document
    assert '<h2>All &lt;good&gt;</h2><p>Every request returned HTTP 200.</p>' in document
    assert 'class="status-callout status-info" role="note"' in document
    assert '.status-info { background: #eaf2f8; border: 2px solid #005a9e; color: #1f2937; }' in document
    assert '<span class="status-icon" aria-hidden="true">&#9432;</span>' in document
    assert '<h2>Lab &lt;note&gt;</h2><p>Capacity is intentionally low.</p>' in document
    assert '<th scope="col">Name</th>' in document
    assert '<h2>Rows for <strong>gpt-5.1</strong></h2>' in document
    assert '<p><strong>Bold &lt;caption&gt;</strong> then plain text.</p>' in document
    assert '<td><strong>P1</strong>: route-a<br><strong>P2</strong>: route-b</td>' in document
    assert '<tr class="table-row-success">' in document
    assert '<td><span class="table-success" role="img" aria-label="All requests returned HTTP 200">&#10003;</span></td>' in document
    assert '.table-row-success td { background: #146c43; border-color: #0a3622; color: #ffffff; }' in document
    assert '.table-success { color: #198754; display: inline-block; font-size: 1.8rem; font-weight: 900; line-height: 1; }' in document
    assert '<tr class="table-row-warning">' in document
    assert '<td><span class="table-warning" role="img" aria-label="Some requests returned non-200 responses">&#9888;</span></td>' in document
    assert '.table-row-warning td { background: #fff3cd; border-color: #b45309; color: #3d2c00; }' in document
    assert '.table-warning { color: #8a4b00; display: inline-block; font-size: 1.5rem; font-weight: 900; line-height: 1; }' in document
    assert '<td><ul class="table-list"><li>One &lt;item&gt;.</li><li>Two.</li></ul></td>' in document
    assert '.table-list { list-style: none; margin: 0; padding: 0; }' in document
    assert '.table-list li { column-gap: 0.1rem; display: grid; grid-template-columns: 0.55rem 1fr; margin: 0 0 0.2rem; }' in document
    assert ".table-list li::before { content: '\\2022'; }" in document
    assert '<colgroup><col style="width: 10%"><col style="width: 50%"><col style="width: 40%"></colgroup>' in document
    assert '.table-wrap { max-width: 100%; overflow-x: auto; } table { border-collapse: collapse; table-layout: fixed; width: 100%; }' in document
    assert 'overflow-wrap: anywhere;' in document
    assert 'word-break: break-word;' in document
    assert 'vertical-align: top;' in document
    assert 'data:image/png;base64,cG5nIGJ5dGVz' in document
    assert 'href="https://portal.azure.com/example"' in document


def test_html_report_rejects_unsupported_link_scheme() -> None:
    """Reject executable links in generated reports."""
    report = HtmlReport('Report')

    with pytest.raises(ValueError, match='Unsupported report link scheme'):
        report.add_links('Unsafe', {'Bad': 'javascript:alert(1)'})


def test_html_report_rejects_mismatched_table_column_widths() -> None:
    """Reject table widths that do not map one-to-one with headers."""
    report = HtmlReport('Report')

    with pytest.raises(ValueError, match='Table column widths must match the header count'):
        report.add_table('Rows', ['Name', 'Value'], [['one', 1]], column_widths=['100%'])


def test_html_report_renders_plain_rows_and_unformatted_html_text() -> None:
    """Render fallback table rows and HtmlText without optional bold formatting."""
    assert HtmlReport._table_row(['<plain>']) == '<tr><td>&lt;plain&gt;</td></tr>'
    assert HtmlReport._render_text(HtmlText('<plain>')) == '&lt;plain&gt;'
