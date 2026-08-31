@echo off
cd /d "%~dp0\.."
python scripts\log_button.py "تشغيل لوحة الكريبتو" START >nul 2>&1
python scripts\run_governance.py --market crypto
