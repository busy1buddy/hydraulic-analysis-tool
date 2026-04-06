@echo off
echo ============================================
echo  Hydraulic Tool — Review Bridge
echo ============================================

REM Load ANTHROPIC_API_KEY from .env if not already set
if not defined ANTHROPIC_API_KEY (
    for /f "tokens=1,* delims==" %%a in ('type "%~dp0..\.env" ^| findstr ANTHROPIC_API_KEY') do (
        set "ANTHROPIC_API_KEY=%%b"
    )
)

REM Strip quotes and spaces from key value
if defined ANTHROPIC_API_KEY (
    for /f "tokens=* delims= " %%k in ("%ANTHROPIC_API_KEY%") do set "ANTHROPIC_API_KEY=%%~k"
)

REM Check key exists
if not defined ANTHROPIC_API_KEY (
    echo ERROR: ANTHROPIC_API_KEY not found.
    echo Add to .env file: ANTHROPIC_API_KEY=sk-ant-...
    exit /b 1
)

REM Kill any existing bridge on port 7771
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr :7771 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
timeout /t 1 /nobreak > nul

REM Install dependencies quietly
pip install flask anthropic --quiet 2>nul

REM Ensure log directory exists
if not exist "%~dp0..\docs\review_loop" mkdir "%~dp0..\docs\review_loop"

REM Start bridge
echo Starting bridge...
start /B python "%~dp0review_bridge.py" > "%~dp0..\docs\review_loop\bridge.log" 2>&1
timeout /t 3 /nobreak > nul

REM Health check
echo.
curl -s localhost:7771/health 2>nul
if errorlevel 1 (
    echo.
    echo FAILED to start bridge. Check docs\review_loop\bridge.log
    exit /b 1
)

echo.
echo ============================================
echo  Bridge running on localhost:7771
echo  Default model: claude-sonnet-4-6
echo  Thorough model: claude-opus-4-6
echo  Logs: docs\review_loop\bridge.log
echo ============================================
