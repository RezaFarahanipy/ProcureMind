@echo off
cd /d "%~dp0.."
echo Project folder: %CD%
rem ---- choose the model file here (only this line) ----
set "QWEN_MODEL=models\Qwen_Qwen3.5-9B-IQ4_XS.gguf"
rem Previous choice: models\Qwen3.5-9B-Q4_K_M.gguf
rem Lighter options: Qwen_Qwen3.5-9B-IQ3_M.gguf  /  Qwen_Qwen3.5-9B-Q3_K_M.gguf
rem -----------------------------------------------------
if not exist "bin\llama.cpp\llama-server.exe" (
  echo [ERROR] bin\llama.cpp\llama-server.exe not found. Run scripts\setup_windows.ps1 first.
  pause
  exit /b 1
)
if not exist "%QWEN_MODEL%" (
  echo [ERROR] %QWEN_MODEL% not found.
  pause
  exit /b 1
)
echo Model: %QWEN_MODEL%
rem 4 physical cores, so -t 4
"bin\llama.cpp\llama-server.exe" -m "%QWEN_MODEL%" --host 127.0.0.1 --port 8080 -np 1 -c 4096 -t 4 --jinja
pause
