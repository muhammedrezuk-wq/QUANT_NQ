@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set QUANT_LOCAL_MODE=1
cd /d "%~dp0\.."
python scripts\log_button.py "٨_كلشي_بزر_واحد" START >nul 2>&1
echo ======================================================================
echo   التشغيل المحلي الكامل — اللوحة + النواتان + الحوكمة
 echo  الوضع المحلي: لا مفتاح مطلوب للإقلاع. Online والتداول يبقيان مقفولين
 echo  وتظهر أي خطوة ناقصة داخل لوحة الأمان.
echo ======================================================================
python scripts\launch_market.py --both
set CODE=%ERRORLEVEL%
echo.
if not "%CODE%"=="0" echo انتهى التشغيل برمز %CODE% — افتح لوحة الأمان لمعرفة السبب.
pause
endlocal & exit /b %CODE%
