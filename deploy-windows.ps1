# ============================================================================
#  Factory Operations Platform - ONE-STEP Windows deployment script
#
#  USAGE (from the project root - the folder containing backend\ + frontend\):
#      Right-click PowerShell -> "Run as Administrator", then:
#      Set-ExecutionPolicy Bypass -Scope Process -Force
#      .\deploy-windows.ps1                # auto-detects LAN IP
#      .\deploy-windows.ps1 -HostIp 192.168.1.50   # or force an IP/hostname
#
#  WHAT IT DOES:
#      1/7  Installs Python 3.11, Node.js LTS, MongoDB (via winget, if missing)
#      2/7  Backend: venv + pip deps + .env (existing .env preserved)
#      3/7  Frontend: yarn install + production build (REACT_APP_BACKEND_URL baked in)
#      4/7  Installs 'serve' to host the UI on port 80
#      5/7  Registers 2 Scheduled Tasks (auto-start at boot): backend :8001, UI :80
#      6/7  Opens Windows Firewall ports 80 + 8001
#      7/7  Health checks
#
#  PREREQUISITES: Windows 10/11 or Server 2019+, winget available, run as Admin.
#  IDEMPOTENT: safe to re-run; installed components are skipped, DB preserved.
#  AFTER: open http://<this-pc-ip>/  (default admin login, then change passwords)
# ============================================================================
param([string]$HostIp = "")

$ErrorActionPreference = "Stop"
$AppDir = $PSScriptRoot
$BackendPort = 8001
$UiPort = 80
$DbName = "factory_ops"

function Log($m)  { Write-Host "[deploy] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[deploy] OK  $m" -ForegroundColor Green }
function Fail($m) { Write-Host "[deploy] ERROR: $m" -ForegroundColor Red; exit 1 }
function RefreshPath {
  $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
              [Environment]::GetEnvironmentVariable("Path","User")
}

# ---------------------------------------------------------------- preflight
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Fail "run this script as Administrator"
}
if (-not (Test-Path "$AppDir\backend\server.py")) { Fail "run from the project root (backend\ and frontend\ must sit next to this script)" }
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { Fail "winget not found - install 'App Installer' from the Microsoft Store first" }

if (-not $HostIp) {
  $HostIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "169.254*" -and $_.IPAddress -ne "127.0.0.1" -and $_.PrefixOrigin -ne "WellKnown" } | Select-Object -First 1).IPAddress
  if (-not $HostIp) { $HostIp = "localhost" }
}
Log "Target host/IP baked into the UI: $HostIp   (backend http://${HostIp}:$BackendPort)"

# ---------------------------------------------------------------- 1/7 tools
Log "1/7  System tools (Python 3.11 / Node LTS / MongoDB via winget)"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  winget install -e --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements | Out-Null; RefreshPath
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements | Out-Null; RefreshPath
}
if (-not (Get-Service -Name "MongoDB" -ErrorAction SilentlyContinue)) {
  winget install -e --id MongoDB.Server --accept-source-agreements --accept-package-agreements | Out-Null
}
Start-Service -Name "MongoDB" -ErrorAction SilentlyContinue
Set-Service  -Name "MongoDB" -StartupType Automatic -ErrorAction SilentlyContinue
if ((Get-Service -Name "MongoDB").Status -ne "Running") { Fail "MongoDB service failed to start" }
if (-not (Get-Command yarn -ErrorAction SilentlyContinue)) { npm install -g yarn | Out-Null; RefreshPath }
Ok ("python {0} / node {1} / yarn {2} / MongoDB running" -f (python --version), (node -v), (yarn -v))

# ---------------------------------------------------------------- 2/7 backend
Log "2/7  Backend (venv + deps + .env)"
Set-Location "$AppDir\backend"
if (-not (Test-Path "venv")) { python -m venv venv }
& .\venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .\venv\Scripts\pip.exe install -r requirements.txt --quiet
if (-not (Test-Path ".env")) {
  $jwt = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 40 | ForEach-Object {[char]$_})
  @"
MONGO_URL=mongodb://localhost:27017
DB_NAME=$DbName
JWT_SECRET=$jwt
CORS_ORIGINS=*
"@ | Set-Content -Encoding ascii ".env"
  Log "backend\.env created (random JWT secret)"
} else { Log "backend\.env already exists - kept as-is" }
Ok "backend dependencies installed"

# ---------------------------------------------------------------- 3/7 frontend
Log "3/7  Frontend production build (this can take a few minutes)"
Set-Location "$AppDir\frontend"
"REACT_APP_BACKEND_URL=http://${HostIp}:$BackendPort" | Set-Content -Encoding ascii ".env"
yarn install --network-timeout 600000
yarn build
if (-not (Test-Path "build\index.html")) { Fail "frontend build failed" }
Ok "frontend built -> frontend\build"

# ---------------------------------------------------------------- 4/7 serve
Log "4/7  Static file server ('serve')"
if (-not (Get-Command serve -ErrorAction SilentlyContinue)) { npm install -g serve | Out-Null; RefreshPath }
Ok "serve installed"

# ---------------------------------------------------------------- 5/7 tasks
Log "5/7  Scheduled Tasks (auto-start at boot)"
$uvicorn = "$AppDir\backend\venv\Scripts\uvicorn.exe"
$serveCmd = (Get-Command serve.cmd -ErrorAction SilentlyContinue).Source
if (-not $serveCmd) { $serveCmd = "serve" }

foreach ($t in @("FactoryOps-Backend","FactoryOps-Frontend")) {
  Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue
}
Get-Process uvicorn,node -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$AppDir*" } | Stop-Process -Force -ErrorAction SilentlyContinue

$sets = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 3650)
$trig = New-ScheduledTaskTrigger -AtStartup
$user = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest

$aB = New-ScheduledTaskAction -Execute $uvicorn -Argument "server:app --host 0.0.0.0 --port $BackendPort" -WorkingDirectory "$AppDir\backend"
Register-ScheduledTask -TaskName "FactoryOps-Backend" -Action $aB -Trigger $trig -Principal $user -Settings $sets | Out-Null

$aF = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$serveCmd`" -s build -l $UiPort" -WorkingDirectory "$AppDir\frontend"
Register-ScheduledTask -TaskName "FactoryOps-Frontend" -Action $aF -Trigger $trig -Principal $user -Settings $sets | Out-Null

Start-ScheduledTask -TaskName "FactoryOps-Backend"
Start-ScheduledTask -TaskName "FactoryOps-Frontend"
Ok "tasks registered + started (backend :$BackendPort, UI :$UiPort)"

# ---------------------------------------------------------------- 6/7 firewall
Log "6/7  Windows Firewall (open $UiPort + $BackendPort)"
foreach ($p in @($UiPort,$BackendPort)) {
  $rn = "FactoryOps-$p"
  if (-not (Get-NetFirewallRule -DisplayName $rn -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $rn -Direction Inbound -Protocol TCP -LocalPort $p -Action Allow | Out-Null
  }
}
Ok "firewall rules in place"

# ---------------------------------------------------------------- 7/7 health
Log "7/7  Health checks"
Start-Sleep -Seconds 8
try {
  $r = Invoke-WebRequest -UseBasicParsing "http://localhost:$BackendPort/api/machines?limit=1" -TimeoutSec 15
  Ok "backend answering ($($r.StatusCode))"
} catch {
  try { Invoke-WebRequest -UseBasicParsing "http://localhost:$BackendPort/docs" -TimeoutSec 10 | Out-Null; Ok "backend answering (/docs)" }
  catch { Log "WARNING: backend not answering yet - check: Get-ScheduledTaskInfo FactoryOps-Backend" }
}
try {
  Invoke-WebRequest -UseBasicParsing "http://localhost:$UiPort/" -TimeoutSec 15 | Out-Null
  Ok "UI served on port $UiPort"
} catch { Log "WARNING: UI not answering yet - check: Get-ScheduledTaskInfo FactoryOps-Frontend" }

Write-Host ""
Ok "DEPLOYMENT COMPLETE"
Write-Host "  Open:      http://$HostIp/           (from any device on the LAN)" -ForegroundColor Yellow
Write-Host "  Backend:   http://${HostIp}:$BackendPort/api" -ForegroundColor Yellow
Write-Host "  Manage:    Task Scheduler -> FactoryOps-Backend / FactoryOps-Frontend" -ForegroundColor Yellow
Write-Host "  IMPORTANT: change all default passwords (Administration -> Users)" -ForegroundColor Yellow
