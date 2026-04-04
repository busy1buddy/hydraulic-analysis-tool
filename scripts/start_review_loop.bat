@echo off
echo Starting review bridge on localhost:7771...
pip install flask --quiet 2>nul
start /B python "%~dp0review_bridge.py" > "%~dp0..\docs\review_loop\bridge.log" 2>&1
timeout /t 3 /nobreak > nul
curl -s localhost:7771/health
echo.
echo Bridge running. Warming up...
python "%~dp0submit_for_review.py" --context "warmup" --question "warmup" --output "warmup" --fast >nul 2>&1
echo Warmup complete. Bridge ready.
echo Logs: docs\review_loop\bridge.log
