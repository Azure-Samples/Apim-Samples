"""Runtime helpers for the Secure Blob Access sample notebook."""

import json
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# APIM Samples imports
import azure_resources as az
import requests as http_requests
from apimrequests import ApimRequests
from apimtypes import HttpStatusCode, Output

STORAGE_BLOB_DATA_CONTRIBUTOR_ROLE_ID = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'


@dataclass(frozen=True)
class SampleBlobPreparation:
    """Describe the role-assignment and sample-blob upload outcome."""

    role_assignment_succeeded: bool
    storage_account_resource_id: str


@dataclass(frozen=True)
class ValetKey:
    """Represent the time-limited blob URL returned by APIM."""

    sas_url: str
    expires_at: str | None


@dataclass(frozen=True)
class BlobDownload:
    """Represent one direct download through a valet key."""

    status_code: int
    content: str | None
    response_body: str


class SecureBlobAccessRunner:
    """Request valet keys and own the APIM and direct-download sessions."""

    def __init__(
        self,
        requests: ApimRequests,
        *,
        session_factory: Callable[[], http_requests.Session] = http_requests.Session,
    ) -> None:
        self.requests = requests
        self._session_factory = session_factory
        self._session: http_requests.Session | None = None

    def __enter__(self) -> 'SecureBlobAccessRunner':
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        """Close the APIM client and direct-download session."""
        if self._session is not None:
            self._session.close()
            self._session = None
        self.requests.close()

    def request_valet_key(self, path: str, jwt_token: str) -> ValetKey:
        """Request and parse a valet key from the secured APIM operation."""
        response = self.request_apim(path, jwt_token, print_response=False)
        try:
            access_info = json.loads(response)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError('APIM did not return a valid valet-key JSON response.') from exc

        sas_url = access_info.get('sas_url')
        if not isinstance(sas_url, str) or not sas_url:
            raise ValueError('APIM valet-key response did not include a SAS URL.')

        expires_at = access_info.get('expire_at')
        return ValetKey(sas_url, str(expires_at) if expires_at is not None else None)

    def request_apim(self, path: str, jwt_token: str, *, print_response: bool = True) -> str | None:
        """Call the secured APIM operation with the supplied JWT token."""
        self.requests.headers['Authorization'] = f'Bearer {jwt_token}'
        return self.requests.singleGet(path, printResponse=print_response)

    def download(self, valet_key: ValetKey) -> BlobDownload:
        """Download a blob directly from storage through its valet key."""
        response = self._get_session().get(valet_key.sas_url, timeout=30)
        content = response.text.strip() if response.status_code == HttpStatusCode.OK else None
        return BlobDownload(response.status_code, content, response.text)

    def _get_session(self) -> http_requests.Session:
        if self._session is None:
            self._session = self._session_factory()
        return self._session


def prepare_sample_blob(
    *,
    subscription_id: str,
    resource_group_name: str,
    storage_account_name: str,
    container_name: str,
    file_name: str,
    content: str,
    user_object_id: str,
    propagation_seconds: int = 30,
    run_command: Callable[..., Output] = az.run,
    sleep: Callable[[float], None] = time.sleep,
) -> SampleBlobPreparation:
    """Assign blob contributor access and upload a temporary sample file."""
    storage_account_resource_id = (
        f'/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Storage/storageAccounts/{storage_account_name}'
    )
    role_result = run_command(
        'az role assignment create'
        f' --assignee-object-id {user_object_id}'
        ' --assignee-principal-type User'
        f' --role {STORAGE_BLOB_DATA_CONTRIBUTOR_ROLE_ID}'
        f' --scope {storage_account_resource_id}'
    )

    if propagation_seconds > 0:
        sleep(propagation_seconds)

    with tempfile.TemporaryDirectory() as temp_directory:
        temp_file = Path(temp_directory) / file_name
        temp_file.write_text(content, encoding='utf-8')
        upload_result = run_command(
            'az storage blob upload'
            f' --account-name {storage_account_name}'
            f' --container-name {container_name}'
            f' --name {file_name}'
            f' --file "{temp_file}"'
            ' --auth-mode login'
            ' --overwrite'
        )

    if not upload_result.success:
        raise RuntimeError(f'Failed to upload sample blob {file_name}.')

    return SampleBlobPreparation(role_result.success, storage_account_resource_id)
