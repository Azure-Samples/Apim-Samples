"""Verify Python-side unmasking while preserving Azure CLI's own masking."""

import json
import logging
import re
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

# APIM Samples imports
import apimtypes
import azure_resources as az
import bicep_deployment
import console
import unmasked_logging


@pytest.mark.parametrize('enabled', [False, True])
def test_repository_secrets_follow_global_setting(enabled, monkeypatch, caplog):
    monkeypatch.setenv('APIM_SAMPLES_UNMASK_SENSITIVE_HEADERS', str(enabled))
    caplog.set_level(logging.INFO)
    secret = 'dummy-complete-secret'
    console.print_secret('Password', secret)
    output = apimtypes.Output(True, json.dumps({'password': {'value': secret}, 'config': {'value': {'token': secret}}}))
    assert output.get('password', 'Password', secure = True) == secret
    assert output.getJson('config', 'Config', secure = True) == {'token': secret}
    assert (secret in caplog.text) is enabled
    assert apimtypes.Output._mask_secure_value(secret) == (secret if enabled else '****cret')
    text = json.dumps({'accessToken': secret, 'primaryKey': secret})
    assert (secret in az._redact_secrets(text)) is enabled


def test_python_logs_raw_cli_output_without_recovering_masked_values(monkeypatch, caplog):
    monkeypatch.setenv('APIM_SAMPLES_UNMASK_SENSITIVE_HEADERS', 'true')
    monkeypatch.setattr(az, 'is_debug_enabled', lambda: True)
    caplog.set_level(logging.DEBUG)
    payload = json.dumps({'accessToken': 'dummy-access-token'})
    process = Mock(return_value = SimpleNamespace(stdout = payload, stderr = 'Authorization: *****', returncode = 1))
    monkeypatch.setattr(az.subprocess, 'run', process)

    output = az.run(['program', '--password', 'dummy-password'], sensitive_output = True, error_message = 'Failed', retries = 0)

    assert not output.success
    assert 'dummy-password' in caplog.text
    assert 'dummy-access-token' in caplog.text
    assert 'Authorization: *****' in caplog.text
    assert 'withheld' not in caplog.text


def test_unmasking_overrides_secure_output_suppression(monkeypatch, caplog):
    monkeypatch.setenv('APIM_SAMPLES_UNMASK_SENSITIVE_HEADERS', 'true')
    caplog.set_level(logging.INFO)
    output = apimtypes.Output(True, '{"token": {"value": "dummy-token"}}')
    output.get('token', 'Token', secure = True, suppress_logging = True)
    output.getJson('token', 'Token JSON', secure = True, suppress_logging = True)
    assert caplog.text.count('dummy-token') == 2


def test_sensitive_bicep_debug_can_be_explicitly_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv('APIM_SAMPLES_UNMASK_SENSITIVE_HEADERS', 'true')
    template = tmp_path / 'main.bicep'
    template.write_text('', encoding = 'utf-8')
    runner = Mock(return_value = apimtypes.Output(True, '{}'))

    bicep_deployment.deploy_bicep_template('rg', 'deployment', template, {}, sensitive_output = True, is_debug = True, runner = runner)

    assert '--debug' in runner.call_args.args[0]
    assert runner.call_args.kwargs['sensitive_output'] is True


def test_sdk_wrappers_unmask_and_restore_without_touching_requests(monkeypatch, caplog):
    class HttpPolicy:
        def _redact_header(self, key, value):
            return 'REDACTED'

        def _redact_query_param(self, key, value):
            return 'REDACTED'

    logger = logging.getLogger('fake-sdk')
    legacy = SimpleNamespace(_LOGGER = logger, log_request = lambda *_args, **_kwargs: logger.debug('*****'))
    modules = {
        'azure.core.pipeline.policies': SimpleNamespace(HttpLoggingPolicy = HttpPolicy),
        'msrest.http_logger': legacy,
    }
    monkeypatch.setattr(unmasked_logging.importlib, 'import_module', modules.__getitem__)
    monkeypatch.setenv('APIM_SAMPLES_UNMASK_SENSITIVE_HEADERS', 'true')
    caplog.set_level(logging.DEBUG)
    request = SimpleNamespace(url = 'https://example.test', method = 'POST', headers = {'Authorization': 'dummy-header'}, body = 'dummy-body')
    unmasked_logging.enable_unmasked_logging()
    wrapped = HttpPolicy._redact_header
    unmasked_logging.enable_unmasked_logging()
    assert HttpPolicy._redact_header is wrapped
    assert HttpPolicy()._redact_header('Authorization', 'dummy-header') == 'dummy-header'
    assert HttpPolicy()._redact_query_param('sig', 'dummy-signature') == 'dummy-signature'
    legacy.log_request(None, request)
    assert 'dummy-header' in caplog.text
    assert 'dummy-body' in caplog.text
    assert '*****' not in caplog.text
    assert request.headers == {'Authorization': 'dummy-header'}

    caplog.clear()
    monkeypatch.setenv('APIM_SAMPLES_UNMASK_SENSITIVE_HEADERS', 'false')
    assert HttpPolicy()._redact_header('Authorization', 'dummy-header') == 'REDACTED'
    assert HttpPolicy()._redact_query_param('sig', 'dummy-signature') == 'REDACTED'
    legacy.log_request(None, request)
    assert 'dummy-header' not in caplog.text
    assert '*****' in caplog.text


def test_optional_sdk_import_does_not_hide_broken_dependencies(monkeypatch):
    monkeypatch.setattr(unmasked_logging.importlib, 'import_module', Mock(side_effect = ModuleNotFoundError(name = 'azure')))
    assert unmasked_logging._optional_module('azure.core.pipeline.policies') is None
    monkeypatch.setattr(unmasked_logging.importlib, 'import_module', Mock(side_effect = ModuleNotFoundError(name = 'broken-dependency')))
    with pytest.raises(ModuleNotFoundError):
        unmasked_logging._optional_module('azure.core.pipeline.policies')


@pytest.mark.parametrize('shell_command', [False, True])
def test_installed_cli_retains_internal_masking(shell_command, monkeypatch, caplog):
    """Run az rest through the normal launcher against localhost, never Azure."""
    if shutil.which('az') is None:
        pytest.skip('Azure CLI is not installed.')
    monkeypatch.setenv('APIM_SAMPLES_UNMASK_SENSITIVE_HEADERS', 'true')
    monkeypatch.setenv('AZURE_CORE_COLLECT_TELEMETRY', 'false')
    monkeypatch.setenv('APIM_SAMPLES_LOG_LEVEL', 'DEBUG')
    monkeypatch.setattr(az, 'is_debug_enabled', lambda: True)
    caplog.set_level(logging.DEBUG)
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(self.headers.get('Authorization'))
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"accessToken":"dummy-json-token"}')

        def log_message(self, _format, *args):
            pass

    with HTTPServer(('127.0.0.1', 0), Handler) as server:
        worker = threading.Thread(target = server.serve_forever)
        worker.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}/dummy'
            arguments = ['az', 'rest', '--method', 'get', '--url', url, '--skip-authorization-header', '--headers', 'Authorization=Bearer dummy-local-token']
            command = subprocess.list2cmdline(arguments) if shell_command else arguments
            output = az.run(command, sensitive_output = True, retries = 0, timeout = 30)
        finally:
            server.shutdown()
            worker.join(timeout = 5)

    assert output.success, output.text
    assert output.json_data == {'accessToken': 'dummy-json-token'}
    assert received == ['Bearer dummy-local-token']
    header = re.search(r"'Authorization': '([^']*)'", caplog.text)
    assert header is not None
    assert header.group(1) != received[0]
    assert "'Authorization': 'Bearer dummy-local-token'" not in caplog.text
    assert 'dummy-json-token' in caplog.text
