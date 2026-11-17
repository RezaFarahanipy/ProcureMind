@echo off
chcp 65001 >nul
cd /d "%~dp0.."
if not exist bin\llama.cpp\llama-server.exe ( echo ابتدا scripts\setup_windows.ps1 را اجرا کنید & pause & exit /b 1 )
if not exist models\Dots.Ocr-1.8B-Q8_0.gguf ( echo فایل models\Dots.Ocr-1.8B-Q8_0.gguf پیدا نشد & pause & exit /b 1 )
if not exist models\mmproj-Dots.Ocr-F16.gguf ( echo فایل models\mmproj-Dots.Ocr-F16.gguf پیدا نشد & pause & exit /b 1 )
rem ctx کوچک‌تر از مقدار پیشنهادی مدل (131072) تا RAM پر نشود؛ اگر صفحه بزرگ بود افزایش دهید
bin\llama.cpp\llama-server.exe -m models\Dots.Ocr-1.8B-Q8_0.gguf --mmproj models\mmproj-Dots.Ocr-F16.gguf --host 127.0.0.1 --port 8081 -c 8192 -n 4096 -t 4 --temp 0 --jinja
pause
