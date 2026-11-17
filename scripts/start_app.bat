@echo off
cd /d "%~dp0.."
echo Project folder: %CD%
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv not found in the project root. Create it: python -m venv .venv
  pause
  exit /b 1
)
set HOST=127.0.0.1
set PORT=8000
if exist ".env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
)
echo Open: http://%HOST%:%PORT%
".venv\Scripts\python.exe" -m uvicorn backend.main:app --host %HOST% --port %PORT%
pause
