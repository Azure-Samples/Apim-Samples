#!/usr/bin/env pwsh

<#
.SYNOPSIS
Runs offline end-to-end tests for the APIOps backend filtering POC.

.DESCRIPTION
The harness copies the fictitious canonical artifacts to a temporary directory and invokes the preparation script in child PowerShell processes. It requires
PowerShell 7 but no Azure access, APIOps binary, Pester module, or YAML module.

The success cases verify one stable pool with DEV=10, QA=2, and two regional PROD targets with the same seven concrete members. For each target, the harness
reports the artifacts selected for staging and the canonical-to-target property transformations configured for the APIOps publisher. Capacity checks verify
that all simulated PTU tiers precede PAYG. The PROD checks also verify local PTU, peer-region PTU, local PAYG, peer-region PAYG, and tertiary PAYG priorities.
Negative cases verify that an absent configured backend and a pool member omitted from the environment selection both fail before staging.
The harness checks that non-backend artifacts are preserved and the source copy is not modified by any test.

.PARAMETER KeepTemporaryFiles
Retains the generated temporary directory for manual inspection.

.EXAMPLE
pwsh ./tests/test-prepare-apiops-artifacts.ps1
#>

[CmdletBinding()]
param(
    [switch] $KeepTemporaryFiles
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:PassedCount = 0
$script:Failures = [System.Collections.Generic.List[string]]::new()

function Assert-PocTest {
    param(
        [bool] $Condition,
        [string] $Message
    )

    if ($Condition) {
        $script:PassedCount++
        Write-Host "PASS: $Message" -ForegroundColor Green
        return
    }

    $script:Failures.Add($Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
}

function Get-TreeFingerprint {
    param([string] $RootPath)

    return @(
        Get-ChildItem -LiteralPath $RootPath -File -Recurse |
            ForEach-Object {
                $relativePath = [System.IO.Path]::GetRelativePath($RootPath, $_.FullName).Replace('\', '/')
                $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
                "$relativePath|$hash"
            } |
            Sort-Object
    )
}

function Get-ConfiguredBackendTransformations {
    param(
        [string] $Path,
        [string] $PoolName
    )

    $backendUrls = [ordered]@{}
    $poolServices = [System.Collections.Generic.List[object]]::new()
    $currentBackend = $null
    $insidePool = $false
    $currentPoolMember = $null

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^  - name:\s*(?<name>[A-Za-z0-9._-]+)\s*$') {
            $currentBackend = $Matches.name
            $insidePool = $currentBackend -eq $PoolName
            $currentPoolMember = $null
            continue
        }

        if ($null -ne $currentBackend -and -not $insidePool -and $line -match '^      url:\s*(?<url>\S+)\s*$') {
            $backendUrls[$currentBackend] = $Matches.url
            continue
        }

        if (-not $insidePool) {
            continue
        }

        if ($line -match '^          - id: /backends/(?<name>[A-Za-z0-9._-]+)\s*$') {
            $currentPoolMember = [pscustomobject]@{
                Name = $Matches.name
                Id = "/backends/$($Matches.name)"
                Priority = $null
                Weight = $null
            }
            continue
        }

        if ($null -ne $currentPoolMember -and $line -match '^            priority:\s*(?<priority>\d+)\s*$') {
            $currentPoolMember.Priority = [int] $Matches.priority
            continue
        }

        if ($null -ne $currentPoolMember -and $line -match '^            weight:\s*(?<weight>\d+)\s*$') {
            $currentPoolMember.Weight = [int] $Matches.weight
            $poolServices.Add($currentPoolMember)
            $currentPoolMember = $null
        }
    }

    return [pscustomobject]@{
        BackendUrls = $backendUrls
        PoolServices = $poolServices.ToArray()
    }
}

function Write-SelectionAndTransformationReport {
    param(
        [string] $TargetName,
        [pscustomobject] $Audit,
        [pscustomobject] $Transformations,
        [string] $CanonicalPath,
        [string] $PoolName,
        [object[]] $CanonicalServices
    )

    Write-Host "`n=== $TargetName Selection and Transformation Report ===" -ForegroundColor Magenta
    Write-Host "Selected staged backend artifacts ($($Audit.selectedBackendResourceCount)):" -ForegroundColor White
    foreach ($backendName in $Audit.selectedBackendResources) {
        Write-Host "  + $backendName"
    }

    Write-Host "Removed canonical backend artifacts ($($Audit.removedBackendResourceCount)):" -ForegroundColor White
    if ($Audit.removedBackendResourceCount -eq 0) {
        Write-Host '  (none)'
    }
    else {
        foreach ($backendName in $Audit.removedBackendResources) {
            Write-Host "  - $backendName"
        }
    }

    Write-Host 'Configured APIOps property transformations (applied by the publisher, not written into the staged JSON):' -ForegroundColor White
    Write-Host "  Backend URL overrides ($($Transformations.BackendUrls.Count)):"
    foreach ($urlOverride in $Transformations.BackendUrls.GetEnumerator()) {
        $canonicalBackendPath = Join-Path $CanonicalPath "backends/$($urlOverride.Key)/backendInformation.json"
        $canonicalUrl = (Get-Content -LiteralPath $canonicalBackendPath -Raw | ConvertFrom-Json).properties.url
        Write-Host "    * $($urlOverride.Key): $canonicalUrl -> $($urlOverride.Value)"
    }

    $poolCountChange = "$($CanonicalServices.Count) -> $($Transformations.PoolServices.Count) members"
    Write-Host "  Pool services override: $PoolName replaces the complete canonical array ($poolCountChange)"
    foreach ($targetService in $Transformations.PoolServices) {
        $canonicalService = $CanonicalServices | Where-Object { $_.id -eq $targetService.Id } | Select-Object -First 1
        $priorityChange = "$($canonicalService.priority) -> $($targetService.Priority)"
        $weightChange = "$($canonicalService.weight) -> $($targetService.Weight)"
        Write-Host "    * $($targetService.Name): priority $priorityChange; weight $weightChange"
    }

    $targetMemberIds = @($Transformations.PoolServices | ForEach-Object Id)
    $removedPoolMemberIds = @($CanonicalServices | Where-Object { $_.id -notin $targetMemberIds } | ForEach-Object id)
    if ($removedPoolMemberIds.Count -gt 0) {
        Write-Host "  Pool members omitted by the target configuration ($($removedPoolMemberIds.Count)):"
        foreach ($memberId in $removedPoolMemberIds) {
            Write-Host "    - $memberId"
        }
    }
    else {
        Write-Host '  Pool members omitted by the target configuration: (none)'
    }
}

function Write-ExpectedFailureReport {
    param(
        [string] $ScenarioName,
        [pscustomobject] $Result,
        [string] $DestinationPath
    )

    Write-Host "`n=== $ScenarioName Expected Failure Report ===" -ForegroundColor Magenta
    Write-Host 'Caller-visible process output (stdout and stderr merged by the harness):' -ForegroundColor White
    Write-Host ($Result.Output.TrimEnd())
    Write-Host "Exit code: $($Result.ExitCode)"
    Write-Host "Staging directory exists after failure: $(Test-Path -LiteralPath $DestinationPath)"
}

function Invoke-PreparationProcess {
    param(
        [string] $PowerShellPath,
        [string] $ScriptPath,
        [string] $SourcePath,
        [string] $DestinationPath,
        [string] $ConfigurationPath,
        [string] $AuditPath
    )

    $arguments = @(
        '-NoLogo'
        '-NoProfile'
        '-File'
        $ScriptPath
        '-SourceArtifactsPath'
        $SourcePath
        '-DestinationArtifactsPath'
        $DestinationPath
        '-ConfigurationPath'
        $ConfigurationPath
        '-AuditManifestPath'
        $AuditPath
    )

    $output = & $PowerShellPath @arguments 2>&1 | Out-String

    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = $output
    }
}

$pocRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$scriptPath = Join-Path $pocRoot 'scripts/prepare-apiops-artifacts.ps1'
$sourceFixturePath = Join-Path $pocRoot 'artifacts'
$configurationRoot = Join-Path $pocRoot 'configurations'
$missingBackendConfiguration = Join-Path $PSScriptRoot 'fixtures/configuration.missing-backend.yaml'
$unselectedPoolMemberConfiguration = Join-Path $PSScriptRoot 'fixtures/configuration.pool-member-not-selected.yaml'
$poolName = 'inference-gpt-5-1-pool'
$powerShellPath = (Get-Command pwsh -ErrorAction Stop).Source
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) "apiops-backend-poc-$([guid]::NewGuid().ToString('N'))"
$canonicalPath = Join-Path $temporaryRoot 'canonical-artifacts'

try {
    $null = New-Item -ItemType Directory -Path $canonicalPath -Force
    Get-ChildItem -LiteralPath $sourceFixturePath -Force | Copy-Item -Destination $canonicalPath -Recurse -Force

    $markerDirectory = Join-Path $canonicalPath 'namedValues/poc-marker'
    $null = New-Item -ItemType Directory -Path $markerDirectory -Force
    @{
        properties = @{
            displayName = 'poc-marker'
            secret = $false
            tags = @('backend-filtering-poc')
            value = 'preserved'
        }
    } |
        ConvertTo-Json -Depth 3 |
        Set-Content -LiteralPath (Join-Path $markerDirectory 'namedValueInformation.json') -Encoding utf8

    $sourceFingerprintBefore = @(Get-TreeFingerprint -RootPath $canonicalPath)

    $canonicalPoolPath = Join-Path $canonicalPath "backends/$poolName/backendInformation.json"
    $canonicalServices = @((Get-Content -LiteralPath $canonicalPoolPath -Raw | ConvertFrom-Json).properties.pool.services)
    $canonicalPtuPriorities = @($canonicalServices | Where-Object { $_.id -match '-PTU-' } | ForEach-Object priority)
    $canonicalPaygPriorities = @($canonicalServices | Where-Object { $_.id -match '-PAYG-' } | ForEach-Object priority)
    Assert-PocTest `
        -Condition (@($canonicalPtuPriorities | Where-Object { $_ -ne 1 }).Count -eq 0) `
        -Message 'The canonical pool assigns priority 1 to all simulated PTU capacity.'
    Assert-PocTest `
        -Condition (@($canonicalPaygPriorities | Where-Object { $_ -ne 2 }).Count -eq 0) `
        -Message 'The canonical pool assigns priority 2 to all PAYG capacity.'

    $cases = @(
        [pscustomobject]@{
            Name = 'DEV'
            Configuration = Join-Path $configurationRoot 'configuration.dev.yaml'
            ExpectedConcreteNames = @(
                'gpt-5-1-PAYG-centralus',
                'gpt-5-1-PAYG-eastus2',
                'gpt-5-1-PAYG-eastus2-02',
                'gpt-5-1-PAYG-northcentralus',
                'gpt-5-1-PAYG-southcentralus',
                'gpt-5-1-PAYG-westus3',
                'gpt-5-1-PAYG-westus3-02',
                'gpt-5-1-PTU-eastus2',
                'gpt-5-1-PTU-southcentralus',
                'gpt-5-1-PTU-westus3'
            )
            ExpectedPtuBackends = @(
                'gpt-5-1-PTU-eastus2',
                'gpt-5-1-PTU-southcentralus',
                'gpt-5-1-PTU-westus3'
            )
            ExpectedPaygBackends = @(
                'gpt-5-1-PAYG-centralus',
                'gpt-5-1-PAYG-eastus2',
                'gpt-5-1-PAYG-eastus2-02',
                'gpt-5-1-PAYG-northcentralus',
                'gpt-5-1-PAYG-southcentralus',
                'gpt-5-1-PAYG-westus3',
                'gpt-5-1-PAYG-westus3-02'
            )
        }
        [pscustomobject]@{
            Name = 'QA'
            Configuration = Join-Path $configurationRoot 'configuration.qa.yaml'
            ExpectedConcreteNames = @('gpt-5-1-PTU-eastus2', 'gpt-5-1-PTU-westus3')
        }
        [pscustomobject]@{
            Name = 'PROD East US 2'
            Configuration = Join-Path $configurationRoot 'configuration.prod-eastus2.yaml'
            ExpectedConcreteNames = @(
                'gpt-5-1-PAYG-eastus2',
                'gpt-5-1-PAYG-eastus2-02',
                'gpt-5-1-PAYG-southcentralus',
                'gpt-5-1-PAYG-westus3',
                'gpt-5-1-PAYG-westus3-02',
                'gpt-5-1-PTU-eastus2',
                'gpt-5-1-PTU-westus3'
            )
            ExpectedLocalPtuBackends = @(
                'gpt-5-1-PTU-eastus2'
            )
            ExpectedLocalPaygBackends = @(
                'gpt-5-1-PAYG-eastus2',
                'gpt-5-1-PAYG-eastus2-02'
            )
            ExpectedRemotePtuBackends = @(
                'gpt-5-1-PTU-westus3'
            )
            ExpectedRemotePaygBackends = @(
                'gpt-5-1-PAYG-westus3',
                'gpt-5-1-PAYG-westus3-02'
            )
            ExpectedFallbackBackends = @('gpt-5-1-PAYG-southcentralus')
        }
        [pscustomobject]@{
            Name = 'PROD West US 3'
            Configuration = Join-Path $configurationRoot 'configuration.prod-westus3.yaml'
            ExpectedConcreteNames = @(
                'gpt-5-1-PAYG-eastus2',
                'gpt-5-1-PAYG-eastus2-02',
                'gpt-5-1-PAYG-southcentralus',
                'gpt-5-1-PAYG-westus3',
                'gpt-5-1-PAYG-westus3-02',
                'gpt-5-1-PTU-eastus2',
                'gpt-5-1-PTU-westus3'
            )
            ExpectedLocalPtuBackends = @(
                'gpt-5-1-PTU-westus3'
            )
            ExpectedLocalPaygBackends = @(
                'gpt-5-1-PAYG-westus3',
                'gpt-5-1-PAYG-westus3-02'
            )
            ExpectedRemotePtuBackends = @(
                'gpt-5-1-PTU-eastus2'
            )
            ExpectedRemotePaygBackends = @(
                'gpt-5-1-PAYG-eastus2',
                'gpt-5-1-PAYG-eastus2-02'
            )
            ExpectedFallbackBackends = @('gpt-5-1-PAYG-southcentralus')
        }
    )

    foreach ($case in $cases) {
        Write-Host "`n--- $($case.Name) selection test ---" -ForegroundColor Cyan
        $transformations = Get-ConfiguredBackendTransformations -Path $case.Configuration -PoolName $poolName
        $destinationPath = Join-Path $temporaryRoot "staged-$($case.Name.ToLowerInvariant())"
        $auditPath = "$destinationPath.selection.json"
        $result = Invoke-PreparationProcess `
            -PowerShellPath $powerShellPath `
            -ScriptPath $scriptPath `
            -SourcePath $canonicalPath `
            -DestinationPath $destinationPath `
            -ConfigurationPath $case.Configuration `
            -AuditPath $auditPath

        Assert-PocTest -Condition ($result.ExitCode -eq 0) -Message "$($case.Name) exits with code 0. Output: $($result.Output.Trim())"
        Assert-PocTest -Condition (Test-Path -LiteralPath $destinationPath -PathType Container) -Message "$($case.Name) creates a staged artifact tree."

        if (Test-Path -LiteralPath $destinationPath -PathType Container) {
            $actualNames = @(Get-ChildItem -LiteralPath (Join-Path $destinationPath 'backends') -Directory | ForEach-Object Name | Sort-Object)
            $expectedNames = @($case.ExpectedConcreteNames + $poolName | Sort-Object)
            $nameDifference = @(Compare-Object -ReferenceObject $expectedNames -DifferenceObject $actualNames)
            Assert-PocTest `
                -Condition ($nameDifference.Count -eq 0) `
                -Message "$($case.Name) stages $($case.ExpectedConcreteNames.Count) concrete backends and the stable pool ID."

            $poolArtifactPath = Join-Path $destinationPath "backends/$poolName/backendInformation.json"
            Assert-PocTest `
                -Condition (Test-Path -LiteralPath $poolArtifactPath -PathType Leaf) `
                -Message "$($case.Name) preserves the canonical $poolName artifact."

            $markerPath = Join-Path $destinationPath 'namedValues/poc-marker/namedValueInformation.json'
            Assert-PocTest -Condition (Test-Path -LiteralPath $markerPath -PathType Leaf) -Message "$($case.Name) preserves non-backend artifact collections."
        }

        Assert-PocTest -Condition (Test-Path -LiteralPath $auditPath -PathType Leaf) -Message "$($case.Name) writes an audit manifest."
        if (Test-Path -LiteralPath $auditPath -PathType Leaf) {
            $audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
            $auditMembers = @($audit.backendPoolMemberships.$poolName)
            $memberDifference = @(Compare-Object -ReferenceObject @($case.ExpectedConcreteNames) -DifferenceObject $auditMembers)
            Assert-PocTest `
                -Condition ($audit.selectedConcreteBackendCount -eq $case.ExpectedConcreteNames.Count) `
                -Message "$($case.Name) audit records the concrete backend count."
            Assert-PocTest -Condition ($audit.selectedBackendPoolCount -eq 1) -Message "$($case.Name) audit records one selected backend pool."
            Assert-PocTest -Condition ($audit.availableBackendResourceCount -eq 11) -Message "$($case.Name) audit records 11 canonical backend resources."
            Assert-PocTest -Condition ($audit.availableConcreteBackendCount -eq 10) -Message "$($case.Name) audit records 10 canonical concrete backends."
            Assert-PocTest -Condition ($audit.availableBackendPoolCount -eq 1) -Message "$($case.Name) audit records one canonical backend pool."
            Assert-PocTest -Condition ($memberDifference.Count -eq 0) -Message "$($case.Name) audit records the exact target-specific pool composition."
            Write-SelectionAndTransformationReport `
                -TargetName $case.Name `
                -Audit $audit `
                -Transformations $transformations `
                -CanonicalPath $canonicalPath `
                -PoolName $poolName `
                -CanonicalServices $canonicalServices
        }

        if ($null -ne $case.PSObject.Properties['ExpectedLocalPtuBackends']) {
            $priorities = [ordered]@{}
            foreach ($service in $transformations.PoolServices) {
                $priorities[$service.Name] = $service.Priority
            }
            $localPtuPriorities = @($case.ExpectedLocalPtuBackends | ForEach-Object { $priorities[$_] })
            $localPaygPriorities = @($case.ExpectedLocalPaygBackends | ForEach-Object { $priorities[$_] })
            $remotePtuPriorities = @($case.ExpectedRemotePtuBackends | ForEach-Object { $priorities[$_] })
            $remotePaygPriorities = @($case.ExpectedRemotePaygBackends | ForEach-Object { $priorities[$_] })
            $fallbackPriorities = @($case.ExpectedFallbackBackends | ForEach-Object { $priorities[$_] })

            Assert-PocTest `
                -Condition (@($localPtuPriorities | Where-Object { $_ -ne 1 }).Count -eq 0) `
                -Message "$($case.Name) assigns priority 1 to simulated local PTU capacity."
            Assert-PocTest `
                -Condition (@($remotePtuPriorities | Where-Object { $_ -ne 2 }).Count -eq 0) `
                -Message "$($case.Name) assigns priority 2 to simulated peer-region PTU capacity."
            Assert-PocTest `
                -Condition (@($localPaygPriorities | Where-Object { $_ -ne 3 }).Count -eq 0) `
                -Message "$($case.Name) assigns priority 3 to local PAYG capacity."
            Assert-PocTest `
                -Condition (@($remotePaygPriorities | Where-Object { $_ -ne 4 }).Count -eq 0) `
                -Message "$($case.Name) assigns priority 4 to peer-region PAYG capacity."
            Assert-PocTest `
                -Condition (@($fallbackPriorities | Where-Object { $_ -ne 5 }).Count -eq 0) `
                -Message "$($case.Name) assigns priority 5 to the tertiary PAYG fallback."
        }

        if ($null -ne $case.PSObject.Properties['ExpectedPtuBackends']) {
            $priorities = [ordered]@{}
            foreach ($service in $transformations.PoolServices) {
                $priorities[$service.Name] = $service.Priority
            }
            $ptuPriorities = @($case.ExpectedPtuBackends | ForEach-Object { $priorities[$_] })
            $paygPriorities = @($case.ExpectedPaygBackends | ForEach-Object { $priorities[$_] })
            Assert-PocTest `
                -Condition (@($ptuPriorities | Where-Object { $_ -ne 1 }).Count -eq 0) `
                -Message "$($case.Name) assigns priority 1 to all simulated PTU capacity."
            Assert-PocTest `
                -Condition (@($paygPriorities | Where-Object { $_ -ne 2 }).Count -eq 0) `
                -Message "$($case.Name) assigns priority 2 to all PAYG capacity."
        }
    }

    Write-Host "`n--- Missing configured backend test ---" -ForegroundColor Cyan
    $failedDestinationPath = Join-Path $temporaryRoot 'staged-missing'
    $failedAuditPath = "$failedDestinationPath.selection.json"
    $failureResult = Invoke-PreparationProcess `
        -PowerShellPath $powerShellPath `
        -ScriptPath $scriptPath `
        -SourcePath $canonicalPath `
        -DestinationPath $failedDestinationPath `
        -ConfigurationPath $missingBackendConfiguration `
        -AuditPath $failedAuditPath

    Write-ExpectedFailureReport -ScenarioName 'Missing Configured Backend' -Result $failureResult -DestinationPath $failedDestinationPath

    Assert-PocTest -Condition ($failureResult.ExitCode -eq 4) -Message 'A missing configured backend exits with code 4.'
    Assert-PocTest -Condition ($failureResult.Output -match 'POC004') -Message 'The failure identifies the source-artifact error category.'
    Assert-PocTest `
        -Condition ($failureResult.Output -match 'selects 2 backend IDs; canonical artifacts resolve 1 and cannot resolve 1') `
        -Message 'The failure quantifies the configuration-to-artifact mismatch.'
    Assert-PocTest -Condition ($failureResult.Output -match 'gpt-5-1-PTU-japaneast') -Message 'The failure names the missing configured backend ID.'
    Assert-PocTest -Condition ($failureResult.Output -match 'configuration line 8') -Message 'The failure identifies the exact configuration line.'
    Assert-PocTest -Condition ($failureResult.Output -match 'Required artifact path') -Message 'The failure reports the absent canonical artifact path.'
    Assert-PocTest `
        -Condition ($failureResult.Output -match 'cannot create a backend') `
        -Message 'The failure explains the relevant APIOps configuration limitation.'
    Assert-PocTest -Condition ($failureResult.Output -match 'typo or stale entry') -Message 'The failure distinguishes the two likely correction paths.'
    Assert-PocTest `
        -Condition ($failureResult.Output -match 'before staging.*publisher execution') `
        -Message 'The failure states exactly where processing stopped.'
    Assert-PocTest -Condition (-not (Test-Path -LiteralPath $failedDestinationPath)) -Message 'No staging directory remains after preflight validation fails.'

    Write-Host "`n--- Unselected backend-pool member test ---" -ForegroundColor Cyan
    $failedPoolDestinationPath = Join-Path $temporaryRoot 'staged-invalid-pool'
    $failedPoolResult = Invoke-PreparationProcess `
        -PowerShellPath $powerShellPath `
        -ScriptPath $scriptPath `
        -SourcePath $canonicalPath `
        -DestinationPath $failedPoolDestinationPath `
        -ConfigurationPath $unselectedPoolMemberConfiguration `
        -AuditPath "$failedPoolDestinationPath.selection.json"

    Assert-PocTest -Condition ($failedPoolResult.ExitCode -eq 3) -Message 'A pool member omitted from direct selection exits with code 3.'
    Assert-PocTest `
        -Condition ($failedPoolResult.Output -match 'BACKEND POOL MEMBER IS NOT SELECTED') `
        -Message 'The pool dependency error explains why selection is invalid.'
    Assert-PocTest -Condition ($failedPoolResult.Output -match 'gpt-5-1-PTU-westus3') -Message 'The pool dependency error names the unselected member.'
    Assert-PocTest `
        -Condition ($failedPoolResult.Output -match 'publisher was not started') `
        -Message 'The invalid pool composition confirms that APIOps was not started.'
    Assert-PocTest `
        -Condition (-not (Test-Path -LiteralPath $failedPoolDestinationPath)) `
        -Message 'No staging directory remains after pool dependency validation fails.'

    Write-Host "`n--- Invalid path safety tests ---" -ForegroundColor Cyan
    $missingSourceDestination = Join-Path $temporaryRoot 'staged-missing-source'
    $missingSourceResult = Invoke-PreparationProcess `
        -PowerShellPath $powerShellPath `
        -ScriptPath $scriptPath `
        -SourcePath (Join-Path $temporaryRoot 'source-does-not-exist') `
        -DestinationPath $missingSourceDestination `
        -ConfigurationPath (Join-Path $configurationRoot 'configuration.dev.yaml') `
        -AuditPath "$missingSourceDestination.selection.json"

    Assert-PocTest -Condition ($missingSourceResult.ExitCode -eq 2) -Message 'A nonexistent source path exits with code 2.'
    Assert-PocTest -Condition ($missingSourceResult.Output -match 'POC002') -Message 'A nonexistent source path reports the invalid-input category.'
    Assert-PocTest -Condition (-not (Test-Path -LiteralPath $missingSourceDestination)) -Message 'A nonexistent source path cannot create staging.'

    $overlapDestination = Join-Path $temporaryRoot 'staged-audit-overlap'
    $overlapResult = Invoke-PreparationProcess `
        -PowerShellPath $powerShellPath `
        -ScriptPath $scriptPath `
        -SourcePath $canonicalPath `
        -DestinationPath $overlapDestination `
        -ConfigurationPath (Join-Path $configurationRoot 'configuration.dev.yaml') `
        -AuditPath (Join-Path $overlapDestination 'selection.json')

    Assert-PocTest -Condition ($overlapResult.ExitCode -eq 2) -Message 'An audit path inside staging exits with code 2.'
    Assert-PocTest -Condition ($overlapResult.Output -match 'AUDIT MANIFEST PATH OVERLAPS') -Message 'An overlapping audit path receives a descriptive error.'
    Assert-PocTest -Condition (-not (Test-Path -LiteralPath $overlapDestination)) -Message 'An overlapping audit path is rejected before staging is created.'

    $sourceFingerprintAfter = @(Get-TreeFingerprint -RootPath $canonicalPath)
    $sourceDifference = @(Compare-Object -ReferenceObject $sourceFingerprintBefore -DifferenceObject $sourceFingerprintAfter)
    Assert-PocTest -Condition ($sourceDifference.Count -eq 0) -Message 'The canonical source artifact tree remains byte-for-byte unchanged.'
}
finally {
    if ($KeepTemporaryFiles) {
        Write-Host "Temporary test files retained at: $temporaryRoot" -ForegroundColor Yellow
    }
    elseif (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "`n=== POC Test Summary ===" -ForegroundColor Cyan
Write-Host "Passed assertions: $script:PassedCount"
Write-Host "Failed assertions: $($script:Failures.Count)"

if ($script:Failures.Count -gt 0) {
    foreach ($failure in $script:Failures) {
        Write-Host " - $failure" -ForegroundColor Red
    }
    exit 1
}

Write-Host 'All APIOps backend filtering POC tests passed.' -ForegroundColor Green
exit 0
