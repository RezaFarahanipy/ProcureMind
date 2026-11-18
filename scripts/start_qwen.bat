@echo off
cd /d "%~dp0.."
echo Project folder: %CD%
if not exist "bin\llama.cpp\llama-server.exe" (
  echo [ERROR] bin\llama.cpp\llama-server.exe not found. Run scripts\setup_windows.ps1 first.
  pause
  exit /b 1
)
if not exist "models\Qwen3.5-9B-Q4_K_M.gguf" (
  echo [ERROR] models\Qwen3.5-9B-Q4_K_M.gguf not found.
  pause
  exit /b 1
)
rem i7-7700 has 4 physical cores, so -t 4
"bin\llama.cpp\llama-server.exe" -m "models\Qwen3.5-9B-Q4_K_M.gguf" --host 127.0.0.1 --port 8080 -np 1 -c 4096 -t 4 --jinja
pause
