@echo off
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv not found in the project root. Create it first: python -m venv .venv
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\update.py
echo.
pause
