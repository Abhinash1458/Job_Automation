# Daily job-hunt run — invoked by Windows Task Scheduler at 6 AM.
# Runs the pipeline, logs output, and opens the review report.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$logDir = Join-Path $root "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd"
$log = Join-Path $logDir "daily_$stamp.log"

$py = Join-Path $root ".venv\Scripts\python.exe"
& $py -m src.main daily *>&1 | Tee-Object -FilePath $log

# Open today's report so it's waiting for you when you're free.
$report = Join-Path $root "data\reports\daily_$stamp.html"
if (Test-Path $report) { Start-Process $report }
