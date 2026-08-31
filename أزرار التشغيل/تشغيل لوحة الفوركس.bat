@echo off
cd /d "%~dp0\.."
python scripts\log_button.py "تشغيل لوحة الفوركس" START >nul 2>&1
python scripts\run_governance.py --market forex
