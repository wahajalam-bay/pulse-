@echo off
REM ZD PULSE - Architecture & Design.  Double-click to run.
cd /d "%~dp0"
set PORT=4010
set MOUNT=/zd
set HOST=127.0.0.1
echo.
echo   ZD PULSE  -  Architecture ^& Design
echo   ---------------------------------
echo   Opening http://127.0.0.1:4010/zd/
echo   Sign in: haroon@zameen.com  /  ZDesign!2026
echo.
echo   Leave this window open. Close it to stop the server.
echo.
start "" "http://127.0.0.1:4010/zd/"
python server.py
pause
