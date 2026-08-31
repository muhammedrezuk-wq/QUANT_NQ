@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0\.."
python scripts\log_button.py "٥_فحص_المشروع" START >nul 2>&1
echo ======================================================================
echo   فحص المشروع
echo ======================================================================
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" governance\checks\check_project.py
) else (
  py -3 governance\checks\check_project.py
)
echo.
pause
