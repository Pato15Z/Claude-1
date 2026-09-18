# Instalação em um comando (Windows, PowerShell).
# Se der erro de política: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv")) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install -q -e ".[dev]"
& .\.venv\Scripts\Activate.ps1
playwright install chromium
lp db init
lp doctor
Write-Host ""
Write-Host "Pronto. Sempre que abrir um terminal novo: .\.venv\Scripts\Activate.ps1"
Write-Host 'Teste pequeno: lp source maps --vertical "roof cleaning" --state OH --city Columbus --max-results 30 --debug'
