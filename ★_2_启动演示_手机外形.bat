@echo off
chcp 65001 >nul
title Xiangyin Medicine Box - Phone-shaped Demo
cd /d "%~dp0"
setlocal enabledelayedexpansion

REM ============================================================
REM  Xiangyin Medicine Box  -  launcher 2/4
REM  ----------------------------------------------------------
REM  Root-level one-click launcher. It only locates the Chinese
REM  "02_*" code folder and hands over to the real launcher
REM  inside. Chinese never appears in this file on purpose:
REM  cmd mis-decodes CJK text inside a .bat when the path
REM  contains Chinese characters.
REM
REM  Steps:
REM    1. find the 02_* folder with a wildcard (for /d)
REM    2. check the folder is there
REM    3. run start_phone_demo.bat
REM
REM  No bare "timeout" command anywhere - that name collides
REM  with the Unix timeout. We sleep with PowerShell instead.
REM ============================================================

echo.
echo   Xiangyin Medicine Box  -  Phone-shaped Demo
echo   ---------------------------------------------------------

set "SUB="
for /d %%D in ("02_*") do set "SUB=%%~fD"
if not defined SUB (
  echo   ERROR: the code folder "02_*" was not found next to this file.
  echo          Keep this file in the same folder as the "02_*" folder.
  echo.
  pause
  exit /b 1
)

echo   Code folder: %SUB%
echo.
echo   Handing over to start_phone_demo.bat ...
echo.

start "" "%SUB%\start_phone_demo.bat"
exit /b 0
