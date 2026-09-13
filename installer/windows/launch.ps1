param([ValidateSet('Dashboard','Terminal','Project')][string]$Mode = 'Dashboard')
$ErrorActionPreference = 'Stop'
try {
    $Config = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'config.json') -Raw | ConvertFrom-Json
    $Wsl = Join-Path $env:SystemRoot 'System32\wsl.exe'
    if ($Mode -eq 'Project') {
        $UncPath = "\\wsl.localhost\$($Config.distro)$($Config.project.Replace('/', '\'))"
        Start-Process explorer.exe -ArgumentList "`"$UncPath`""
        exit 0
    }
    $Arguments = @('--distribution', $Config.distro, '--user', 'bigweather', '--cd', $Config.project,
                   '--exec', 'bash', 'scripts/team-launch.sh', $Mode.ToLowerInvariant())
    if ($Mode -eq 'Terminal') {
        & $Wsl @Arguments
        exit $LASTEXITCODE
    }
    # Refuse to confuse another service on this port with this project's dashboard.
    $Busy = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
    if ($Busy) { throw 'Port 8501 is already in use. Close the previous dashboard/server, then try again.' }
    $Server = Start-Process -FilePath $Wsl -ArgumentList $Arguments -PassThru -NoNewWindow
    $Ready = $false
    for ($Attempt = 0; $Attempt -lt 60; $Attempt++) {
        $Server.Refresh()
        if ($Server.HasExited) { throw 'The dashboard stopped before it was ready. Check the messages above.' }
        try {
            $Health = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8501/_stcore/health' -TimeoutSec 2
            if ($Health.StatusCode -eq 200) { $Ready = $true; break }
        } catch { }
        Start-Sleep -Seconds 1
    }
    if (-not $Ready) { throw 'The dashboard is taking longer than expected. Check the log above and try http://localhost:8501 manually.' }
    Start-Process 'http://localhost:8501'
    Write-Host 'Dashboard running. Keep this window open; press Ctrl+C to stop.'
    Wait-Process -Id $Server.Id
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Read-Host 'Press Enter to close'
    exit 1
}
