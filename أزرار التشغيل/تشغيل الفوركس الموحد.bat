@echo off
cd /d "%~dp0\.."
python scripts\prepare_unified.py
if errorlevel 1 (
  echo تعذر إنشاء روابط المشروع الموحد.
  pause
  exit /b 1
)
python scripts\run_forex.py %*
