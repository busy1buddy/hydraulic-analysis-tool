@echo off
echo Starting review bridge on localhost:7771...

REM Configure timeout (seconds) — increase if reviews are timing out
if not defined REVIEW_TIMEOUT set REVIEW_TIMEOUT=240
echo Timeout: %REVIEW_TIMEOUT%s (set REVIEW_TIMEOUT=N to change)

pip install flask --quiet 2>nul
start /B python "%~dp0review_bridge.py" > "%~dp0..\docs\review_loop\bridge.log" 2>&1
timeout /t 4 /nobreak > nul
curl -s localhost:7771/health
echo.
echo Bridge running. Warming up...
python "%~dp0submit_for_review.py" --context "warmup" --question "warmup" --output "warmup" --fast >nul 2>&1
echo Warmup complete. Bridge ready.
echo Logs: docs\review_loop\bridge.log
