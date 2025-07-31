"""
Unit tests for the Charts module.
"""

import pytest
from unittest.mock import patch, MagicMock, call
import sys
import os
import json

# Add the shared/python directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shared', 'python'))

from charts import BarChart


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
        assert call_args[0]['Backend Index'] == 0    # Valid index 0
        assert call_args[1]['Backend Index'] == 99   # Missing index field
        assert call_args[2]['Backend Index'] == 99   # Empty JSON
        assert call_args[3]['Backend Index'] == 99   # Non-200 status
