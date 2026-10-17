# Scheduled-task wrapper for scripts/daily.py: loads .env, makes sure the local Postgres
# container is up, runs the daily job and appends everything to logs/daily.log.
# Register/refresh the task: powershell -File scripts/register_task.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force (Join-Path $root "logs") | Out-Null
$log = Join-Path $root "logs\daily.log"

function Log($msg) { Add-Content -Path $log -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" -Encoding utf8 }

try {
    Log "start"
    foreach ($line in Get-Content (Join-Path $root ".env")) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim(), "Process")
        }
    }

    # Docker Desktop must be running; this starts the db container if it isn't.
    docker compose up -d db | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed (is Docker Desktop running?)" }
    $ready = $false
    for ($i = 0; $i -lt 30 -and -not $ready; $i++) {
        docker compose exec -T db pg_isready -U gridwatch | Out-Null
        $ready = $LASTEXITCODE -eq 0
        if (-not $ready) { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) { throw "Postgres not ready after 60 s" }

    $out = Join-Path $env:TEMP "gridwatch_daily.out"
    $err = Join-Path $env:TEMP "gridwatch_daily.err"
    $p = Start-Process -FilePath (Join-Path $root ".venv\Scripts\python.exe") `
        -ArgumentList "scripts\daily.py" -WorkingDirectory $root -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $out -RedirectStandardError $err
    Get-Content $out, $err | Add-Content -Path $log -Encoding utf8
    if ($p.ExitCode -ne 0) { throw "daily.py exited with $($p.ExitCode)" }
    Log "ok"
} catch {
    Log "FAILED: $_"
    exit 1
}
