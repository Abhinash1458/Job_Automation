# Registers (or updates) a Windows Task Scheduler job that runs the daily
# pipeline every morning at 6:00 AM. Run this ONCE:
#   powershell -ExecutionPolicy Bypass -File scripts\install_schedule.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $root "scripts\daily_run.ps1"
$taskName = "JobHuntDaily"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`""
$trigger = New-ScheduledTaskTrigger -Daily -At 6:00AM
# Run whether or not you're logged in; wake the machine if asleep.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Daily GCC job-hunt: scrape, score, review report" `
    -Force

Write-Host "Scheduled task '$taskName' installed — runs daily at 6:00 AM."
Write-Host "Check it:   Get-ScheduledTask -TaskName $taskName"
Write-Host "Run now:    Start-ScheduledTask -TaskName $taskName"
Write-Host "Remove it:  Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
