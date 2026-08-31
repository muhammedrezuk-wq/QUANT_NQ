@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0\.."
python scripts\log_button.py "٣_تلغرام_الموبايل" START >nul 2>&1
echo ======================================================================
echo   منصة تلغرام الموبايل — قفل على المالك (:8098)
echo ======================================================================
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" governance\telegram.py
) else (
  py -3 governance\telegram.py
)
echo.
pause
