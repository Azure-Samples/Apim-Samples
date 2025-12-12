"""
Rudimentary test framework to offload validations from the Jupyter notebooks.
"""

# APIM Samples imports
from apimtypes import INFRASTRUCTURE

# ------------------------------
#    CLASSES
# ------------------------------

class ApimTesting:
    """
    A simple test framework for validating APIM deployments and configurations.
    """

    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, test_suite_name: str = 'APIM Tests', sample_name: str = None, deployment: INFRASTRUCTURE = None) -> None:
        """
        Initialize the ApimTesting instance.

        Args:
            test_suite_name (str, optional): The name of the test suite. Defaults to 'APIM Tests'.
            sample_name (str, optional): The name of the sample being tested. Defaults to None.
            deployment (str, optional): The deployment name (INFRASTRUCTURE)
        """
        self.test_suite_name = test_suite_name
        self.sample_name = sample_name
        self.deployment = deployment
        self.tests_passed = 0
        self.tests_failed = 0
        self.total_tests = 0
        self.errors = []


    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def verify(self, value: any, expected: any) -> bool:
        """
        Verify (i.e. assert) that a value matches an expected value.

        Args:
            value: The actual value to check
            expected: The expected value to match

        Returns:
            bool: True, if the assertion passes; otherwise, False.
        """
        try:
            print(f'🔍 Assert that [{value}] matches [{expected}].')
            self.total_tests += 1
            assert value == expected, f'Value [{value}] does not match expected [{expected}]'
            self.tests_passed += 1
            print(f'✅ Test {self.total_tests}: PASS')

            return True
        except AssertionError as e:
            self.tests_failed += 1
            self.errors.append(f'{str(e)}')
            print(f'❌ Test {self.total_tests}: FAIL - {str(e)}')

            return False

    def print_summary(self) -> None:
        """
        Print a summary of the test results with visual flair and comprehensive details.

        Displays the number of tests passed, failed, and any errors encountered
        in a professionally formatted, visually appealing summary box.
        """

        # Calculate success rate and create visual elements
        success_rate = (self.tests_passed / self.total_tests * 100) if self.total_tests > 0 else 0
        border_width = 70
        border_line = '=' * border_width

        # Create padded title
        title = f'🧪 {self.test_suite_name} - Test Results Summary 🧪'
        title_padding = max(0, (border_width - len(title)) // 2)

        # Start the fancy display
        print('\n')  # Blank lines for spacing
        print(border_line)
        print(f'{' ' * title_padding}{title}')
        print(border_line)
        print()

        print(f' Sample Name : {self.sample_name if self.sample_name else 'N/A'}')
        print(f' Deployment  : {self.deployment.name if self.deployment else 'N/A'}\n')

        # Test statistics with visual indicators
        print('📊 Test Execution Statistics:')
        print(f'    • Total Tests  : {self.total_tests:>5}')
        print(f'    • Tests Passed : {self.tests_passed:>5}')
        print(f'    • Tests Failed : {self.tests_failed:>5} {'❌' if self.tests_failed > 0 else ''}')
        print(f'    • Success Rate : {success_rate:>5.1f}%\n')

        # Overall result
        if not self.tests_failed and self.total_tests > 0:
            print('🎉 OVERALL RESULT: ALL TESTS PASSED! 🎉')
            print('✨ Congratulations! Your APIM deployment is working flawlessly! ✨')
        elif not self.total_tests:
            print('⚠️  OVERALL RESULT: NO TESTS EXECUTED')
            print('🤔 Consider adding some tests to validate your deployment.')
        else:
            print('❌ OVERALL RESULT: SOME TESTS FAILED')
            print('🛠️ Your APIM deployment needs attention')
            print(f'💡 {self.tests_failed} issue(s) require investigation.')

        print()

        test_completion_msg = '🎯 Test execution completed successfully! 🎯'

        # Detailed error reporting with style
        if self.errors and len(self.errors) > 0:
            test_completion_msg = f'Test execution completed with {len(self.errors)} error(s)!'

            print('🔍 Detailed Error Analysis:')
            print('─' * 50)
            for i, error in enumerate(self.errors, 1):
                print(f'{i:>2}. {error}\n')

        print()
        print(border_line)
        print(f'{test_completion_msg:^{border_width}}')
        print(border_line)
        print()  # Final spacing
