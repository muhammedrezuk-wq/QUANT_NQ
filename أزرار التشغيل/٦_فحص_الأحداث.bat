@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0\.."
echo ======================================================================
echo   فحص الأحداث (روابط/يتامى)
echo ======================================================================
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" governance\checks\check_events.py
) else (
  py -3 governance\checks\check_events.py
)
echo.
pause
