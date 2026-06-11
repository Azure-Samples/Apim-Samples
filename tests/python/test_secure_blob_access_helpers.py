"""Tests for the Secure Blob Access sample-local runtime helpers."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# APIM Samples imports
from apimtypes import HttpStatusCode, Output

SECURE_BLOB_ACCESS_DIR = Path(__file__).resolve().parents[2] / 'samples' / 'secure-blob-access'
sys.path.insert(0, str(SECURE_BLOB_ACCESS_DIR))

from secure_blob_access_helpers import SecureBlobAccessRunner, ValetKey, prepare_sample_blob  # noqa: E402


@pytest.mark.unit
def test_prepare_sample_blob_assigns_role_uploads_content_and_cleans_temp_file():
    commands = []
    uploaded_path = None

    def run_command(command):
        nonlocal uploaded_path
        commands.append(command)
        if command.startswith('az storage blob upload'):
            uploaded_path = Path(command.split(' --file "', maxsplit=1)[1].split('"', maxsplit=1)[0])
            assert uploaded_path.read_text(encoding='utf-8') == 'sample content'
        return Output(True, '')

    sleep = MagicMock()
    result = prepare_sample_blob(
        subscription_id='subscription',
        resource_group_name='resource-group',
        storage_account_name='storage',
        container_name='documents',
        file_name='sample.txt',
        content='sample content',
        user_object_id='user-id',
        run_command=run_command,
        sleep=sleep,
    )

    assert result.role_assignment_succeeded is True
    assert result.storage_account_resource_id.endswith('/storageAccounts/storage')
    assert '--assignee-object-id user-id' in commands[0]
    assert '--auth-mode login' in commands[1]
    assert uploaded_path is not None and not uploaded_path.exists()
    sleep.assert_called_once_with(30)


@pytest.mark.unit
def test_prepare_sample_blob_reports_existing_role_and_skips_wait():
    outputs = iter([Output(False, 'already exists'), Output(True, '')])
    sleep = MagicMock()

    result = prepare_sample_blob(
        subscription_id='subscription',
        resource_group_name='resource-group',
        storage_account_name='storage',
        container_name='documents',
        file_name='sample.txt',
        content='sample content',
        user_object_id='user-id',
        propagation_seconds=0,
        run_command=lambda command: next(outputs),
        sleep=sleep,
    )

    assert result.role_assignment_succeeded is False
    sleep.assert_not_called()


@pytest.mark.unit
def test_prepare_sample_blob_raises_on_upload_failure_and_cleans_temp_file():
    outputs = iter([Output(True, ''), Output(False, 'upload failed')])
    uploaded_path = None

    def run_command(command):
        nonlocal uploaded_path
        if command.startswith('az storage blob upload'):
            uploaded_path = Path(command.split(' --file "', maxsplit=1)[1].split('"', maxsplit=1)[0])
        return next(outputs)

    with pytest.raises(RuntimeError, match='Failed to upload'):
        prepare_sample_blob(
            subscription_id='subscription',
            resource_group_name='resource-group',
            storage_account_name='storage',
            container_name='documents',
            file_name='sample.txt',
            content='sample content',
            user_object_id='user-id',
            propagation_seconds=0,
            run_command=run_command,
        )

    assert uploaded_path is not None and not uploaded_path.exists()


@pytest.mark.unit
def test_runner_requests_valet_key_and_downloads_blob():
    requests = MagicMock()
    requests.headers = {}
    requests.singleGet.return_value = '{"sas_url": "https://storage/blob?sig=secret", "expire_at": "2030-01-01"}'
    session = MagicMock()
    session.get.return_value.status_code = HttpStatusCode.OK
    session.get.return_value.text = '  This is an HR document.  '

    with SecureBlobAccessRunner(requests, session_factory=lambda: session) as runner:
        valet_key = runner.request_valet_key('/secure-files/document.txt', 'jwt-token')
        download = runner.download(valet_key)

    assert requests.headers['Authorization'] == 'Bearer jwt-token'
    requests.singleGet.assert_called_once_with('/secure-files/document.txt', printResponse=False)
    assert valet_key == ValetKey('https://storage/blob?sig=secret', '2030-01-01')
    assert download.status_code == HttpStatusCode.OK
    assert download.content == 'This is an HR document.'
    session.get.assert_called_once_with(valet_key.sas_url, timeout=30)
    session.close.assert_called_once_with()
    requests.close.assert_called_once_with()


@pytest.mark.unit
@pytest.mark.parametrize('response', [None, 'not JSON', '{}', '{"sas_url": ""}'])
def test_runner_rejects_invalid_valet_key_response(response):
    requests = MagicMock()
    requests.headers = {}
    requests.singleGet.return_value = response
    runner = SecureBlobAccessRunner(requests)

    with pytest.raises(ValueError, match='valet-key|SAS URL'):
        runner.request_valet_key('/secure-files/document.txt', 'jwt-token')


@pytest.mark.unit
def test_runner_preserves_failed_download_body_and_closes_after_exception():
    requests = MagicMock()
    requests.headers = {}
    session = MagicMock()
    session.get.return_value.status_code = HttpStatusCode.FORBIDDEN
    session.get.return_value.text = 'forbidden details'
    runner = SecureBlobAccessRunner(requests, session_factory=lambda: session)

    with pytest.raises(RuntimeError, match='cell failed'):
        with runner:
            download = runner.download(ValetKey('https://storage/blob', None))
            assert download.content is None
            assert download.response_body == 'forbidden details'
            raise RuntimeError('cell failed')

    session.close.assert_called_once_with()
    requests.close.assert_called_once_with()


@pytest.mark.unit
def test_runner_close_without_download_still_closes_apim_client():
    requests = MagicMock()
    runner = SecureBlobAccessRunner(requests)

    runner.close()

    requests.close.assert_called_once_with()


@pytest.mark.unit
def test_runner_reuses_direct_download_session():
    requests = MagicMock()
    session = MagicMock()
    session.get.return_value.status_code = HttpStatusCode.OK
    session.get.return_value.text = 'content'
    session_factory = MagicMock(return_value=session)
    runner = SecureBlobAccessRunner(requests, session_factory=session_factory)
    valet_key = ValetKey('https://storage/blob', None)

    runner.download(valet_key)
    runner.download(valet_key)

    session_factory.assert_called_once_with()
    assert session.get.call_count == 2
