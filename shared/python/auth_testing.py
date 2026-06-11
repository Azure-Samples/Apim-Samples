"""Role-based authentication test orchestration for APIM samples."""

import json
from dataclasses import dataclass
from typing import Any

# APIM Samples imports
from apimrequests import ApimRequests
from apimtesting import ApimTesting
from apimtypes import HTTP_VERB
from authfactory import AuthFactory
from users import UserHelper


@dataclass(frozen=True)
class AuthTestCase:
    """Describe one role-based APIM authorization test."""

    role: str
    method: HTTP_VERB
    path: str
    expected: Any
    message: str
    include_subscription_key: bool = True
    data: Any = None


class RoleBasedAuthTestRunner:
    """Execute role-based APIM tests while owning request authentication state."""

    def __init__(self, requests: ApimRequests, tests: ApimTesting, jwt_key: str) -> None:
        if not jwt_key:
            raise ValueError('JWT key is required to run role-based authentication tests.')

        self.requests = requests
        self.tests = tests
        self.jwt_key = jwt_key
        self._subscription_key = requests.subscriptionKey
        self._tokens: dict[str, str] = {}

    def __enter__(self) -> 'RoleBasedAuthTestRunner':
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        """Close the owned APIM request session."""
        self.requests.close()

    def run(self, test_cases: list[AuthTestCase]) -> None:
        """Execute and verify each authentication test case in order."""
        for test_case in test_cases:
            self.run_test_case(test_case)

    def run_test_case(self, test_case: AuthTestCase) -> bool:
        """Execute one authentication test case and record its assertion."""
        self.requests.subscriptionKey = self._subscription_key if test_case.include_subscription_key else None
        self.requests.headers['Authorization'] = f'Bearer {self._get_token(test_case.role)}'

        if test_case.method == HTTP_VERB.GET:
            output = self.requests.singleGet(test_case.path, msg=test_case.message)
        elif test_case.method == HTTP_VERB.POST:
            output = self.requests.singlePost(test_case.path, data=test_case.data, msg=test_case.message)
        else:
            raise ValueError(f'Unsupported authentication test method: {test_case.method}')

        if isinstance(test_case.expected, dict):
            try:
                response_data = json.loads(output)
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError('Expected a JSON response for structured authentication assertions.') from exc

            results = [self.tests.verify(response_data.get(name), expected, name) for name, expected in test_case.expected.items()]
            return all(results)

        return self.tests.verify(output, test_case.expected)

    def _get_token(self, role: str) -> str:
        if role not in self._tokens:
            user = UserHelper.get_user_by_role(role)
            if user is None:
                raise ValueError(f'No test user is configured for role: {role}')
            self._tokens[role] = AuthFactory.create_symmetric_jwt_token_for_user(user, self.jwt_key)

        return self._tokens[role]
