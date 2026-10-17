# Registers (or replaces) the Windows scheduled task that runs run_daily.ps1 at 10:00 daily.
# Runs only while you're logged in (no stored password); a missed run starts when the PC is
# next on. Remove with: Unregister-ScheduledTask -TaskName AlbertaGridWatchDaily

$script = Join-Path $PSScriptRoot "run_daily.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At 10:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "AlbertaGridWatchDaily" -Action $action -Trigger $trigger `
    -Settings $settings -Description "Alberta Grid Watch: ingest + next-day forecast" -Force |
    Select-Object TaskName, State
