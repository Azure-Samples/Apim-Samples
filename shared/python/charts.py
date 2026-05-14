"""
Module providing charting functions.

This module will likely be moved to the /shared/python directory in the future once it's more generic.
"""

import json

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from apimtypes import HttpStatusCode
from matplotlib.patches import Rectangle as pltRectangle

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
        """
        self.title = title
        self.x_label = x_label
        self.y_label = y_label
        self.api_results = api_results
        self.fig_text = fig_text
        self.vertical_separator = vertical_separator

    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def plot(self) -> None:
        """
        Plot the bar chart based on the provided API results.
        """
        self._plot_barchart(self.api_results)

    # ------------------------------
    #    PRIVATE METHODS
    # ------------------------------

    def _plot_barchart(self, api_results: list[dict]) -> None:
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

        mpl.rcParams['figure.figsize'] = [15, 8]

        # Define a color map for each backend index (OK) and errors (non-OK always lightcoral)
        backend_indexes_200 = sorted(df[df['Status Code'] == HttpStatusCode.OK]['Backend Index'].unique())
        color_palette = ['lightyellow', 'lightblue', 'lightgreen', 'plum', 'orange']
        color_map_200 = {idx: color_palette[i % len(color_palette)] for i, idx in enumerate(backend_indexes_200)}

        bar_colors = []
        for _, row in df.iterrows():
            if row['Status Code'] == HttpStatusCode.OK:
                bar_colors.append(color_map_200.get(row['Backend Index'], 'gray'))
            else:
                bar_colors.append('lightcoral')

        # Plot the dataframe with colored bars
        ax = df.plot(kind='bar', x='Run', y='Response Time (ms)', color=bar_colors, legend=False, edgecolor='black')

        # Add dynamic legend based on backend indexes present in the data. We let the legend
        # auto-size to its contents and use `borderpad` to add internal padding (especially at
        # the top) so entries do not visually touch the legend frame.
        legend_labels = []
        legend_names = []
        for idx in backend_indexes_200:
            legend_labels.append(pltRectangle((0, 0), 1, 1, color=color_map_200[idx]))
            legend_names.append(f'Backend index {idx} (200)')
        legend_labels.append(pltRectangle((0, 0), 1, 1, color='lightcoral'))
        legend_names.append('Error/Other (non-200)')
        ax.legend(legend_labels, legend_names, borderpad=1.5)

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

        # Add figtext under the chart
        plt.figtext(0.13, -0.1, wrap=True, ha='left', fontsize=11, s=self.fig_text)

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

        plt.show()
