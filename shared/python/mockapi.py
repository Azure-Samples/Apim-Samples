"""Credential reuse and first-run configuration for infrastructure-owned MockAPI instances."""

import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# APIM Samples imports
from apimtypes import Output
from mockapi_dashboard import MockApiDashboardClient

_HASH_ITERATIONS = 600_000
_SECRET_NAMES = ('dashboard-password', 'dashboard-password-hash', 'mock-api-key')


@dataclass(frozen = True, repr = False)
class MockApiCredentials:
    """Keep recoverable deployment credentials out of object representations."""

    dashboard_password: str
    dashboard_password_hash: str
    api_key: str

    def to_parameters(self) -> dict[str, str]:
        """Return the secure Bicep object without logging its contents."""
        return {
            'dashboardPassword': self.dashboard_password,
            'dashboardPasswordHash': self.dashboard_password_hash,
            'apiKey': self.api_key,
        }


def generate_credentials() -> MockApiCredentials:
    """Generate a 16-character dashboard password and an independent 256-bit API key."""
    password = secrets.token_urlsafe(12)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, _HASH_ITERATIONS)
    password_hash = f'v1.{_HASH_ITERATIONS}.{base64.b64encode(salt).decode("ascii")}.{base64.b64encode(digest).decode("ascii")}'

    return MockApiCredentials(password, password_hash, secrets.token_urlsafe(32))


def _validate_credentials(credentials: MockApiCredentials) -> None:
    """Reject partial, malformed, or inconsistent saved credentials without revealing them."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{16}', credentials.dashboard_password) or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', credentials.api_key):
        raise ValueError('Stored MockAPI credentials are invalid; restore the original Container Apps secrets.')

    try:
        version, iteration_text, salt_text, digest_text = credentials.dashboard_password_hash.split('.')
        iterations = int(iteration_text)
        salt = base64.b64decode(salt_text, validate = True)
        digest = base64.b64decode(digest_text, validate = True)
    except (ValueError, binascii.Error):
        raise ValueError('Stored MockAPI dashboard password hash is malformed.') from None

    if version != 'v1' or not 100_000 <= iterations <= 1_000_000 or len(salt) != 16 or len(digest) != 32:
        raise ValueError('Stored MockAPI dashboard password hash is invalid.')
    if not hmac.compare_digest(hashlib.pbkdf2_hmac('sha256', credentials.dashboard_password.encode('utf-8'), salt, iterations), digest):
        raise ValueError('Stored MockAPI dashboard password and hash do not match.')


def prepare_credentials(
    rg_name: str,
    resource_suffix: str,
    subscription_id: str,
    *,
    runner: Callable[..., Output],
) -> MockApiCredentials:
    """Reuse credentials from either existing backend, including after a partial deployment."""
    app_names = {f'ca-{resource_suffix}-{generation}-{index}' for generation in ('mockwebapi', 'mockapi') for index in (1, 2)}
    result = runner(f'az resource list --resource-group {rg_name} --resource-type Microsoft.App/containerApps --query "[].name" -o json')
    if not result.success:
        raise RuntimeError('Cannot discover existing MockAPI containers; credentials were not regenerated.')
    existing = result.json_data
    if not isinstance(existing, list) or any(not isinstance(name, str) for name in existing):
        raise ValueError('Container Apps discovery returned an invalid name list.')

    saved: MockApiCredentials | None = None
    for name in sorted(app_names.intersection(existing)):
        url = f'/subscriptions/{subscription_id}/resourceGroups/{rg_name}/providers/Microsoft.App/containerApps/{name}/listSecrets?api-version=2025-01-01'
        result = runner(f'az rest --method post --url "{url}" -o json', sensitive_output = True, log_command = False)
        if not result.success:
            raise RuntimeError('Cannot read existing MockAPI secrets; credentials were not regenerated.')
        payload = result.json_data
        if not isinstance(payload, dict) or not isinstance(payload.get('value'), list):
            raise ValueError('Container Apps returned an invalid secrets document.')
        values: dict[str, str] = {}
        for entry in payload['value']:
            if not isinstance(entry, dict) or not isinstance(entry.get('name'), str):
                raise ValueError('Container Apps returned an invalid secret entry.')
            if entry['name'] in _SECRET_NAMES:
                value = entry.get('value')
                if not isinstance(value, str) or not value or entry['name'] in values:
                    raise ValueError('Stored MockAPI secrets are missing values or contain duplicate names.')
                values[entry['name']] = value
        if not values:
            continue  # The previous mockwebapi image did not have MockAPI secrets.
        if set(values) != set(_SECRET_NAMES):
            raise ValueError('Stored MockAPI secrets are incomplete; credentials were not regenerated.')
        credentials = MockApiCredentials(*(values[key] for key in _SECRET_NAMES))
        _validate_credentials(credentials)
        if saved is not None and saved != credentials:
            raise ValueError('MockAPI backends have different saved credentials; reconcile them before redeployment.')
        saved = credentials

    if saved is not None:
        return saved

    result = runner(f'az resource list --resource-group {rg_name} --resource-type Microsoft.Storage/storageAccounts --query "[].name" -o json')
    if not result.success:
        raise RuntimeError('Cannot inspect existing MockAPI persistence; credentials were not regenerated.')
    accounts = result.json_data
    if not isinstance(accounts, list) or any(not isinstance(name, str) for name in accounts):
        raise ValueError('Storage discovery returned an invalid account name list.')
    if f'stmock{resource_suffix}' in accounts:
        raise ValueError('MockAPI persistence exists without recoverable credentials. Restore the original secrets or explicitly reset the lab state before redeployment.')

    return generate_credentials()


def seed_configuration(
    rg_name: str,
    storage_account_name: str,
    container_app_names: list[str],
    *,
    runner: Callable[..., Output],
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Seed missing Hello World fixtures and reload persisted configuration without overwriting edits."""
    if not re.fullmatch(r'[a-z0-9]{3,24}', storage_account_name):
        raise ValueError('MockAPI deployment returned an invalid storage account name.')
    if len(container_app_names) != 2 or any(not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', name) for name in container_app_names) or len(set(container_app_names)) != 2:
        raise ValueError('MockAPI deployment must return two distinct container names.')

    result = runner(
        f'az storage account show --resource-group {rg_name} --name {storage_account_name} --query publicNetworkAccess -o tsv',
        error_message = 'Cannot inspect MockAPI storage network access.',
    )
    if not result.success:
        raise RuntimeError('Cannot inspect MockAPI storage network access; see the Azure CLI error above.')
    network_access = result.text.strip()
    if network_access == 'Disabled':
        raise RuntimeError(
            f'MockAPI storage account {storage_account_name} has publicNetworkAccess=Disabled. '
            'This public-Blob configuration uploader cannot reach the account. '
            'If Azure Policy requires private access, provision private connectivity and seed through the authenticated management API instead of retrying or overriding policy.'
        )
    if network_access not in ('Enabled', 'SecuredByPerimeter'):
        raise ValueError('MockAPI storage returned an unknown public network access setting.')

    fixture_path = Path(__file__).resolve().parents[1] / 'mockapi' / 'hello-world.json'
    fixture = json.loads(fixture_path.read_text(encoding = 'utf-8'))
    with tempfile.TemporaryDirectory(prefix = 'apim-mockapi-') as directory:
        for index, app_name in enumerate(container_app_names, 1):
            blob_name = f'mockapi-{index}.json'
            blob_options = f'--account-name {storage_account_name} --container-name mockapi-config --name {blob_name} --auth-mode login'
            result = runner(
                f'az storage blob exists {blob_options} --query exists -o tsv',
                error_message = f'Cannot inspect MockAPI configuration blob {blob_name}.',
                retries = 12,
            )
            if not result.success:
                raise RuntimeError('Cannot inspect MockAPI configuration storage; see the Azure CLI error above for network, authentication, or Blob role failures.')
            exists = result.text.strip().lower()
            if exists not in ('true', 'false'):
                raise ValueError('MockAPI configuration lookup returned an invalid existence flag.')
            if exists == 'false':
                fixture['endpoints'][0]['response']['headers']['X-Mock-Backend'] = [str(index)]
                path = Path(directory) / blob_name
                path.write_text(json.dumps(fixture), encoding = 'utf-8')
                result = runner(
                    f'az storage blob upload {blob_options} --file "{path}" --overwrite false --only-show-errors -o none',
                    error_message = f'Cannot upload MockAPI configuration blob {blob_name}.',
                    retries = 12,
                )
                if not result.success:
                    raise RuntimeError('Failed to seed MockAPI configuration; saved configurations were not overwritten.')

            _wait_for_readiness(rg_name, app_name, runner = runner, sleep = sleep, restart = True)


def _wait_for_readiness(
    rg_name: str,
    app_name: str,
    *,
    runner: Callable[..., Output],
    sleep: Callable[[float], None],
    restart: bool = False,
) -> None:
    """Wait for the current revision, optionally restarting after an external Blob upload."""
    result = runner(f'az containerapp show --resource-group {rg_name} --name {app_name} --query properties.latestRevisionName -o tsv')
    revision = result.text.strip()
    if not result.success or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', revision):
        raise RuntimeError('Cannot identify the MockAPI revision to verify after configuration seeding.')
    if restart:
        result = runner(f'az containerapp revision restart --resource-group {rg_name} --name {app_name} --revision {revision}')
        if not result.success:
            raise RuntimeError('Failed to restart MockAPI after configuration seeding.')
    for attempt in range(60):
        result = runner(f'az containerapp revision show --resource-group {rg_name} --name {app_name} --revision {revision} --query properties.healthState -o tsv')
        if not result.success:
            raise RuntimeError('Cannot verify MockAPI readiness after configuration seeding.')
        state = result.text.strip()
        if state == 'Healthy':
            return
        if state not in ('None', 'Unhealthy'):
            raise ValueError('MockAPI revision returned an unknown health state.')
        if attempt < 59:
            sleep(5)

    raise RuntimeError(f'MockAPI app {app_name} revision {revision} did not become healthy; inspect Container Apps console logs for the startup error.')


def seed_dashboard_configuration(
    rg_name: str,
    container_app_names: list[str],
    dashboard_urls: list[str],
    dashboard_password: str,
    *,
    runner: Callable[..., Output],
    sleep: Callable[[float], None] = time.sleep,
    client_factory: Callable[..., MockApiDashboardClient] = MockApiDashboardClient,
) -> None:
    """Seed Hello World through authenticated dashboards so only runtime identities access private Blob storage."""
    if (
        len(container_app_names) != 2
        or any(not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', name) for name in container_app_names)
        or len(set(container_app_names)) != 2
    ):
        raise ValueError('MockAPI deployment must return two distinct container names.')
    if len(dashboard_urls) != 2:
        raise ValueError('MockAPI deployment must return two dashboard URLs.')

    fixture_path = Path(__file__).resolve().parents[1] / 'mockapi' / 'hello-world.json'
    for index, (app_name, dashboard_url) in enumerate(zip(container_app_names, dashboard_urls), 1):
        _wait_for_readiness(rg_name, app_name, runner = runner, sleep = sleep)
        endpoint = json.loads(fixture_path.read_text(encoding = 'utf-8'))['endpoints'][0]
        endpoint['response']['headers']['X-Mock-Backend'] = [str(index)]
        with client_factory(dashboard_url, dashboard_password) as client:
            client.ensure_endpoint(endpoint, preserve_existing = True)
