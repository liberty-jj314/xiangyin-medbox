@echo off
chcp 65001 >nul
title Xiangyin Medicine Box - Phone Demo
cd /d "%~dp0"
setlocal enabledelayedexpansion

REM ============================================================
REM  Xiangyin Medicine Box  -  Virtual Phone Demo (one click)
REM  ----------------------------------------------------------
REM  This file is intentionally ASCII-only: Chinese text inside a
REM  .bat is mis-decoded by cmd when the path contains CJK chars.
REM  All Chinese hints are printed by demo_server.py instead.
REM ============================================================

echo.
echo   [1/4] Locating Python ...
set "PYEXE=python"
py -3 --version >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3"
%PYEXE% --version >nul 2>nul
if errorlevel 1 (
  echo   ERROR: Python not found in PATH.
  pause
  exit /b 1
)

echo   [2/4] Pre-flight check (keys / drug data) ...
%PYEXE% demo_server.py --check --open
if errorlevel 1 (
  echo   ^>^> Fix the problem listed above, then run this file again.
  echo      The folder that needs the files has just been opened.
  echo.
  pause
  exit /b 1
)

echo   [3/4] Locating Chrome / Edge ...
REM  Chrome first; if not installed, fall back to Edge (built into
REM  Windows 10/11, same engine, supports --app the same way).
REM  NOTE: use "if exist" chains (not a for-loop) and !DELAYED!
REM  expansion below - Edge's path contains "(x86)" and a %VAR%
REM  inside a parenthesized block would close the block early.
set "CHROME="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
set "EDGE="
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not defined EDGE if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if defined CHROME (echo         Chrome: !CHROME!) else (
  if defined EDGE (echo         Chrome not found - using Edge: !EDGE!
  ) else (echo         neither found - will use default browser)
)

REM  Clear any stale lockfile left by a previous window that was closed
REM  forcefully. A leftover lock makes Chrome silently refuse to open a
REM  new --app window (the real cause of "double-click does nothing").
if exist "%TEMP%\xiangyin_phone_profile\lockfile" del /q "%TEMP%\xiangyin_phone_profile\lockfile"

echo   [4/4] Checking the local server on port 8000 ...
REM  0 = our own server is already running -> reuse it
REM  1 = nothing is listening              -> start it
REM  2 = port taken by something else      -> stop and warn
REM Serialize startup across all three entry points.
%PYEXE% -X utf8 ensure_service.py
if errorlevel 2 goto foreign
if errorlevel 1 goto noluck
powershell -NoProfile -Command "try{$r=Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/version' -TimeoutSec 5;if($r.build -eq '20261028-step1'){exit 0}else{exit 2}}catch{try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',8000);$c.Close();exit 2}catch{exit 1}}"
set "RC=%errorlevel%"
if "%RC%"=="2" goto foreign
if not "%RC%"=="0" goto noluck
goto reuse

:reuse
echo         already running - reusing it (no second server started)
echo.
goto ready

:noluck
echo.
echo   ERROR: server did not come up within 30 seconds.
echo   Please check the minimized console window named
echo   "Xiangyin Demo Server" for details.
echo.
pause
exit /b 1

:foreign
echo.
echo   ERROR: port 8000 is used by another program or an older build.
echo   Close the OLD server window first, then run THIS launcher again.
echo.
pause
exit /b 1

:ready
echo   Opening the virtual phone ...
echo.

if defined CHROME (
  start "" "!CHROME!" ^
    --app=http://127.0.0.1:8000/phone.html ^
    --window-size=800,940 ^
    --window-position=120,60 ^
    --user-data-dir="%TEMP%\xiangyin_phone_profile" ^
    --no-first-run ^
    --no-default-browser-check ^
    --no-proxy-server ^
    --autoplay-policy=no-user-gesture-required ^
    --disable-backgrounding-occluded-windows
) else (
  if defined EDGE (
    start "" "!EDGE!" ^
      --app=http://127.0.0.1:8000/phone.html ^
      --window-size=800,940 ^
      --window-position=120,60 ^
      --user-data-dir="%TEMP%\xiangyin_phone_profile" ^
      --no-first-run ^
      --no-default-browser-check ^
      --no-proxy-server ^
      --autoplay-policy=no-user-gesture-required ^
      --disable-backgrounding-occluded-windows
  ) else (
    start "" http://127.0.0.1:8000/phone.html
  )
)

echo   Done. Two windows are now open:
echo     - the virtual phone  (this is what you show the judges)
echo     - a minimized "Xiangyin Demo Server" console (keep it open)
echo.
echo   To stop everything: close the virtual phone, then close the
echo   minimized server console.
echo.
powershell -NoProfile -Command "Start-Sleep -Seconds 1"
exit /b 0
