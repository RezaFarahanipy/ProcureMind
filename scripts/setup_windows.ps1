# Windows setup: Python venv + llama.cpp (CPU build)
# Run:  powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "== 1/2 Python environment ==" -ForegroundColor Cyan
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

Write-Host "== 2/2 llama.cpp ==" -ForegroundColor Cyan
if (Test-Path bin\llama.cpp\llama-server.exe) {
    Write-Host "llama-server.exe already exists. Delete bin\llama.cpp to update."
} else {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $rel = Invoke-RestMethod "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest" -Headers @{ "User-Agent" = "procuremind" }
    $asset = $rel.assets | Where-Object { $_.name -match '^llama-.*-bin-win-(cpu|avx2)-x64\.zip$' } | Select-Object -First 1
    if (-not $asset) { throw "No Windows CPU build found in the latest release. Download it manually from https://github.com/ggml-org/llama.cpp/releases and extract into bin\llama.cpp" }
    New-Item -ItemType Directory -Force bin | Out-Null
    $zip = "bin\$($asset.name)"
    Write-Host "Downloading $($asset.name) ($($rel.tag_name))"
    Invoke-WebRequest $asset.browser_download_url -OutFile $zip
    Expand-Archive $zip -DestinationPath bin\llama.cpp -Force
    Remove-Item $zip
    $exe = Get-ChildItem bin\llama.cpp -Recurse -Filter llama-server.exe | Select-Object -First 1
    if (-not $exe) { throw "llama-server.exe not found after extraction." }
    if ($exe.DirectoryName -ne (Resolve-Path bin\llama.cpp).Path) { Move-Item "$($exe.DirectoryName)\*" bin\llama.cpp -Force }
    $rel.tag_name | Out-File bin\llama_version.txt
    Write-Host "Installed llama.cpp version: $($rel.tag_name)"
}
Write-Host "`nDone. Put the model files in the models folder (see README)." -ForegroundColor Green
