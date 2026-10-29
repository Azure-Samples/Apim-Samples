"""Exercise local artifact cleanup in isolated repositories without touching user files."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('shell', ['pwsh', 'bash'])
@pytest.mark.parametrize('artifacts_present', [True, False])
def test_cleanup_removes_root_artifacts_and_preserves_user_files(tmp_path: Path, shell: str, artifacts_present: bool) -> None:
    """Both cleanup scripts handle missing folders and preserve nested names and .env."""
    executable = shutil.which(shell)
    if shell == 'bash' and os.name == 'nt':
        git_bash = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Git' / 'bin' / 'bash.exe'
        executable = str(git_bash) if git_bash.is_file() else None
    if not executable:
        pytest.skip(f'{shell} is not available')

    root = tmp_path / 'fixture repo'
    setup = root / 'setup'
    setup.mkdir(parents = True)
    filename = f'clean-local-artifacts.{"ps1" if shell == "pwsh" else "sh"}'
    script = setup / filename
    script.write_text((PROJECT_ROOT / 'setup' / filename).read_text(encoding = 'utf-8'), encoding = 'utf-8', newline = '\n')
    preserved = [root / '.env', root / 'keep.txt', root / 'nested' / '.playwright-mcp' / 'keep.txt', root / 'nested' / 'tmp' / 'keep.txt']
    for path in preserved:
        path.parent.mkdir(parents = True, exist_ok = True)
        path.write_text('keep', encoding = 'utf-8')
    if artifacts_present:
        for directory in ('tmp', '.playwright-mcp'):
            artifact = root / directory / 'nested' / '.hidden-artifact'
            artifact.parent.mkdir(parents = True)
            artifact.write_text('disposable', encoding = 'utf-8')

    arguments = ['-NoProfile', '-NonInteractive', '-File', str(script)] if shell == 'pwsh' else ['--noprofile', '--norc', f'./setup/{filename}']
    for _ in range(2):
        subprocess.run([executable, *arguments], cwd = root, capture_output = True, text = True, check = True, timeout = 30)
        assert not (root / 'tmp').exists()
        assert not (root / '.playwright-mcp').exists()
        for path in preserved:
            assert path.read_text(encoding = 'utf-8') == 'keep'
