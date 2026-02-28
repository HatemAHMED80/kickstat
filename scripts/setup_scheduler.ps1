# setup_scheduler.ps1 — One-time setup for Windows Task Scheduler
# Creates a daily task that runs the predictions pipeline at 08:00
#
# Usage:
#   .\scripts\setup_scheduler.ps1              # Setup with default time (08:00)
#   .\scripts\setup_scheduler.ps1 -Time 09:30  # Custom time
#   .\scripts\setup_scheduler.ps1 -Remove      # Remove the scheduled task

param(
    [string]$Time = "08:00",
    [switch]$Remove
)

$TASK_NAME = "KickstatDailyPredictions"
$PROJECT_ROOT = "C:\Users\sami ahmed\kickstat"
$SCRIPT_PATH = Join-Path $PROJECT_ROOT "scripts\daily_predictions.ps1"

if ($Remove) {
    Write-Host "Removing scheduled task '$TASK_NAME'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Task removed." -ForegroundColor Green
    exit 0
}

# Check if task already exists
$existing = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Task '$TASK_NAME' already exists. Updating..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false
}

# Create the action
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$SCRIPT_PATH`"" `
    -WorkingDirectory $PROJECT_ROOT

# Create the trigger (daily at specified time)
$trigger = New-ScheduledTaskTrigger -Daily -At $Time

# Settings: run even if on battery, don't stop on battery switch, allow on demand
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# Register the task
Register-ScheduledTask `
    -TaskName $TASK_NAME `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Kickstat: Generate daily ML predictions for football matches (all 8 leagues)" `
    -RunLevel Limited

Write-Host ""
Write-Host "=== Task Scheduler Setup Complete ===" -ForegroundColor Green
Write-Host "  Task name:  $TASK_NAME"
Write-Host "  Schedule:   Daily at $Time"
Write-Host "  Script:     $SCRIPT_PATH"
Write-Host "  Logs:       $PROJECT_ROOT\logs\"
Write-Host ""
Write-Host "To test manually:" -ForegroundColor Cyan
Write-Host "  powershell -File `"$SCRIPT_PATH`" -Verbose"
Write-Host ""
Write-Host "To change time:" -ForegroundColor Cyan
Write-Host "  .\scripts\setup_scheduler.ps1 -Time 10:00"
Write-Host ""
Write-Host "To remove:" -ForegroundColor Cyan
Write-Host "  .\scripts\setup_scheduler.ps1 -Remove"
