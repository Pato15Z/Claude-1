# Atualiza o código do leadpipe para a versão mais nova do GitHub, sem mexer
# em data\ (banco, fotos, heros) nem em .venv. Rode dentro da pasta leadpipe.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$zip = "$env:TEMP\leadpipe-update.zip"
$tmp = "$env:TEMP\leadpipe-update"
Write-Host "baixando..."
Invoke-WebRequest -Uri "https://github.com/Pato15Z/Claude-1/archive/refs/heads/claude/epic-volta-r7nfcf.zip" -OutFile $zip
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive $zip -DestinationPath $tmp -Force
$src = Get-ChildItem $tmp | Select-Object -First 1
foreach ($item in @("leadpipe", "tests", "docs", "pyproject.toml", "README.md", "setup.ps1", "setup.sh", "update.ps1", ".gitignore")) {
  $from = Join-Path $src.FullName $item
  if (Test-Path $from) {
    if (Test-Path $item) { Remove-Item $item -Recurse -Force }
    Copy-Item $from -Destination $item -Recurse -Force
  }
}
Remove-Item $zip -Force; Remove-Item $tmp -Recurse -Force
Write-Host "instalando..."
& .\.venv\Scripts\python.exe -m pip install -q -e . --no-deps
Write-Host "atualizado. Rode: .\.venv\Scripts\Activate.ps1 ; lp.exe doctor"
