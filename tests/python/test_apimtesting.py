"""
Unit tests for the ApimTesting module.
"""

from unittest.mock import patch
import sys
import os

# APIM Samples imports
from apimtesting import ApimTesting
from apimtypes import INFRASTRUCTURE

# Add the shared/python directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shared', 'python'))


# ------------------------------
#    TEST INITIALIZATION
# ------------------------------

def test_apimtesting_init_default():
    """Test ApimTesting initialization with default parameters."""
    testing = ApimTesting()

    assert testing.test_suite_name == 'APIM Tests'
    assert testing.sample_name is None
    assert testing.deployment is None
    assert not testing.tests_passed
    assert not testing.tests_failed
    assert not testing.total_tests
    assert testing.errors == []


def test_apimtesting_init_with_parameters():
    """Test ApimTesting initialization with custom parameters."""
    testing = ApimTesting(
        test_suite_name='Custom Tests',
        sample_name='test-sample',
        deployment=INFRASTRUCTURE.SIMPLE_APIM
    )

    assert testing.test_suite_name == 'Custom Tests'
    assert testing.sample_name == 'test-sample'
    assert testing.deployment == INFRASTRUCTURE.SIMPLE_APIM
    assert not testing.tests_passed
    assert not testing.tests_failed
    assert not testing.total_tests
    assert testing.errors == []


# ------------------------------
#    TEST VERIFY METHOD
# ------------------------------

def test_verify_success():
    """Test the verify method with matching values."""
    testing = ApimTesting()

    with patch('builtins.print') as mock_print:
        result = testing.verify(5, 5)

        assert result is True
        assert testing.tests_passed == 1
        assert not testing.tests_failed
        assert testing.total_tests == 1
        mock_print.assert_called_with('✅ Test 1: PASS')


def test_verify_failure():
    """Test the verify method with non-matching values."""
    testing = ApimTesting()

    with patch('builtins.print') as mock_print:
        result = testing.verify(5, 10)

        assert result is False
        assert not testing.tests_passed
        assert testing.tests_failed == 1
        assert testing.total_tests == 1
        assert len(testing.errors) == 1
        assert 'Value [5] does not match expected [10]' in testing.errors[0]
        mock_print.assert_called_with('❌ Test 1: FAIL - Value [5] does not match expected [10]')


def test_verify_multiple_tests():
    """Test the verify method with multiple test cases."""
    testing = ApimTesting()

    with patch('builtins.print'):
        # Test 1: Pass
        result1 = testing.verify('hello', 'hello')
        # Test 2: Fail
        result2 = testing.verify(1, 2)
        # Test 3: Pass
        result3 = testing.verify([1, 2, 3], [1, 2, 3])

        assert result1 is True
        assert result2 is False
        assert result3 is True
        assert testing.tests_passed == 2
        assert testing.tests_failed == 1
        assert testing.total_tests == 3
        assert len(testing.errors) == 1


def test_verify_different_types():
    """Test the verify method with different data types."""
    testing = ApimTesting()

    with patch('builtins.print'):
        # String
        assert testing.verify('test', 'test') is True
        # Number
        assert testing.verify(42, 42) is True
        # Boolean
        assert testing.verify(True, True) is True
        # List
        assert testing.verify([1, 2], [1, 2]) is True
        # Dict
        assert testing.verify({'a': 1}, {'a': 1}) is True
        # None
        assert testing.verify(None, None) is True

        assert testing.tests_passed == 6
        assert not testing.tests_failed


def test_verify_none_vs_empty():
    """Test the verify method with None vs empty values."""
    testing = ApimTesting()

    with patch('builtins.print'):
        # None vs empty string should fail
        assert testing.verify(None, '') is False
        # None vs empty list should fail
        assert testing.verify(None, []) is False
        # Empty string vs empty list should fail
        assert testing.verify('', []) is False

        assert not testing.tests_passed
        assert testing.tests_failed == 3


# ------------------------------
#    TEST PRINT_SUMMARY METHOD
# ------------------------------

def test_print_summary_all_passed():
    """Test print_summary when all tests pass."""
    testing = ApimTesting('Test Suite', 'sample-1', INFRASTRUCTURE.SIMPLE_APIM)

    with patch('builtins.print') as mock_print:
        # Simulate some passing tests
        testing.tests_passed = 5
        testing.total_tests = 5

        testing.print_summary()

        # Check that the right messages were printed
        calls = [call.args[0] for call in mock_print.call_args_list if call.args]

        # Should contain success message
        success_messages = [call for call in calls if 'ALL TESTS PASSED' in call]
        assert len(success_messages) > 0

        # Should contain statistics
        stats_messages = [call for call in calls if 'Tests Passed' in call]
        assert len(stats_messages) > 0


def test_print_summary_some_failed():
    """Test print_summary when some tests fail."""
    testing = ApimTesting('Test Suite', 'sample-1', INFRASTRUCTURE.SIMPLE_APIM)

    with patch('builtins.print') as mock_print:
        # Simulate mixed results
        testing.tests_passed = 3
        testing.tests_failed = 2
        testing.total_tests = 5
        testing.errors = ['Error 1', 'Error 2']

        testing.print_summary()

        # Check that the right messages were printed
        calls = [call.args[0] for call in mock_print.call_args_list if call.args]

        # Should contain failure message
        failure_messages = [call for call in calls if 'SOME TESTS FAILED' in call]
        assert len(failure_messages) > 0

        # Should contain error details
        error_messages = [call for call in calls if 'Detailed Error Analysis' in call]
        assert len(error_messages) > 0


def test_print_summary_no_tests():
    """Test print_summary when no tests were executed."""
    testing = ApimTesting('Test Suite')

    with patch('builtins.print') as mock_print:
        testing.print_summary()

        # Check that the right messages were printed
        calls = [call.args[0] for call in mock_print.call_args_list if call.args]

        # Should contain no tests message
        no_tests_messages = [call for call in calls if 'NO TESTS EXECUTED' in call]
        assert len(no_tests_messages) > 0


def test_print_summary_success_rate_calculation():
    """Test that success rate is calculated correctly."""
    testing = ApimTesting()

    with patch('builtins.print') as mock_print:
        # Simulate 3 passed, 2 failed = 60% success rate
        testing.tests_passed = 3
        testing.tests_failed = 2
        testing.total_tests = 5

        testing.print_summary()

        # Check that 60% appears in the output
        calls = [call.args[0] for call in mock_print.call_args_list if call.args]
        success_rate_messages = [call for call in calls if '60.0%' in call]
        assert len(success_rate_messages) > 0


def test_print_summary_with_none_values():
    """Test print_summary with None values for sample_name and deployment."""
    testing = ApimTesting()

    with patch('builtins.print') as mock_print:
        testing.total_tests = 1
        testing.tests_passed = 1

        testing.print_summary()

        # Check that N/A appears for None values
        calls = [call.args[0] for call in mock_print.call_args_list if call.args]
        na_messages = [call for call in calls if 'N/A' in call]
        assert len(na_messages) > 0


# ------------------------------
#    INTEGRATION TESTS
# ------------------------------

def test_full_testing_workflow():
    """Test a complete testing workflow with mixed results."""
    testing = ApimTesting('Integration Test', 'test-sample', INFRASTRUCTURE.APIM_ACA)

    with patch('builtins.print'):
        # Run several tests
        testing.verify(200, 200)  # Pass
        testing.verify('OK', 'OK')  # Pass
        testing.verify(404, 200)  # Fail
        testing.verify({'status': 'success'}, {'status': 'success'})  # Pass
        testing.verify(None, 'something')  # Fail

        # Check final state
        assert testing.total_tests == 5
        assert testing.tests_passed == 3
        assert testing.tests_failed == 2
        assert len(testing.errors) == 2

        # Test summary
        testing.print_summary()

        # Verify final state hasn't changed
        assert testing.total_tests == 5
        assert testing.tests_passed == 3
        assert testing.tests_failed == 2


def test_edge_cases():
    """Test edge cases and unusual inputs."""
    testing = ApimTesting()

    with patch('builtins.print'):
        # Large numbers
        assert testing.verify(999999999, 999999999) is True

        # Negative numbers
        assert testing.verify(-42, -42) is True

        # Special float values
        assert testing.verify(float('inf'), float('inf')) is True

        # Complex data structures
        complex_dict = {
            'nested': {
                'list': [1, 2, {'deep': 'value'}],
                'tuple': (1, 2, 3)
            }
        }
        assert testing.verify(complex_dict, complex_dict) is True

        # Unicode strings
        assert testing.verify('测试', '测试') is True

        assert testing.tests_passed == 5
        assert not testing.tests_failed
