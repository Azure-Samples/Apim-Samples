param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $rg
)

Write-Host '=== Update Inference Failover Workbook ===' -ForegroundColor Cyan

$displayNamePrefix = 'APIM Inference Failover'
$workbookJsonPath = Join-Path $PSScriptRoot 'inference-failover.workbook.json'
$candidatesJson = az resource list -g $rg --resource-type 'microsoft.insights/workbooks' --query "[?tags.\`"hidden-title\`" != null && starts_with(tags.\`"hidden-title\`", '$displayNamePrefix')].id" -o json
$candidates = @()
if (-not [string]::IsNullOrWhiteSpace($candidatesJson)) {
    $candidates = @($candidatesJson | ConvertFrom-Json)
}

if ($candidates.Count -ne 1) {
    throw "Expected exactly one workbook beginning '$displayNamePrefix' in resource group '$rg'; found $($candidates.Count). Deploy the sample or remove orphaned workbooks first."
}

$workbookId = $candidates[0]
$existingJson = az rest --method get --uri $workbookId --url-parameters 'api-version=2022-04-01' 'canFetchContent=true'
$existing = $existingJson | ConvertFrom-Json
$sourceWorkbook = Get-Content $workbookJsonPath -Raw | ConvertFrom-Json
$existingWorkbook = $existing.properties.serializedData | ConvertFrom-Json

$existingParameterValues = @{}
foreach ($item in @($existingWorkbook.items)) {
    if ($item.type -eq 9 -and $item.content.parameters) {
        foreach ($parameter in @($item.content.parameters)) {
            $existingParameterValues[$parameter.name] = $parameter.value
        }
    }
}

foreach ($item in @($sourceWorkbook.items)) {
    if ($item.type -eq 9 -and $item.content.parameters) {
        foreach ($parameter in @($item.content.parameters)) {
            if ($existingParameterValues.ContainsKey($parameter.name)) {
                $parameter.value = $existingParameterValues[$parameter.name]
            }
        }
    }
}

$existing.properties.serializedData = $sourceWorkbook | ConvertTo-Json -Depth 100 -Compress

$bodyFile = New-TemporaryFile
try {
    $body = $existing | ConvertTo-Json -Depth 100 -Compress
    Set-Content -Path $bodyFile -Value $body -Encoding UTF8 -NoNewline
    az rest --method put --uri "${workbookId}?api-version=2022-04-01" --headers 'Content-Type=application/json' --body "@$($bodyFile.FullName)" | Out-Null
    Write-Host "Workbook updated: $workbookId" -ForegroundColor Green
}
finally {
    Remove-Item $bodyFile -ErrorAction SilentlyContinue
}
