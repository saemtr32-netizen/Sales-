@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.10 or newer from python.org, then run this file again.
  pause
  exit /b 1
)
py -3 reset_account.py --desktop
set "reset_result=%errorlevel%"
pause
exit /b %reset_result%
