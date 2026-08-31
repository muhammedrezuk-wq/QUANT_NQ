@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set QUANT_LOCAL_MODE=1
cd /d "%~dp0\.."
python scripts\log_button.py "غرفة القيادة" START >nul 2>&1
python scripts\launch_market.py --both
set CODE=%ERRORLEVEL%
pause
endlocal & exit /b %CODE%
