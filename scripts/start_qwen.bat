@echo off
chcp 65001 >nul
cd /d "%~dp0.."
if not exist bin\llama.cpp\llama-server.exe ( echo ابتدا scripts\setup_windows.ps1 را اجرا کنید & pause & exit /b 1 )
if not exist models\Qwen3.5-9B-Q4_K_M.gguf ( echo فایل models\Qwen3.5-9B-Q4_K_M.gguf پیدا نشد & pause & exit /b 1 )
rem ctx کوچک = RAM کمتر. روی i7-7700 چهار هسته فیزیکی دارد، پس -t 4
bin\llama.cpp\llama-server.exe -m models\Qwen3.5-9B-Q4_K_M.gguf --host 127.0.0.1 --port 8080 -c 4096 -t 4 --jinja
pause
