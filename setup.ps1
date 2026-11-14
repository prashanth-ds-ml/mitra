# CodeMitra one-command setup for Windows (D-083).
# Run it in the folder you cloned:   powershell -ExecutionPolicy Bypass -File setup.ps1
# It installs uv (Python tool manager) if missing, installs CodeMitra, then runs `codemitra setup`
# (Ollama, the model for this machine, the free Kaggle GPU, sharing). Safe to run again.
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Have($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

Write-Host "CodeMitra setup" -ForegroundColor Green

if (-not (Have "uv")) {
    Write-Host "Installing uv (Python tool manager)..."
    powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Have "uv")) { Write-Host "uv did not install. Install it from https://docs.astral.sh/uv/ and run this again." -ForegroundColor Red; exit 1 }
}

Write-Host "Installing CodeMitra..."
uv tool install --reinstall -e . --python 3.12
if ($LASTEXITCODE -ne 0) { Write-Host "Installing CodeMitra failed (see above)." -ForegroundColor Red; exit 1 }
uv tool update-shell | Out-Null

$bin = (uv tool dir --bin).Trim()
$env:Path = "$bin;$env:Path"
& "$bin\codemitra.exe" setup @args
exit $LASTEXITCODE
