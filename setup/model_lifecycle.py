"""Report published AI model retirement dates without changing the catalog.

Uses only the standard library and the approved manifest. No Azure credentials,
agent, notebook execution, dependency installation, or model migration is needed.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import TypedDict

# APIM Samples imports
from setup.model_catalog import ModelRecord, load_models


SOURCE_URL = 'https://learn.microsoft.com/azure/foundry/openai/concepts/model-retirement-schedule'
WINDOW_DAYS = 30
HEADERS = ['Model', 'Version', 'Lifecycle', 'Retirement date', 'Replacement']
PROVIDER_HEADINGS = {
    'anthropic': 'Anthropic',
    'black-forest-labs': 'Black Forest Labs',
    'cohere': 'Cohere',
    'deepseek': 'DeepSeek',
    'meta': 'Meta',
    'microsoft': 'Microsoft',
    'mistral': 'Mistral AI',
    'moonshot': 'MoonshotAI',
    'openai': 'Azure OpenAI',
    'openai-oss': 'OpenAI-OSS',
    'xai': 'xAI',
}
NO_VERSION = {'', '-', '\u2014'}


class Finding(TypedDict):
    """Evidence for one exact approved model identity."""

    member: str
    provider: str
    model_name: str
    version: str | None
    status: str
    lifecycle: str | None
    retirement_date: str | None
    days_remaining: int | None
    replacement: str | None
    error: str | None


class Report(TypedDict):
    """A complete check, including explicit coverage gaps."""

    status: str
    checked_at: str
    source_url: str
    window_days: int
    findings: list[Finding]
    errors: list[str]


class ScheduleParser(HTMLParser):
    """Keep provider tables separate and exclude nested fine-tuning schedules."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[tuple[str, list[list[str]]]] = []
        self._heading: list[str] | None = None
        self._provider: str | None = None
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if re.fullmatch(r'h[1-6]', tag):
            self._heading = []
            self._provider = None
        elif tag == 'table' and self._provider is not None:
            self._table = []
        elif tag == 'tr' and self._table is not None:
            self._row = []
        elif tag in {'th', 'td'} and self._row is not None:
            self._cell = []
        elif tag == 'sup' and self._cell is not None:
            # Preserve qualification rather than silently accepting a footnoted date.
            self._cell.append('[footnote]')
        elif tag == 'br' and self._cell is not None:
            self._cell.append(' ')

    def handle_data(self, data: str) -> None:
        if self._heading is not None:
            self._heading.append(data)
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if re.fullmatch(r'h[1-6]', tag) and self._heading is not None:
            heading = ''.join(self._heading).strip()
            if tag == 'h3':
                self._provider = next((provider for provider, title in PROVIDER_HEADINGS.items() if title == heading), None)
            self._heading = None
        elif tag in {'th', 'td'} and self._cell is not None and self._row is not None:
            self._row.append(' '.join(''.join(self._cell).split()))
            self._cell = None
        elif tag == 'tr' and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == 'table' and self._table is not None and self._provider is not None:
            self.tables.append((self._provider, self._table))
            self._table = None


def fetch_schedule() -> str:
    """Fetch the fixed authoritative public page with a bounded network timeout."""
    request = urllib.request.Request(SOURCE_URL, headers = {'User-Agent': 'APIM-Samples-model-lifecycle'})
    with urllib.request.urlopen(request, timeout = 60) as response:
        return response.read().decode('utf-8')


def check_models(models: dict[str, ModelRecord], document: str, checked_at: datetime) -> Report:
    """Require exact provider/name/version coverage; never infer dates or versions."""
    parser = ScheduleParser()
    parser.feed(document)
    parser.close()
    report: Report = {
        'status': 'clear', 'checked_at': checked_at.astimezone(timezone.utc).isoformat(),
        'source_url': SOURCE_URL, 'window_days': WINDOW_DAYS, 'findings': [], 'errors': [],
    }
    today = checked_at.astimezone(timezone.utc).date()
    for member, spec in sorted(models.items()):
        finding: Finding = {
            'member': member, **spec, 'status': 'blocked', 'lifecycle': None,
            'retirement_date': None, 'days_remaining': None, 'replacement': None, 'error': None,
        }
        tables = [table for provider, table in parser.tables if provider == spec['provider']]
        malformed = any(not table or table[0] != HEADERS or any(len(row) != len(HEADERS) for row in table[1:]) for table in tables)
        rows = [row for table in tables for row in table[1:]] if not malformed else []
        # Some providers appear in both Azure-sold and partner sections.
        matches = sorted({
            tuple(row) for row in rows
            if row[0] == spec['model_name'] and (None if row[1] in NO_VERSION else row[1]) == spec['version']
        })
        if spec['provider'] not in PROVIDER_HEADINGS:
            finding['error'] = f"No retirement source mapping for provider {spec['provider']!r}."
        elif not tables or malformed:
            finding['error'] = f"Missing or malformed retirement table for provider {spec['provider']!r}."
        elif len(matches) != 1:
            finding['error'] = f'Expected one exact provider/name/version row; found {len(matches)} distinct rows.'
        else:
            _, _, lifecycle, cutoff, replacement = matches[0]
            finding['lifecycle'] = lifecycle
            finding['replacement'] = replacement if replacement not in {'', '-', '\u2014'} else None
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', cutoff):
                finding['error'] = f'Missing, qualified, or unsupported retirement date: {cutoff!r}.'
            else:
                try:
                    retirement = date.fromisoformat(cutoff)
                except ValueError:
                    finding['error'] = f'Invalid retirement date: {cutoff!r}.'
                else:
                    finding['retirement_date'] = cutoff
                    finding['days_remaining'] = (retirement - today).days
                    if lifecycle not in {'GA', 'Preview', 'Legacy', 'Deprecated', 'Retired'}:
                        finding['error'] = f'Missing or unsupported lifecycle state: {lifecycle!r}.'
                    elif lifecycle == 'Retired' and retirement > today:
                        finding['error'] = 'Retired lifecycle state conflicts with a future retirement date.'
                    else:
                        finding['status'] = 'attention' if finding['days_remaining'] <= WINDOW_DAYS else 'clear'
        report['findings'].append(finding)
    if report['errors'] or any(item['status'] == 'blocked' for item in report['findings']):
        report['status'] = 'blocked'
    elif any(item['status'] == 'attention' for item in report['findings']):
        report['status'] = 'attention'

    return report


def render_report(report: Report) -> str:
    """Render evidence as escaped text, never executable remote HTML."""
    titles = {'clear': 'Check complete', 'attention': 'Action required', 'blocked': 'Check blocked'}
    lines = [
        f"## {titles[report['status']]}", '', f"UTC check time: {report['checked_at']}", '',
        f"Source: {report['source_url']}", '',
        f"Window: {report['window_days']} calendar days, including overdue retirements.", '',
        'Scope: published base-model retirement dates only. Regional/SKU availability,',
        'earlier new-deployment cutoffs, and compatibility are not verified.',
        'Maintainers choose and validate replacements; this check never changes models.', '',
    ]
    for error in report['errors']:
        lines.extend([f'- {html.escape(error)}', ''])
    for finding in report['findings']:
        lines.extend([f"### {html.escape(finding['member'])}: {finding['status']}", ''])
        for label, value in finding.items():
            if label not in {'member', 'status'} and value is not None:
                lines.append(f'- {label.replace("_", " ")}: {html.escape(str(value))}')
        lines.append('')
    if report['status'] == 'clear':
        lines.extend(['Every approved model has an exact dated row; none is within the retirement window.', ''])

    return '\n'.join(lines)


def main() -> int:
    """Persist reports even when retrieval or manifest validation blocks the check."""
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--root', type = Path, default = Path(__file__).resolve().parents[1])
    parser.add_argument('--output-dir', type = Path, required = True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    try:
        models = load_models(args.root)
        report = check_models(models, fetch_schedule(), now)
    except (OSError, ValueError, urllib.error.URLError) as error:
        report = {
            'status': 'blocked', 'checked_at': now.isoformat(), 'source_url': SOURCE_URL,
            'window_days': WINDOW_DAYS, 'findings': [], 'errors': [f'{type(error).__name__}: {error}'],
        }
    args.output_dir.mkdir(parents = True, exist_ok = True)
    args.output_dir.joinpath('report.json').write_text(json.dumps(report, indent = 2) + '\n', encoding = 'utf-8', newline = '\n')
    markdown = render_report(report)
    args.output_dir.joinpath('report.md').write_text(markdown, encoding = 'utf-8', newline = '\n')
    print(markdown)
    if report['status'] != 'clear':
        print(f"Model lifecycle check: {report['status']}. See the report for evidence and coverage gaps.", file = sys.stderr)

    return {'clear': 0, 'blocked': 1, 'attention': 2}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())
