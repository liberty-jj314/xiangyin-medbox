@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal
set "SUB="
for /d %%D in ("02_*") do set "SUB=%%~fD"
if not defined SUB (
  echo ERROR: Code folder 02_* is missing. Extract the whole ZIP first.
  pause
  exit /b 1
)
set "PYEXE=python"
py -3 --version >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3"
%PYEXE% --version >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python 3 is not installed or is missing from PATH.
  pause
  exit /b 1
)
%PYEXE% "%SUB%\preflight.py"
set "RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RESULT%
