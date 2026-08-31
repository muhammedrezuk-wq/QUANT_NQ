@echo off
REM ---------------------------------------------------------------------
REM  One interpreter for every button.  ASCII only on purpose: cmd reads a
REM  .bat in the console OEM codepage, so Arabic on a command line is a
REM  parsing hazard.  Keep this file ASCII forever.
REM
REM  Order of preference:
REM    1. vendor\python\runtime\python.exe  - OUR OWN Python, shipped with
REM       the project.  Nothing on the machine can move it, upgrade it or
REM       break it.  Owner ruling 2026-09-01: "we mount on the machine and
REM       use its resources without anyone disturbing us - if someone
REM       installs an app or updates a library, our house must not break."
REM    2. venv\Scripts\python.exe           - a project venv, if one was
REM       built from a system Python (older setups).
REM    3. py -3                             - last resort only.
REM
REM  2026-09-01, measured: the project had TWO interpreters in use.
REM    venv\Scripts\python.exe -> complete against requirements.txt
REM    bare "python" (system)  -> missing deep-translator
REM  Twelve of twenty buttons called the bare one, so those runs started
REM  the platform with an incomplete environment and news headlines stayed
REM  untranslated (the import failure is swallowed by design).
REM ---------------------------------------------------------------------
setlocal
set "ROOT=%~dp0.."
if exist "%ROOT%\vendor\python\runtime\python.exe" (
  "%ROOT%\vendor\python\runtime\python.exe" %*
  exit /b %ERRORLEVEL%
)
if exist "%ROOT%\venv\Scripts\python.exe" (
  "%ROOT%\venv\Scripts\python.exe" %*
  exit /b %ERRORLEVEL%
)
py -3 %*
exit /b %ERRORLEVEL%
