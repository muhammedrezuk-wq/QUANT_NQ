@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
cd /d "%~dp0\.."
python scripts\log_button.py "٠_إيقاف_النواة" START >nul 2>&1
echo ======================================================================
echo   إيقاف خدمات QUANT_NQ المحددة
 echo  لا يتم تشغيل غرفة القيادة أو أي واجهة إضافية.
echo ======================================================================
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" scripts\stop_all.py
) else (
  py -3 scripts\stop_all.py
)
set CODE=%ERRORLEVEL%
echo.
if not "%CODE%"=="0" echo فشل الإيقاف — راجع سجل التشغيل.
pause
endlocal & exit /b %CODE%
