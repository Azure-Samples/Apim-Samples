"""Verification tests for test infrastructure slowness detection."""

#from __future__ import annotations


# @pytest.mark.unit
# def test_slowness_detection_verification():
#     """Intentionally slow test to verify slowness detection feature works.

#     This test adds a deliberate delay to verify that the check_python.ps1 and
#     check_python.sh scripts properly detect and highlight slow tests (>0.1s).

#     The test is intentionally commented out as to not pollute the test results.

#     The pytest durations output should show this test taking >0.1s, and the
#     check scripts should display a yellow warning message with guidance to review
#     slowest durations in the test summary.
#     """
#     time.sleep(0.15)  # Sleep 150ms to exceed 0.1s threshold
#     assert True
