@echo off
REM launch.bat — double-click launcher (always uses venv python)
"%~dp0venv\Scripts\python.exe" "%~dp0app\main.py"
if errorlevel 1 pause
