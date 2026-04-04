@echo off
echo Starting review bridge on localhost:7771...

REM Load ANTHROPIC_API_KEY from .env if not already set
if not defined ANTHROPIC_API_KEY (
    for /f "tokens=1,* delims==" %%a in ('type "%~dp0..\.env" ^| findstr ANTHROPIC_API_KEY') do (
        set ANTHROPIC_API_KEY=%%b
    )
)

REM Now check if key was found
if not defined ANTHROPIC_API_KEY (
    echo ERROR: ANTHROPIC_API_KEY not found in environment or .env file
    exit /b 1
)

echo API key loaded.

pip install flask anthropic --quiet 2>nul
start /B python "%~dp0review_bridge.py" > "%~dp0..\docs\review_loop\bridge.log" 2>&1
timeout /t 3 /nobreak > nul
curl -s localhost:7771/health
echo.
echo Bridge running (Anthropic API direct).
echo Logs: docs\review_loop\bridge.log
