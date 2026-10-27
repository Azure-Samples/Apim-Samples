"""Authenticated endpoint configuration through the MockAPI dashboard API.

Autoreload: reload_conditional
Method edits reload. Recreate clients after constructor changes; close existing sessions normally.
"""

import re
from collections.abc import Callable, Mapping
from typing import Any, Self
from urllib.parse import urlsplit
from uuid import UUID

import requests


class MockApiDashboardClient:
    """Own one dashboard session and preserve unrelated configuration during endpoint updates."""

    def __init__(
        self,
        dashboard_url: str,
        dashboard_password: str,
        *,
        session_factory: Callable[[], requests.Session] = requests.Session,
    ) -> None:
        parsed = urlsplit(dashboard_url)
        if (
            parsed.scheme != 'https'
            or not parsed.hostname
            or parsed.port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ('', '/')
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError('MockAPI dashboard URLs must be HTTPS origins without credentials, query, or fragments.')
        if not dashboard_password:
            raise ValueError('The infrastructure dashboard password is required.')
        host = f'[{parsed.hostname}]' if ':' in parsed.hostname else parsed.hostname
        self._dashboard_url = f'https://{host}/'
        self._api_url = self._dashboard_url + '__mockapi/api'
        self._password = dashboard_password
        self._session_factory = session_factory
        self._session: requests.Session | None = None

    @property
    def dashboard_url(self) -> str:
        """Return the normalized HTTPS origin without authentication information."""
        return self._dashboard_url

    def __enter__(self) -> Self:
        if self._session is not None:
            raise RuntimeError('The MockAPI dashboard client is already open.')
        self._session = self._session_factory()
        self._session.auth = ('admin', self._password)
        self._session.verify = True

        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the owned session, including after a failed mutation."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def ensure_endpoint(self, endpoint: Mapping[str, object], *, preserve_existing: bool = False) -> None:
        """Create or update one endpoint using bounded optimistic-concurrency retries.

        Preserve mode skips routes already covering the requested methods, regardless of ID,
        enabled state, or response edits. It never replaces an existing definition. Ordinary
        mode updates only the supplied stable ID and rejects other IDs sharing its path.
        """
        candidate = dict(endpoint)
        identifier = candidate.get('id')
        path = candidate.get('path')
        if not isinstance(identifier, str) or not isinstance(path, str) or not path.startswith('/'):
            raise ValueError('A MockAPI endpoint requires a UUID ID and an absolute path.')
        try:
            candidate['id'] = str(UUID(identifier))
        except ValueError:
            raise ValueError('A MockAPI endpoint requires a valid UUID ID.') from None
        methods = self._methods(candidate)

        for _ in range(3):
            endpoints, etag = self._export()
            same_path = [item for item in endpoints if item.get('path') == path]
            if preserve_existing and any(methods <= self._methods(item) for item in same_path):
                return
            matches = [item for item in endpoints if item.get('id') == candidate['id']]
            if len(matches) > 1 or (matches and matches[0].get('path') != path):
                raise ValueError('The requested endpoint ID conflicts with existing configuration.')
            collisions = [item for item in same_path if item.get('id') != candidate['id']]
            if any(not preserve_existing or methods.intersection(self._methods(item)) for item in collisions):
                raise ValueError('A non-owned endpoint already uses the requested path; no configuration was changed.')
            if preserve_existing and matches:
                raise ValueError('The endpoint ID is already used for different methods; the existing definition was preserved.')
            if matches and matches[0] == candidate:
                return
            method = 'PUT' if matches else 'POST'
            route = f'/endpoints/{candidate["id"]}' if matches else '/endpoints'
            response = self._request(method, route, payload = candidate, etag = etag)
            if response.status_code == 412:
                continue
            if response.status_code == 500:
                problem = self._json(response)
                if isinstance(problem, dict) and problem.get('type') == 'https://mockapi.local/problems/autosave-failed':
                    self._save()
                    return
            self._check_response(response, 200 if matches else 201)
            return
        raise RuntimeError('MockAPI configuration changed repeatedly; retry after dashboard edits finish.')

    @staticmethod
    def _methods(endpoint: Mapping[str, object]) -> set[str]:
        methods = endpoint.get('methods')
        if not isinstance(methods, list) or not methods or any(not isinstance(method, str) or not method for method in methods):
            raise ValueError('MockAPI returned or received an invalid endpoint method list.')

        return {method.upper() for method in methods}

    def _request(self, method: str, route: str, *, payload: Mapping[str, object] | None = None, etag: str | None = None) -> requests.Response:
        if self._session is None:
            raise RuntimeError('Use the MockAPI dashboard client as a context manager before configuring endpoints.')
        headers = {} if etag is None else {'If-Match': etag}
        try:
            return self._session.request(
                method,
                self._api_url + route,
                json = payload,
                headers = headers,
                timeout = 30,
                allow_redirects = False,
            )
        except requests.RequestException:
            raise RuntimeError('MockAPI dashboard request failed; verify HTTPS connectivity and dashboard availability.') from None

    @staticmethod
    def _json(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            raise ValueError('MockAPI returned invalid JSON; configuration was not replayed.') from None

    @staticmethod
    def _check_response(response: requests.Response, expected_status: int) -> None:
        if response.status_code != expected_status:
            raise RuntimeError(f'MockAPI management returned HTTP {response.status_code}; expected {expected_status}.')

    def _export(self) -> tuple[list[dict[str, Any]], str]:
        response = self._request('GET', '/configuration/export')
        self._check_response(response, 200)
        etag = response.headers.get('ETag', '')
        if not re.fullmatch(r'"[^"\r\n]+"', etag):
            raise ValueError('MockAPI configuration export did not supply a strong ETag.')
        document = self._json(response)
        if not isinstance(document, dict) or document.get('schemaVersion') != '1.0' or not isinstance(document.get('endpoints'), list):
            raise ValueError('MockAPI returned an invalid configuration export.')
        endpoints = document['endpoints']
        if any(not isinstance(item, dict) for item in endpoints):
            raise ValueError('MockAPI returned an invalid endpoint definition.')

        return endpoints, etag

    def _save(self) -> None:
        # A failed autosave leaves the mutation active. Retry persistence, never replay it.
        for _ in range(3):
            _, etag = self._export()
            response = self._request('POST', '/configuration/save', etag = etag)
            if response.status_code == 412:
                continue
            self._check_response(response, 200)
            return
        raise RuntimeError('MockAPI configuration changed repeatedly while saving; the endpoint remains active but may be unsaved.')
