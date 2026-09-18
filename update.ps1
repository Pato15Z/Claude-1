# Atualiza o código do leadpipe sem mexer em data\ (banco, fotos, heros) nem em .venv.
# O repositório é privado, então o download direto dá 404. Dois jeitos:
#   1) Baixe o ZIP no navegador (logado no GitHub):
#      https://github.com/Pato15Z/Claude-1/archive/refs/heads/claude/epic-volta-r7nfcf.zip
#      e rode:  .\update.ps1            (pega o ZIP mais novo da pasta Downloads)
#      ou:      .\update.ps1 C:\caminho\do\arquivo.zip
#   2) Se o repositório virar público, .\update.ps1 -Online baixa sozinho.
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
  if (-not $cand) { Write-Host "Nenhum ZIP em Downloads. Baixe no navegador: https://github.com/Pato15Z/Claude-1/archive/refs/heads/claude/epic-volta-r7nfcf.zip"; exit 1 }
  $Zip = $cand.FullName
}
Write-Host "usando $Zip"
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive $Zip -DestinationPath $tmp -Force
$src = Get-ChildItem $tmp | Select-Object -First 1
foreach ($item in @("leadpipe", "tests", "docs", "pyproject.toml", "README.md", "setup.ps1", "setup.sh", "update.ps1", ".gitignore")) {
  $from = Join-Path $src.FullName $item
  if (Test-Path $from) {
    if (Test-Path $item) { Remove-Item $item -Recurse -Force }
    Copy-Item $from -Destination $item -Recurse -Force
  }
}
Remove-Item $tmp -Recurse -Force
Write-Host "instalando..."
& .\.venv\Scripts\python.exe -m pip install -q -e . --no-deps
Write-Host "atualizado."
