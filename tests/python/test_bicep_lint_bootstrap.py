"""Exercise Bicep lint bootstrap without downloading tools or accessing Azure."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('scenario', ['installed', 'missing', 'install-fails', 'recheck-fails', 'no-az'])
def test_powershell_bicep_bootstrap(tmp_path: Path, scenario: str) -> None:
    """PowerShell installs only when needed, checks failures, and honors custom config."""
    pwsh = shutil.which('pwsh')
    if not pwsh:
        pytest.skip('PowerShell is not available')

    script = PROJECT_ROOT / 'tests' / 'bicep' / 'run_bicep_lint.ps1'
    config = tmp_path / 'azure config'
    (config / 'bin').mkdir(parents = True)
    if scenario == 'installed':
        (config / 'bin' / 'bicep.exe').touch()
    code = r"""
param($ScriptPath, $ConfigPath, $Scenario)
$ErrorActionPreference = 'Stop'
$env:AZURE_CONFIG_DIR = $ConfigPath
$global:Calls = [System.Collections.Generic.List[string]]::new()
function Get-Command {
    param($Name, $ErrorAction)
    if ($Name -eq 'az' -and $Scenario -ne 'no-az') { return @{ Source = 'mock-az' } }
    return $null
}
function az {
    $global:Calls.Add(($args -join ' '))
    $global:LASTEXITCODE = 1
    if ($args[1] -eq 'install') {
        if ($Scenario -eq 'install-fails') { return }
        [System.IO.File]::WriteAllText((Join-Path $env:AZURE_CONFIG_DIR 'bin/bicep.exe'), '')
        $global:LASTEXITCODE = 0
    } elseif ((Test-Path (Join-Path $env:AZURE_CONFIG_DIR 'bin/bicep.exe')) -and $Scenario -ne 'recheck-fails') {
        $global:LASTEXITCODE = 0
    }
}
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($ScriptPath, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$function = $ast.Find({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-BicepExecutable'
}, $true)
. ([scriptblock]::Create($function.Extent.Text))
$result = Get-BicepExecutable
[pscustomobject]@{ Result = $result; Calls = @($global:Calls) } | ConvertTo-Json -Compress
"""
    harness = tmp_path / 'bootstrap.ps1'
    harness.write_text(code, encoding = 'utf-8')
    result = subprocess.run(
        [pwsh, '-NoProfile', '-NonInteractive', '-File', str(harness), str(script), str(config), scenario],
        capture_output = True, text = True, check = True, timeout = 30,
    )
    # Host progress messages precede the structured result.
    data = json.loads(result.stdout.splitlines()[-1])
    expected_calls = [] if scenario in ('installed', 'no-az') else ['bicep version', 'bicep install']
    if scenario in ('missing', 'recheck-fails'):
        expected_calls.append('bicep version')
    assert data['Calls'] == expected_calls
    if scenario in ('installed', 'missing'):
        assert Path(data['Result']) == config / 'bin' / 'bicep.exe'
    else:
        assert data['Result'] is None


@pytest.mark.parametrize('scenario', ['installed', 'missing', 'install-fails', 'recheck-fails', 'no-az'])
def test_bash_bicep_bootstrap(tmp_path: Path, scenario: str) -> None:
    """Bash keeps installer output out of the captured binary path and rechecks."""
    bash = shutil.which('bash')
    if os.name == 'nt':
        git_bash = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Git' / 'bin' / 'bash.exe'
        bash = str(git_bash) if git_bash.is_file() else None
    if not bash:
        pytest.skip('Bash is not available')

    source = (PROJECT_ROOT / 'tests' / 'bicep' / 'run_bicep_lint.sh').read_text(encoding = 'utf-8')
    function = source.split('get_bicep_executable() {', 1)[1].split('\n}\n', 1)[0]
    code = 'get_bicep_executable() {' + function + '\n}\n' + r"""
export AZURE_CONFIG_DIR="$PWD/azure config"
if [ "$1" != "no-az" ]; then
  az() {
    printf '%s\n' "$*" >> "$PWD/calls.txt"
    if [ "$2" = "install" ]; then
      if [ "$SCENARIO" = "install-fails" ]; then return 1; fi
      printf 'installer stdout\n'
      printf '' > "$AZURE_CONFIG_DIR/bin/bicep"
      return 0
    fi
    [ -f "$AZURE_CONFIG_DIR/bin/bicep" ] && [ "$SCENARIO" != "recheck-fails" ]
  }
fi
export SCENARIO="$1"
PATH=""
result="$(get_bicep_executable)"
status=$?
printf 'STATUS=%s\nRESULT=%s\n' "$status" "$result"
"""
    config = tmp_path / 'azure config'
    (config / 'bin').mkdir(parents = True)
    if scenario == 'installed':
        (config / 'bin' / 'bicep').touch()
    result = subprocess.run(
        [bash, '--noprofile', '--norc', '-c', code, 'bootstrap', scenario],
        cwd = tmp_path, capture_output = True, text = True, check = True, timeout = 30,
    )
    calls_file = tmp_path / 'calls.txt'
    calls = calls_file.read_text(encoding = 'utf-8').splitlines() if calls_file.exists() else []
    expected_calls = [] if scenario in ('installed', 'no-az') else ['bicep version', 'bicep install']
    if scenario in ('missing', 'recheck-fails'):
        expected_calls.append('bicep version')
    assert calls == expected_calls
    if scenario in ('installed', 'missing'):
        assert 'STATUS=0\n' in result.stdout
        assert result.stdout.split('RESULT=', 1)[1].strip().endswith('/azure config/bin/bicep')
        assert 'installer stdout' not in result.stdout
    else:
        assert result.stdout == 'STATUS=1\nRESULT=\n'
