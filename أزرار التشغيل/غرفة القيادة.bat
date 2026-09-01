@echo off
REM أداة داخلية قديمة؛ العقد الرسمي هو زرا الفوركس والكريبتو المستقلان.
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set QUANT_LOCAL_MODE=1
cd /d "%~dp0\.."
call scripts\py.bat scripts\log_button.py "control_room" START >nul 2>&1
call scripts\py.bat governance\app.py
set CODE=%ERRORLEVEL%
if not "%CODE%"=="0" pause
endlocal & exit /b %CODE%
