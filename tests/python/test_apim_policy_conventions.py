"""Regression tests for repository-wide APIM policy conventions."""

from pathlib import Path
from xml.etree import ElementTree

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_forward_request_policies_use_sixty_second_timeout() -> None:
    """Require an explicit 60-second timeout on every backend request attempt."""
    policy_paths = sorted(path for path in PROJECT_ROOT.rglob('*.xml') if '<forward-request' in path.read_text(encoding='utf-8'))
    violations = [path.relative_to(PROJECT_ROOT).as_posix() for path in policy_paths if any(policy.get('timeout') != '60' for policy in ElementTree.parse(path).getroot().iter('forward-request'))]

    assert policy_paths
    assert not violations, f'forward-request policies must set timeout="60": {violations}'
