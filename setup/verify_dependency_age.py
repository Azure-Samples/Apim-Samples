"""Verify that locked dependencies have completed the repository waiting period."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


WAITING_PERIOD_DAYS = 7
ACTION_PATTERN = re.compile(
    r'uses:\s*(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_./-]+)?)'
    r'@(?P<sha>[0-9a-fA-F]{40})\s*#\s*(?P<version>v?[^\s#]+)'
)


@dataclass(frozen=True)
class ActionPin:
    """A GitHub Action reference pinned to an immutable commit."""

    action: str
    repository: str
    sha: str
    version: str
    workflow: Path


def _parse_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp and normalize it to UTC."""
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _cutoff(now: datetime | None = None) -> datetime:
    """Return the oldest acceptable publication boundary."""
    current = now or datetime.now(timezone.utc)

    return current.astimezone(timezone.utc) - timedelta(days=WAITING_PERIOD_DAYS)


def verify_python_lock(lock_path: Path, now: datetime | None = None) -> list[str]:
    """Return violations for registry artifacts uploaded inside the waiting period."""
    lock_data = tomllib.loads(lock_path.read_text(encoding='utf-8'))
    cutoff = _cutoff(now)
    violations: list[str] = []

    for package in lock_data.get('package', []):
        source = package.get('source', {})
        if 'registry' not in source:
            continue

        timestamps: list[datetime] = []
        sdist = package.get('sdist')
        if isinstance(sdist, dict) and sdist.get('upload-time'):
            timestamps.append(_parse_timestamp(sdist['upload-time']))
        timestamps.extend(
            _parse_timestamp(wheel['upload-time'])
            for wheel in package.get('wheels', [])
            if wheel.get('upload-time')
        )

        package_id = f'{package.get("name", "unknown")}=={package.get("version", "unknown")}'
        if not timestamps:
            violations.append(f'{package_id}: lockfile has no artifact upload timestamp')
            continue

        newest_artifact = max(timestamps)
        if newest_artifact > cutoff:
            violations.append(
                f'{package_id}: newest locked artifact was uploaded {newest_artifact.isoformat()} '
                f'(cutoff: {cutoff.isoformat()})'
            )

    return violations


def find_action_pins(workflows_path: Path) -> tuple[list[ActionPin], list[str]]:
    """Find pinned actions and return malformed action references as violations."""
    pins: list[ActionPin] = []
    violations: list[str] = []

    for workflow in sorted((*workflows_path.glob('*.yml'), *workflows_path.glob('*.yaml'))):
        for line_number, line in enumerate(workflow.read_text(encoding='utf-8').splitlines(), start=1):
            if 'uses:' not in line or line.lstrip().startswith('#'):
                continue
            if line.split('uses:', maxsplit=1)[1].lstrip().startswith('./'):
                continue

            match = ACTION_PATTERN.search(line)
            if not match:
                violations.append(f'{workflow}:{line_number}: action must use a 40-character SHA and trailing version comment')
                continue

            action = match.group('action')
            repository = '/'.join(action.split('/')[:2])
            pins.append(
                ActionPin(
                    action=action,
                    repository=repository,
                    sha=match.group('sha').lower(),
                    version=match.group('version'),
                    workflow=workflow,
                )
            )

    return pins, violations


def _github_json(url: str, token: str | None = None) -> dict[str, Any]:
    """Read a JSON object from the GitHub API."""
    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'apim-samples-dependency-age-check',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    if token:
        headers['Authorization'] = f'Bearer {token}'

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _tag_commit_and_date(pin: ActionPin, token: str | None = None) -> tuple[str, datetime]:
    """Resolve an action version tag to its commit and best available publication time."""
    base_url = f'https://api.github.com/repos/{pin.repository}'
    tag_ref = _github_json(f'{base_url}/git/ref/tags/{pin.version}', token)
    target = tag_ref['object']

    if target['type'] == 'tag':
        tag = _github_json(f'{base_url}/git/tags/{target["sha"]}', token)
        tag_date = _parse_timestamp(tag['tagger']['date'])
        target = tag['object']
    else:
        tag_date = None

    if target['type'] != 'commit':
        raise ValueError(f'{pin.repository}@{pin.version}: tag resolves to unsupported object type {target["type"]}')

    commit = _github_json(f'{base_url}/git/commits/{target["sha"]}', token)
    commit_date = _parse_timestamp(commit['committer']['date'])

    return target['sha'].lower(), max(date for date in (tag_date, commit_date) if date is not None)


def _action_release_date(pin: ActionPin, token: str | None = None) -> tuple[str, datetime]:
    """Return the tagged commit and release date for an action pin."""
    tagged_sha, fallback_date = _tag_commit_and_date(pin, token)
    release_url = f'https://api.github.com/repos/{pin.repository}/releases/tags/{pin.version}'
    try:
        release = _github_json(release_url, token)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        return tagged_sha, fallback_date

    published_at = release.get('published_at') or release.get('created_at')
    if not published_at:
        return tagged_sha, fallback_date

    return tagged_sha, max(_parse_timestamp(published_at), fallback_date)


def verify_github_actions(
    workflows_path: Path,
    now: datetime | None = None,
    token: str | None = None,
) -> list[str]:
    """Return violations for mutable, mismatched, or too-new GitHub Actions."""
    pins, violations = find_action_pins(workflows_path)
    cutoff = _cutoff(now)
    checked: dict[tuple[str, str, str], tuple[str, datetime]] = {}

    for pin in pins:
        key = (pin.repository, pin.version, pin.sha)
        try:
            if key not in checked:
                checked[key] = _action_release_date(pin, token)
            tagged_sha, release_date = checked[key]
        except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
            violations.append(f'{pin.action}@{pin.version}: could not verify release metadata: {error}')
            continue

        if tagged_sha != pin.sha:
            violations.append(
                f'{pin.action}@{pin.version}: workflow SHA {pin.sha} does not match tagged commit {tagged_sha}'
            )
        if release_date > cutoff:
            violations.append(
                f'{pin.action}@{pin.version}: released {release_date.isoformat()} '
                f'(cutoff: {cutoff.isoformat()})'
            )

    return violations


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--scope',
        choices=('all', 'github-actions', 'python'),
        default='all',
        help='Dependency ecosystem to verify (default: all).',
    )
    parser.add_argument(
        '--root',
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help='Repository root (default: inferred from this script).',
    )

    return parser.parse_args()


def main() -> int:
    """Run dependency age checks selected on the command line."""
    args = _parse_args()
    violations: list[str] = []

    if args.scope in {'all', 'python'}:
        violations.extend(verify_python_lock(args.root / 'uv.lock'))
    if args.scope in {'all', 'github-actions'}:
        violations.extend(
            verify_github_actions(
                args.root / '.github' / 'workflows',
                token=os.environ.get('GITHUB_TOKEN'),
            )
        )

    if violations:
        print(f'Dependency age validation failed ({WAITING_PERIOD_DAYS}-day minimum):', file=sys.stderr)
        for violation in violations:
            print(f'- {violation}', file=sys.stderr)
        return 1

    print(f'Dependency age validation passed ({WAITING_PERIOD_DAYS}-day minimum).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
