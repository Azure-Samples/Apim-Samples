"""Exercise Developer CLI selection loops with deterministic terminal input."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MENU_CHOICES = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'u', 'l', 'p', 'e', 'w', 'd', 'c']
POWERSHELL_KEYS = r"""
$ErrorActionPreference = 'Stop'
$scenario = $env:MENU_TEST_CASE | ConvertFrom-Json
$script:events = [Collections.Generic.Queue[string]]::new()
foreach ($event in $scenario.events) { $script:events.Enqueue($event) }
$script:events.Enqueue('unused')
function Read-TestMenuKey {
    $event = $script:events.Dequeue()
    switch ($event) {
        'Enter' { $key = [ConsoleKey]::Enter; $character = [char]13 }
        'Backspace' { $key = [ConsoleKey]::Backspace; $character = [char]8 }
        'Control' { $key = [ConsoleKey]::Tab; $character = [char]9 }
        default { $key = [ConsoleKey]::NoName; $character = [char]$event }
    }
    return [pscustomobject]@{ Key = $key; KeyChar = $character }
}
function Write-Host { param($Object, [switch] $NoNewline) }
"""
BASH_KEYS = r"""
set -euo pipefail
expected="$1"
IFS=, read -r -a choices <<< "$2"
shift 2
events=("$@" unused)
position=0
read() {
  [[ "$#" -eq 5 && "$1" == '-r' && "$2" == '-s' && "$3" == '-n' && "$4" == 1 && "$5" == key ]] || exit 90
  (( position < ${#events[@]} )) || exit 91
  case "${events[$position]}" in
    Enter) key='' ;;
    Backspace) key=$'\177' ;;
    Control) key=$'\t' ;;
    *) key="${events[$position]}" ;;
  esac
  position=$((position + 1))
}
"""


@pytest.fixture(params = ['pwsh', 'bash'])
def shell_reader(request: pytest.FixtureRequest) -> tuple[str, str, str]:
    """Load each production reader without executing menu actions."""
    shell = request.param
    executable = shutil.which(shell)
    if shell == 'bash' and os.name == 'nt':
        git_bash = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Git' / 'bin' / 'bash.exe'
        executable = str(git_bash) if git_bash.is_file() else None
    if not executable:
        pytest.skip(f'{shell} is not available')
    filename = 'start.ps1' if shell == 'pwsh' else 'start.sh'
    source = (PROJECT_ROOT / filename).read_text(encoding = 'utf-8')
    pattern = r'^function Read-MenuSelection \{.*?^\}' if shell == 'pwsh' else r'^read_menu_selection\(\) \{.*?^\}'
    reader = re.search(pattern, source, re.MULTILINE | re.DOTALL)
    assert reader is not None

    return shell, executable, reader.group()


@pytest.mark.parametrize(
    ('events', 'expected', 'choices'),
    [
        *[(list(choice), choice, MENU_CHOICES) for choice in MENU_CHOICES if choice != '1'],
        *[([choice.upper()], choice.upper(), MENU_CHOICES) for choice in ('u', 'l', 'p', 'e', 'w', 'd', 'c')],
        (['1', 'Enter'], '1', MENU_CHOICES),
        (['1', 'Backspace', '2'], '2', MENU_CHOICES),
        (['x', 'Backspace', 'p'], 'p', MENU_CHOICES),
        (['x', 'Enter'], 'x', MENU_CHOICES),
        (['Enter'], '', MENU_CHOICES),
        (['Backspace', 'Control', '3'], '3', MENU_CHOICES),
        (['1'], '1', ['1', '2']),
        (['1', '0', 'Enter'], '10', ['1', '10', '100']),
        (['1', '0', '0'], '100', ['1', '10', '100']),
        (['p', '1'], 'p1', ['p1', 'p2']),
        *[([choice], choice, ['y', 'n']) for choice in ('y', 'Y', 'n', 'N')],
    ],
)
def test_interactive_selection(
    shell_reader: tuple[str, str, str], tmp_path: Path, events: list[str], expected: str, choices: list[str],
) -> None:
    """Run unchanged selection logic, substituting only terminal detection and key reads."""
    shell, executable, reader = shell_reader
    environment = os.environ | {'MENU_TEST_CASE': json.dumps({'events': events, 'expected': expected, 'choices': choices})}
    if shell == 'pwsh':
        reader = reader.replace('[Console]::IsInputRedirected', '$false').replace('[Console]::ReadKey($true)', '(Read-TestMenuKey)')
        harness = POWERSHELL_KEYS + reader + r"""
$actual = Read-MenuSelection -Choices $scenario.choices
if ($actual -cne $scenario.expected) { throw "Unexpected selection: $actual" }
if ($script:events.Count -ne 1) { throw 'Read beyond the complete selection' }
"""
        script = tmp_path / 'reader.ps1'
        arguments = ['-NoProfile', '-NonInteractive', '-File', str(script)]
    else:
        reader = reader.replace('[[ ! -t 0 ]]', 'false')
        harness = BASH_KEYS + reader + r"""
read_menu_selection 'Select an option' "${choices[@]}"
[[ "$MENU_INPUT" == "$expected" && "$position" -eq "$((${#events[@]} - 1))" ]]
"""
        script = tmp_path / 'reader.sh'
        arguments = ['--noprofile', '--norc', './reader.sh', expected, ','.join(choices), *events]
    script.write_text(harness, encoding = 'utf-8', newline = '\n')
    result = subprocess.run([executable, *arguments], cwd = tmp_path, env = environment, capture_output = True, text = True, timeout = 15, check = False)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('selection', ['1', '10', 'P', '', 'invalid'])
def test_redirected_selection_stays_line_based(shell_reader: tuple[str, str, str], tmp_path: Path, selection: str) -> None:
    """Piped input consumes whole lines and never uses raw terminal APIs."""
    shell, executable, reader = shell_reader
    if shell == 'pwsh':
        harness = "$ErrorActionPreference = 'Stop'\n" + reader + r"""
$first = Read-MenuSelection -Choices @('1', '10', 'p')
$second = Read-MenuSelection -Choices @('0')
Write-Output ("RESULT:" + ($first, $second | ConvertTo-Json -Compress))
"""
        script = tmp_path / 'redirected.ps1'
        arguments = ['-NoProfile', '-File', str(script)]
    else:
        harness = 'set -euo pipefail\n' + reader + r"""
read_menu_selection 'Select an option' 1 10 p
first="$MENU_INPUT"
read_menu_selection 'Select an option' 0
printf 'RESULT:%s|%s\n' "$first" "$MENU_INPUT"
"""
        script = tmp_path / 'redirected.sh'
        arguments = ['--noprofile', '--norc', './redirected.sh']
    script.write_text(harness, encoding = 'utf-8', newline = '\n')
    result = subprocess.run([executable, *arguments], cwd = tmp_path, input = f'{selection}\n0\n'.encode(), capture_output = True, timeout = 15, check = False)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = json.dumps([selection, '0'], separators = (',', ':')) if shell == 'pwsh' else f'{selection}|0'
    assert f'RESULT:{expected}' in result.stdout.decode()


def test_menu_dispatch_preserves_redirected_input(shell_reader: tuple[str, str, str]) -> None:
    """Both real entry points still report invalid choices and exit on zero."""
    shell, executable, _ = shell_reader
    arguments = ['-NoProfile', '-File', str(PROJECT_ROOT / 'start.ps1')] if shell == 'pwsh' else ['--noprofile', '--norc', './start.sh']
    result = subprocess.run([executable, *arguments], cwd = PROJECT_ROOT, input = b'invalid\n0\n', capture_output = True, timeout = 15, check = False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count(b'Invalid option. Please try again.') == 1
    assert b'Goodbye!' in result.stdout
