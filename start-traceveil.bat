@echo off
setlocal
title Traceveil Launcher
cd /d "%~dp0"

echo.
echo  ============================================================
echo                         TRACEVEIL
echo               Local investigation platform launcher
echo  ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-traceveil.ps1"
set "TRACEVEIL_EXIT=%ERRORLEVEL%"

echo.
if not "%TRACEVEIL_EXIT%"=="0" (
  echo Traceveil did not start successfully. Review the message above
  echo and the Backend or Frontend service console for details.
) else (
  echo The launcher can now be closed. Keep the Backend and Frontend
  echo service consoles open while using Traceveil.
)
echo.
pause
exit /b %TRACEVEIL_EXIT%
