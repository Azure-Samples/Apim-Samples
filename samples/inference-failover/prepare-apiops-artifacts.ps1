#!/usr/bin/env pwsh

<#
.SYNOPSIS
Creates an environment-specific APIOps artifact tree from a backend superset.

.DESCRIPTION
Copies a complete APIOps artifact tree to a separate staging directory, reads
the top-level backends list from an APIOps publisher configuration YAML file,
and removes backend artifact directories that are not named in that list.

The script validates configured backend names, effective backend-pool members,
and literal set-backend-service policy references before publication. It does
not modify the source artifact tree or delete resources from API Management.

The process has six phases:
1. Validate and resolve all input paths.
2. Read the environment's backend allowlist from the configuration YAML.
3. Validate that every selected backend exists in the source artifacts.
4. Copy the source tree and filter only the staged backends directory.
5. Validate pool membership and literal policy backend references.
6. Write a JSON audit manifest and report the result.

Expected failures use stable exit codes and print an error category, a specific
message, and a suggested corrective action. A failed run removes any partial
staging directory so it cannot be passed accidentally to the APIOps publisher.

.PARAMETER SourceArtifactsPath
Path to the canonical APIOps artifact root. This is the directory that contains
artifact collections such as backends, apis, namedValues, and products. Pass
the artifact root, not the backends directory. The script never changes it.

.PARAMETER DestinationArtifactsPath
Path to the temporary artifact root that the APIOps publisher will consume.
The destination must not equal, contain, or be contained by the source path.
If it exists, the script stops unless Force is supplied.

.PARAMETER ConfigurationPath
Path to configuration.<environment>.yaml. Every backend resource to publish,
including backend pools, must have a direct entry in the top-level backends
array. The script intentionally supports this constrained APIOps YAML shape;
it is not a general-purpose YAML parser.

.PARAMETER AuditManifestPath
Optional path for the JSON selection manifest. The default is adjacent to the
staged artifact directory with a .selection.json suffix. The manifest is kept
outside the artifact tree so the publisher cannot interpret it as an artifact.

.PARAMETER Force
Removes and recreates DestinationArtifactsPath when it already exists. Force
never permits the source and destination trees to overlap.

.OUTPUTS
The script writes human-readable progress to the console and a JSON audit
manifest to AuditManifestPath. It does not write pipeline objects to stdout.

Process exit codes:
    0  Success. The staged tree and audit manifest are ready.
    1  PowerShell could not start or bind the script parameters.
    2  An input path or invocation option is invalid.
    3  The APIOps configuration YAML selection is invalid.
    4  Required source artifacts are missing or unreadable.
    5  A pool or policy references a backend that is not selected.
    6  The staging tree could not be created, copied, filtered, or cleaned up.
    7  The JSON audit manifest could not be created.
    99 An unexpected error occurred.

.EXAMPLE
./prepare-apiops-artifacts.ps1 `
    -SourceArtifactsPath ./apimartifacts `
    -DestinationArtifactsPath "$env:RUNNER_TEMP/apimartifacts-prod" `
    -ConfigurationPath ./configuration.prod.yaml `
    -Force

Creates a PROD staging tree, uses the default adjacent audit-manifest path,
and replaces a previous staging directory if one exists.

.EXAMPLE
./prepare-apiops-artifacts.ps1 `
    -SourceArtifactsPath ./apimartifacts `
    -DestinationArtifactsPath ./out/apimartifacts-qa `
    -ConfigurationPath ./configuration.qa.yaml `
    -AuditManifestPath ./out/qa-backend-selection.json `
    -Verbose

Creates a QA staging tree, writes the audit manifest to an explicit path, and
shows additional diagnostic detail. The command fails if the destination
already exists because Force is not supplied.

.NOTES
Prerequisites:
- PowerShell 7 or later on Windows, Linux, or macOS.
- A canonical APIOps artifact tree containing a backends directory.
- One backendInformation.json file in every selected backend directory.
- A target configuration with exactly one top-level backends array.

Safety boundaries:
- This script does not call Azure or the APIOps publisher.
- This script does not delete resources already deployed in APIM.
- This script does not alter the source artifact tree.
- Dynamic policy backend references cannot be validated statically.

Use Get-Help ./prepare-apiops-artifacts.ps1 -Full to view this documentation.
#>

[CmdletBinding()]
param(
    [string] $SourceArtifactsPath,

    [string] $DestinationArtifactsPath,

    [string] $ConfigurationPath,

    [string] $AuditManifestPath,

    [switch] $Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# These codes form the public automation contract. Do not renumber an existing
# code without updating the guide and every workflow that handles the result.
$script:ExitCodes = [ordered]@{
    Success = 0
    InvalidInput = 2
    InvalidConfiguration = 3
    InvalidSourceArtifacts = 4
    InvalidReferences = 5
    StagingFailure = 6
    AuditFailure = 7
    UnexpectedFailure = 99
}

function New-PreparationException {
    <#
    .SYNOPSIS
    Creates an exception containing the script's stable error metadata.

    .DESCRIPTION
    The top-level error handler reads ExitCode, Category, and Resolution from
    the exception Data dictionary. Keeping this metadata on the exception lets
    nested functions add context without printing duplicate error messages.

    .OUTPUTS
    System.InvalidOperationException
    #>
    param(
        [Parameter(Mandatory = $true)]
        [int] $ExitCode,

        [Parameter(Mandatory = $true)]
        [string] $Category,

        [Parameter(Mandatory = $true)]
        [string] $Message,

        [Parameter(Mandatory = $true)]
        [string] $Resolution,

        [System.Exception] $InnerException
    )

    $exception = if ($null -eq $InnerException) {
        [System.InvalidOperationException]::new($Message)
    }
    else {
        [System.InvalidOperationException]::new($Message, $InnerException)
    }

    $exception.Data['ExitCode'] = $ExitCode
    $exception.Data['Category'] = $Category
    $exception.Data['Resolution'] = $Resolution
    return $exception
}

function Stop-Preparation {
    <#
    .SYNOPSIS
    Stops processing with a categorized, actionable error.

    .DESCRIPTION
    This is the only helper used to create expected terminating errors. It does
    not print output; the top-level handler prints one consistent error block.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [int] $ExitCode,

        [Parameter(Mandatory = $true)]
        [string] $Category,

        [Parameter(Mandatory = $true)]
        [string] $Message,

        [Parameter(Mandatory = $true)]
        [string] $Resolution,

        [System.Exception] $InnerException
    )

    throw (New-PreparationException `
        -ExitCode $ExitCode `
        -Category $Category `
        -Message $Message `
        -Resolution $Resolution `
        -InnerException $InnerException)
}

function Invoke-PreparationOperation {
    <#
    .SYNOPSIS
    Runs one operation and maps unclassified exceptions to a stable exit code.

    .DESCRIPTION
    Errors already created by Stop-Preparation retain their original metadata.
    Other exceptions are wrapped with the phase-specific code and remediation.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock] $Operation,

        [Parameter(Mandatory = $true)]
        [int] $ExitCode,

        [Parameter(Mandatory = $true)]
        [string] $Category,

        [Parameter(Mandatory = $true)]
        [string] $Message,

        [Parameter(Mandatory = $true)]
        [string] $Resolution
    )

    try {
        return & $Operation
    }
    catch {
        if ($_.Exception.Data.Contains('ExitCode')) {
            throw
        }

        Stop-Preparation `
            -ExitCode $ExitCode `
            -Category $Category `
            -Message "$Message $($_.Exception.Message)" `
            -Resolution $Resolution `
            -InnerException $_.Exception
    }
}

function Get-FullPath {
    <#
    .SYNOPSIS
    Converts a relative or absolute path into a normalized absolute path.

    .PARAMETER MustExist
    Uses Resolve-Path when set, which also verifies that the path exists.

    .OUTPUTS
    System.String containing the normalized absolute path.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [switch] $MustExist
    )

    if ($MustExist) {
        return (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
    }

    return [System.IO.Path]::GetFullPath($Path)
}

function Test-PathContains {
    <#
    .SYNOPSIS
    Determines whether ChildPath is inside ParentPath.

    .DESCRIPTION
    A trailing directory separator prevents sibling paths with a shared prefix
    from being treated as parent and child paths. For example, artifacts-old
    is not considered a child of artifacts.

    .OUTPUTS
    System.Boolean
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string] $ParentPath,

        [Parameter(Mandatory = $true)]
        [string] $ChildPath
    )

    $separator = [System.IO.Path]::DirectorySeparatorChar
    $normalizedParent = $ParentPath.TrimEnd($separator, [System.IO.Path]::AltDirectorySeparatorChar) + $separator
    $normalizedChild = $ChildPath.TrimEnd($separator, [System.IO.Path]::AltDirectorySeparatorChar) + $separator
    return $normalizedChild.StartsWith($normalizedParent, [System.StringComparison]::OrdinalIgnoreCase)
}

function ConvertFrom-BackendYamlScalar {
    <#
    .SYNOPSIS
    Reads one backend name or pool-member ID from constrained YAML syntax.

    .DESCRIPTION
    Supports unquoted, single-quoted, and JSON-compatible double-quoted YAML
    scalars. The parser intentionally does not support anchors, aliases, tags,
    multiline scalars, or flow collections. Limiting the supported syntax
    keeps the dependency-free selection parser predictable and reviewable.

    .OUTPUTS
    System.String containing the decoded scalar value.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string] $Value,

        [Parameter(Mandatory = $true)]
        [int] $LineNumber
    )

    $scalar = $Value.Trim()

    if ($scalar.StartsWith("'", [System.StringComparison]::Ordinal)) {
        if (-not $scalar.EndsWith("'", [System.StringComparison]::Ordinal) -or $scalar.Length -lt 2) {
            throw "Unterminated single-quoted YAML scalar on line $LineNumber."
        }

        $result = $scalar.Substring(1, $scalar.Length - 2).Replace("''", "'")
    }
    elseif ($scalar.StartsWith('"', [System.StringComparison]::Ordinal)) {
        try {
            $result = $scalar | ConvertFrom-Json
        }
        catch {
            throw "Invalid double-quoted YAML scalar on line $LineNumber. $($_.Exception.Message)"
        }
    }
    else {
        $result = ($scalar -split '\s+#', 2)[0].TrimEnd()
    }

    if ([string]::IsNullOrWhiteSpace($result)) {
        throw "Empty YAML scalar on line $LineNumber."
    }

    return [string] $result
}

function Assert-SafeBackendName {
    <#
    .SYNOPSIS
    Rejects backend names that are invalid or unsafe as directory names.

    .DESCRIPTION
    The allowlist prevents path traversal and keeps names compatible with APIM
    backend artifact directories. The function returns no value on success and
    throws a configuration error for its caller to categorize on failure.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [int] $LineNumber
    )

    if ($Name -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$' -or
        $Name -in @('.', '..') -or
        $Name.Contains([System.IO.Path]::DirectorySeparatorChar) -or
        $Name.Contains([System.IO.Path]::AltDirectorySeparatorChar) -or
        [System.IO.Path]::GetFileName($Name) -ne $Name) {
        throw "Backend name '$Name' on line $LineNumber is invalid. Use 1-80 letters, numbers, periods, underscores, or hyphens, starting with a letter or number."
    }
}

function Get-BackendSelection {
    <#
    .SYNOPSIS
    Reads the environment backend allowlist and configured pool memberships.

    .DESCRIPTION
    Scans exactly one top-level backends array. Every direct array item must
    begin with '- name:'. For pool overrides, only IDs beneath
    properties.pool.services are collected; unrelated id properties are
    ignored. This avoids mistaking credentials or certificate IDs for pool
    members.

    .OUTPUTS
    PSCustomObject with these properties:
    - Names: ordered backend and pool names selected for publication.
    - NameSet: case-sensitive set used for exact membership checks.
    - PoolMembers: configured pool members grouped by selected backend name.
    - ConfiguredPoolServices: names whose services array is overridden.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    $lines = [System.IO.File]::ReadAllLines($Path)
    $backendSectionFound = $false
    $backendSectionComplete = $false
    $itemIndent = $null
    $currentBackend = $null
    $poolIndent = $null
    $servicesIndent = $null
    $orderedNames = [System.Collections.Generic.List[string]]::new()
    $names = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $poolMembers = [System.Collections.Generic.Dictionary[string, System.Collections.Generic.List[string]]]::new([System.StringComparer]::Ordinal)
    $configuredPoolServices = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)

    $backendSectionCount = @($lines | Where-Object { $_ -match '^backends\s*:' }).Count
    if ($backendSectionCount -ne 1) {
        throw "Configuration '$Path' must contain exactly one top-level backends property; found $backendSectionCount."
    }

    for ($index = 0; $index -lt $lines.Length; $index++) {
        $line = $lines[$index]
        $lineNumber = $index + 1

        if ($line.Contains("`t")) {
            throw "Tab indentation is not supported in YAML (line $lineNumber)."
        }

        if ($line -match '^\s*$' -or $line -match '^\s*#') {
            continue
        }

        $indent = $line.Length - $line.TrimStart(' ').Length

        if (-not $backendSectionFound) {
            if ($line -match '^backends\s*:\s*(?:#.*)?$') {
                $backendSectionFound = $true
            }
            continue
        }

        if ($indent -eq 0) {
            $backendSectionComplete = $true
            break
        }

        $trimmed = $line.TrimStart(' ')

        if ($null -ne $poolIndent -and $indent -le $poolIndent) {
            $poolIndent = $null
            $servicesIndent = $null
        }
        elseif ($null -ne $servicesIndent -and $indent -le $servicesIndent) {
            $servicesIndent = $null
        }

        if ($trimmed -match '^-\s+name\s*:\s*(?<value>.+?)\s*$') {
            if ($null -eq $itemIndent) {
                $itemIndent = $indent
            }

            if ($indent -eq $itemIndent) {
                $name = ConvertFrom-BackendYamlScalar -Value $Matches['value'] -LineNumber $lineNumber
                Assert-SafeBackendName -Name $name -LineNumber $lineNumber

                if (-not $names.Add($name)) {
                    throw "Duplicate backend name '$name' in configuration on line $lineNumber."
                }

                $orderedNames.Add($name)
                $poolMembers.Add($name, [System.Collections.Generic.List[string]]::new())
                $currentBackend = $name
                $poolIndent = $null
                $servicesIndent = $null
                continue
            }
        }

        if ($trimmed -match '^-\s+' -and ($null -eq $itemIndent -or $indent -eq $itemIndent)) {
            if ($null -eq $itemIndent) {
                $itemIndent = $indent
            }

            throw "Each direct item under top-level backends must start with '- name:' (line $lineNumber)."
        }

        if ($null -ne $currentBackend -and $indent -gt $itemIndent -and $trimmed -match '^pool\s*:\s*(?:#.*)?$') {
            $poolIndent = $indent
            $servicesIndent = $null
            continue
        }

        if ($null -ne $poolIndent -and $indent -gt $poolIndent -and $trimmed -match '^services\s*:\s*(?<value>.*?)\s*$') {
            $servicesValue = ($Matches['value'] -split '\s+#', 2)[0].Trim()
            if (-not [string]::IsNullOrWhiteSpace($servicesValue)) {
                throw "Pool services must use block-list syntax and must not be empty (line $lineNumber)."
            }

            $null = $configuredPoolServices.Add($currentBackend)
            $servicesIndent = $indent
            continue
        }

        if ($null -ne $servicesIndent -and $indent -gt $servicesIndent -and $trimmed -match '^-\s+id\s*:\s*(?<value>.+?)\s*$') {
            $backendId = ConvertFrom-BackendYamlScalar -Value $Matches['value'] -LineNumber $lineNumber
            if ($backendId -notmatch '(?:^|/)backends/(?<name>[^/]+)$') {
                throw "Backend pool member ID '$backendId' on line $lineNumber must end with '/backends/<name>'."
            }

            $memberName = $Matches['name']
            Assert-SafeBackendName -Name $memberName -LineNumber $lineNumber
            $poolMembers[$currentBackend].Add($memberName)
        }
    }

    if (-not $backendSectionFound) {
        throw "Configuration '$Path' does not contain a top-level backends property."
    }

    if (-not $backendSectionComplete -and $lines.Length -eq 0) {
        throw "Configuration '$Path' is empty."
    }

    if ($orderedNames.Count -eq 0) {
        throw "Configuration '$Path' must select at least one backend resource."
    }

    return [pscustomobject]@{
        Names = $orderedNames.ToArray()
        NameSet = $names
        PoolMembers = $poolMembers
        ConfiguredPoolServices = $configuredPoolServices
    }
}

function Get-CanonicalPoolMembers {
    <#
    .SYNOPSIS
    Reads pool members from one canonical backendInformation.json artifact.

    .DESCRIPTION
    Concrete backend artifacts do not have properties.pool.services and return
    an empty array. Pool artifacts return the terminal backend name from every
    service ID. Malformed JSON and malformed service IDs stop validation.

    .OUTPUTS
    System.String[] containing zero or more backend names.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string] $InformationFilePath
    )

    try {
        $document = Get-Content -LiteralPath $InformationFilePath -Raw | ConvertFrom-Json
    }
    catch {
        throw "Unable to parse '$InformationFilePath'. $($_.Exception.Message)"
    }

    if ($null -eq $document.properties -or
        $null -eq $document.properties.PSObject.Properties['pool'] -or
        $null -eq $document.properties.pool -or
        $null -eq $document.properties.pool.PSObject.Properties['services']) {
        return @()
    }

    $services = @($document.properties.pool.services)
    $members = [System.Collections.Generic.List[string]]::new()

    foreach ($service in $services) {
        if ($null -eq $service -or [string]::IsNullOrWhiteSpace([string] $service.id)) {
            throw "Backend pool '$InformationFilePath' contains a service without an ID."
        }

        $backendId = [string] $service.id
        if ($backendId -notmatch '(?:^|/)backends/(?<name>[^/]+)$') {
            throw "Backend pool member ID '$backendId' in '$InformationFilePath' must end with '/backends/<name>'."
        }

        $members.Add($Matches['name'])
    }

    return $members.ToArray()
}

function Assert-BackendReferences {
    <#
    .SYNOPSIS
    Verifies that selected pools and literal policy references are complete.

    .DESCRIPTION
    Configured pool services take precedence over canonical pool services,
    matching APIOps publisher override behavior. Every effective pool member
    must be selected. Literal set-backend-service backend-id values in XML
    policies must also be selected. Dynamic expressions and Named Value
    substitutions are skipped because their runtime value cannot be resolved
    safely without an APIM deployment context.

    .OUTPUTS
    No output. Throws on the first invalid reference.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string] $ArtifactsPath,

        [Parameter(Mandatory = $true)]
        [pscustomobject] $Selection
    )

    $backendsPath = Join-Path $ArtifactsPath 'backends'

    foreach ($backendName in $Selection.Names) {
        $informationFile = Join-Path (Join-Path $backendsPath $backendName) 'backendInformation.json'
        if (-not (Test-Path -LiteralPath $informationFile -PathType Leaf)) {
            throw "Selected backend '$backendName' does not contain backendInformation.json."
        }

        $configuredMembers = $Selection.PoolMembers[$backendName]
        if ($Selection.ConfiguredPoolServices.Contains($backendName) -and $configuredMembers.Count -eq 0) {
            throw "Selected backend pool '$backendName' declares an empty services list."
        }

        if ($Selection.ConfiguredPoolServices.Contains($backendName)) {
            $effectiveMembers = @($configuredMembers)
        }
        else {
            $effectiveMembers = @(Get-CanonicalPoolMembers -InformationFilePath $informationFile)
        }

        $distinctMembers = @($effectiveMembers | Sort-Object -Unique)
        if ($distinctMembers.Count -ne $effectiveMembers.Count) {
            throw "Selected backend pool '$backendName' contains duplicate service IDs."
        }

        foreach ($memberName in $effectiveMembers) {
            if ($memberName -eq $backendName) {
                throw "Selected backend pool '$backendName' cannot reference itself."
            }

            if (-not $Selection.NameSet.Contains($memberName)) {
                throw "Selected backend pool '$backendName' references filtered backend '$memberName'."
            }
        }
    }

    $policyPattern = '<set-backend-service\b[^>]*\bbackend-id\s*=\s*["''](?<name>[^"'']+)["'']'
    foreach ($policyFile in Get-ChildItem -LiteralPath $ArtifactsPath -Recurse -File -Filter '*.xml') {
        $content = Get-Content -LiteralPath $policyFile.FullName -Raw
        foreach ($match in [System.Text.RegularExpressions.Regex]::Matches($content, $policyPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            $backendName = $match.Groups['name'].Value.Trim()
            if ($backendName.Contains('{{') -or $backendName.Contains('@(')) {
                continue
            }

            if (-not $Selection.NameSet.Contains($backendName)) {
                throw "Policy '$($policyFile.FullName)' references filtered backend or pool '$backendName'."
            }
        }
    }
}

function Write-GitHubStepSummary {
    <#
    .SYNOPSIS
    Adds the successful selection result to the GitHub Actions job summary.

    .DESCRIPTION
    The summary is optional operational output. A summary-writing failure emits
    a warning but does not invalidate an otherwise complete staging operation.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject] $Result
    )

    if ([string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
        return
    }

    try {
        $summaryLines = [System.Collections.Generic.List[string]]::new()
        $summaryLines.Add('## APIOps backend selection')
        $summaryLines.Add('')
        $summaryLines.Add('- Result: Success (exit code 0)')
        $summaryLines.Add("- Selected backend resources: $($Result.SelectedBackends.Count)")
        $summaryLines.Add("- Filtered backend resources: $($Result.RemovedBackends.Count)")
        $summaryLines.Add("- Audit manifest: ``$($Result.AuditManifestPath)``")
        $summaryLines.Add('')
        $summaryLines.Add('### Selected resources')
        $summaryLines.Add('')
        foreach ($backendName in $Result.SelectedBackends) {
            $summaryLines.Add("- ``$backendName``")
        }

        $summaryLines | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding utf8
    }
    catch {
        Write-Warning "Staging succeeded, but the GitHub job summary could not be updated: $($_.Exception.Message)"
    }
}

function Write-PreparationFailure {
    <#
    .SYNOPSIS
    Writes one consistent, actionable failure block to standard error.

    .DESCRIPTION
    GitHub Actions also receives an error workflow command. The workflow
    command is best-effort and never replaces the standard error block.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [int] $ExitCode,

        [Parameter(Mandatory = $true)]
        [string] $Category,

        [Parameter(Mandatory = $true)]
        [string] $Message,

        [Parameter(Mandatory = $true)]
        [string] $Resolution,

        [System.Management.Automation.ErrorRecord] $ErrorRecord
    )

    [Console]::Error.WriteLine('')
    [Console]::Error.WriteLine('[ERROR] APIOps artifact preparation failed.')
    [Console]::Error.WriteLine("Category : $Category")
    [Console]::Error.WriteLine("Exit code: $ExitCode")
    [Console]::Error.WriteLine("Message  : $Message")
    [Console]::Error.WriteLine("Resolution: $Resolution")

    if ($VerbosePreference -ne 'SilentlyContinue' -and $null -ne $ErrorRecord) {
        [Console]::Error.WriteLine("Exception : $($ErrorRecord.Exception.GetType().FullName)")
        if (-not [string]::IsNullOrWhiteSpace($ErrorRecord.ScriptStackTrace)) {
            [Console]::Error.WriteLine("Stack     : $($ErrorRecord.ScriptStackTrace)")
        }
    }

    if ($env:GITHUB_ACTIONS -eq 'true') {
        $annotation = "$Category (exit code $ExitCode): $Message Resolution: $Resolution"
        $annotation = $annotation.Replace('%', '%25').Replace("`r", '%0D').Replace("`n", '%0A')
        [Console]::Error.WriteLine("::error title=APIOps artifact preparation failed::$annotation")
    }
}

function Invoke-ApimArtifactPreparation {
    <#
    .SYNOPSIS
    Coordinates validation, staging, reference checks, and audit generation.

    .DESCRIPTION
    This function is the single owner of the end-to-end process. Parsing and
    reference helpers remain side-effect free; file-system changes occur only
    in phases 4 and 6. Any failure after staging begins removes the partial
    destination before the categorized error is returned to the caller.

    .OUTPUTS
    PSCustomObject describing the successful staging result.
    #>
    param(
        [string] $SourcePathInput,
        [string] $DestinationPathInput,
        [string] $ConfigurationPathInput,
        [string] $AuditPathInput,
        [switch] $ReplaceDestination
    )

    $requiredInputs = [ordered]@{
        SourceArtifactsPath = $SourcePathInput
        DestinationArtifactsPath = $DestinationPathInput
        ConfigurationPath = $ConfigurationPathInput
    }
    $missingInputs = @($requiredInputs.GetEnumerator() | Where-Object { [string]::IsNullOrWhiteSpace([string] $_.Value) } | ForEach-Object Key)
    if ($missingInputs.Count -gt 0) {
        Stop-Preparation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -Category 'Invalid input' `
            -Message "Required parameter values are missing: $($missingInputs -join ', ')." `
            -Resolution 'Run the script with -SourceArtifactsPath, -DestinationArtifactsPath, and -ConfigurationPath. Use Get-Help with -Full for examples.'
    }

    Write-Host '=== APIOps Environment Artifact Preparation ===' -ForegroundColor Cyan
    Write-Host '[1/6] Validating and resolving input paths...'

    $sourcePath = Invoke-PreparationOperation `
        -ExitCode $script:ExitCodes.InvalidInput `
        -Category 'Invalid input' `
        -Message "Could not resolve source artifact path '$SourcePathInput'." `
        -Resolution 'Confirm that SourceArtifactsPath exists and points to the APIOps artifact root.' `
        -Operation { Get-FullPath -Path $SourcePathInput -MustExist }

    $configurationFullPath = Invoke-PreparationOperation `
        -ExitCode $script:ExitCodes.InvalidInput `
        -Category 'Invalid input' `
        -Message "Could not resolve configuration path '$ConfigurationPathInput'." `
        -Resolution 'Confirm that ConfigurationPath exists and points to the intended environment configuration YAML file.' `
        -Operation { Get-FullPath -Path $ConfigurationPathInput -MustExist }

    $destinationPath = Invoke-PreparationOperation `
        -ExitCode $script:ExitCodes.InvalidInput `
        -Category 'Invalid input' `
        -Message "Could not normalize destination artifact path '$DestinationPathInput'." `
        -Resolution 'Use a valid local or runner-temporary directory path for DestinationArtifactsPath.' `
        -Operation { Get-FullPath -Path $DestinationPathInput }

    if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) {
        Stop-Preparation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -Category 'Invalid input' `
            -Message "SourceArtifactsPath is not a directory: $sourcePath" `
            -Resolution 'Pass the APIOps artifact root directory, not an individual artifact file.'
    }

    if (-not (Test-Path -LiteralPath $configurationFullPath -PathType Leaf)) {
        Stop-Preparation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -Category 'Invalid input' `
            -Message "ConfigurationPath is not a file: $configurationFullPath" `
            -Resolution 'Pass one configuration.<environment>.yaml file.'
    }

    if ($sourcePath -eq $destinationPath -or
        (Test-PathContains -ParentPath $sourcePath -ChildPath $destinationPath) -or
        (Test-PathContains -ParentPath $destinationPath -ChildPath $sourcePath)) {
        Stop-Preparation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -Category 'Invalid input' `
            -Message 'Source and destination artifact paths overlap.' `
            -Resolution 'Choose a separate staging directory, preferably beneath the CI runner temporary directory.'
    }

    $auditPath = if ([string]::IsNullOrWhiteSpace($AuditPathInput)) {
        "$destinationPath.selection.json"
    }
    else {
        Invoke-PreparationOperation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -Category 'Invalid input' `
            -Message "Could not normalize audit manifest path '$AuditPathInput'." `
            -Resolution 'Use a valid file path outside both the source and staged artifact trees.' `
            -Operation { Get-FullPath -Path $AuditPathInput }
    }

    if ($auditPath -eq $sourcePath -or $auditPath -eq $destinationPath -or
        (Test-PathContains -ParentPath $sourcePath -ChildPath $auditPath) -or
        (Test-PathContains -ParentPath $destinationPath -ChildPath $auditPath)) {
        Stop-Preparation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -Category 'Invalid input' `
            -Message "AuditManifestPath must be outside the source and staged artifact trees: $auditPath" `
            -Resolution 'Place the audit manifest beside the staged directory or in a separate release-evidence directory.'
    }

    Write-Verbose "Source artifacts : $sourcePath"
    Write-Verbose "Configuration    : $configurationFullPath"
    Write-Verbose "Staged artifacts : $destinationPath"
    Write-Verbose "Audit manifest   : $auditPath"

    Write-Host '[2/6] Reading the target backend allowlist...'
    $selection = Invoke-PreparationOperation `
        -ExitCode $script:ExitCodes.InvalidConfiguration `
        -Category 'Invalid configuration' `
        -Message "Could not read the backend selection from '$configurationFullPath'." `
        -Resolution 'Correct the top-level backends array. Each direct item must begin with - name:, and pool services must use block-list syntax.' `
        -Operation { Get-BackendSelection -Path $configurationFullPath }
    Write-Host "      Selected $($selection.Names.Count) backend resources, including pools."

    Write-Host '[3/6] Checking selected resources against the source artifacts...'
    $sourceInventory = Invoke-PreparationOperation `
        -ExitCode $script:ExitCodes.InvalidSourceArtifacts `
        -Category 'Invalid source artifacts' `
        -Message "The source artifact tree '$sourcePath' is incomplete or unreadable." `
        -Resolution 'Re-run the APIOps extractor or restore the missing backend directories and backendInformation.json files.' `
        -Operation {
            $sourceBackendsPath = Join-Path $sourcePath 'backends'
            if (-not (Test-Path -LiteralPath $sourceBackendsPath -PathType Container)) {
                throw "The required backends directory does not exist: $sourceBackendsPath"
            }

            $availableNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
            foreach ($directory in Get-ChildItem -LiteralPath $sourceBackendsPath -Force -Directory) {
                $null = $availableNames.Add($directory.Name)
            }

            $missingNames = @($selection.Names | Where-Object { -not $availableNames.Contains($_) })
            if ($missingNames.Count -gt 0) {
                throw "Selected backend directories do not exist: $($missingNames -join ', ')"
            }

            foreach ($backendName in $selection.Names) {
                $informationFile = Join-Path (Join-Path $sourceBackendsPath $backendName) 'backendInformation.json'
                if (-not (Test-Path -LiteralPath $informationFile -PathType Leaf)) {
                    throw "Selected backend '$backendName' is missing backendInformation.json."
                }

                try {
                    $null = Get-Content -LiteralPath $informationFile -Raw | ConvertFrom-Json
                }
                catch {
                    throw "Selected backend '$backendName' has invalid backendInformation.json. $($_.Exception.Message)"
                }
            }

            return [pscustomobject]@{
                BackendsPath = $sourceBackendsPath
                AvailableNames = $availableNames
            }
        }
    Write-Host "      Found $($sourceInventory.AvailableNames.Count) backend resources in the canonical superset."

    # This check intentionally occurs before the staging try/catch. When Force
    # is absent, the existing directory remains user-owned and must never enter
    # the cleanup path for artifacts created by this script.
    if ((Test-Path -LiteralPath $destinationPath) -and -not $ReplaceDestination) {
        Stop-Preparation `
            -ExitCode $script:ExitCodes.InvalidInput `
            -Category 'Invalid input' `
            -Message "DestinationArtifactsPath already exists: $destinationPath" `
            -Resolution 'Choose a new staging path or rerun with -Force to replace the existing destination.'
    }

    try {
        Write-Host '[4/6] Copying the artifact tree and filtering staged backends...'
        $removedNames = @(Invoke-PreparationOperation `
            -ExitCode $script:ExitCodes.StagingFailure `
            -Category 'Staging failure' `
            -Message "Could not prepare staged artifacts at '$destinationPath'." `
            -Resolution 'Check file-system permissions and available disk space. Remove stale files or rerun with -Force when replacing the destination is intended.' `
            -Operation {
                if (Test-Path -LiteralPath $destinationPath) {
                    Write-Verbose "Removing existing staging directory because -Force was supplied: $destinationPath"
                    Remove-Item -LiteralPath $destinationPath -Recurse -Force
                }

                $null = New-Item -ItemType Directory -Path $destinationPath -Force
                Get-ChildItem -LiteralPath $sourcePath -Force |
                    Copy-Item -Destination $destinationPath -Recurse -Force

                $stagedBackendsPath = Join-Path $destinationPath 'backends'
                $removed = [System.Collections.Generic.List[string]]::new()
                foreach ($directory in Get-ChildItem -LiteralPath $stagedBackendsPath -Force -Directory) {
                    if (-not $selection.NameSet.Contains($directory.Name)) {
                        $removed.Add($directory.Name)
                        Remove-Item -LiteralPath $directory.FullName -Recurse -Force
                    }
                }

                return $removed.ToArray()
            })
        Write-Host "      Removed $($removedNames.Count) unselected backend resources from staging."

        Write-Host '[5/6] Validating pool members and policy backend references...'
        $null = Invoke-PreparationOperation `
            -ExitCode $script:ExitCodes.InvalidReferences `
            -Category 'Invalid backend references' `
            -Message 'The selected backend set is not dependency-complete.' `
            -Resolution 'Select every backend referenced by a retained pool or literal set-backend-service policy, then rerun the script.' `
            -Operation { Assert-BackendReferences -ArtifactsPath $destinationPath -Selection $selection }

        Write-Host '[6/6] Writing the backend selection audit manifest...'
        $auditManifest = [ordered]@{
            schemaVersion = 1
            status = 'Succeeded'
            exitCode = $script:ExitCodes.Success
            generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
            sourceArtifactsPath = $sourcePath
            destinationArtifactsPath = $destinationPath
            configurationPath = $configurationFullPath
            configurationSha256 = (Get-FileHash -LiteralPath $configurationFullPath -Algorithm SHA256).Hash.ToLowerInvariant()
            availableBackendCount = $sourceInventory.AvailableNames.Count
            selectedBackendCount = $selection.Names.Count
            selectedBackends = @($selection.Names | Sort-Object)
            removedBackendCount = $removedNames.Count
            removedBackends = @($removedNames | Sort-Object)
        }

        $null = Invoke-PreparationOperation `
            -ExitCode $script:ExitCodes.AuditFailure `
            -Category 'Audit failure' `
            -Message "Could not write the selection audit manifest '$auditPath'." `
            -Resolution 'Check the audit directory permissions and available disk space, then rerun the script. The partial staging directory has been removed.' `
            -Operation {
                $auditParent = Split-Path -Path $auditPath -Parent
                if (-not (Test-Path -LiteralPath $auditParent -PathType Container)) {
                    $null = New-Item -ItemType Directory -Path $auditParent -Force
                }

                # Write to a temporary sibling first so a failed write cannot
                # leave a truncated manifest that appears valid to automation.
                $temporaryAuditPath = Join-Path $auditParent ".$(Split-Path -Path $auditPath -Leaf).$([guid]::NewGuid().ToString('N')).tmp"
                try {
                    $auditManifest | ConvertTo-Json -Depth 10 |
                        Set-Content -LiteralPath $temporaryAuditPath -Encoding utf8
                    Move-Item -LiteralPath $temporaryAuditPath -Destination $auditPath -Force
                }
                finally {
                    Remove-Item -LiteralPath $temporaryAuditPath -Force -ErrorAction SilentlyContinue
                }
            }
    }
    catch {
        if (Test-Path -LiteralPath $destinationPath) {
            try {
                Remove-Item -LiteralPath $destinationPath -Recurse -Force -ErrorAction Stop
                Write-Verbose "Removed partial staging directory after failure: $destinationPath"
            }
            catch {
                Write-Warning "Could not completely remove the partial staging directory '$destinationPath': $($_.Exception.Message)"
            }
        }
        throw
    }

    return [pscustomobject]@{
        DestinationArtifactsPath = $destinationPath
        AuditManifestPath = $auditPath
        SelectedBackends = @($selection.Names | Sort-Object)
        RemovedBackends = @($removedNames | Sort-Object)
    }
}

# The entry point prints exactly one final result and owns the process exit
# code. Helper functions throw metadata-rich exceptions but never call exit.
try {
    $result = Invoke-ApimArtifactPreparation `
        -SourcePathInput $SourceArtifactsPath `
        -DestinationPathInput $DestinationArtifactsPath `
        -ConfigurationPathInput $ConfigurationPath `
        -AuditPathInput $AuditManifestPath `
        -ReplaceDestination:$Force

    Write-Host ''
    Write-Host '[SUCCESS] APIOps artifact preparation completed.' -ForegroundColor Green
    Write-Host "Exit code : $($script:ExitCodes.Success)"
    Write-Host "Staged at : $($result.DestinationArtifactsPath)"
    Write-Host "Audit file: $($result.AuditManifestPath)"
    Write-Host "Selected  : $($result.SelectedBackends.Count) backend resources"
    Write-Host "Filtered  : $($result.RemovedBackends.Count) backend resources"
    Write-GitHubStepSummary -Result $result
    exit $script:ExitCodes.Success
}
catch {
    $exitCode = $script:ExitCodes.UnexpectedFailure
    $category = 'Unexpected failure'
    $resolution = 'Rerun with -Verbose for diagnostic context. If the problem continues, provide the complete error block to the script maintainer.'

    if ($_.Exception.Data.Contains('ExitCode')) {
        $exitCode = [int] $_.Exception.Data['ExitCode']
        $category = [string] $_.Exception.Data['Category']
        $resolution = [string] $_.Exception.Data['Resolution']
    }

    Write-PreparationFailure `
        -ExitCode $exitCode `
        -Category $category `
        -Message $_.Exception.Message `
        -Resolution $resolution `
        -ErrorRecord $_
    exit $exitCode
}
