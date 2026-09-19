# Atualiza (ou instala) o leadpipe nesta pasta, sem mexer em data\ (banco, fotos, heros).
#   .\update.ps1 -Online              baixa a versão mais nova do GitHub e aplica
#   .\update.ps1                      usa o ZIP mais novo em Downloads
#   .\update.ps1 C:\caminho\x.zip     usa esse ZIP
# Se não existir .venv (ambiente Python), cria e instala tudo.
param([string]$Zip = "", [switch]$Online)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$tmp = "$env:TEMP\leadpipe-update"
if ($Online) {
  $Zip = "$env:TEMP\leadpipe-update.zip"
  Write-Host "baixando..."
  Invoke-WebRequest -Uri "https://github.com/Pato15Z/Claude-1/archive/refs/heads/claude/epic-volta-r7nfcf.zip" -OutFile $Zip
} elseif (-not $Zip) {
  $cand = Get-ChildItem "$env:USERPROFILE\Downloads\Claude-1-claude-epic-volta-r7nfcf*.zip" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $cand) { Write-Host "Nenhum ZIP em Downloads. Use: .\update.ps1 -Online"; exit 1 }
  $Zip = $cand.FullName
}
Write-Host "usando $Zip"
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive $Zip -DestinationPath $tmp -Force
$src = Get-ChildItem $tmp | Select-Object -First 1
foreach ($item in @("leadpipe", "tests", "docs", "pyproject.toml", "README.md", "setup.ps1", "setup.sh", "update.ps1", "app.bat", "app-local.bat", ".gitignore")) {
  $from = Join-Path $src.FullName $item
  if (Test-Path $from) {
    if (Test-Path $item) { Remove-Item $item -Recurse -Force }
    Copy-Item $from -Destination $item -Recurse -Force
  }
}
Remove-Item $tmp -Recurse -Force

# ambiente Python: cria se não existir
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "criando ambiente Python (.venv)..."
  python -m venv .venv
  if (-not (Test-Path $py)) { Write-Host "ERRO: Python não encontrado. Instale em https://www.python.org/downloads/ (marque 'Add Python to PATH') e rode de novo."; exit 1 }
  Write-Host "instalando bibliotecas (1-3 min)..."
  & $py -m pip install -q typer==0.27.2 click==8.5.0 rich==15.0.0 httpx==0.28.1 playwright==1.63.0 phonenumbers==9.0.39 timezonefinder==8.2.0 geonamescache==3.0.2 beautifulsoup4==4.15.0 lxml==6.1.3 python-slugify==9.0.0 pillow==12.3.0 jinja2==3.1.6 numpy==2.2.6 h3==4.5.0 pytest==9.1.1 pytest-asyncio==1.4.0
}
Write-Host "instalando o leadpipe..."
& $py -m pip install -q -e . --no-deps

# banco de leads: onde está?
if (Test-Path ".\data\leadpipe.db") {
  Write-Host "banco encontrado: $PSScriptRoot\data\leadpipe.db"
} else {
  Write-Host "AVISO: não há data\leadpipe.db nesta pasta. Procurando no disco D: e C:\Users..."
  $found = @(Get-ChildItem "D:\", "$env:USERPROFILE" -Recurse -Filter leadpipe.db -ErrorAction SilentlyContinue -Force | Select-Object -ExpandProperty FullName)
  if ($found.Count -gt 0) {
    Write-Host "encontrado em:"; $found | ForEach-Object { Write-Host "  $_" }
    Write-Host "Para usar: mova a pasta 'data' inteira (que contém esse arquivo) para $PSScriptRoot\data"
  } else { Write-Host "nenhum banco encontrado; um novo será criado ao abrir o app." }
}
Write-Host "atualizado. Abra o app com app.bat"
