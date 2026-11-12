@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 (
    echo Python 3.12 is required. Install it from https://www.python.org/downloads/ and enable the Python launcher.
    exit /b 1
)

py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3.12 is required. Install it from https://www.python.org/downloads/.
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo Node.js LTS is required. Install it with:
    echo   winget install --id OpenJS.NodeJS.LTS --exact
    echo Then reopen this terminal and run setup-local.bat again.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 exit /b 1

pushd frontend
call npm install
if errorlevel 1 (
    popd
    exit /b 1
)
popd

if not exist "backend\.env" copy "backend\.env.example" "backend\.env" >nul
if errorlevel 1 exit /b 1

echo.
echo Setup complete. Run run-local.bat to start the application.
