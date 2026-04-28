param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $rg
)

Write-Host '=== Update Workbook Script ===' -ForegroundColor Cyan

# Force UTF-8 end-to-end so Azure CLI (Python/knack) can emit the workbook JSON
# (which contains emoji and other non-cp1252 characters) without the
# 'Unable to encode the output with cp1252 encoding. Unsupported characters are
# discarded.' warning on Windows PowerShell hosts. We also flip the active
# console codepage to 65001 (UTF-8) for the duration of the script and enable
# PEP 540 UTF-8 mode in the child Python process.
$prevOutputEncoding        = [Console]::OutputEncoding
$prevPSOutputEncoding      = $OutputEncoding
$prevCodePage              = (chcp) -replace '[^\d]', ''
[Console]::OutputEncoding  = [System.Text.UTF8Encoding]::new()
$OutputEncoding            = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING      = 'utf-8'
$env:PYTHONUTF8            = '1'
chcp 65001 | Out-Null

# Find the costing workbook in the resource group. Filter by a display name
# starting with 'APIM Cost Tracking' (stored as the 'hidden-title' tag) so we
# cannot accidentally pick up an unrelated or orphaned workbook in the same
# RG. If multiple matches exist, fail loudly so the caller can delete the
# orphan rather than silently updating the wrong one.
Write-Host "Looking up costing workbook in resource group '$rg'..." -ForegroundColor Gray
$candidatesJson = az resource list -g $rg --resource-type 'microsoft.insights/workbooks' --query "[?tags.\`"hidden-title\`" != null && starts_with(tags.\`"hidden-title\`", 'APIM Cost Tracking')].id" -o json
$candidates = @()
if (-not [string]::IsNullOrWhiteSpace($candidatesJson)) {
    $candidates = @($candidatesJson | ConvertFrom-Json)
}

if ($candidates.Count -eq 0) {
    throw "No costing workbook (display name starting 'APIM Cost Tracking') found in resource group '$rg'. Deploy the costing sample first."
}
if ($candidates.Count -gt 1) {
    Write-Host 'Multiple matching workbooks found:' -ForegroundColor Yellow
    $candidates | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    throw "More than one costing workbook found in resource group '$rg'. Delete orphans (e.g. workbooks whose sourceId references a deleted Log Analytics workspace) before re-running."
}

$workbookId = $candidates[0]
Write-Host "Found workbook: $workbookId" -ForegroundColor Gray

$tenantId = az account show --query tenantId -o tsv
$workbookPortalUrl = if (-not [string]::IsNullOrWhiteSpace($tenantId)) {
    "https://ms.portal.azure.com/#@$tenantId/resource$workbookId/workbook"
}
else {
    "https://ms.portal.azure.com/#resource$workbookId/workbook"
}

# Fetch the existing workbook so we can preserve required top-level fields
# (kind, location, tags, etc.). 'canFetchContent=true' is required; without
# it the ARM GET response returns properties.serializedData as null, which
# would cause every token-substitution lookup below to silently fall back to
# empty values and leave '__APP_INSIGHTS_NAME__' style placeholders in the
# uploaded body.
Write-Host 'Fetching existing workbook definition...' -ForegroundColor Gray
$existingJson = az rest --method get --uri $workbookId --url-parameters 'api-version=2022-04-01' 'canFetchContent=true'
$existing = $existingJson | ConvertFrom-Json

function Get-WorkbookParameterValue {
    param(
        [AllowNull()]
        [object[]] $Items,

        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    if (-not $Items) {
        return $null
    }

    foreach ($item in $Items) {
        if ($item.type -eq 9 -and $item.content.parameters) {
            $parameter = $item.content.parameters | Where-Object { $_.name -eq $Name } | Select-Object -First 1
            if ($null -ne $parameter) {
                $value = [string] $parameter.value
                # Reject placeholder-shaped values (e.g. '__APIM_SKU__'). These
                # indicate the previously deployed workbook itself still held
                # unsubstituted Bicep tokens, so we treat them as missing
                # rather than re-substituting a placeholder with itself.
                if ($value -match '^__[A-Z0-9_]+__$') {
                    return $null
                }
                return $value
            }
        }

        if ($item.content.items) {
            $nestedValue = Get-WorkbookParameterValue -Items $item.content.items -Name $Name
            if (-not [string]::IsNullOrEmpty($nestedValue)) {
                return $nestedValue
            }
        }
    }

    return $null
}

# Read the new workbook JSON as a single string (this is what gets stored in properties.serializedData)
Write-Host 'Reading local costing.workbook.json...' -ForegroundColor Gray
$workbookJsonPath = Join-Path $PSScriptRoot 'costing.workbook.json'
$serialized = Get-Content $workbookJsonPath -Raw

$existingSerialized = [string] $existing.properties.serializedData
$existingWorkbook = $null
if (-not [string]::IsNullOrWhiteSpace($existingSerialized)) {
    try {
        $existingWorkbook = $existingSerialized | ConvertFrom-Json
    }
    catch {
        Write-Warning 'Could not parse existing workbook serializedData as JSON; token preservation will use defaults where needed.'
    }
}

$existingItems = @()
if ($existingWorkbook -and $existingWorkbook.PSObject.Properties['items'] -and $existingWorkbook.items) {
    $existingItems = @($existingWorkbook.items)
}
elseif ($existingWorkbook -and $existingWorkbook.PSObject.Properties['content'] -and $existingWorkbook.content -and $existingWorkbook.content.PSObject.Properties['items'] -and $existingWorkbook.content.items) {
    $existingItems = @($existingWorkbook.content.items)
}

$appInsightsMatch = [regex]::Match($existingSerialized, 'app\("(?<appId>[^"]+)"\)\.customMetrics')
$appInsightsAppId = if ($appInsightsMatch.Success) { $appInsightsMatch.Groups['appId'].Value } else { '' }
# If the previously deployed workbook already contained an unsubstituted
# placeholder, the regex match will hand us back the placeholder itself.
# Discard it and fall through to live discovery below.
if ($appInsightsAppId -match '^__[A-Z0-9_]+__$') {
    $appInsightsAppId = ''
}

# Fall back to live Azure discovery for the App Insights AppId. The
# infrastructure deploys exactly one Application Insights component into the
# resource group (named 'appi-<suffix>'); read its AppId directly so we no
# longer depend on the previously deployed workbook holding a substituted
# value. This is the single most common source of placeholder leakage.
if ([string]::IsNullOrWhiteSpace($appInsightsAppId)) {
    Write-Host 'Discovering Application Insights AppId from Azure...' -ForegroundColor Gray
    $appInsightsIdsJson = az resource list -g $rg --resource-type 'microsoft.insights/components' --query '[].id' -o json
    $appInsightsIds = @()
    if (-not [string]::IsNullOrWhiteSpace($appInsightsIdsJson)) {
        $appInsightsIds = @($appInsightsIdsJson | ConvertFrom-Json)
    }
    if ($appInsightsIds.Count -eq 1) {
        $appInsightsAppId = az resource show --ids $appInsightsIds[0] --query 'properties.AppId' -o tsv
        Write-Host "  Resolved AppId: $appInsightsAppId" -ForegroundColor Gray
    }
    elseif ($appInsightsIds.Count -gt 1) {
        Write-Warning "Multiple Application Insights components found in '$rg'; cannot auto-pick one. Re-deploy via Bicep to seed the workbook with a substituted value."
    }
    else {
        Write-Warning "No Application Insights component found in '$rg'."
    }
}
$baseMonthlyCost = Get-WorkbookParameterValue -Items $existingItems -Name 'BaseMonthlyCost'
$completionTokenRate = Get-WorkbookParameterValue -Items $existingItems -Name 'CompletionTokenRate'
$promptTokenRate = Get-WorkbookParameterValue -Items $existingItems -Name 'PromptTokenRate'
$apimSku = Get-WorkbookParameterValue -Items $existingItems -Name 'ApimSku'
$perKRate = Get-WorkbookParameterValue -Items $existingItems -Name 'PerRequestRate'

# Fall back to the Bicep defaults from samples/costing/main.bicep when the
# deployed workbook has no usable value (e.g. it was previously corrupted by
# a failed push that left literal placeholder strings in the parameters).
if ([string]::IsNullOrWhiteSpace($apimSku))             { $apimSku = 'Basicv2' }
if ([string]::IsNullOrWhiteSpace($baseMonthlyCost))     { $baseMonthlyCost = '150.01' }
if ([string]::IsNullOrWhiteSpace($perKRate))            { $perKRate = '0.003' }
if ([string]::IsNullOrWhiteSpace($promptTokenRate))     { $promptTokenRate = '0.00025' }
if ([string]::IsNullOrWhiteSpace($completionTokenRate)) { $completionTokenRate = '0.002' }

$tokenValues = [ordered] @{
    '__APP_INSIGHTS_NAME__'     = $appInsightsAppId
    '__APIM_SKU__'              = $apimSku
    '__BASE_MONTHLY_COST__'     = $baseMonthlyCost
    '__COMPLETION_TOKEN_RATE__' = $completionTokenRate
    '__PER_K_RATE__'            = $perKRate
    '__PROMPT_TOKEN_RATE__'     = $promptTokenRate
    '987654321.123456'          = $baseMonthlyCost
}

# Fail loudly if any required token cannot be resolved. Silently skipping
# substitution would leave literal '__APP_INSIGHTS_NAME__' style strings in
# the deployed workbook, which then surface as broken queries in the portal.
$missingTokens = @()
foreach ($token in $tokenValues.GetEnumerator()) {
    if ([string]::IsNullOrEmpty($token.Value)) {
        $missingTokens += $token.Key
        continue
    }
    if ($serialized.Contains($token.Key)) {
        $serialized = $serialized.Replace($token.Key, $token.Value)
    }
}

# Verify no placeholder survived (covers tokens we did not enumerate above and
# guards against future regressions in the token list).
$residualMatches = [regex]::Matches($serialized, '__[A-Z][A-Z0-9_]*__')
if ($residualMatches.Count -gt 0) {
    $residual = $residualMatches | ForEach-Object { $_.Value } | Sort-Object -Unique
    throw "Workbook serializedData still contains unsubstituted placeholders: $($residual -join ', '). Source values were missing for: $($missingTokens -join ', '). Re-deploy the costing sample via Bicep first to seed parameter values."
}

# Update serializedData in place while preserving kind, location, tags, etc.
$existing.properties.serializedData = $serialized

# Write the full body to a temp file (Windows has an 8191-char command-line limit)
$body = $existing | ConvertTo-Json -Depth 100 -Compress
$bodyFile = New-TemporaryFile
Set-Content -Path $bodyFile -Value $body -Encoding UTF8 -NoNewline

try {
    Write-Host 'Uploading updated workbook (PUT)...' -ForegroundColor Gray
    # Merge stderr into the pipeline and drop the benign cp1252 encoding
    # warning that knack/Azure CLI emits on Windows even when PYTHONUTF8=1
    # and the console codepage is 65001. Real errors (non-warning lines) are
    # passed through so failures still surface.
    az rest `
        --method put `
        --uri "${workbookId}?api-version=2022-04-01" `
        --headers 'Content-Type=application/json' `
        --body "@$($bodyFile.FullName)" 2>&1 |
        Where-Object { $_ -notmatch 'Unable to encode the output with cp1252 encoding' } |
        Out-Null
    Write-Host 'Workbook updated successfully.' -ForegroundColor Green
    Write-Host "Workbook link: $workbookPortalUrl" -ForegroundColor Cyan
}
finally {
    Remove-Item $bodyFile -ErrorAction SilentlyContinue
    [Console]::OutputEncoding = $prevOutputEncoding
    $OutputEncoding           = $prevPSOutputEncoding
    if ($prevCodePage) { chcp $prevCodePage | Out-Null }
}
