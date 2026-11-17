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
    $ProgressPreference = "SilentlyContinue"   # much faster downloads in Windows PowerShell 5.1
    $pinnedTag = "b10621"                      # fallback build if the GitHub API lookup fails
    $assetPattern = '^llama-.*-bin-win-cpu-x64\.zip$'
    $url = $null; $tag = $null; $name = $null
    try {
        # Look at the 15 newest releases: the very latest one may not have its Windows files uploaded yet
        $releases = Invoke-RestMethod "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=15" -Headers @{ "User-Agent" = "procuremind" }
        foreach ($r in $releases) {
            $a = $r.assets | Where-Object { $_.name -match $assetPattern } | Select-Object -First 1
            if ($a) { $url = $a.browser_download_url; $tag = $r.tag_name; $name = $a.name; break }
        }
    } catch {
        Write-Host "GitHub API lookup failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    if (-not $url) {
        Write-Host "Using pinned build $pinnedTag" -ForegroundColor Yellow
        $tag = $pinnedTag
        $name = "llama-$pinnedTag-bin-win-cpu-x64.zip"
        $url = "https://github.com/ggml-org/llama.cpp/releases/download/$pinnedTag/$name"
    }
    New-Item -ItemType Directory -Force bin | Out-Null
    $zip = "bin\$name"
    Write-Host "Downloading $name ($tag) ..."
    Invoke-WebRequest $url -OutFile $zip -UseBasicParsing
    Expand-Archive $zip -DestinationPath bin\llama.cpp -Force
    Remove-Item $zip
    $exe = Get-ChildItem bin\llama.cpp -Recurse -Filter llama-server.exe | Select-Object -First 1
    if (-not $exe) { throw "llama-server.exe not found after extraction." }
    if ($exe.DirectoryName -ne (Resolve-Path bin\llama.cpp).Path) { Move-Item "$($exe.DirectoryName)\*" bin\llama.cpp -Force }
    $tag | Out-File bin\llama_version.txt
    Write-Host "Installed llama.cpp version: $tag"
}
Write-Host "`nDone. Put the model files in the models folder (see README)." -ForegroundColor Green
