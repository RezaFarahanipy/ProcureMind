@echo off
chcp 65001 >nul
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe ( echo ابتدا scripts\setup_windows.ps1 را اجرا کنید & pause & exit /b 1 )
set HOST=127.0.0.1
set PORT=8000
if exist .env for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
  echo %%a| findstr /b "#" >nul || set "%%a=%%b"
)
echo http://%HOST%:%PORT%
.venv\Scripts\python.exe -m uvicorn backend.main:app --host %HOST% --port %PORT%
pause
