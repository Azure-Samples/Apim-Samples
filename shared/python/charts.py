"""
Module providing charting functions.

This module will likely be moved to the /shared/python directory in the future once it's more generic.
"""

import json
from collections import Counter

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from apimtypes import HttpStatusCode
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle as pltRectangle


def _format_request_count(count: int) -> str:
    """Return a request count with the grammatically correct noun."""
    noun = 'request' if count == 1 else 'requests'

    return f'{count} {noun}'


def _format_percentage(count: int, total: int) -> str:
    """Return a percentage while handling an empty denominator."""
    return f'{count / total:.1%}' if total else '0.0%'


# ------------------------------
#    CLASSES
# ------------------------------


class BarChart:
    """
    Class for creating bar charts with colored bars based on backend indexes.
    """

    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(
        self,
        title: str,
        x_label: str,
        y_label: str,
        api_results: list[dict],
        fig_text: str = None,
        vertical_separator: tuple[float, str] | list[tuple[float, str]] | None = None,
        backend_labels: dict[int, str] | None = None,
    ) -> None:
        """
        Initialize the BarChart with API results.

        Args:
            title (str): The title of the chart.
            x_label (str): The label for the x-axis.
            y_label (str): The label for the y-axis.
            api_results (list[dict]): List of API result dictionaries.
            fig_text (str, optional): Additional figure text to display. Defaults to None.
            vertical_separator (tuple[float, str] | list[tuple[float, str]], optional): Either a
                single (x_position, label) tuple or a list of such tuples. Each entry draws a
                dashed vertical separator at the given x (in bar-index units) with an annotation.
            backend_labels (dict[int, str], optional): Human-readable legend labels keyed by
                backend index. Missing indexes use the default numeric label.
        """
        self.title = title
        self.x_label = x_label
        self.y_label = y_label
        self.api_results = api_results
        self.fig_text = fig_text
        self.vertical_separator = vertical_separator
        self.backend_labels = backend_labels or {}

    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def plot(self) -> None:
        """
        Plot the bar chart based on the provided API results.
        """
        self._plot_barchart(self.api_results)

    def render(self) -> Figure:
        """Render the bar chart without displaying it and return the figure."""
        return self._plot_barchart(self.api_results, show=False)

    # ------------------------------
    #    PRIVATE METHODS
    # ------------------------------

    def _plot_barchart(self, api_results: list[dict], show: bool = True) -> Figure:
        """
        Internal method to plot the bar chart.

        Args:
            api_results (list[dict]): List of API result dictionaries.
        """
        # Parse the data into a DataFrame
        rows = []

        for entry in api_results:
            run = entry['run']
            response_time = entry['response_time']
            status_code = entry['status_code']

            if status_code == HttpStatusCode.OK and entry['response']:
                try:
                    resp = json.loads(entry['response'])
                    backend_index = resp.get('index', 99)
                except Exception:
                    backend_index = 99
            else:
                backend_index = 99
            rows.append(
                {
                    'Run': run,
                    'Response Time (ms)': response_time * 1000,  # Convert to ms
                    'Backend Index': backend_index,
                    'Status Code': status_code,
                }
            )

        df = pd.DataFrame(rows)

        mpl.rcParams['figure.figsize'] = [17, 11]

        # Define a color map for each successful backend and conspicuous error categories.
        backend_indexes_200 = sorted(df[df['Status Code'] == HttpStatusCode.OK]['Backend Index'].unique())
        color_palette = ['lightyellow', 'lightblue', 'lightgreen', 'plum', 'orange']
        color_map_200 = {idx: color_palette[i % len(color_palette)] for i, idx in enumerate(backend_indexes_200)}
        backend_request_counts = Counter(row['Backend Index'] for row in rows if row['Status Code'] == HttpStatusCode.OK)
        request_count = len(api_results)
        response_count = len(rows)
        successful_response_count = sum(200 <= row['Status Code'] < 300 for row in rows)
        client_error_count = sum(400 <= row['Status Code'] < 500 for row in rows)
        server_error_count = sum(500 <= row['Status Code'] < 600 for row in rows)
        other_error_count = sum(row['Status Code'] != HttpStatusCode.OK and not 400 <= row['Status Code'] < 600 for row in rows)
        client_error_color = '#d83b01'
        server_error_color = '#a4262c'
        other_error_color = '#5c2d91'

        bar_colors = []
        for _, row in df.iterrows():
            if row['Status Code'] == HttpStatusCode.OK:
                bar_colors.append(color_map_200.get(row['Backend Index'], 'gray'))
            elif 400 <= row['Status Code'] < 500:
                bar_colors.append(client_error_color)
            elif 500 <= row['Status Code'] < 600:
                bar_colors.append(server_error_color)
            else:
                bar_colors.append(other_error_color)

        # Plot the dataframe with colored bars
        ax = df.plot(kind='bar', x='Run', y='Response Time (ms)', color=bar_colors, legend=False, edgecolor='black')

        # Add a dynamic legend based on backend indexes present in the data.
        legend_labels = []
        legend_names = []
        for idx in backend_indexes_200:
            legend_labels.append(pltRectangle((0, 0), 1, 1, color=color_map_200[idx]))
            backend_label = self.backend_labels.get(idx, f'Backend index {idx}')
            legend_names.append(f'{backend_label} - {_format_request_count(backend_request_counts[idx])}')
        if client_error_count:
            legend_labels.append(pltRectangle((0, 0), 1, 1, color=client_error_color))
            legend_names.append(f'!!! 4xx CLIENT ERRORS - {_format_request_count(client_error_count)} !!!')
        if server_error_count:
            legend_labels.append(pltRectangle((0, 0), 1, 1, color=server_error_color))
            legend_names.append(f'!!! 5xx SERVER ERRORS - {_format_request_count(server_error_count)} !!!')
        if other_error_count:
            legend_labels.append(pltRectangle((0, 0), 1, 1, color=other_error_color))
            legend_names.append(f'!!! OTHER NON-200 RESPONSES - {_format_request_count(other_error_count)} !!!')
        ax.legend(legend_labels, legend_names, loc='upper left', bbox_to_anchor=(1.01, 1), borderpad=1.2)

        has_errors = client_error_count or server_error_count or other_error_count
        status_summary = (
            f'Requests: {request_count}\n'
            f'Responses: {response_count} ({_format_percentage(response_count, request_count)})\n\n'
            f'2xx: {successful_response_count} ({_format_percentage(successful_response_count, response_count)})\n'
            f'4xx: {client_error_count} ({_format_percentage(client_error_count, response_count)})\n'
            f'5xx: {server_error_count} ({_format_percentage(server_error_count, response_count)})'
        )
        ax.text(
            1.02,
            0.62,
            status_summary,
            transform=ax.transAxes,
            ha='left',
            va='top',
            fontsize=11,
            color=server_error_color if has_errors else 'black',
            fontweight='bold' if has_errors else 'normal',
            bbox={
                'boxstyle': 'square,pad=0.8',
                'facecolor': '#fff1f0' if has_errors else 'white',
                'edgecolor': server_error_color if has_errors else 'lightgray',
                'linewidth': 2.5 if has_errors else 1,
            },
        )

        plt.title(self.title)
        plt.xlabel(self.x_label)
        plt.ylabel(self.y_label)
        plt.xticks(rotation=0)

        # Exclude high outliers for average calculation
        valid_200 = df[(df['Status Code'] == HttpStatusCode.OK)].copy()

        # Exclude high outliers (e.g., above 95th percentile)
        if not valid_200.empty:
            upper = valid_200['Response Time (ms)'].quantile(0.95)
            filtered = valid_200[valid_200['Response Time (ms)'] <= upper]
            if not filtered.empty:
                avg = filtered['Response Time (ms)'].mean()
                avg_label = f'Mean APIM response time: {avg:.1f} ms'
                plt.axhline(y=avg, color='b', linestyle='--')
                plt.text(len(df) - 1, avg, avg_label, color='b', va='bottom', ha='right', fontsize=10)

        # Reserve room for the right-side summary and explanatory text below the x-axis.
        plt.subplots_adjust(right=0.76, bottom=0.3)
        plt.figtext(0.08, 0.03, wrap=True, ha='left', fontsize=11, s=self.fig_text)

        # Optional vertical separator(s) with annotation (e.g. wait-period marker). Accepts
        # either a single (x, label) tuple or a list of them. The label is nudged slightly to
        # the left of the line (in bar-position units) so the text does not visually touch the
        # dashed separator.
        if self.vertical_separator is not None:
            separators = self.vertical_separator if isinstance(self.vertical_separator, list) else [self.vertical_separator]
            y_min, y_max = ax.get_ylim()
            for sep_x, sep_label in separators:
                plt.axvline(x=sep_x, color='gray', linestyle='--', linewidth=4, alpha=0.7)
                plt.text(sep_x - 0.25, y_max * 0.95, sep_label, color='dimgray', rotation=90, va='top', ha='right', fontsize=10)

        if show:
            plt.show()

        return ax.figure
