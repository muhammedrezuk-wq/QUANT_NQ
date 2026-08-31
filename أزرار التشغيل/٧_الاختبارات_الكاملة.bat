@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0\.."
python scripts\log_button.py "٧_الاختبارات_الكاملة" START >nul 2>&1
echo ======================================================================
echo   الاختبارات الكاملة (نواة + ذرّات)
echo ======================================================================
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" -m pytest -q tests atoms
) else (
  py -3 -m pytest -q tests atoms
)
echo.
pause
