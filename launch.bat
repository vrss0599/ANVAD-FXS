@echo off
REM launch.bat — Foolproof double-click launcher (always uses venv python, no ExecutionPolicy issues)
REM Handles spaces in path via quoted args.

setlocal
set "VENV_PY=%~dp0venv\Scripts\python.exe"
set "MAIN_PY=%~dp0app\main.py"

if not exist "%VENV_PY%" (
  echo venv not found at "%VENV_PY%"
  echo Run install first: double-click install.bat
  pause
  exit /b 1
)
if not exist "%MAIN_PY%" (
  echo app\main.py not found at "%MAIN_PY%"
  pause
  exit /b 1
)
echo Launching UGA-SUB via venv: "%VENV_PY%"
"%VENV_PY%" "%MAIN_PY%"
set EC=%ERRORLEVEL%
if not "%EC%"=="0" (
  echo GUI exited with code %EC%
  echo Try: "%VENV_PY%" tools\check_cuda.py
  pause
)
endlocal
