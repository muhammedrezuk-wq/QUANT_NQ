@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0\.."
python scripts\log_button.py "٦_فحص_الأحداث" START >nul 2>&1
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
