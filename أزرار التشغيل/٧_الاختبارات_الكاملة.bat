@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0\.."
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
