@echo off
REM install.bat — Foolproof one-shot installer (handles spaces + ExecutionPolicy)
REM Usage: double-click (recommended) or run:  install.bat
REM Calls install.ps1 with Bypass so Restricted policy never blocks.

setlocal
REM Use Bypass for this invocation only; also handles spaces in path
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
set EC=%ERRORLEVEL%
if not "%EC%"=="0" (
  echo Installer exited with code %EC% - see log above
)
echo Press Enter to close...
pause >nul
endlocal
