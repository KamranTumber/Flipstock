# Boots FlipScout UK on Windows: FastAPI backend on :8000 and Vite frontend on :5173.
#   powershell -ExecutionPolicy Bypass -File .\start.ps1          dev mode — open http://localhost:5173
#   powershell -ExecutionPolicy Bypass -File .\start.ps1 -Prod    serve everything from http://localhost:8000
param([switch]$Prod)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Created .env from .env.example" }

# ---- backend ---------------------------------------------------------------
Set-Location "$Root\backend"
$hasUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)
if (-not (Test-Path .venv)) {
  Write-Host "Creating Python virtualenv..."
  if ($hasUv) { uv venv .venv -q } elseif (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv .venv } else { python -m venv .venv }
}
$Py = "$Root\backend\.venv\Scripts\python.exe"
$marker = ".venv\.deps-installed"
if (-not (Test-Path $marker) -or (Get-Item requirements.txt).LastWriteTime -gt (Get-Item $marker).LastWriteTime) {
  Write-Host "Installing Python dependencies..."
  if ($hasUv) { uv pip install --python $Py -q -r requirements.txt } else { & $Py -m pip install -q -r requirements.txt }
  & $Py -m playwright install chromium
  if ($LASTEXITCODE -ne 0) { Write-Warning "Playwright Chromium install failed - FB Marketplace will report 'unavailable'." }
  New-Item -ItemType File -Force $marker | Out-Null
}

# ---- frontend --------------------------------------------------------------
Set-Location "$Root\frontend"
if (-not (Test-Path node_modules)) { Write-Host "Installing frontend dependencies..."; npm install --no-audit --no-fund }

if ($Prod) {
  npm run build
  Set-Location "$Root\backend"
  Write-Host "FlipScout UK on http://localhost:8000"
  & $Py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
  exit
}

$back = Start-Process -FilePath $Py -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000","--reload","--reload-dir","app" `
  -WorkingDirectory "$Root\backend" -PassThru -NoNewWindow
try {
  Write-Host "Backend http://127.0.0.1:8000  -  Frontend http://localhost:5173"
  npm run dev
} finally {
  if ($back -and -not $back.HasExited) { Stop-Process -Id $back.Id -Force }
}
