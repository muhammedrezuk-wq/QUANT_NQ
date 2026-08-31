@echo off
cd /d "%~dp0\.."
python scripts\log_button.py "تهيئة المشروع الموحد" START >nul 2>&1
python scripts\prepare_unified.py
if errorlevel 1 pause
