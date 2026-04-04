@echo off
echo Starting review bridge on localhost:7771...

REM Check API key
if not defined ANTHROPIC_API_KEY (
    echo ERROR: ANTHROPIC_API_KEY not set
    echo Run: set ANTHROPIC_API_KEY=sk-ant-...
    exit /b 1
)

pip install flask anthropic --quiet 2>nul
start /B python "%~dp0review_bridge.py" > "%~dp0..\docs\review_loop\bridge.log" 2>&1
timeout /t 3 /nobreak > nul
curl -s localhost:7771/health
echo.
echo Bridge running (Anthropic API direct).
echo Logs: docs\review_loop\bridge.log
