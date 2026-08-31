@echo off
chcp 65001 >nul
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set QUANT_LOCAL_MODE=1
cd /d "%~dp0\.."
python scripts\log_button.py "تشغيل الفوركس والكريبتو معًا" START >nul 2>&1
python scripts\launch_market.py --both
set CODE=%ERRORLEVEL%
echo.
echo لوحة الفوركس: http://127.0.0.1:8090
echo لوحة الكريبتو: http://127.0.0.1:8091
pause
endlocal & exit /b %CODE%
