"""Build self-contained HTML reports for APIM sample runs."""

import base64
import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from matplotlib.figure import Figure


@dataclass(frozen=True)
class HtmlText:
    """Describe escaped report text with optional bold tokens and line breaks."""

    text: str
    bold_tokens: tuple[str, ...] = ()
    preserve_line_breaks: bool = False


@dataclass(frozen=True)
class HtmlSuccess:
    """Describe an accessible success checkmark for a report table cell."""

    label: str


@dataclass(frozen=True)
class HtmlWarning:
    """Describe an accessible warning marker for a report table cell."""

    label: str


@dataclass(frozen=True)
class HtmlList:
    """Describe an escaped flush-left bullet list for a report table cell."""

    items: tuple[str, ...]


class HtmlReport:
    """Collect metrics, tables, figures, and links into a portable HTML report."""

    def __init__(self, title: str, subtitle: str = '') -> None:
        """Initialize an empty report."""
        self.title = title
        self.subtitle = subtitle
        self.sections: list[str] = []

    def add_metrics(self, title: str, metrics: dict[str, object], highlight_success: bool = True) -> None:
        """Add a compact grid of named values."""
        metric_items = ''.join(self._metric(label, value, highlight_success) for label, value in metrics.items())
        self.sections.append(self._section(title, f'<div class="metrics">{metric_items}</div>'))

    def add_success_callout(self, title: str, message: str) -> None:
        """Add a prominent accessible success message."""
        callout_html = (
            '<section class="status-callout status-success" role="status">'
            '<span class="status-icon" aria-hidden="true">&#10003;</span>'
            f'<div><h2>{html.escape(title)}</h2><p>{html.escape(message)}</p></div>'
            '</section>'
        )
        self.sections.append(callout_html)

    def add_info_callout(self, title: str, message: str) -> None:
        """Add a prominent accessible informational note."""
        callout_html = (
            '<section class="status-callout status-info" role="note">'
            '<span class="status-icon" aria-hidden="true">&#9432;</span>'
            f'<div><h2>{html.escape(title)}</h2><p>{html.escape(message)}</p></div>'
            '</section>'
        )
        self.sections.append(callout_html)

    def add_table(
        self,
        title: str | HtmlText,
        headers: list[str],
        rows: list[list[object]],
        description: str | HtmlText = '',
        column_widths: list[str] | None = None,
    ) -> None:
        """Add an accessible data table."""
        if column_widths is not None and len(column_widths) != len(headers):
            raise ValueError('Table column widths must match the header count')

        header_html = ''.join(f'<th scope="col">{html.escape(str(header))}</th>' for header in headers)
        row_html = ''.join(self._table_row(row) for row in rows)
        column_html = (
            ''
            if column_widths is None
            else '<colgroup>' + ''.join(f'<col style="width: {html.escape(width, quote=True)}">' for width in column_widths) + '</colgroup>'
        )
        table_html = f'<div class="table-wrap"><table>{column_html}<thead><tr>{header_html}</tr></thead><tbody>{row_html}</tbody></table></div>'
        body = self._paragraph(description) + table_html
        self.sections.append(self._section(title, body))

    def add_figure(self, title: str, figure: Figure, description: str | HtmlText = '') -> None:
        """Embed a matplotlib figure as a PNG data URI."""
        buffer = BytesIO()
        figure.savefig(buffer, format='png', bbox_inches='tight', dpi=140)
        encoded_figure = base64.b64encode(buffer.getvalue()).decode('ascii')
        figure_html = f'<img src="data:image/png;base64,{encoded_figure}" alt="{html.escape(title)}">'
        self.sections.append(self._section(title, self._paragraph(description) + figure_html))

    def add_links(self, title: str, links: dict[str, str]) -> None:
        """Add a list of links after validating their URL schemes."""
        link_items = ''.join(
            f'<li><a href="{html.escape(self._validated_url(url), quote=True)}">{html.escape(str(label))}</a></li>' for label, url in links.items()
        )
        self.sections.append(self._section(title, f'<ul class="links">{link_items}</ul>'))

    def write(self, output_path: Path) -> Path:
        """Write the self-contained report and return its resolved path."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        generated_at = datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')
        subtitle = f'<p class="subtitle">{html.escape(self.subtitle)}</p>' if self.subtitle else ''
        document = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(self.title)}</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; background: #f4f6f8; color: #1f2937; }}
    body {{ margin: 0; }}
    header {{ background: #12344d; color: #ffffff; padding: 2rem max(1rem, calc((100vw - 1180px) / 2)); }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 1.25rem 1rem 2rem; }}
    section {{ background: #ffffff; border: 1px solid #d0d7de; border-radius: 6px; margin: 0 0 1rem; padding: 1rem; }}
    h1, h2 {{ margin: 0 0 0.75rem; }}
    h1 {{ font-size: 1.8rem; }} h2 {{ color: #12344d; font-size: 1.2rem; }}
    p {{ line-height: 1.55; }} .subtitle {{ margin: 0; color: #e6edf3; }} .generated {{ color: #57606a; font-size: 0.9rem; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.75rem; }}
    .metric {{ border-left: 4px solid #0078d4; background: #f6f8fa; padding: 0.75rem; }}
    .metric-label {{ display: block; color: #57606a; font-size: 0.85rem; margin-bottom: 0.3rem; }}
    .metric-success {{ background: #146c43; border-left-color: #0a3622; color: #ffffff; }} .metric-success .metric-label {{ color: #ffffff; }}
    .status-callout {{ align-items: center; display: flex; gap: 0.85rem; }}
    .status-success {{ background: #146c43; border: 2px solid #0a3622; color: #ffffff; }}
    .status-success h2 {{ color: #ffffff; margin-bottom: 0.25rem; }} .status-success p {{ margin: 0; }}
    .status-info {{ background: #eaf2f8; border: 2px solid #005a9e; color: #1f2937; }}
    .status-info h2 {{ color: #12344d; margin-bottom: 0.25rem; }} .status-info p {{ margin: 0; }}
    .status-icon {{ font-size: 2rem; font-weight: bold; line-height: 1; }}
    .table-success {{ color: #198754; display: inline-block; font-size: 1.8rem; font-weight: 900; line-height: 1; }}
    .table-row-success td {{ background: #146c43; border-color: #0a3622; color: #ffffff; }} .table-row-success .table-success {{ color: #ffffff; }}
    .table-warning {{ color: #8a4b00; display: inline-block; font-size: 1.5rem; font-weight: 900; line-height: 1; }}
    .table-row-warning td {{ background: #fff3cd; border-color: #b45309; color: #3d2c00; }}
    .table-list {{ list-style: none; margin: 0; padding: 0; }}
    .table-list li {{ column-gap: 0.1rem; display: grid; grid-template-columns: 0.55rem 1fr; margin: 0 0 0.2rem; }}
    .table-list li::before {{ content: '\\2022'; }} .table-list li:last-child {{ margin-bottom: 0; }}
    .table-wrap {{ max-width: 100%; overflow-x: auto; }} table {{ border-collapse: collapse; table-layout: fixed; width: 100%; }}
    th, td {{ border: 1px solid #d0d7de; overflow-wrap: anywhere; padding: 0.55rem; text-align: left; vertical-align: top; word-break: break-word; }}
    th {{ background: #eaf2f8; color: #12344d; }}
    img {{ display: block; height: auto; max-width: 100%; }} .links {{ line-height: 1.8; padding-left: 1.25rem; }}
    a {{ color: #005a9e; }} a:focus, a:hover {{ color: #003f6f; }}
  </style>
</head>
<body>
  <header><h1>{html.escape(self.title)}</h1>{subtitle}</header>
  <main><p class="generated">Generated {generated_at}</p>{''.join(self.sections)}</main>
</body>
</html>
"""
        output_path.write_text(document, encoding='utf-8', newline='\n')

        return output_path.resolve()

    @staticmethod
    def _paragraph(text: str | HtmlText) -> str:
        """Render optional escaped paragraph text."""
        return f'<p>{HtmlReport._render_text(text)}</p>' if text else ''

    @staticmethod
    def _section(title: str | HtmlText, body: str) -> str:
        """Wrap report content in a named section."""
        return f'<section><h2>{HtmlReport._render_text(title)}</h2>{body}</section>'

    @staticmethod
    def _metric(label: object, value: object, highlight_success: bool = True) -> str:
        """Render one metric, highlighting perfect run outcomes."""
        normalized_label = str(label).strip().casefold()
        normalized_value = str(value).strip().casefold()
        is_perfect = (normalized_label == 'result' and normalized_value == 'passed') or (
            normalized_label == 'success rate' and re.fullmatch(r'100(?:\.0+)?%', normalized_value)
        )
        success_class = ' metric-success' if highlight_success and is_perfect else ''

        return (
            f'<div class="metric{success_class}"><span class="metric-label">{html.escape(str(label))}</span>'
            f'<strong>{html.escape(str(value))}</strong></div>'
        )

    @staticmethod
    def _table_row(row: list[object]) -> str:
        """Render one table row, highlighting caller-perfect and warning scenarios."""
        if any(isinstance(value, HtmlWarning) for value in row):
            row_class = ' class="table-row-warning"'
        elif any(isinstance(value, HtmlSuccess) for value in row):
            row_class = ' class="table-row-success"'
        else:
            row_class = ''
        cells = ''.join(f'<td>{HtmlReport._render_text(value)}</td>' for value in row)

        return f'<tr{row_class}>{cells}</tr>'

    @staticmethod
    def _render_text(value: object) -> str:
        """Render escaped text with narrowly scoped formatting when requested."""
        if isinstance(value, HtmlSuccess):
            return f'<span class="table-success" role="img" aria-label="{html.escape(value.label, quote=True)}">&#10003;</span>'

        if isinstance(value, HtmlWarning):
            return f'<span class="table-warning" role="img" aria-label="{html.escape(value.label, quote=True)}">&#9888;</span>'

        if isinstance(value, HtmlList):
            list_items = ''.join(f'<li>{html.escape(item)}</li>' for item in value.items)
            return f'<ul class="table-list">{list_items}</ul>'

        if not isinstance(value, HtmlText):
            return html.escape(str(value))

        bold_tokens = sorted({token for token in value.bold_tokens if token}, key=len, reverse=True)
        if not bold_tokens:
            rendered_text = html.escape(value.text)
        else:
            pattern = '|'.join(re.escape(token) for token in bold_tokens)
            fragments = []
            last_end = 0
            for match in re.finditer(pattern, value.text):
                fragments.append(html.escape(value.text[last_end : match.start()]))
                fragments.append(f'<strong>{html.escape(match.group())}</strong>')
                last_end = match.end()
            fragments.append(html.escape(value.text[last_end:]))
            rendered_text = ''.join(fragments)

        return rendered_text.replace('\n', '<br>') if value.preserve_line_breaks else rendered_text

    @staticmethod
    def _validated_url(url: str) -> str:
        """Return a safe report link URL."""
        parsed_url = urlparse(url)
        if parsed_url.scheme not in {'file', 'http', 'https'}:
            raise ValueError(f'Unsupported report link scheme: {parsed_url.scheme}')

        return url
