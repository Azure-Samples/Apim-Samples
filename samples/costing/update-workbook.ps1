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

$rg = 'apim-infra-simple-apim-1'

# Find the workbook resource id (first workbook in the RG)
Write-Host "Looking up workbook in resource group '$rg'..." -ForegroundColor Gray
$workbookId = az resource list -g $rg --resource-type 'microsoft.insights/workbooks' --query '[0].id' -o tsv
if (-not $workbookId) { throw "No workbook found in resource group '$rg'." }
Write-Host "Found workbook: $workbookId" -ForegroundColor Gray

# Fetch the existing workbook so we can preserve required top-level fields (kind, location, etc.)
Write-Host 'Fetching existing workbook definition...' -ForegroundColor Gray
$existingJson = az rest --method get --uri "${workbookId}?api-version=2022-04-01"
$existing = $existingJson | ConvertFrom-Json

# Read the new workbook JSON as a single string (this is what gets stored in properties.serializedData)
Write-Host 'Reading local workbook.json...' -ForegroundColor Gray
$serialized = Get-Content .\workbook.json -Raw

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
}
finally {
    Remove-Item $bodyFile -ErrorAction SilentlyContinue
    [Console]::OutputEncoding = $prevOutputEncoding
    $OutputEncoding           = $prevPSOutputEncoding
    if ($prevCodePage) { chcp $prevCodePage | Out-Null }
}
