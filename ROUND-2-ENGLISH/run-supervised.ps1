param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$nodePath = (Get-Command node -ErrorAction Stop).Source
$logDirectory = Join-Path $PSScriptRoot 'logs'
$stopFile = Join-Path $PSScriptRoot 'STOP-SUPERVISOR'
$retrySeconds = @(120, 300, 3600)
if ($CheckOnly) {
    Write-Output "Node: $nodePath; restart waits: $($retrySeconds -join ', ') seconds; stop file: $stopFile"
    exit 0
}
$mutex = [System.Threading.Mutex]::new($false, 'Local\CDI-English-Round2-Supervisor')
if (-not $mutex.WaitOne(0)) { throw 'The round-two supervisor is already running.' }
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
function Write-SupervisorLog([string]$Message) {
    Add-Content -LiteralPath (Join-Path $logDirectory 'supervisor.log') -Value "[$([DateTime]::Now.ToString('s'))] $Message"
}
try {
    Write-SupervisorLog 'Started. Existing database and CSV will be reused.'
    for ($restart = 0; $restart -le $retrySeconds.Count; $restart++) {
        if (Test-Path -LiteralPath $stopFile) { Write-SupervisorLog 'Stop file found; exiting.'; break }
        $attemptLog = Join-Path $logDirectory ("supervised-{0}-{1}.log" -f ([DateTime]::Now.ToString('yyyyMMdd-HHmmss')), $restart)
        Write-SupervisorLog "Starting scraper; output: $attemptLog"
        # Windows PowerShell can treat native stderr as an error even when redirected.
        $ErrorActionPreference = 'Continue'
        & $nodePath --experimental-sqlite --disable-warning=ExperimentalWarning --import tsx ../src/scrape.ts 2>&1 |
            ForEach-Object { Add-Content -LiteralPath $attemptLog -Value ([string]$_) }
        $scraperExit = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        $runText = if (Test-Path -LiteralPath $attemptLog) { Get-Content -LiteralPath $attemptLog -Raw } else { '' }
        if (Test-Path -LiteralPath $stopFile) { Write-SupervisorLog 'Stop file found; no restart.'; break }
        if ($scraperExit -eq 0) { Write-SupervisorLog 'Scraper exited successfully; no restart.'; break }
        $manualReview = $runText -match '(?i)\b403\b|\b429\b|cloudflare|captcha|verify you are human|verification challenge|access denied'
        $timeout = $runText -match '(?i)timed out|timeout|ETIMEDOUT'
        if ($manualReview -or -not $timeout) { Write-SupervisorLog "Stopped for manual review (exit $scraperExit). See $attemptLog"; break }
        if ($restart -ge $retrySeconds.Count) { Write-SupervisorLog 'Restart budget exhausted after three automatic restarts; manual review required.'; break }
        $waitSeconds = $retrySeconds[$restart]
        Write-SupervisorLog "Timeout exit $scraperExit; cooldown $waitSeconds seconds. Scheduled restart: $([DateTime]::Now.AddSeconds($waitSeconds).ToString('s'))"
        for ($elapsed = 0; $elapsed -lt $waitSeconds; $elapsed++) {
            if (Test-Path -LiteralPath $stopFile) { break }
            Start-Sleep -Seconds 1
        }
    }
} finally {
    Write-SupervisorLog 'Supervisor stopped.'
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
