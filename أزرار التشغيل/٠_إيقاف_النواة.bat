@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0\.."
echo ======================================================================
echo   إيقاف النواة صراحةً
echo ======================================================================
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" governance\app.py --stop
) else (
  py -3 governance\app.py --stop
)
echo.
pause
