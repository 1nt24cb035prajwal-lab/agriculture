@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Run setup-local.bat first.
    exit /b 1
)
if not exist "backend\.env" (
    echo Run setup-local.bat first to create backend\.env.
    exit /b 1
)
if not exist "frontend\node_modules" (
    echo Run setup-local.bat first to install frontend dependencies.
    exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
    echo Node.js LTS is required. Install it with:
    echo   winget install --id OpenJS.NodeJS.LTS --exact
    exit /b 1
)

start "Agriculture Threat Fusion API" /D "%~dp0backend" cmd /k "..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
start "Agriculture Threat Fusion Web" /D "%~dp0frontend" cmd /k "npm run dev -- --host 127.0.0.1"

powershell -NoProfile -Command "$backend = 'http://127.0.0.1:8000/api/health'; $frontend = 'http://127.0.0.1:5173'; for ($i = 0; $i -lt 90; $i++) { try { Invoke-WebRequest -Uri $backend -TimeoutSec 2 | Out-Null; Invoke-WebRequest -Uri $frontend -TimeoutSec 2 | Out-Null; Start-Process $frontend; exit 0 } catch { }; Start-Sleep -Seconds 1 }; Write-Error 'The app did not become ready. Check the backend and frontend windows for errors.'; exit 1"
if errorlevel 1 exit /b 1
