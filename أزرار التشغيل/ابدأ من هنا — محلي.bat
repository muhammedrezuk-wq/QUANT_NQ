@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set QUANT_LOCAL_MODE=1
cd /d "%~dp0\.."
python scripts\log_button.py "ابدأ من هنا — محلي" START >nul 2>&1
echo.
echo   QUANT_NQ — تشغيل محلي آمن
 echo  لا مفتاح مطلوب. لا Online. لا تداول.
echo  سيتم فتح اللوحة، وأي مشكلة ستظهر بالعربي داخل لوحة الأمان.
echo.
python scripts\launch_market.py --both
set CODE=%ERRORLEVEL%
echo.
if "%CODE%"=="0" (
  echo تم التشغيل. افتح: http://127.0.0.1:8090
) else (
  echo تعذر اكتمال الإقلاع. افتح لوحة الأمان أو اقرأ رسالة الخطأ أعلاه.
)
pause
endlocal & exit /b %CODE%
