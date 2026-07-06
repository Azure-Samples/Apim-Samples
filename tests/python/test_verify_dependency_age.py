"""Tests for supply-chain dependency age validation."""

from __future__ import annotations

import importlib
import runpy
import sys
import urllib.error
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_PATH = PROJECT_ROOT / 'setup'
if str(SETUP_PATH) not in sys.path:
    sys.path.insert(0, str(SETUP_PATH))

dependency_age = importlib.import_module('verify_dependency_age')
ActionPin = dependency_age.ActionPin
_action_release_date = dependency_age._action_release_date
_github_json = dependency_age._github_json
_parse_timestamp = dependency_age._parse_timestamp
_tag_commit_and_date = dependency_age._tag_commit_and_date
find_action_pins = dependency_age.find_action_pins
verify_github_actions = dependency_age.verify_github_actions
verify_python_lock = dependency_age.verify_python_lock


NOW = datetime(2026, 7, 6, 12, tzinfo=timezone.utc)


def test_parse_timestamp_assumes_utc_for_naive_values() -> None:
    assert _parse_timestamp('2026-06-20T00:00:00') == datetime(2026, 6, 20, tzinfo=timezone.utc)


def test_verify_python_lock_accepts_old_artifacts(tmp_path: Path) -> None:
    lock_path = tmp_path / 'uv.lock'
    lock_path.write_text(
        """
[[package]]
name = "safe-package"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
sdist = { upload-time = "2026-06-20T00:00:00Z" }
wheels = [{ upload-time = "2026-06-21T00:00:00Z" }]
    """,
        encoding='utf-8',
    )

    assert not verify_python_lock(lock_path, NOW)


def test_verify_python_lock_rejects_newest_recent_artifact(tmp_path: Path) -> None:
    lock_path = tmp_path / 'uv.lock'
    lock_path.write_text(
        """
[[package]]
name = "unsafe-package"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
sdist = { upload-time = "2026-06-20T00:00:00Z" }
wheels = [{ upload-time = "2026-07-01T00:00:00Z" }]
    """,
        encoding='utf-8',
    )

    violations = verify_python_lock(lock_path, NOW)

    assert len(violations) == 1
    assert 'unsafe-package==1.0.0' in violations[0]


def test_verify_python_lock_rejects_missing_timestamps(tmp_path: Path) -> None:
    lock_path = tmp_path / 'uv.lock'
    lock_path.write_text(
        """
[[package]]
name = "unknown-age"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
    """,
        encoding='utf-8',
    )

    assert 'no artifact upload timestamp' in verify_python_lock(lock_path, NOW)[0]


def test_verify_python_lock_ignores_non_registry_sources_and_incomplete_artifacts(tmp_path: Path) -> None:
    lock_path = tmp_path / 'uv.lock'
    lock_path.write_text(
        """
[[package]]
name = "workspace-package"
version = "1.0.0"
source = { editable = "." }

[[package]]
source = { registry = "https://pypi.org/simple" }
sdist = "not-a-table"
wheels = [{ url = "https://example.test/package.whl" }]
        """,
        encoding='utf-8',
    )

    assert verify_python_lock(lock_path, NOW) == ['unknown==unknown: lockfile has no artifact upload timestamp']


def test_find_action_pins_requires_sha_and_version_comment(tmp_path: Path) -> None:
    workflows_path = tmp_path / 'workflows'
    workflows_path.mkdir()
    (workflows_path / 'test.yml').write_text(
        """
steps:
  - uses: actions/checkout@0123456789012345678901234567890123456789 # v6.0.2
  - uses: actions/setup-python@v6
  - uses: ./local-action
    """,
        encoding='utf-8',
    )

    pins, violations = find_action_pins(workflows_path)

    assert len(pins) == 1
    assert pins[0].repository == 'actions/checkout'
    assert len(violations) == 1
    assert '40-character SHA' in violations[0]


def test_find_action_pins_reads_yaml_and_ignores_comments_without_uses(tmp_path: Path) -> None:
    workflows_path = tmp_path / 'workflows'
    workflows_path.mkdir()
    sha = 'A' * 40
    (workflows_path / 'test.yaml').write_text(
        f'# uses: ignored/action@main\nname: test\n- uses: owner/repository/sub-action@{sha} # 1.2.3\n',
        encoding='utf-8',
    )

    pins, violations = find_action_pins(workflows_path)

    assert not violations
    assert pins == [ActionPin('owner/repository/sub-action', 'owner/repository', sha.lower(), '1.2.3', workflows_path / 'test.yaml')]


@pytest.mark.parametrize('token', [None, 'secret-token'])
def test_github_json_builds_expected_request(token: str | None) -> None:
    response = MagicMock()
    response.__enter__.return_value = response

    with patch('verify_dependency_age.urllib.request.urlopen', return_value=response) as mock_urlopen:
        with patch('verify_dependency_age.json.load', return_value={'ok': True}) as mock_json_load:
            assert _github_json('https://api.github.test/resource', token) == {'ok': True}

    request = mock_urlopen.call_args.args[0]
    assert request.get_header('Accept') == 'application/vnd.github+json'
    assert request.get_header('Authorization') == (f'Bearer {token}' if token else None)
    mock_urlopen.assert_called_once_with(request, timeout=30)
    mock_json_load.assert_called_once_with(response)


@patch('verify_dependency_age._action_release_date')
def test_verify_github_actions_accepts_matching_old_release(mock_release: object, tmp_path: Path) -> None:
    workflows_path = tmp_path / 'workflows'
    workflows_path.mkdir()
    sha = '0123456789012345678901234567890123456789'
    (workflows_path / 'test.yml').write_text(f'- uses: actions/checkout@{sha} # v6.0.2\n', encoding='utf-8')
    mock_release.return_value = (sha, datetime(2026, 6, 20, tzinfo=timezone.utc))

    assert not verify_github_actions(workflows_path, NOW)


@pytest.mark.parametrize(
    ('tagged_sha', 'released_at', 'expected'),
    [
        ('f' * 40, datetime(2026, 6, 20, tzinfo=timezone.utc), 'does not match tagged commit'),
        ('0' * 40, datetime(2026, 7, 1, tzinfo=timezone.utc), 'released'),
    ],
)
@patch('verify_dependency_age._action_release_date')
def test_verify_github_actions_rejects_invalid_pin(
    mock_release: object,
    tagged_sha: str,
    released_at: datetime,
    expected: str,
    tmp_path: Path,
) -> None:
    workflows_path = tmp_path / 'workflows'
    workflows_path.mkdir()
    sha = '0' * 40
    (workflows_path / 'test.yml').write_text(f'- uses: actions/checkout@{sha} # v6.0.2\n', encoding='utf-8')
    mock_release.return_value = (tagged_sha, released_at)

    assert expected in verify_github_actions(workflows_path, NOW)[0]


@patch('verify_dependency_age._github_json')
def test_action_release_date_falls_back_when_no_release(mock_github_json: object) -> None:
    sha = '0' * 40
    pin = ActionPin('actions/checkout', 'actions/checkout', sha, 'v6.0.2', Path('test.yml'))
    no_release = urllib.error.HTTPError('url', 404, 'not found', {}, None)
    mock_github_json.side_effect = [
        {'object': {'type': 'commit', 'sha': sha}},
        {'committer': {'date': '2026-06-20T00:00:00Z'}},
        no_release,
    ]

    assert _action_release_date(pin) == (sha, datetime(2026, 6, 20, tzinfo=timezone.utc))


@patch('verify_dependency_age._github_json')
def test_action_release_date_uses_newer_commit_date(mock_github_json: object) -> None:
    sha = '0' * 40
    pin = ActionPin('actions/checkout', 'actions/checkout', sha, 'v6.0.2', Path('test.yml'))
    mock_github_json.side_effect = [
        {'object': {'type': 'commit', 'sha': sha}},
        {'committer': {'date': '2026-07-01T00:00:00Z'}},
        {'published_at': '2026-06-20T00:00:00Z'},
    ]

    assert _action_release_date(pin) == (sha, datetime(2026, 7, 1, tzinfo=timezone.utc))


@patch('verify_dependency_age._github_json')
def test_tag_commit_and_date_resolves_annotated_tag(mock_github_json: MagicMock) -> None:
    tag_sha = '1' * 40
    commit_sha = '2' * 40
    pin = ActionPin('owner/action', 'owner/action', commit_sha, 'v1.0.0', Path('test.yml'))
    mock_github_json.side_effect = [
        {'object': {'type': 'tag', 'sha': tag_sha}},
        {'tagger': {'date': '2026-06-22T00:00:00Z'}, 'object': {'type': 'commit', 'sha': commit_sha}},
        {'committer': {'date': '2026-06-20T00:00:00Z'}},
    ]

    assert _tag_commit_and_date(pin, 'token') == (commit_sha, datetime(2026, 6, 22, tzinfo=timezone.utc))
    assert mock_github_json.call_args_list == [
        call('https://api.github.com/repos/owner/action/git/ref/tags/v1.0.0', 'token'),
        call(f'https://api.github.com/repos/owner/action/git/tags/{tag_sha}', 'token'),
        call(f'https://api.github.com/repos/owner/action/git/commits/{commit_sha}', 'token'),
    ]


@patch('verify_dependency_age._github_json')
def test_tag_commit_and_date_rejects_unsupported_target(mock_github_json: MagicMock) -> None:
    pin = ActionPin('owner/action', 'owner/action', '0' * 40, 'v1.0.0', Path('test.yml'))
    mock_github_json.return_value = {'object': {'type': 'tree', 'sha': '1' * 40}}

    with pytest.raises(ValueError, match='unsupported object type tree'):
        _tag_commit_and_date(pin)


@patch('verify_dependency_age._tag_commit_and_date')
@patch('verify_dependency_age._github_json')
def test_action_release_date_uses_created_date_when_publication_is_missing(
    mock_github_json: MagicMock,
    mock_tag: MagicMock,
) -> None:
    sha = '0' * 40
    fallback = datetime(2026, 6, 20, tzinfo=timezone.utc)
    pin = ActionPin('owner/action', 'owner/action', sha, 'v1.0.0', Path('test.yml'))
    mock_tag.return_value = (sha, fallback)
    mock_github_json.return_value = {'created_at': '2026-06-21T00:00:00Z'}

    assert _action_release_date(pin) == (sha, datetime(2026, 6, 21, tzinfo=timezone.utc))


@patch('verify_dependency_age._tag_commit_and_date')
@patch('verify_dependency_age._github_json')
def test_action_release_date_uses_fallback_when_release_has_no_date(
    mock_github_json: MagicMock,
    mock_tag: MagicMock,
) -> None:
    sha = '0' * 40
    fallback = datetime(2026, 6, 20, tzinfo=timezone.utc)
    pin = ActionPin('owner/action', 'owner/action', sha, 'v1.0.0', Path('test.yml'))
    mock_tag.return_value = (sha, fallback)
    mock_github_json.return_value = {}

    assert _action_release_date(pin) == (sha, fallback)


@patch('verify_dependency_age._tag_commit_and_date')
@patch('verify_dependency_age._github_json')
def test_action_release_date_reraises_non_404_errors(mock_github_json: MagicMock, mock_tag: MagicMock) -> None:
    sha = '0' * 40
    pin = ActionPin('owner/action', 'owner/action', sha, 'v1.0.0', Path('test.yml'))
    mock_tag.return_value = (sha, NOW)
    mock_github_json.side_effect = urllib.error.HTTPError('url', 500, 'server error', {}, None)

    with pytest.raises(urllib.error.HTTPError) as error:
        _action_release_date(pin)

    assert error.value.code == 500


@patch('verify_dependency_age._action_release_date')
def test_verify_github_actions_caches_results_and_reports_metadata_errors(mock_release: MagicMock, tmp_path: Path) -> None:
    workflows_path = tmp_path / 'workflows'
    workflows_path.mkdir()
    sha = '0' * 40
    duplicate = f'- uses: owner/action@{sha} # v1.0.0\n'
    (workflows_path / 'a.yml').write_text(duplicate * 2, encoding='utf-8')
    (workflows_path / 'b.yml').write_text(f'- uses: broken/action@{sha} # v2.0.0\n', encoding='utf-8')
    mock_release.side_effect = [(sha, NOW - timedelta(days=8)), OSError('offline')]

    violations = verify_github_actions(workflows_path, NOW)

    assert mock_release.call_count == 2
    assert violations == ['broken/action@v2.0.0: could not verify release metadata: offline']


@pytest.mark.parametrize(
    ('scope', 'expected_python_calls', 'expected_action_calls'),
    [('all', 1, 1), ('python', 1, 0), ('github-actions', 0, 1)],
)
@patch('verify_dependency_age.verify_github_actions')
@patch('verify_dependency_age.verify_python_lock')
@patch('verify_dependency_age._parse_args')
def test_main_runs_selected_scope_and_reports_success(
    mock_parse_args: MagicMock,
    mock_python: MagicMock,
    mock_actions: MagicMock,
    scope: str,
    expected_python_calls: int,
    expected_action_calls: int,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_parse_args.return_value = Namespace(scope=scope, root=tmp_path)
    mock_python.return_value = []
    mock_actions.return_value = []
    monkeypatch.setenv('GITHUB_TOKEN', 'token')

    assert dependency_age.main() == 0
    assert mock_python.call_count == expected_python_calls
    assert mock_actions.call_count == expected_action_calls
    if expected_action_calls:
        mock_actions.assert_called_once_with(tmp_path / '.github' / 'workflows', token='token')
    assert 'validation passed' in capsys.readouterr().out


@patch('verify_dependency_age.verify_github_actions', return_value=['bad action'])
@patch('verify_dependency_age.verify_python_lock', return_value=['bad package'])
@patch('verify_dependency_age._parse_args')
def test_main_reports_all_violations(
    mock_parse_args: MagicMock,
    _mock_python: MagicMock,
    _mock_actions: MagicMock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_parse_args.return_value = Namespace(scope='all', root=tmp_path)

    assert dependency_age.main() == 1
    assert capsys.readouterr().err.splitlines() == [
        'Dependency age validation failed (7-day minimum):',
        '- bad package',
        '- bad action',
    ]


def test_parse_args_uses_cli_values(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, 'argv', ['verify_dependency_age.py', '--scope', 'python', '--root', str(tmp_path)])

    args = dependency_age._parse_args()

    assert args.scope == 'python'
    assert args.root == tmp_path


def test_script_entry_point_returns_main_result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lock_path = tmp_path / 'uv.lock'
    lock_path.write_text('', encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['verify_dependency_age.py', '--scope', 'python', '--root', str(tmp_path)])

    with pytest.raises(SystemExit) as error:
        runpy.run_path(SETUP_PATH / 'verify_dependency_age.py', run_name='__main__')

    assert error.value.code == 0
