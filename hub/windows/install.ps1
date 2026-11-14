# HomeHub install for Windows: Mosquitto + Python venv + settings + firewall (+ optional autostart).
# Run from the repository:
#   powershell -ExecutionPolicy Bypass -File hub\windows\install.ps1 -AutoStart
# One administrator prompt (UAC) appears for the firewall rules and the Mosquitto service.
param([switch]$AutoStart, [switch]$NoFirewall)
$ErrorActionPreference = 'Stop'
$HubSrc = Split-Path -Parent $PSScriptRoot
$Data = Join-Path $env:USERPROFILE 'HomeHub'
$Venv = Join-Path $Data 'venv'
$Py = Join-Path $Venv 'Scripts\python.exe'

Write-Host '1/5 Mosquitto (MQTT broker)'
if (-not (Test-Path "$env:ProgramFiles\mosquitto\mosquitto.exe")) {
    winget install -e --id EclipseFoundation.Mosquitto --accept-source-agreements --accept-package-agreements
}

Write-Host '2/5 Python environment in' $Venv
New-Item -ItemType Directory -Force -Path $Data | Out-Null
if (-not (Test-Path $Py)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv $Venv } else { & python -m venv $Venv }
}
& $Py -m pip install --quiet --upgrade pip
& $Py -m pip install --quiet "$HubSrc" bleak
if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }

Write-Host '3/5 Settings, passwords, Mosquitto config'
& $Py -m homehub init
if ($LASTEXITCODE -ne 0) { throw 'homehub init failed' }

if (-not $NoFirewall) {
    Write-Host '4/5 Firewall rules for the home network (administrator prompt)'
    $admin = @'
$s = Get-Service mosquitto -ErrorAction SilentlyContinue
if ($s) { Stop-Service mosquitto -Force -ErrorAction SilentlyContinue; Set-Service mosquitto -StartupType Disabled }
$rules = @(@('HomeHub MQTT 1883','TCP',1883), @('HomeHub page 8780','TCP',8780),
           @('HomeHub discovery 8781','UDP',8781), @('HomeHub firmware 8782','TCP',8782))
foreach ($r in $rules) {
    Get-NetFirewallRule -DisplayName $r[0] -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule -DisplayName $r[0] -Direction Inbound -Protocol $r[1] -LocalPort $r[2] `
        -RemoteAddress LocalSubnet -Profile Any -Action Allow | Out-Null
}
'@
    Start-Process powershell -Verb RunAs -Wait -ArgumentList @('-NoProfile', '-Command', $admin)
}

if ($AutoStart) {
    Write-Host '5/5 Start HomeHub at logon'
    $action = New-ScheduledTaskAction -Execute (Join-Path $Venv 'Scripts\pythonw.exe') -Argument '-m homehub run'
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName 'HomeHub' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName 'HomeHub'
} else {
    Write-Host '5/5 Start it yourself:' "$Py -m homehub run"
}
& $Py -m homehub info
