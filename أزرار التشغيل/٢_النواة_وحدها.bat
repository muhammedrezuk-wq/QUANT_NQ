@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0\.."
echo ======================================================================
echo   النواة وحدها (:8010)
echo ======================================================================
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" scripts\run_core.py
) else (
  py -3 scripts\run_core.py
)
echo.
pause
