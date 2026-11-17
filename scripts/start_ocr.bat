@echo off
cd /d "%~dp0.."
echo Project folder: %CD%
if not exist "bin\llama.cpp\llama-server.exe" (
  echo [ERROR] bin\llama.cpp\llama-server.exe not found. Run scripts\setup_windows.ps1 first.
  pause
  exit /b 1
)
if not exist "models\Dots.Ocr-1.8B-Q8_0.gguf" (
  echo [ERROR] models\Dots.Ocr-1.8B-Q8_0.gguf not found.
  pause
  exit /b 1
)
if not exist "models\mmproj-Dots.Ocr-F16.gguf" (
  echo [ERROR] models\mmproj-Dots.Ocr-F16.gguf not found.
  pause
  exit /b 1
)
rem Context is kept small to save RAM. Increase -c if pages are large.
"bin\llama.cpp\llama-server.exe" -m "models\Dots.Ocr-1.8B-Q8_0.gguf" --mmproj "models\mmproj-Dots.Ocr-F16.gguf" --host 127.0.0.1 --port 8081 -c 8192 -n 4096 -t 4 --temp 0 --jinja
pause
