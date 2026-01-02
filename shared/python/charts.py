"""
Module providing charting functions.

This module will likely be moved to the /shared/python directory in the future once it's more generic.
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle as pltRectangle
import matplotlib as mpl


# ------------------------------
#    CLASSES
# ------------------------------

# TODO: A specialized barchart for multi-request scenarios should be created and use a more generic base class barchart.
# TODO: BarChart should be a base class for other chart types once it's more generic.
class BarChart:
    """
    Class for creating bar charts with colored bars based on backend indexes.
    """

    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, title: str, x_label: str, y_label: str, api_results: list[dict], fig_text: str = None) -> None:
        """
        Initialize the BarChart with API results.

        Args:
            title (str): The title of the chart.
            x_label (str): The label for the x-axis.
            y_label (str): The label for the y-axis.
            api_results (list[dict]): List of API result dictionaries.
            fig_text (str, optional): Additional figure text to display. Defaults to None.
        """
        self.title = title
        self.x_label = x_label
        self.y_label = y_label
        self.api_results = api_results
        self.fig_text = fig_text


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

            if status_code == 200 and entry['response']:
                try:
                    resp = json.loads(entry['response'])
                    backend_index = resp.get('index', 99)
                except Exception:
                    backend_index = 99
            else:
                backend_index = 99
            rows.append({
                'Run': run,
                'Response Time (ms)': response_time * 1000,  # Convert to ms
                'Backend Index': backend_index,
                'Status Code': status_code
            })

        df = pd.DataFrame(rows)

        mpl.rcParams['figure.figsize'] = [15, 7]

        # Define a color map for each backend index (200) and errors (non-200 always lightcoral)
        backend_indexes_200 = sorted(df[df['Status Code'] == 200]['Backend Index'].unique())
        color_palette = ['lightyellow', 'lightblue', 'lightgreen', 'plum', 'orange']
        color_map_200 = {idx: color_palette[i % len(color_palette)] for i, idx in enumerate(backend_indexes_200)}

        bar_colors = []
        for _, row in df.iterrows():
            if row['Status Code'] == 200:
                bar_colors.append(color_map_200.get(row['Backend Index'], 'gray'))
            else:
                bar_colors.append('lightcoral')

        # Plot the dataframe with colored bars
        ax = df.plot(
            kind='bar',
            x='Run',
            y='Response Time (ms)',
            color=bar_colors,
            legend=False,
            edgecolor='black'
        )

        # Add dynamic legend based on backend indexes present in the data
        legend_labels = []
        legend_names = []
        for idx in backend_indexes_200:
            legend_labels.append(pltRectangle((0, 0), 1, 1, color=color_map_200[idx]))
            legend_names.append(f'Backend index {idx} (200)')
        legend_labels.append(pltRectangle((0, 0), 1, 1, color='lightcoral'))
        legend_names.append('Error/Other (non-200)')
        ax.legend(legend_labels, legend_names)

        plt.title(self.title)
        plt.xlabel(self.x_label)
        plt.ylabel(self.y_label)
        plt.xticks(rotation = 0)

        # Exclude high outliers for average calculation
        valid_200 = df[(df['Status Code'] == 200)].copy()

        # Exclude high outliers (e.g., above 95th percentile)
        if not valid_200.empty:
            upper = valid_200['Response Time (ms)'].quantile(0.95)
            filtered = valid_200[valid_200['Response Time (ms)'] <= upper]
            if not filtered.empty:
                avg = filtered['Response Time (ms)'].mean()
                avg_label = f'Mean APIM response time: {avg:.1f} ms'
                plt.axhline(y = avg, color = 'b', linestyle = '--')
                plt.text(len(df) - 1, avg, avg_label, color = 'b', va = 'bottom', ha = 'right', fontsize = 10)

        # Add figtext under the chart
        plt.figtext(0.13, -0.1, wrap = True, ha = 'left', fontsize = 11, s = self.fig_text)

        plt.show()
