@echo off
chcp 65001 >nul
cd /d "%~dp0"
python scripts\log_button.py "شغّل_إثبات_ورقة_١٥" START >nul 2>&1
echo ======================================================================
echo   اثبات ورقة 15 — منظومة التحليل والقرار والمحافظ
echo ======================================================================
python scripts\proof_paper15.py .
echo.
echo ======================================================================
echo   اختبارات المشروع الكاملة
echo ======================================================================
python -m pip install -q pytest pytest-asyncio
python -m pytest -q --ignore=tests/core/test_websocket_queue_continuity.py
echo.
pause
