@echo off
cd /d "%~dp0\.."
python scripts\prepare_unified.py
if errorlevel 1 pause
