@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set QUANT_LOCAL_MODE=1
cd /d "%~dp0\.."
python scripts\log_button.py "٢_النواة_وحدها" START >nul 2>&1
echo ======================================================================
echo   النواة المحلية وحدها — بدون مفتاح API
 echo  الفحص والتشخيص يعملان محليًا؛ Online والتداول لا يعملان بدون اعتماداتهما.
echo ======================================================================
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" scripts\run_forex.py
) else (
  py -3 scripts\run_forex.py
)
set CODE=%ERRORLEVEL%
echo.
if not "%CODE%"=="0" echo فشل إقلاع النواة — افتح لوحة القيادة أو لوحة الأمان.
pause
endlocal & exit /b %CODE%
