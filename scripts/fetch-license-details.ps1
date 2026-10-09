param([int]$Limit = 0)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$cacheDir = Join-Path $taskRoot 'exports/license-details-cache'
New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
$snapshot = Join-Path $cacheDir 'source-rows.json'
if (Test-Path -LiteralPath $snapshot) {
    $rows = @(Get-Content -Raw -LiteralPath $snapshot | ConvertFrom-Json)
} else {
    $rows = @(Import-Csv (Join-Path $taskRoot 'exports/cdi-agents.csv'))
}
if ($Limit -gt 0) { $rows = @($rows | Select-Object -First $Limit) }
$completed = 0
foreach ($row in $rows) {
    if ($row.license_number -notmatch '^[A-Za-z0-9]+$') { throw 'Invalid license identifier' }
    $uri = [uri]$row.license_url
    if ($uri.Scheme -ne 'https' -or $uri.Host -ne 'cdicloud.insurance.ca.gov' -or $uri.AbsolutePath -ne '/cal/LicenseDetail') { throw 'Unexpected licensing URL' }
    $target = Join-Path $cacheDir ($row.license_number + '.html')
    $errorTarget = Join-Path $cacheDir ($row.license_number + '.error.txt')
    if (-not (Test-Path -LiteralPath $target)) {
        $lastError = ''
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 30
                if ($response.Content -notmatch 'id="licenseDetailGrid"') { throw 'License detail table missing' }
                if ($response.Content -notmatch ('License #:\s*' + [regex]::Escape($row.license_number) + '\s*<')) { throw 'License identifier does not match' }
                [System.IO.File]::WriteAllText($target, $response.Content, [System.Text.UTF8Encoding]::new($false))
                $lastError = ''
                break
            } catch {
                $lastError = $_.Exception.Message
                if ($attempt -lt 3) { Start-Sleep -Seconds 2 }
            }
        }
        if ($lastError) { [System.IO.File]::WriteAllText($errorTarget, $lastError) }
        Start-Sleep -Milliseconds 750
    }
    $completed++
    if ($completed % 10 -eq 0 -or $completed -eq $rows.Count) { Write-Output "$completed/$($rows.Count) licensing pages checked" }
}
