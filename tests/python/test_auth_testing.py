"""Tests for shared role-based authentication test orchestration."""

from unittest.mock import MagicMock, patch

import pytest

# APIM Samples imports
from apimtypes import HTTP_VERB, Role
from auth_testing import AuthTestCase, RoleBasedAuthTestRunner


@pytest.fixture
def requests_mock():
    requests = MagicMock()
    requests.subscriptionKey = 'subscription-key'
    requests.headers = {}
    requests.singleGet.return_value = 'GET response'
    requests.singlePost.return_value = 'POST response'
    return requests


@pytest.fixture
def tests_mock():
    tests = MagicMock()
    tests.verify.return_value = True
    return tests


@pytest.mark.unit
def test_run_dispatches_get_and_post_and_verifies_results(requests_mock, tests_mock):
    test_cases = [
        AuthTestCase(Role.HR_ADMINISTRATOR, HTTP_VERB.GET, 'employees', 'GET response', 'GET employees'),
        AuthTestCase(Role.HR_ADMINISTRATOR, HTTP_VERB.POST, 'employees', 'POST response', 'POST employees', data={'name': 'Test'}),
    ]

    with (
        patch('auth_testing.UserHelper.get_user_by_role', return_value=MagicMock()) as get_user,
        patch('auth_testing.AuthFactory.create_symmetric_jwt_token_for_user', return_value='jwt-token') as create_token,
    ):
        runner = RoleBasedAuthTestRunner(requests_mock, tests_mock, 'jwt-key')
        runner.run(test_cases)

    requests_mock.singleGet.assert_called_once_with('employees', msg='GET employees')
    requests_mock.singlePost.assert_called_once_with('employees', data={'name': 'Test'}, msg='POST employees')
    assert tests_mock.verify.call_args_list == [
        (('GET response', 'GET response'),),
        (('POST response', 'POST response'),),
    ]
    get_user.assert_called_once_with(Role.HR_ADMINISTRATOR)
    create_token.assert_called_once()
    assert requests_mock.headers['Authorization'] == 'Bearer jwt-token'


@pytest.mark.unit
def test_run_toggles_and_restores_subscription_key_for_each_case(requests_mock, tests_mock):
    test_cases = [
        AuthTestCase(Role.HR_ADMINISTRATOR, HTTP_VERB.GET, 'employees', 'GET response', 'Without key', include_subscription_key=False),
        AuthTestCase(Role.HR_ADMINISTRATOR, HTTP_VERB.GET, 'employees', 'GET response', 'With key'),
    ]
    observed_keys = []
    requests_mock.singleGet.side_effect = lambda *args, **kwargs: observed_keys.append(requests_mock.subscriptionKey) or 'GET response'

    with (
        patch('auth_testing.UserHelper.get_user_by_role', return_value=MagicMock()),
        patch('auth_testing.AuthFactory.create_symmetric_jwt_token_for_user', return_value='jwt-token'),
    ):
        RoleBasedAuthTestRunner(requests_mock, tests_mock, 'jwt-key').run(test_cases)

    assert observed_keys == [None, 'subscription-key']


@pytest.mark.unit
def test_structured_expectation_verifies_each_json_field(requests_mock, tests_mock):
    requests_mock.singleGet.return_value = '{"statusCode": 401, "message": "Missing key"}'
    test_case = AuthTestCase(
        Role.HR_ADMINISTRATOR,
        HTTP_VERB.GET,
        'employees',
        {'statusCode': 401, 'message': 'Missing key'},
        'Without key',
        include_subscription_key=False,
    )

    with (
        patch('auth_testing.UserHelper.get_user_by_role', return_value=MagicMock()),
        patch('auth_testing.AuthFactory.create_symmetric_jwt_token_for_user', return_value='jwt-token'),
    ):
        result = RoleBasedAuthTestRunner(requests_mock, tests_mock, 'jwt-key').run_test_case(test_case)

    assert result is True
    assert tests_mock.verify.call_args_list == [
        ((401, 401, 'statusCode'),),
        (('Missing key', 'Missing key', 'message'),),
    ]


@pytest.mark.unit
def test_structured_expectation_rejects_non_json_response(requests_mock, tests_mock):
    requests_mock.singleGet.return_value = 'not JSON'
    test_case = AuthTestCase(Role.HR_ADMINISTRATOR, HTTP_VERB.GET, 'employees', {'statusCode': 401}, 'Without key')

    with (
        patch('auth_testing.UserHelper.get_user_by_role', return_value=MagicMock()),
        patch('auth_testing.AuthFactory.create_symmetric_jwt_token_for_user', return_value='jwt-token'),
        pytest.raises(ValueError, match='Expected a JSON response'),
    ):
        RoleBasedAuthTestRunner(requests_mock, tests_mock, 'jwt-key').run_test_case(test_case)


@pytest.mark.unit
def test_context_manager_closes_requests_on_exception(requests_mock, tests_mock):
    with pytest.raises(RuntimeError):
        with RoleBasedAuthTestRunner(requests_mock, tests_mock, 'jwt-key'):
            raise RuntimeError('test failure')

    requests_mock.close.assert_called_once_with()


@pytest.mark.unit
def test_missing_jwt_key_is_rejected(requests_mock, tests_mock):
    with pytest.raises(ValueError, match='JWT key is required'):
        RoleBasedAuthTestRunner(requests_mock, tests_mock, '')


@pytest.mark.unit
def test_missing_role_user_is_rejected(requests_mock, tests_mock):
    test_case = AuthTestCase('missing-role', HTTP_VERB.GET, 'employees', 'response', 'Missing role')

    with patch('auth_testing.UserHelper.get_user_by_role', return_value=None), pytest.raises(ValueError, match='No test user'):
        RoleBasedAuthTestRunner(requests_mock, tests_mock, 'jwt-key').run_test_case(test_case)


@pytest.mark.unit
def test_unsupported_method_is_rejected(requests_mock, tests_mock):
    test_case = AuthTestCase(Role.HR_ADMINISTRATOR, HTTP_VERB.DELETE, 'employees', 'response', 'Delete employees')

    with (
        patch('auth_testing.UserHelper.get_user_by_role', return_value=MagicMock()),
        patch('auth_testing.AuthFactory.create_symmetric_jwt_token_for_user', return_value='jwt-token'),
        pytest.raises(ValueError, match='Unsupported authentication test method'),
    ):
        RoleBasedAuthTestRunner(requests_mock, tests_mock, 'jwt-key').run_test_case(test_case)
