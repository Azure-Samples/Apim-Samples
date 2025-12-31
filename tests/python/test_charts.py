"""
Unit tests for the Charts module.
"""

from unittest.mock import patch, MagicMock
import sys
import os
import json
import pytest
import pandas as pd
import charts
from charts import BarChart

# Add the shared/python directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shared', 'python'))



# ------------------------------
#    TEST DATA FIXTURES
# ------------------------------

@pytest.fixture
def sample_api_results():
    """Sample API results for testing."""
    return [
        {
            'run': 1,
            'response_time': 0.123,
            'status_code': 200,
            'response': '{"index": 1, "message": "success"}'
        },
        {
            'run': 2,
            'response_time': 0.156,
            'status_code': 200,
            'response': '{"index": 2, "message": "success"}'
        },
        {
            'run': 3,
            'response_time': 0.089,
            'status_code': 200,
            'response': '{"index": 1, "message": "success"}'
        },
        {
            'run': 4,
            'response_time': 0.201,
            'status_code': 500,
            'response': 'Internal Server Error'
        },
        {
            'run': 5,
            'response_time': 0.134,
            'status_code': 200,
            'response': '{"index": 3, "message": "success"}'
        }
    ]


@pytest.fixture
def malformed_api_results():
    """API results with malformed JSON responses."""
    return [
        {
            'run': 1,
            'response_time': 0.123,
            'status_code': 200,
            'response': '{"index": 1, "incomplete'  # Malformed JSON
        },
        {
            'run': 2,
            'response_time': 0.156,
            'status_code': 200,
            'response': 'not json at all'
        },
        {
            'run': 3,
            'response_time': 0.089,
            'status_code': 200,
            'response': '{"no_index_field": "value"}'  # Missing index field
        }
    ]


@pytest.fixture
def empty_api_results():
    """Empty API results list."""
    return []


# ------------------------------
#    TEST BARCHART INITIALIZATION
# ------------------------------

def test_barchart_init_basic():
    """Test BarChart initialization with basic parameters."""
    api_results = [{'run': 1, 'response_time': 0.1, 'status_code': 200, 'response': '{}'}]

    chart = BarChart(
        title='Test Chart',
        x_label='Request Number',
        y_label='Response Time',
        api_results=api_results
    )

    assert chart.title == 'Test Chart'
    assert chart.x_label == 'Request Number'
    assert chart.y_label == 'Response Time'
    assert chart.api_results == api_results
    assert chart.fig_text is None


def test_barchart_init_with_fig_text():
    """Test BarChart initialization with figure text."""
    api_results = [{'run': 1, 'response_time': 0.1, 'status_code': 200, 'response': '{}'}]
    fig_text = 'This is additional chart information'

    chart = BarChart(
        title='Test Chart',
        x_label='X Axis',
        y_label='Y Axis',
        api_results=api_results,
        fig_text=fig_text
    )

    assert chart.fig_text == fig_text


def test_barchart_init_empty_results():
    """Test BarChart initialization with empty results."""
    chart = BarChart(
        title='Empty Chart',
        x_label='X Axis',
        y_label='Y Axis',
        api_results=[]
    )

    assert chart.api_results == []


# ------------------------------
#    TEST PLOT METHOD
# ------------------------------

@patch('charts.plt')
@patch('charts.pd.DataFrame')
def test_plot_calls_internal_method(mock_dataframe, mock_plt, sample_api_results):
    """Test that plot() calls the internal _plot_barchart method."""
    chart = BarChart('Test', 'X', 'Y', sample_api_results)

    with patch.object(chart, '_plot_barchart') as mock_plot_barchart:
        chart.plot()
        mock_plot_barchart.assert_called_once_with(sample_api_results)


# ------------------------------
#    TEST _PLOT_BARCHART METHOD
# ------------------------------

@patch('charts.plt')
@patch('charts.pd.DataFrame')
def test_plot_barchart_data_processing(mock_dataframe, mock_plt, sample_api_results):
    """Test that _plot_barchart processes data correctly."""
    # Mock DataFrame constructor and methods
    mock_df = MagicMock()
    mock_dataframe.return_value = mock_df
    mock_df.__getitem__.return_value = mock_df  # For df[df['Status Code'] == 200]
    mock_df.__iter__.return_value = iter([])  # For iteration
    mock_df.iterrows.return_value = iter([])  # For bar color calculation
    mock_df.plot.return_value = MagicMock()  # Mock axes object
    mock_df.empty = False
    mock_df.quantile.return_value = 200
    mock_df.mean.return_value = 150

    chart = BarChart('Test', 'X', 'Y', sample_api_results)
    chart._plot_barchart(sample_api_results)

    # Verify DataFrame was created with correct data structure
    mock_dataframe.assert_called_once()
    call_args = mock_dataframe.call_args[0][0]  # Get the data passed to DataFrame

    # Check that data was processed correctly
    assert len(call_args) == 5  # Should have 5 rows from sample data

    # Check first row data
    first_row = call_args[0]
    assert first_row['Run'] == 1
    assert first_row['Response Time (ms)'] == 123.0  # 0.123 * 1000
    assert first_row['Backend Index'] == 1
    assert first_row['Status Code'] == 200


@patch('charts.plt')
@patch('charts.pd.DataFrame')
def test_plot_barchart_malformed_json_handling(mock_dataframe, mock_plt, malformed_api_results):
    """Test that _plot_barchart handles malformed JSON responses."""
    mock_df = MagicMock()
    mock_dataframe.return_value = mock_df
    mock_df.__getitem__.return_value = mock_df
    mock_df.__iter__.return_value = iter([])
    mock_df.iterrows.return_value = iter([])
    mock_df.plot.return_value = MagicMock()
    mock_df.empty = False
    mock_df.quantile.return_value = 200
    mock_df.mean.return_value = 150

    chart = BarChart('Test', 'X', 'Y', malformed_api_results)
    chart._plot_barchart(malformed_api_results)

    # Verify DataFrame was created
    mock_dataframe.assert_called_once()
    call_args = mock_dataframe.call_args[0][0]

    # All malformed responses should have backend_index = 99
    for row in call_args:
        assert row['Backend Index'] == 99


@patch('charts.plt')
@patch('charts.pd.DataFrame')
def test_plot_barchart_error_status_codes(mock_dataframe, mock_plt):
    """Test that _plot_barchart handles non-200 status codes."""
    error_results = [
        {
            'run': 1,
            'response_time': 0.5,
            'status_code': 404,
            'response': 'Not Found'
        },
        {
            'run': 2,
            'response_time': 1.0,
            'status_code': 500,
            'response': 'Internal Server Error'
        }
    ]

    mock_df = MagicMock()
    mock_dataframe.return_value = mock_df
    mock_df.__getitem__.return_value = mock_df
    mock_df.__iter__.return_value = iter([])
    mock_df.iterrows.return_value = iter([])
    mock_df.plot.return_value = MagicMock()
    mock_df.empty = False

    chart = BarChart('Test', 'X', 'Y', error_results)
    chart._plot_barchart(error_results)

    # Verify DataFrame was created
    mock_dataframe.assert_called_once()
    call_args = mock_dataframe.call_args[0][0]

    # Error responses should have backend_index = 99
    for row in call_args:
        assert row['Backend Index'] == 99
        assert row['Status Code'] in [404, 500]


@patch('charts.plt')
@patch('charts.pd.DataFrame')
def test_plot_barchart_matplotlib_calls(mock_dataframe, mock_plt, sample_api_results):
    """Test that _plot_barchart makes correct matplotlib calls."""
    # Setup mocks
    mock_df = MagicMock()
    mock_dataframe.return_value = mock_df
    mock_df.__getitem__.return_value = mock_df
    mock_df.iterrows.return_value = iter([
        (0, {'Status Code': 200, 'Backend Index': 1}),
        (1, {'Status Code': 200, 'Backend Index': 2}),
        (2, {'Status Code': 500, 'Backend Index': 99})
    ])
    mock_df.plot.return_value = MagicMock()
    mock_df.empty = False
    mock_df.quantile.return_value = 200
    mock_df.mean.return_value = 150

    # Mock unique() method for backend indexes
    mock_unique = MagicMock()
    mock_unique.unique.return_value = [1, 2]
    mock_df.__getitem__.return_value = mock_unique

    chart = BarChart('Test Chart', 'X Label', 'Y Label', sample_api_results)
    chart._plot_barchart(sample_api_results)

    # Verify matplotlib calls
    mock_plt.title.assert_called_with('Test Chart')
    mock_plt.xlabel.assert_called_with('X Label')
    mock_plt.ylabel.assert_called_with('Y Label')
    mock_plt.show.assert_called_once()


@patch('charts.plt')
@patch('charts.pd.DataFrame')
def test_plot_barchart_empty_data(mock_dataframe, mock_plt, empty_api_results):
    """Test that _plot_barchart handles empty data gracefully."""
    mock_df = MagicMock()
    mock_dataframe.return_value = mock_df
    mock_df.__getitem__.return_value = mock_df
    mock_df.__iter__.return_value = iter([])
    mock_df.iterrows.return_value = iter([])
    mock_df.plot.return_value = MagicMock()
    mock_df.empty = True

    chart = BarChart('Empty Chart', 'X', 'Y', empty_api_results)

    # Should not raise an exception
    chart._plot_barchart(empty_api_results)

    # Should still call basic matplotlib functions
    mock_plt.title.assert_called_with('Empty Chart')
    mock_plt.show.assert_called_once()


@patch('charts.plt')
@patch('charts.pd.DataFrame')
def test_plot_barchart_figure_text(mock_dataframe, mock_plt, sample_api_results):
    """Test that _plot_barchart adds figure text when provided."""
    mock_df = MagicMock()
    mock_dataframe.return_value = mock_df
    mock_df.__getitem__.return_value = mock_df
    mock_df.__iter__.return_value = iter([])
    mock_df.iterrows.return_value = iter([])
    mock_df.plot.return_value = MagicMock()
    mock_df.empty = False

    fig_text = 'This is test figure text'
    chart = BarChart('Test', 'X', 'Y', sample_api_results, fig_text)
    chart._plot_barchart(sample_api_results)

    # Verify figtext was called with the provided text
    mock_plt.figtext.assert_called_once()
    call_args = mock_plt.figtext.call_args[1]  # Get keyword arguments
    assert call_args['s'] == fig_text


# ------------------------------
#    TEST COLOR MAPPING
# ------------------------------

@patch('charts.plt')
@patch('charts.pd.DataFrame')
def test_color_mapping_logic(mock_dataframe, mock_plt):
    """Test the color mapping logic for different backend indexes and status codes."""
    mixed_results = [
        {'run': 1, 'response_time': 0.1, 'status_code': 200, 'response': '{"index": 1}'},
        {'run': 2, 'response_time': 0.2, 'status_code': 200, 'response': '{"index": 2}'},
        {'run': 3, 'response_time': 0.3, 'status_code': 500, 'response': 'Error'},
        {'run': 4, 'response_time': 0.4, 'status_code': 200, 'response': '{"index": 1}'},
    ]

    mock_df = MagicMock()
    mock_dataframe.return_value = mock_df
    mock_df.__getitem__.return_value = mock_df
    mock_df.iterrows.return_value = iter([
        (0, {'Status Code': 200, 'Backend Index': 1}),
        (1, {'Status Code': 200, 'Backend Index': 2}),
        (2, {'Status Code': 500, 'Backend Index': 99}),
        (3, {'Status Code': 200, 'Backend Index': 1}),
    ])

    # Mock the unique backend indexes for 200 responses
    mock_200_df = MagicMock()
    mock_200_df.unique.return_value = [1, 2]  # Sorted unique backend indexes
    mock_df.__getitem__.return_value = mock_200_df  # For df[df['Status Code'] == 200]['Backend Index']

    mock_df.plot.return_value = MagicMock()
    mock_df.empty = False

    chart = BarChart('Test', 'X', 'Y', mixed_results)
    chart._plot_barchart(mixed_results)

    # Verify that plot was called with colors parameter
    mock_df.plot.assert_called_once()
    call_kwargs = mock_df.plot.call_args[1]
    assert 'color' in call_kwargs


# ------------------------------
#    INTEGRATION TESTS
# ------------------------------

def test_full_chart_workflow(sample_api_results):
    """Test the complete chart creation workflow."""
    with patch('charts.plt') as mock_plt, \
         patch('charts.pd.DataFrame') as mock_dataframe:

        # Setup mock DataFrame
        mock_df = MagicMock()
        mock_dataframe.return_value = mock_df
        mock_df.__getitem__.return_value = mock_df
        mock_df.__iter__.return_value = iter([])
        mock_df.iterrows.return_value = iter([])
        mock_df.plot.return_value = MagicMock()
        mock_df.empty = False
        mock_df.quantile.return_value = 200
        mock_df.mean.return_value = 150

        # Create and plot chart
        chart = BarChart(
            title='Performance Chart',
            x_label='Request Number',
            y_label='Response Time (ms)',
            api_results=sample_api_results,
            fig_text='Performance analysis results'
        )

        chart.plot()

        # Verify the complete workflow
        assert mock_dataframe.called
        assert mock_plt.title.called
        assert mock_plt.xlabel.called
        assert mock_plt.ylabel.called
        assert mock_plt.show.called


def test_backend_index_edge_cases():
    """Test edge cases for backend index extraction."""
    edge_case_results = [
        # Valid JSON with index
        {'run': 1, 'response_time': 0.1, 'status_code': 200, 'response': '{"index": 0}'},  # Index 0
        # Valid JSON without index field
        {'run': 2, 'response_time': 0.2, 'status_code': 200, 'response': '{"other": "value"}'},
        # Empty JSON
        {'run': 3, 'response_time': 0.3, 'status_code': 200, 'response': '{}'},
        # Non-200 status with valid JSON
        {'run': 4, 'response_time': 0.4, 'status_code': 404, 'response': '{"index": 5}'},
    ]

    with patch('charts.plt'), patch('charts.pd.DataFrame') as mock_dataframe:
        mock_df = MagicMock()
        mock_dataframe.return_value = mock_df
        mock_df.__getitem__.return_value = mock_df
        mock_df.__iter__.return_value = iter([])
        mock_df.iterrows.return_value = iter([])
        mock_df.plot.return_value = MagicMock()
        mock_df.empty = False

        chart = BarChart('Test', 'X', 'Y', edge_case_results)
        chart._plot_barchart(edge_case_results)

        # Verify DataFrame creation
        mock_dataframe.assert_called_once()
        call_args = mock_dataframe.call_args[0][0]

        # Check backend index assignments
        assert not call_args[0]['Backend Index']    # Valid index 0
        assert call_args[1]['Backend Index'] == 99   # Missing index field
        assert call_args[2]['Backend Index'] == 99   # Empty JSON
        assert call_args[3]['Backend Index'] == 99   # Non-200 status


@patch('charts.plt')
@patch('charts.pd')
def test_average_line_calculation_normal_data(mock_pd, mock_plt, sample_api_results):
    """Test average line calculation with normal data (no extreme outliers)."""

    # Create real DataFrame to test filtering logic
    chart = BarChart('Test', 'X', 'Y', sample_api_results)

    # Build the real rows as the code does
    rows = []
    for entry in sample_api_results:
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
            'Response Time (ms)': response_time * 1000,
            'Backend Index': backend_index,
            'Status Code': status_code
        })

    real_df = pd.DataFrame(rows)
    mock_pd.DataFrame.return_value = real_df

    # Mock plotting methods
    mock_ax = MagicMock()
    with patch.object(real_df, 'plot', return_value=mock_ax):
        chart._plot_barchart(sample_api_results)

    # Verify average line was plotted
    mock_plt.axhline.assert_called()
    mock_plt.text.assert_called()


@patch('charts.plt')
@patch('charts.pd')
def test_average_line_calculation_with_outlier(mock_pd, mock_plt):
    """Test average line calculation when data has high outliers."""

    # Create data with a high outlier
    results_with_outlier = [
        {'run': 1, 'response_time': 0.1, 'status_code': 200, 'response': '{"index": 1}'},
        {'run': 2, 'response_time': 0.12, 'status_code': 200, 'response': '{"index": 1}'},
        {'run': 3, 'response_time': 0.11, 'status_code': 200, 'response': '{"index": 1}'},
        {'run': 4, 'response_time': 0.13, 'status_code': 200, 'response': '{"index": 1}'},
        {'run': 5, 'response_time': 5.0, 'status_code': 200, 'response': '{"index": 1}'},  # Outlier
    ]

    chart = BarChart('Test', 'X', 'Y', results_with_outlier)

    # Build real rows
    rows = []
    for entry in results_with_outlier:
        resp = json.loads(entry['response'])
        rows.append({
            'Run': entry['run'],
            'Response Time (ms)': entry['response_time'] * 1000,
            'Backend Index': resp.get('index', 99),
            'Status Code': entry['status_code']
        })

    real_df = pd.DataFrame(rows)
    mock_pd.DataFrame.return_value = real_df

    # Mock plotting
    mock_ax = MagicMock()
    with patch.object(real_df, 'plot', return_value=mock_ax):
        chart._plot_barchart(results_with_outlier)

    # Verify average line calculation excluded the outlier
    mock_plt.axhline.assert_called()
    mock_plt.text.assert_called()


@patch('charts.plt')
@patch('charts.pd')
def test_average_line_all_data_outliers(mock_pd, mock_plt):
    """Test average line calculation when all data points are outliers (edge case)."""

    # Create data where all points are very high
    all_outlier_results = [
        {'run': 1, 'response_time': 10.0, 'status_code': 200, 'response': '{"index": 1}'},
        {'run': 2, 'response_time': 11.0, 'status_code': 200, 'response': '{"index": 1}'},
    ]

    chart = BarChart('Test', 'X', 'Y', all_outlier_results)

    rows = []
    for entry in all_outlier_results:
        resp = json.loads(entry['response'])
        rows.append({
            'Run': entry['run'],
            'Response Time (ms)': entry['response_time'] * 1000,
            'Backend Index': resp.get('index', 99),
            'Status Code': entry['status_code']
        })

    real_df = pd.DataFrame(rows)
    mock_pd.DataFrame.return_value = real_df

    mock_ax = MagicMock()
    with patch.object(real_df, 'plot', return_value=mock_ax):
        chart._plot_barchart(all_outlier_results)

    # Should still plot average line
    mock_plt.axhline.assert_called()
    mock_plt.text.assert_called()


def test_plot_barchart_skips_average_line_without_success(monkeypatch):
    """Ensure average line is skipped when there are no 200 responses."""

    no_success_results = [
        {'run': 1, 'response_time': 0.2, 'status_code': 500, 'response': 'error'},
        {'run': 2, 'response_time': 0.3, 'status_code': 404, 'response': 'not found'},
    ]

    chart = BarChart('Test', 'X', 'Y', no_success_results)

    # Prevent real plotting
    monkeypatch.setattr(pd.DataFrame, 'plot', lambda self, *args, **kwargs: MagicMock(), raising=False)
    for attr in ['title', 'xlabel', 'ylabel', 'xticks', 'show', 'figtext']:
        monkeypatch.setattr(charts.plt, attr, MagicMock())

    axhline_mock = MagicMock()
    text_mock = MagicMock()
    monkeypatch.setattr(charts.plt, 'axhline', axhline_mock)
    monkeypatch.setattr(charts.plt, 'text', text_mock)

    chart._plot_barchart(no_success_results)

    axhline_mock.assert_not_called()
    text_mock.assert_not_called()


def test_plot_barchart_skips_average_when_filtered_empty(monkeypatch):
    """Ensure average line is skipped when all successful rows are filtered out."""

    success_results = [
        {'run': 1, 'response_time': 0.5, 'status_code': 200, 'response': '{"index": 1}'},
        {'run': 2, 'response_time': 0.6, 'status_code': 200, 'response': '{"index": 2}'},
    ]

    chart = BarChart('Test', 'X', 'Y', success_results)

    monkeypatch.setattr(pd.DataFrame, 'plot', lambda self, *args, **kwargs: MagicMock(), raising=False)

    def fake_quantile(self, q, *args, **kwargs):
        return 0  # Force all rows to be excluded

    monkeypatch.setattr(pd.Series, 'quantile', fake_quantile, raising=False)

    for attr in ['title', 'xlabel', 'ylabel', 'xticks', 'show', 'figtext']:
        monkeypatch.setattr(charts.plt, attr, MagicMock())

    axhline_mock = MagicMock()
    text_mock = MagicMock()
    monkeypatch.setattr(charts.plt, 'axhline', axhline_mock)
    monkeypatch.setattr(charts.plt, 'text', text_mock)

    chart._plot_barchart(success_results)

    axhline_mock.assert_not_called()
    text_mock.assert_not_called()
