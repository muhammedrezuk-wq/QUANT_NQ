@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0\.."
python scripts\log_button.py "٤_المدقق_الشامل" START >nul 2>&1
echo ======================================================================
echo   المدقق الشامل لكل الذرّات
echo ======================================================================
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" governance\scripts\validate_atoms.py
) else (
  py -3 governance\scripts\validate_atoms.py
)
echo.
pause
