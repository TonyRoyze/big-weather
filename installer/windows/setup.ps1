# Runs as the current Windows user. Only WSL feature enablement requests elevation.
param(
    [Parameter(Mandatory=$true)][string]$PackageDir,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$PayloadHash
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Distro = 'Ubuntu-24.04'
$Wsl = Join-Path $env:SystemRoot 'System32\wsl.exe'
$TranscriptStarted = $false

function Invoke-Wsl {
    param([string[]]$WslArguments)
    & $Wsl @WslArguments
    if ($LASTEXITCODE -ne 0) { throw "WSL command failed (exit $LASTEXITCODE): $($WslArguments -join ' ')" }
}

try {
    Start-Transcript -Path (Join-Path $PackageDir 'setup.log') -Append | Out-Null
    $TranscriptStarted = $true
    $Payload = Join-Path $PackageDir 'payload.tar.gz'
    if ((Get-FileHash -LiteralPath $Payload -Algorithm SHA256).Hash.ToLowerInvariant() -ne $PayloadHash) {
        throw 'The extracted project archive failed its integrity check. Run the EXE again.'
    }
    if (-not (Test-Path -LiteralPath $Wsl)) {
        throw 'WSL is unavailable. Update to a supported Windows 10/11 release, then rerun setup.'
    }
    Write-Host '[1/4] Checking Windows Subsystem for Linux...'
    # Native commands can write diagnostics to stderr; status is handled by exit code.
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $Wsl --status
    $StatusCode = $LASTEXITCODE
    $ErrorActionPreference = $PreviousPreference
    if ($StatusCode -ne 0) {
        Write-Host 'Enabling WSL. Approve the Windows administrator prompt if shown.'
        $Enable = Start-Process -FilePath $Wsl -ArgumentList '--install --no-distribution --web-download' -Verb RunAs -Wait -PassThru
        if ($Enable.ExitCode -notin @(0, 3010)) {
            throw "Windows could not enable WSL (exit $($Enable.ExitCode)). See https://learn.microsoft.com/windows/wsl/install"
        }
        Write-Host 'Restart Windows, then run the same BigWeather-Setup.exe again. Setup has not finished yet.'
        exit 3010
    }
    Write-Host '[2/4] Preparing Ubuntu 24.04...'
    $Installed = @(& $Wsl --list --quiet | ForEach-Object { ($_ -replace "`0", '').Trim() })
    if ($LASTEXITCODE -ne 0) { throw 'Could not list WSL distributions. Restart Windows and rerun setup.' }
    if ($Installed -notcontains $Distro) {
        Invoke-Wsl -WslArguments @('--install', '--distribution', $Distro, '--no-launch', '--web-download')
    }
    # Explicit distro/user avoids changing any existing default Linux account or distro.
    Invoke-Wsl -WslArguments @('--distribution', $Distro, '--user', 'root', '--exec', 'true')
    $LinuxPackage = (& $Wsl --distribution $Distro --user root --exec wslpath -a -u $PackageDir | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $LinuxPackage.StartsWith('/')) { throw 'Could not resolve the setup directory inside WSL.' }
    Write-Host '[3/4] Installing Java, Python and project dependencies (this can take several minutes)...'
    Invoke-Wsl -WslArguments @('--distribution', $Distro, '--user', 'root', '--exec', 'bash', "$LinuxPackage/setup-linux.sh", $LinuxPackage, $PayloadHash.Substring(0,12))

    Write-Host '[4/4] Creating launchers...'
    $ProjectRoot = "/home/bigweather/projects/big-weather-$($PayloadHash.Substring(0,12))"
    $LaunchDir = Join-Path $env:LOCALAPPDATA 'BigWeather'
    New-Item -ItemType Directory -Force -Path $LaunchDir | Out-Null
    Copy-Item -LiteralPath (Join-Path $PackageDir 'launch.ps1') -Destination (Join-Path $LaunchDir 'launch.ps1') -Force
    $Config = @{ distro = $Distro; project = $ProjectRoot }
    $Config | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LaunchDir 'config.json') -Encoding UTF8
    $Shell = New-Object -ComObject WScript.Shell
    $Desktop = [Environment]::GetFolderPath('Desktop')
    $PowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    foreach ($Mode in @('Dashboard', 'Terminal', 'Project')) {
        $Shortcut = $Shell.CreateShortcut((Join-Path $Desktop "Big Weather $Mode.lnk"))
        $Shortcut.TargetPath = $PowerShell
        $Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $LaunchDir 'launch.ps1')`" -Mode $Mode"
        $Shortcut.WorkingDirectory = $LaunchDir
        $Shortcut.Description = "Big Weather $Mode"
        $Shortcut.Save()
    }
    Write-Host ''
    Write-Host 'Setup complete. Open Big Weather Dashboard on your desktop.'
    Write-Host 'Big Weather Terminal opens the project environment; Big Weather Project opens its files.'
    Write-Host "Project folder: \\wsl.localhost\$Distro$($ProjectRoot.Replace('/', '\'))"
    Write-Host "Setup log: $(Join-Path $PackageDir 'setup.log')"
} catch {
    Write-Host "SETUP FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Keep this log when asking for help: $(Join-Path $PackageDir 'setup.log')"
    exit 1
} finally {
    if ($TranscriptStarted) { Stop-Transcript | Out-Null }
}
