@echo off
cd /d "%~dp0.."
echo Project folder: %CD%
rem ---- choose the model files here (only these two lines) ----
set "OCR_MODEL=models\dots.ocr.Q4_K_M.gguf"
set "OCR_MMPROJ=models\dots.ocr.mmproj-q8_0.gguf"
rem Previous heavier choice: dots.ocr.Q8_0.gguf + dots.ocr.mmproj-f16.gguf
rem ------------------------------------------------------------
if not exist "bin\llama.cpp\llama-server.exe" (
  echo [ERROR] bin\llama.cpp\llama-server.exe not found. Run scripts\setup_windows.ps1 first.
  pause
  exit /b 1
)
if not exist "%OCR_MODEL%" (
  echo [ERROR] %OCR_MODEL% not found.
  pause
  exit /b 1
)
if not exist "%OCR_MMPROJ%" (
  echo [ERROR] %OCR_MMPROJ% not found.
  pause
  exit /b 1
)
echo Model: %OCR_MODEL%
echo Projector: %OCR_MMPROJ%
rem Context is kept small to save RAM. Increase -c if pages are large.
"bin\llama.cpp\llama-server.exe" -m "%OCR_MODEL%" --mmproj "%OCR_MMPROJ%" --host 127.0.0.1 --port 8081 -np 1 -c 8192 -n 4096 -t 4 --temp 0.1 --jinja
pause
