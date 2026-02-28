# daily_predictions.ps1 — Runs the full ML pipeline daily
# Generates predictions for tomorrow's matches across all 8 leagues
# Designed to be called by Windows Task Scheduler

param(
    [switch]$Verbose
)

$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
if (-not $PROJECT_ROOT) { $PROJECT_ROOT = "C:\Users\sami ahmed\kickstat" }

$LOG_DIR = Join-Path $PROJECT_ROOT "logs"
$TIMESTAMP = Get-Date -Format "yyyy-MM-dd_HH-mm"
$LOG_FILE = Join-Path $LOG_DIR "predictions_$TIMESTAMP.log"

# Create logs directory
if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null }

function Write-Log {
    param([string]$Message)
    $entry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $Message"
    Add-Content -Path $LOG_FILE -Value $entry
    if ($Verbose) { Write-Host $entry }
}

Write-Log "=== KICKSTAT DAILY PREDICTIONS ==="
Write-Log "Project root: $PROJECT_ROOT"

# Activate venv if it exists
$venvActivate = Join-Path $PROJECT_ROOT "venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    Write-Log "Activating virtual environment..."
    & $venvActivate
} else {
    Write-Log "WARNING: No venv found at $venvActivate, using system Python"
}

# Run predictions
Write-Log "Starting generate_predictions_json.py..."
$startTime = Get-Date

$scriptPath = Join-Path $PROJECT_ROOT "generate_predictions_json.py"

# Run Python with stderr redirected — loguru writes to stderr, not an error
$proc = Start-Process -FilePath "python" `
    -ArgumentList "`"$scriptPath`"" `
    -WorkingDirectory $PROJECT_ROOT `
    -RedirectStandardOutput (Join-Path $LOG_DIR "stdout_$TIMESTAMP.tmp") `
    -RedirectStandardError (Join-Path $LOG_DIR "stderr_$TIMESTAMP.tmp") `
    -NoNewWindow -PassThru -Wait

$exitCode = $proc.ExitCode

# Collect output into log
$stdoutFile = Join-Path $LOG_DIR "stdout_$TIMESTAMP.tmp"
$stderrFile = Join-Path $LOG_DIR "stderr_$TIMESTAMP.tmp"

if (Test-Path $stdoutFile) {
    Get-Content $stdoutFile | ForEach-Object { Write-Log "  $_" }
    Remove-Item $stdoutFile -Force
}
if (Test-Path $stderrFile) {
    Get-Content $stderrFile | ForEach-Object { Write-Log "  [LOG] $_" }
    Remove-Item $stderrFile -Force
}

$elapsed = ((Get-Date) - $startTime).TotalSeconds
Write-Log "Elapsed: $([math]::Round($elapsed, 1))s | Exit code: $exitCode"

if ($exitCode -ne 0) {
    Write-Log "ERROR: Pipeline failed with exit code $exitCode"
    exit 1
}

# Verify output
$predictionsFile = Join-Path $PROJECT_ROOT "web\public\predictions.json"
if (Test-Path $predictionsFile) {
    $fileInfo = Get-Item $predictionsFile
    $content = Get-Content $predictionsFile -Raw | ConvertFrom-Json
    $count = $content.Count
    Write-Log "SUCCESS: predictions.json updated ($count predictions, $([math]::Round($fileInfo.Length / 1024, 1)) KB)"
} else {
    Write-Log "ERROR: predictions.json not found after pipeline run"
    exit 1
}

# Fetch results for past predictions
Write-Log "Starting fetch_results.py..."
$resultsScript = Join-Path $PROJECT_ROOT "scripts\fetch_results.py"
$proc2 = Start-Process -FilePath "python" `
    -ArgumentList "`"$resultsScript`"" `
    -WorkingDirectory $PROJECT_ROOT `
    -RedirectStandardOutput (Join-Path $LOG_DIR "results_stdout_$TIMESTAMP.tmp") `
    -RedirectStandardError  (Join-Path $LOG_DIR "results_stderr_$TIMESTAMP.tmp") `
    -NoNewWindow -PassThru -Wait

$r2stdout = Join-Path $LOG_DIR "results_stdout_$TIMESTAMP.tmp"
$r2stderr = Join-Path $LOG_DIR "results_stderr_$TIMESTAMP.tmp"
if (Test-Path $r2stdout) { Get-Content $r2stdout | ForEach-Object { Write-Log "  [results] $_" }; Remove-Item $r2stdout -Force }
if (Test-Path $r2stderr) { Get-Content $r2stderr | ForEach-Object { Write-Log "  [results] $_" }; Remove-Item $r2stderr -Force }
Write-Log "fetch_results.py exit code: $($proc2.ExitCode)"

# Clean up old logs (keep 30 days)
$cutoff = (Get-Date).AddDays(-30)
Get-ChildItem $LOG_DIR -Filter "predictions_*.log" | Where-Object { $_.LastWriteTime -lt $cutoff } | ForEach-Object {
    Write-Log "Cleaning old log: $($_.Name)"
    Remove-Item $_.FullName -Force
}

Write-Log "=== DONE ==="
