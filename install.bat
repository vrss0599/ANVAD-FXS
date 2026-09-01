@echo off
REM install.bat — Robust one-shot installer (calls install.ps1)
REM Usage: double-click or run:  install.bat
powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
