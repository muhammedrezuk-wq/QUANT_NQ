@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0\.."
echo ======================================================================
echo   غرفة القيادة — النواة + الحوكمة معًا (:8010 / :8090)
echo ======================================================================
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" governance\app.py %*
) else (
  py -3 governance\app.py %*
)
echo.
pause
