param(
  [int]$Port = 8010,
  [string]$BindHost = "0.0.0.0"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $scriptDir "backend"
$venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"

if (-not (Test-Path $backendDir)) {
  Write-Host "backend directory not found: $backendDir" -ForegroundColor Red
  exit 1
}

$pythonCmd = "python"
if (Test-Path $venvPython) {
  $pythonCmd = $venvPython
}

try {
  $oldPid = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty OwningProcess
  if ($oldPid) {
    Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 700
    Write-Host "stopped old process PID=$oldPid (port=$Port)"
  } else {
    Write-Host "no existing process on port $Port"
  }
} catch {
  Write-Host "warning while stopping old process: $($_.Exception.Message)"
}

$proc = Start-Process $pythonCmd `
  -ArgumentList "-m","uvicorn","app.main:app","--host",$BindHost,"--port",$Port `
  -WorkingDirectory $backendDir `
  -PassThru

Write-Host "start command sent with python: $pythonCmd"

$maxAttempts = 20
$ok = $false
$healthContent = ""
for ($i = 1; $i -le $maxAttempts; $i++) {
  Start-Sleep -Seconds 1
  try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 3
    $healthContent = $health.Content
    $ok = $true
    break
  } catch {
    if ($proc.HasExited) {
      Write-Host "backend process exited early. PID=$($proc.Id), code=$($proc.ExitCode)" -ForegroundColor Red
      break
    }
  }
}

if (-not $ok) {
  Write-Host "health check failed after startup." -ForegroundColor Red
  Write-Host "python used: $pythonCmd"
  Write-Host "hint: ensure this python has uvicorn/fastapi installed and backend/.env is valid."
  exit 1
}

$newPid = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
  Select-Object -First 1 -ExpandProperty OwningProcess
Write-Host "backend started: PID=$newPid, port=$Port" -ForegroundColor Green
Write-Host "health: $healthContent"
Write-Host "web: http://127.0.0.1:$Port/web/index.html"
