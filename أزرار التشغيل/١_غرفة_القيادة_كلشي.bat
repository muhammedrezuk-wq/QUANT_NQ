@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set QUANT_LOCAL_MODE=1
cd /d "%~dp0\.."
python scripts\log_button.py "١_غرفة_القيادة_كلشي" START >nul 2>&1
echo ======================================================================
echo   غرفة القيادة المحلية — تشغيل اللوحة والنواة والحوكمة
 echo  لا يوجد مفتاح؟ لا مشكلة: سيقلع الوضع المحلي وتظهر الحالة في لوحة الأمان.
echo ======================================================================
python scripts\launch_market.py --both
set CODE=%ERRORLEVEL%
echo.
if not "%CODE%"=="0" echo يوجد خلل في الإقلاع — راجع لوحة الأمان.
pause
endlocal & exit /b %CODE%
