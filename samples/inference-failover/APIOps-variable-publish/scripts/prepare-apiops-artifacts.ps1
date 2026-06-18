#!/usr/bin/env pwsh

<#
.SYNOPSIS
Creates an environment-specific APIOps artifact tree from a canonical superset.

.DESCRIPTION
This script reads backend resource IDs and backend-pool members from the top-level `backends` array in an APIOps configuration YAML file. It validates
that every configured ID has a matching `backends/<id>/backendInformation.json` artifact and every pool member is a selected concrete backend before staging.

After validation, the script copies the complete source artifact tree to a separate destination and removes only unselected direct children of the staged
`backends` directory. Other APIOps collections are copied without filtering. The source tree is never modified.

The YAML reader is intentionally dependency-free and supports the APIOps shape used by this POC. Each direct backend item must use exactly this form:

  backends:
    - name: backend-id

Nested backend properties may follow each name. Backend IDs may contain ASCII
letters, numbers, periods, underscores, and hyphens.

Selected pool resources must provide a complete services array in this form:

        - name: inference-gpt-5-1-pool
            properties:
                type: Pool
                pool:
                    services:
                        - id: /backends/gpt-5-1-PTU-eastus2

.PARAMETER SourceArtifactsPath
Canonical APIOps artifact root containing the complete `backends` directory.

.PARAMETER DestinationArtifactsPath
Separate staging root that APIOps will receive through `API_MANAGEMENT_SERVICE_OUTPUT_FOLDER_PATH`.

.PARAMETER ConfigurationPath
APIOps configuration YAML whose top-level `backends[].name` values define the backend allowlist for this preprocessing step.

.PARAMETER AuditManifestPath
Optional JSON output path. The default is beside the staged directory with a `.selection.json` suffix.

.PARAMETER Force
Replaces an existing destination. Without this switch, an existing destination is treated as an input error and remains untouched.

.EXAMPLE
pwsh ./scripts/prepare-apiops-artifacts.ps1 `
  -SourceArtifactsPath ./artifacts `
  -DestinationArtifactsPath ./out/qa `
  -ConfigurationPath ./configurations/configuration.qa.yaml

.OUTPUTS
Exit 0: staging completed successfully.
Exit 2: an input path or destination is invalid.
Exit 3: the configuration cannot provide a valid backend allowlist.
Exit 4: configured backend artifacts are absent or invalid in the superset.
Exit 5: staging or audit output could not be created.
Exit 99: an unexpected failure occurred.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $SourceArtifactsPath,

    [Parameter(Mandatory)]
    [string] $DestinationArtifactsPath,

    [Parameter(Mandatory)]
    [string] $ConfigurationPath,

    [string] $AuditManifestPath,

    [switch] $Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:ExitCodes = [ordered]@{
    Success = 0
    InvalidInput = 2
    InvalidConfiguration = 3
    InvalidSourceArtifacts = 4
    StagingFailure = 5
    UnexpectedFailure = 99
}

function New-PocException {
    param(
        [int] $ExitCode,
        [string] $ErrorId,
        [string] $Message
    )

    $exception = [System.InvalidOperationException]::new($Message)
    $exception.Data['ExitCode'] = $ExitCode
    $exception.Data['ErrorId'] = $ErrorId

    return $exception
}

function Stop-PocOperation {
    param(
        [int] $ExitCode,
        [string] $ErrorId,
        [string] $Title,
        [string[]] $Details,
        [string] $Resolution
    )

    $messageLines = [System.Collections.Generic.List[string]]::new()
    $messageLines.Add("[$ErrorId] $Title")
    foreach ($detail in $Details) {
        $messageLines.Add($detail)
    }
    $messageLines.Add("Resolution: $Resolution")

    throw (New-PocException -ExitCode $ExitCode -ErrorId $ErrorId -Message ($messageLines -join [Environment]::NewLine))
}

function Get-NormalizedPath {
    param(
        [string] $Path,
        [switch] $MustExist
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw 'A required path value is empty.'
    }

    $normalizedPath = [System.IO.Path]::GetFullPath($Path)
    if ($MustExist -and -not (Test-Path -LiteralPath $normalizedPath)) {
        throw "Path does not exist: $normalizedPath"
    }

    return [System.IO.Path]::TrimEndingDirectorySeparator($normalizedPath)
}

function Test-PathContains {
    param(
        [string] $ParentPath,
        [string] $ChildPath
    )

    $separator = [System.IO.Path]::DirectorySeparatorChar
    $parentPrefix = $ParentPath.TrimEnd($separator, [System.IO.Path]::AltDirectorySeparatorChar) + $separator

    return $ChildPath.StartsWith($parentPrefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function ConvertFrom-BackendNameScalar {
    param(
        [string] $Value,
        [int] $LineNumber
    )

    $backendName = $Value.Trim()
    if (($backendName.StartsWith("'") -and $backendName.EndsWith("'")) -or ($backendName.StartsWith('"') -and $backendName.EndsWith('"'))) {
        $backendName = $backendName.Substring(1, $backendName.Length - 2)
    }

    if ($backendName -notmatch '^[A-Za-z0-9._-]+$') {
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidConfiguration `
            -ErrorId 'POC003' `
            -Title 'INVALID BACKEND ID IN CONFIGURATION' `
            -Details @("Line $LineNumber contains unsupported backend ID '$backendName'.") `
            -Resolution 'Use a non-empty ID containing only ASCII letters, numbers, periods, underscores, or hyphens.'
    }

    return $backendName
}

function ConvertFrom-PoolMemberScalar {
    param(
        [string] $Value,
        [int] $LineNumber
    )

    $memberId = $Value.Trim()
    if (($memberId.StartsWith("'") -and $memberId.EndsWith("'")) -or ($memberId.StartsWith('"') -and $memberId.EndsWith('"'))) {
        $memberId = $memberId.Substring(1, $memberId.Length - 2)
    }

    if ($memberId -notmatch '^/backends/(?<name>[A-Za-z0-9._-]+)$') {
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidConfiguration `
            -ErrorId 'POC003' `
            -Title 'INVALID BACKEND POOL MEMBER ID' `
            -Details @("Line $LineNumber contains unsupported pool member ID '$memberId'.") `
            -Resolution "Use the literal APIOps backend resource form '/backends/<backend-id>'."
    }

    return $Matches.name
}

function Get-ConfiguredBackendSelection {
    param([string] $Path)

    $lines = @(Get-Content -LiteralPath $Path)
    $backendsSectionCount = @($lines | Where-Object { $_ -match '^backends:\s*(?:#.*)?$' }).Count
    if ($backendsSectionCount -ne 1) {
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidConfiguration `
            -ErrorId 'POC003' `
            -Title 'CONFIGURATION MUST HAVE ONE BACKENDS ARRAY' `
            -Details @("Expected one top-level backends property in '$Path'; found $backendsSectionCount.") `
            -Resolution 'Keep exactly one top-level backends array in the target APIOps configuration.'
    }

    $insideBackends = $false
    $foundBackendsSection = $false
    $names = [System.Collections.Generic.List[string]]::new()
    $nameSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $nameLineNumbers = [ordered]@{}
    $poolMembers = [System.Collections.Generic.Dictionary[string, System.Collections.Generic.List[string]]]::new([System.StringComparer]::Ordinal)
    $configuredPools = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $currentBackendName = $null

    for ($index = 0; $index -lt $lines.Count; $index++) {
        $line = $lines[$index]
        $lineNumber = $index + 1

        if (-not $insideBackends) {
            if ($line -match '^backends:\s*(?:#.*)?$') {
                $insideBackends = $true
                $foundBackendsSection = $true
            }
            continue
        }

        if ($line -match '^\S' -and $line -notmatch '^#') {
            break
        }

        if ($line -match '^  - name:\s*(?<name>[^#]+?)\s*(?:#.*)?$') {
            $backendName = ConvertFrom-BackendNameScalar -Value $Matches.name -LineNumber $lineNumber
            if (-not $nameSet.Add($backendName)) {
                Stop-PocOperation `
                    -ExitCode $script:ExitCodes.InvalidConfiguration `
                    -ErrorId 'POC003' `
                    -Title 'DUPLICATE BACKEND ID IN CONFIGURATION' `
                    -Details @("Backend ID '$backendName' appears more than once in '$Path'.") `
                    -Resolution 'Keep one direct backends entry for each backend ID.'
            }
            $names.Add($backendName)
            $nameLineNumbers[$backendName] = $lineNumber
            $poolMembers.Add($backendName, [System.Collections.Generic.List[string]]::new())
            $currentBackendName = $backendName
            continue
        }

        if ($null -ne $currentBackendName -and $line -match '^        services:\s*(?:#.*)?$') {
            $null = $configuredPools.Add($currentBackendName)
            continue
        }

        if ($null -ne $currentBackendName -and $line -match '^          - id:\s*(?<id>[^#]+?)\s*(?:#.*)?$') {
            if (-not $configuredPools.Contains($currentBackendName)) {
                Stop-PocOperation `
                    -ExitCode $script:ExitCodes.InvalidConfiguration `
                    -ErrorId 'POC003' `
                    -Title 'POOL MEMBER IS OUTSIDE A SERVICES ARRAY' `
                    -Details @("Line $lineNumber in '$Path' is not beneath properties.pool.services.") `
                    -Resolution 'Use the documented indentation for the complete backend-pool services array.'
            }

            $memberName = ConvertFrom-PoolMemberScalar -Value $Matches.id -LineNumber $lineNumber
            if ($poolMembers[$currentBackendName].Contains($memberName)) {
                Stop-PocOperation `
                    -ExitCode $script:ExitCodes.InvalidConfiguration `
                    -ErrorId 'POC003' `
                    -Title 'DUPLICATE BACKEND POOL MEMBER' `
                    -Details @("Pool '$currentBackendName' includes '$memberName' more than once in '$Path'.") `
                    -Resolution 'Keep one services entry for each concrete backend in a pool.'
            }
            $poolMembers[$currentBackendName].Add($memberName)
            continue
        }

        if ($line -match '^  -\s+') {
            Stop-PocOperation `
                -ExitCode $script:ExitCodes.InvalidConfiguration `
                -ErrorId 'POC003' `
                -Title 'INVALID DIRECT BACKEND ITEM' `
                -Details @("Line $lineNumber in '$Path' must begin with exactly '  - name: <backend-id>'.") `
                -Resolution 'Give every direct item in the top-level backends array a name property as its first field.'
        }
    }

    if (-not $foundBackendsSection -or $names.Count -eq 0) {
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidConfiguration `
            -ErrorId 'POC003' `
            -Title 'BACKEND ALLOWLIST IS EMPTY OR MISSING' `
            -Details @("No direct backend names were read from '$Path'.") `
            -Resolution 'Add a top-level backends array with direct items formatted as two spaces, a hyphen, and name: <backend-id>.'
    }

    foreach ($poolName in $configuredPools) {
        if ($poolMembers[$poolName].Count -eq 0) {
            Stop-PocOperation `
                -ExitCode $script:ExitCodes.InvalidConfiguration `
                -ErrorId 'POC003' `
                -Title 'BACKEND POOL SERVICES ARRAY IS EMPTY' `
                -Details @("Pool '$poolName' does not declare any service IDs in '$Path'.") `
                -Resolution 'List every concrete backend that should belong to the target pool.'
        }
    }

    return [pscustomobject]@{
        Names = $names.ToArray()
        NameSet = $nameSet
        NameLineNumbers = $nameLineNumbers
        PoolMembers = $poolMembers
        ConfiguredPools = $configuredPools
    }
}

function Get-CanonicalBackendInventory {
    param(
        [string] $SourcePath,
        [string[]] $SelectedNames,
        [System.Collections.IDictionary] $SelectedNameLineNumbers,
        [string] $ConfigurationFullPath
    )

    $backendsPath = Join-Path $SourcePath 'backends'
    if (-not (Test-Path -LiteralPath $backendsPath -PathType Container)) {
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidSourceArtifacts `
            -ErrorId 'POC004' `
            -Title 'CANONICAL BACKENDS DIRECTORY IS MISSING' `
            -Details @("Expected backend root: $backendsPath", "Configuration: $ConfigurationFullPath") `
            -Resolution 'Restore the canonical artifacts/backends directory before running APIOps.'
    }

    $availableNames = @(Get-ChildItem -LiteralPath $backendsPath -Force -Directory | ForEach-Object Name | Sort-Object)
    $availableSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($availableName in $availableNames) {
        $null = $availableSet.Add($availableName)
    }

    $missingNames = @($SelectedNames | Where-Object { -not $availableSet.Contains($_) } | Sort-Object)
    if ($missingNames.Count -gt 0) {
        $expectedPaths = @($missingNames | ForEach-Object { Join-Path (Join-Path $backendsPath $_) 'backendInformation.json' })
        $resolvedCount = $SelectedNames.Count - $missingNames.Count
        $mismatchSummary = "Mismatch: configuration selects $($SelectedNames.Count) backend IDs; canonical artifacts resolve $resolvedCount " +
            "and cannot resolve $($missingNames.Count)."
        $missingDetails = @(
            "Configuration: $ConfigurationFullPath"
            "Canonical backend root: $backendsPath"
            $mismatchSummary
            'Unresolved configured backend IDs:'
        )
        $missingDetails += @($missingNames | ForEach-Object { "  - $_ (configuration line $($SelectedNameLineNumbers[$_]))" })
        $missingDetails += 'Required artifact path(s) that do not exist:'
        $missingDetails += @($expectedPaths | ForEach-Object { "  - $_" })
        $missingDetails += "Available backend IDs ($($availableNames.Count)):"
        $missingDetails += @($availableNames | ForEach-Object { "  - $_" })
        $missingDetails += ('Why this fails: APIOps configuration can override an artifact-backed resource, but it cannot create a backend ' +
            'whose artifact is absent.')
        $missingDetails += 'Impact: preflight validation stopped before staging, Azure authentication, or APIOps publisher execution.'
        $missingDetails += 'Correction options:'
        $missingDetails += '  1. Intended backend: add backendInformation.json at each required path shown above.'
        $missingDetails += '  2. Typo or stale entry: correct or remove the exact name at the reported configuration line.'
        $missingDetails += 'Matching rule: configured names must match canonical backend directory names exactly, including case.'
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidSourceArtifacts `
            -ErrorId 'POC004' `
            -Title 'CONFIGURATION REFERENCES BACKENDS THAT DO NOT EXIST IN THE CANONICAL ARTIFACTS' `
            -Details $missingDetails `
            -Resolution 'Apply the appropriate correction above, then rerun the preparation step.'
    }

    $invalidArtifacts = [System.Collections.Generic.List[string]]::new()
    $poolNames = [System.Collections.Generic.List[string]]::new()
    $poolNameSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $concreteNames = [System.Collections.Generic.List[string]]::new()
    $concreteNameSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($backendName in $availableNames) {
        $informationPath = Join-Path (Join-Path $backendsPath $backendName) 'backendInformation.json'
        if (-not (Test-Path -LiteralPath $informationPath -PathType Leaf)) {
            $invalidArtifacts.Add("$backendName (missing $informationPath)")
            continue
        }

        try {
            $document = Get-Content -LiteralPath $informationPath -Raw | ConvertFrom-Json
            $isPool = (
                $null -ne $document.properties -and
                $null -ne $document.properties.PSObject.Properties['type'] -and
                [string] $document.properties.type -eq 'Pool'
            )
            if ($isPool) {
                $poolNames.Add($backendName)
                $null = $poolNameSet.Add($backendName)
            }
            else {
                $concreteNames.Add($backendName)
                $null = $concreteNameSet.Add($backendName)
            }
        }
        catch {
            $invalidArtifacts.Add("$backendName (invalid JSON in ${informationPath}: $($_.Exception.Message))")
        }
    }

    if ($invalidArtifacts.Count -gt 0) {
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidSourceArtifacts `
            -ErrorId 'POC004' `
            -Title 'CONFIGURED BACKEND ARTIFACTS ARE INVALID' `
            -Details @($invalidArtifacts) `
            -Resolution 'Restore valid backendInformation.json files for every configured backend before running APIOps.'
    }

    return [pscustomobject]@{
        AvailableNames = $availableNames
        BackendsPath = $backendsPath
        PoolNames = $poolNames.ToArray()
        PoolNameSet = $poolNameSet
        ConcreteNames = $concreteNames.ToArray()
        ConcreteNameSet = $concreteNameSet
    }
}

function Assert-BackendPoolSelection {
    param(
        [pscustomobject] $Selection,
        [pscustomobject] $Inventory,
        [string] $ConfigurationFullPath
    )

    foreach ($configuredPoolName in $Selection.ConfiguredPools) {
        if (-not $Inventory.PoolNameSet.Contains($configuredPoolName)) {
            Stop-PocOperation `
                -ExitCode $script:ExitCodes.InvalidConfiguration `
                -ErrorId 'POC003' `
                -Title 'POOL COMPOSITION TARGET IS NOT A CANONICAL POOL' `
                -Details @("Resource '$configuredPoolName' has a services array but its canonical artifact is not type Pool.") `
                -Resolution 'Move the services array to a selected canonical backend-pool resource.'
        }
    }

    foreach ($poolName in $Inventory.PoolNames) {
        if (-not $Selection.NameSet.Contains($poolName)) {
            continue
        }

        if (-not $Selection.ConfiguredPools.Contains($poolName)) {
            Stop-PocOperation `
                -ExitCode $script:ExitCodes.InvalidConfiguration `
                -ErrorId 'POC003' `
                -Title 'SELECTED POOL HAS NO TARGET COMPOSITION' `
                -Details @("Selected pool '$poolName' has no properties.pool.services override in '$ConfigurationFullPath'.") `
                -Resolution 'Declare the complete target-specific services array for every selected backend pool.'
        }

        foreach ($memberName in $Selection.PoolMembers[$poolName]) {
            if (-not $Selection.NameSet.Contains($memberName)) {
                Stop-PocOperation `
                    -ExitCode $script:ExitCodes.InvalidConfiguration `
                    -ErrorId 'POC003' `
                    -Title 'BACKEND POOL MEMBER IS NOT SELECTED' `
                    -Details @(
                        "Pool: $poolName",
                        "Member: $memberName",
                        "Configuration: $ConfigurationFullPath",
                        'The APIOps publisher was not started and no staging directory was created.'
                    ) `
                    -Resolution "Add '$memberName' as a direct backends entry or remove it from the pool's services array."
            }

            if (-not $Inventory.ConcreteNameSet.Contains($memberName)) {
                Stop-PocOperation `
                    -ExitCode $script:ExitCodes.InvalidConfiguration `
                    -ErrorId 'POC003' `
                    -Title 'BACKEND POOL MEMBER IS NOT A CONCRETE BACKEND' `
                    -Details @("Pool '$poolName' references '$memberName', which is not a canonical concrete backend.") `
                    -Resolution 'Reference only selected concrete backend resources from a pool services array.'
            }
        }
    }
}

function Invoke-ArtifactPreparation {
    try {
        $sourcePath = Get-NormalizedPath -Path $SourceArtifactsPath -MustExist
        $configurationFullPath = Get-NormalizedPath -Path $ConfigurationPath -MustExist
        $destinationPath = Get-NormalizedPath -Path $DestinationArtifactsPath
    }
    catch {
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -ErrorId 'POC002' `
            -Title 'INPUT PATH COULD NOT BE RESOLVED' `
            -Details @($_.Exception.Message) `
            -Resolution 'Confirm that the source and configuration exist and that the destination is a valid separate path.'
    }

    if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) {
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -ErrorId 'POC002' `
            -Title 'SOURCE ARTIFACT PATH IS NOT A DIRECTORY' `
            -Details @("SourceArtifactsPath: $sourcePath") `
            -Resolution 'Pass the canonical APIOps artifact root directory.'
    }

    if (-not (Test-Path -LiteralPath $configurationFullPath -PathType Leaf)) {
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -ErrorId 'POC002' `
            -Title 'CONFIGURATION PATH IS NOT A FILE' `
            -Details @("ConfigurationPath: $configurationFullPath") `
            -Resolution 'Pass one environment APIOps configuration YAML file.'
    }

    if ($sourcePath -eq $destinationPath -or (Test-PathContains -ParentPath $sourcePath -ChildPath $destinationPath) -or
        (Test-PathContains -ParentPath $destinationPath -ChildPath $sourcePath)) {
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -ErrorId 'POC002' `
            -Title 'SOURCE AND DESTINATION PATHS OVERLAP' `
            -Details @("Source: $sourcePath", "Destination: $destinationPath") `
            -Resolution 'Use an isolated staging directory, preferably beneath the CI runner temporary directory.'
    }

    try {
        $auditPath = if ([string]::IsNullOrWhiteSpace($AuditManifestPath)) {
            "$destinationPath.selection.json"
        }
        else {
            Get-NormalizedPath -Path $AuditManifestPath
        }
    }
    catch {
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -ErrorId 'POC002' `
            -Title 'AUDIT MANIFEST PATH COULD NOT BE RESOLVED' `
            -Details @($_.Exception.Message) `
            -Resolution 'Use a valid audit file path outside the source and staged artifact trees.'
    }

    if ($auditPath -eq $sourcePath -or $auditPath -eq $destinationPath -or (Test-PathContains -ParentPath $sourcePath -ChildPath $auditPath) -or
        (Test-PathContains -ParentPath $destinationPath -ChildPath $auditPath)) {
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -ErrorId 'POC002' `
            -Title 'AUDIT MANIFEST PATH OVERLAPS AN ARTIFACT TREE' `
            -Details @("AuditManifestPath: $auditPath", "Source: $sourcePath", "Destination: $destinationPath") `
            -Resolution 'Place the audit manifest beside the staged directory or in a separate release-evidence directory.'
    }

    Write-Host '[1/4] Reading configured backend IDs...'
    $selection = Get-ConfiguredBackendSelection -Path $configurationFullPath
    $selectedNames = @($selection.Names)
    Write-Host "      Selected: $($selectedNames -join ', ')"

    Write-Host '[2/4] Validating configured IDs against the canonical superset...'
    $inventory = Get-CanonicalBackendInventory `
        -SourcePath $sourcePath `
        -SelectedNames $selectedNames `
        -SelectedNameLineNumbers $selection.NameLineNumbers `
        -ConfigurationFullPath $configurationFullPath
    Assert-BackendPoolSelection -Selection $selection -Inventory $inventory -ConfigurationFullPath $configurationFullPath
    Write-Host "      Canonical resources: $($inventory.ConcreteNames.Count) concrete backends, $($inventory.PoolNames.Count) pool."

    if ((Test-Path -LiteralPath $destinationPath) -and -not $Force) {
        Stop-PocOperation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -ErrorId 'POC002' `
            -Title 'DESTINATION ALREADY EXISTS' `
            -Details @("DestinationArtifactsPath: $destinationPath") `
            -Resolution 'Choose a new staging path or explicitly pass -Force to replace it.'
    }

    $stagingStarted = $false
    try {
        Write-Host '[3/4] Copying and filtering the staged artifact tree...'
        if (Test-Path -LiteralPath $destinationPath) {
            Remove-Item -LiteralPath $destinationPath -Recurse -Force
        }

        $null = New-Item -ItemType Directory -Path $destinationPath -Force
        $stagingStarted = $true
        Get-ChildItem -LiteralPath $sourcePath -Force | Copy-Item -Destination $destinationPath -Recurse -Force

        $removedNames = [System.Collections.Generic.List[string]]::new()
        $stagedBackendsPath = Join-Path $destinationPath 'backends'
        foreach ($directory in Get-ChildItem -LiteralPath $stagedBackendsPath -Force -Directory) {
            if (-not $selection.NameSet.Contains($directory.Name)) {
                $removedNames.Add($directory.Name)
                Remove-Item -LiteralPath $directory.FullName -Recurse -Force
            }
        }

        Write-Host '[4/4] Writing selection audit evidence...'
        $auditParent = Split-Path -Path $auditPath -Parent
        if (-not (Test-Path -LiteralPath $auditParent -PathType Container)) {
            $null = New-Item -ItemType Directory -Path $auditParent -Force
        }

        $selectedConcreteNames = @($selectedNames | Where-Object { $inventory.ConcreteNameSet.Contains($_) } | Sort-Object)
        $selectedPoolNames = @($selectedNames | Where-Object { $inventory.PoolNameSet.Contains($_) } | Sort-Object)
        $poolMemberships = [ordered]@{}
        foreach ($poolName in $selectedPoolNames) {
            $poolMemberships[$poolName] = @($selection.PoolMembers[$poolName])
        }

        $manifest = [ordered]@{
            schemaVersion = 1
            status = 'Succeeded'
            generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
            sourceArtifactsPath = $sourcePath
            destinationArtifactsPath = $destinationPath
            configurationPath = $configurationFullPath
            configurationSha256 = (Get-FileHash -LiteralPath $configurationFullPath -Algorithm SHA256).Hash.ToLowerInvariant()
            availableBackendResourceCount = $inventory.AvailableNames.Count
            availableConcreteBackendCount = $inventory.ConcreteNames.Count
            availableBackendPoolCount = $inventory.PoolNames.Count
            selectedBackendResourceCount = $selectedNames.Count
            selectedConcreteBackendCount = $selectedConcreteNames.Count
            selectedBackendPoolCount = $selectedPoolNames.Count
            selectedBackendResources = @($selectedNames | Sort-Object)
            selectedConcreteBackends = $selectedConcreteNames
            selectedBackendPools = $selectedPoolNames
            backendPoolMemberships = $poolMemberships
            removedBackendResourceCount = $removedNames.Count
            removedBackendResources = @($removedNames | Sort-Object)
        }
        $manifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $auditPath -Encoding utf8

        Write-Host `
            "SUCCESS: staged $($selectedConcreteNames.Count) concrete backends and $($selectedPoolNames.Count) pool at '$destinationPath'." `
            -ForegroundColor Green
        Write-Host "Audit manifest: $auditPath"
    }
    catch {
        if ($stagingStarted -and (Test-Path -LiteralPath $destinationPath)) {
            Remove-Item -LiteralPath $destinationPath -Recurse -Force -ErrorAction SilentlyContinue
        }

        if ($_.Exception.Data.Contains('ExitCode')) {
            throw
        }

        Stop-PocOperation `
            -ExitCode $script:ExitCodes.StagingFailure `
            -ErrorId 'POC005' `
            -Title 'STAGING OR AUDIT OUTPUT FAILED' `
            -Details @($_.Exception.Message, "Partial staging was removed: $destinationPath") `
            -Resolution 'Check path permissions and free disk space, then rerun the preparation step.'
    }
}

try {
    Invoke-ArtifactPreparation
    exit $script:ExitCodes.Success
}
catch {
    $exitCode = $script:ExitCodes.UnexpectedFailure
    if ($_.Exception.Data.Contains('ExitCode')) {
        $exitCode = [int] $_.Exception.Data['ExitCode']
    }

    [Console]::Error.WriteLine($_.Exception.Message)
    exit $exitCode
}
