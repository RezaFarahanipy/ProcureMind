# نصب اولیه روی ویندوز: محیط Python + دانلود llama.cpp (نسخه CPU)
# اجرا:  powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "== 1/2 محیط Python ==" -ForegroundColor Cyan
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

Write-Host "== 2/2 llama.cpp ==" -ForegroundColor Cyan
if (Test-Path bin\llama.cpp\llama-server.exe) {
    Write-Host "llama-server.exe از قبل وجود دارد؛ برای به‌روزرسانی پوشه bin\llama.cpp را پاک کنید."
} else {
    $rel = Invoke-RestMethod "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest" -Headers @{ "User-Agent" = "procuremind" }
    $asset = $rel.assets | Where-Object { $_.name -match '^llama-.*-bin-win-(cpu|avx2)-x64\.zip$' } | Select-Object -First 1
    if (-not $asset) { throw "فایل ویندوز CPU در آخرین release پیدا نشد؛ به https://github.com/ggml-org/llama.cpp/releases مراجعه و دستی دانلود کنید." }
    New-Item -ItemType Directory -Force bin | Out-Null
    $zip = "bin\$($asset.name)"
    Write-Host "دانلود $($asset.name) ($($rel.tag_name))"
    Invoke-WebRequest $asset.browser_download_url -OutFile $zip
    Expand-Archive $zip -DestinationPath bin\llama.cpp -Force
    Remove-Item $zip
    $exe = Get-ChildItem bin\llama.cpp -Recurse -Filter llama-server.exe | Select-Object -First 1
    if ($exe.DirectoryName -ne (Resolve-Path bin\llama.cpp).Path) { Move-Item "$($exe.DirectoryName)\*" bin\llama.cpp -Force }
    $rel.tag_name | Out-File bin\llama_version.txt
    Write-Host "نسخه نصب‌شده: $($rel.tag_name)"
}
Write-Host "`nتمام شد. فایل‌های مدل را در پوشه models بگذارید (README را ببینید)." -ForegroundColor Green
