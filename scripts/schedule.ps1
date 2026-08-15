# Register daily 05:00 Windows Task Scheduler entry for the ETL pipeline.
# Idempotent: re-running overwrites the existing task.
#
# Usage: pwsh scripts\schedule.ps1
# Verify:  Get-ScheduledTask -TaskName "MCP-Jobs-ETL" | Format-List
# Remove:  Unregister-ScheduledTask -TaskName "MCP-Jobs-ETL" -Confirm:$false

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python).Source
$etl = Join-Path $repoRoot "scripts\run_etl.py"
$health = Join-Path $repoRoot "scripts\healthcheck.py"
$config = Join-Path $repoRoot "config.yaml"
$log = Join-Path $repoRoot "data\etl_cron.log"

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null

# Encoding rule: run_etl.py scrapes web content -> force UTF-8 for stdout/err
$action = New-ScheduledTaskAction -Execute $python -Argument "-X utf8 `"$etl`" --config `"$config`"" `
    -WorkingDirectory $repoRoot
$post = New-ScheduledTaskAction -Execute $python -Argument "-X utf8 `"$health`"" `
    -WorkingDirectory $repoRoot

$trigger = New-ScheduledTaskTrigger -Daily -At 05:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName "MCP-Jobs-ETL" `
    -Action $action, $post `
    -Trigger $trigger `
    -Settings $settings `
    -Description "MCP-Jobs daily ETL scrape (run_etl.py) + healthcheck heartbeat" `
    -Force | Out-Null

Write-Output "Task MCP-Jobs-ETL registered (daily 05:00)."
Write-Output "  ETL:      $etl"
Write-Output "  Health:   $health"
Write-Output "  Python:   $python"
Write-Output "Verify: Get-ScheduledTask -TaskName 'MCP-Jobs-ETL' | Format-List"