# pylint: disable=C0114,C0115,C0116,W0212,W0621

# Execute with "pytest -v" in the root directory

# https://docs.pytest.org/en/8.2.x/

"""
Unit tests for apimtypes.py
"""
import pytest, sys, os, unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

##########################################################################################################################################################

# Utility Functions

# Test Fixtures

##########################################################################################################################################################

# Tests

class TestApimTypes(unittest.TestCase):
    @pytest.mark.apimtypes

    def test_sample(self) -> None:
        """Sample test - replace with real tests."""
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
