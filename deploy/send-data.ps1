<#
  Envia a pasta data/ do leadpipe (banco, sites gerados, imagens, videos)
  deste PC Windows para o servidor, e reinicia o app la.

  Uso, no PowerShell:
      irm https://raw.githubusercontent.com/pato15z/claude-1/claude/tender-fermi-1albbv/deploy/send-data.ps1 -OutFile "$env:TEMP\send.ps1"
      & "$env:TEMP\send.ps1" -ip SEU.IP.DO.SERVIDOR

  Rode a partir do arquivo, nunca com "| iex": num pipeline o PowerShell toma
  a entrada do teclado, e ai o ssh pergunta a senha e nao consegue ler nada.

  ESTE ARQUIVO E SO ASCII, DE PROPOSITO. O Windows PowerShell 5.1 le .ps1 na
  codificacao ANSI do sistema, nao em UTF-8. Um acento ou um travessao viram
  bytes estranhos no meio de uma string e o script nem chega a rodar. Por isso
  nao ha acentos aqui. Nao adicione.

  Por que nao pelo Git: o repositorio e publico e o banco tem os dados de
  todos os leads; alem disso o GitHub recusa arquivos acima de 100 MB.
  Por isso vai direto, maquina a maquina.
#>

param([string]$ip)

$ErrorActionPreference = "Stop"
function Say($m){ Write-Host "`n==> $m" -ForegroundColor Magenta }
function Warn($m){ Write-Host "    $m" -ForegroundColor Yellow }

# ---------------------------------------------------------------- servidor
if (-not $ip) { $ip = Read-Host "IP do servidor (ex: 162.243.36.84)" }
$ip = "$ip".Trim()
if ($ip -notmatch '^\d{1,3}(\.\d{1,3}){3}$') { throw "IP invalido: '$ip'" }

# ---------------------------------------------------------------- requisitos
# ssh/scp vem no Windows 10/11; tar tambem (bsdtar) desde a build 1803.
foreach ($t in @("ssh","scp","tar")) {
  if (-not (Get-Command $t -ErrorAction SilentlyContinue)) {
    throw "Falta o comando '$t'. Instale em: Configuracoes > Aplicativos > Recursos opcionais > Adicionar > Cliente OpenSSH."
  }
}

# ---------------------------------------------------------------- achar data/
# O banco e a assinatura da pasta: onde esta leadpipe.db, ali e o data/.
Say "procurando a pasta data do leadpipe neste PC"
$roots = @(
  $PWD.Path,
  "$env:USERPROFILE\Desktop", "$env:USERPROFILE\Documents",
  "$env:USERPROFILE\Downloads", "$env:USERPROFILE"
) + (Get-PSDrive -PSProvider FileSystem | ForEach-Object { $_.Root })
$roots = $roots | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

$dataDir = $null
foreach ($r in $roots) {
  $hit = Get-ChildItem -Path $r -Filter "leadpipe.db" -Recurse -Depth 5 -File -ErrorAction SilentlyContinue |
         Select-Object -First 1
  if ($hit) { $dataDir = $hit.Directory.FullName; break }
}

if (-not $dataDir) {
  Warn "Nao achei sozinho."
  $p = (Read-Host "Arraste aqui a pasta 'data' do leadpipe e aperte Enter").Trim().Trim('"')
  if (-not (Test-Path (Join-Path $p "leadpipe.db"))) { throw "Nao encontrei leadpipe.db dentro de '$p'" }
  $dataDir = (Resolve-Path $p).Path
}

$parent = Split-Path $dataDir -Parent
$leaf   = Split-Path $dataDir -Leaf
$files  = Get-ChildItem $dataDir -Recurse -File -ErrorAction SilentlyContinue
$mb     = [math]::Round((($files | Measure-Object Length -Sum).Sum / 1MB), 0)
Say "achei: $dataDir  ($mb MB)"

# ---------------------------------------------------------------- app fechado?
# Copiar o banco com o app escrevendo nele pode levar metade de uma transacao.
if (Test-Path (Join-Path $dataDir "leadpipe.db-wal")) {
  Warn "Existe leadpipe.db-wal: sinal de que o app pode estar aberto agora."
}
if ((Read-Host "Feche o app (a janela do app.bat) antes de seguir. Digite S para continuar") -notmatch '^[sSyY]') {
  throw "cancelado por voce"
}

# ---------------------------------------------------------------- compactar
$tgz = Join-Path $env:TEMP "leadpipe-data.tgz"
# Compactar 1 GB leva minutos. Se ja existe um pacote mais novo que o arquivo
# mais recente do data/, ele representa os mesmos dados: reaproveita.
$newest = ($files | Measure-Object LastWriteTime -Maximum).Maximum
if ((Test-Path $tgz) -and $newest -and (Get-Item $tgz).LastWriteTime -gt $newest) {
  Say "reaproveitando o pacote ja compactado"
} else {
  Say "compactando (pode demorar alguns minutos)"
  if (Test-Path $tgz) { Remove-Item $tgz -Force }
  tar -czf "$tgz" -C "$parent" "$leaf"
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $tgz)) { throw "falhou ao compactar" }
}
$tgzMb = [math]::Round(((Get-Item $tgz).Length / 1MB), 0)
Say "pacote pronto: $tgzMb MB"

# ---------------------------------------------------------------- enviar
# accept-new mata a pergunta yes/no da primeira conexao, que trava quem nao
# consegue responder; ConnectTimeout evita ficar pendurado se o IP estiver errado.
$sshOpts = @("-o","StrictHostKeyChecking=accept-new","-o","ConnectTimeout=20")

Say "enviando para o servidor - vai pedir a senha do servidor"
Warn "Enquanto digita a senha a tela nao mostra nada. E normal."
Warn "Sao $tgzMb MB subindo para Nova York: pode levar de 15 min a 1 hora."
scp @sshOpts "$tgz" "root@${ip}:/opt/leadpipe/upload.tgz"
if ($LASTEXITCODE -ne 0) { throw "falhou ao enviar (senha errada ou servidor fora do ar?)" }

# ---------------------------------------------------------------- instalar la
# O data/ antigo vira data.old em vez de ser apagado: se algo der errado,
# o anterior ainda esta no servidor para voltar atras.
Say "instalando no servidor - vai pedir a senha de novo"
$remote = "cd /opt/leadpipe && rm -rf data.old && if [ -d data ]; then mv data data.old; fi && " +
          "tar -xzf upload.tgz && rm -f upload.tgz && " +
          "if [ ! -d data ]; then mv '$leaf' data; fi && " +
          "cd deploy && docker compose restart app && sleep 10 && " +
          "docker compose exec -T app leadpipe db sql 'SELECT COUNT(*) FROM leads'"
ssh @sshOpts "root@$ip" $remote
if ($LASTEXITCODE -ne 0) { throw "falhou no servidor - me mande o que apareceu acima" }

Remove-Item $tgz -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "PRONTO." -ForegroundColor Green
Write-Host "O numero acima e quantos leads chegaram no servidor. Tem que ser 1015."
Write-Host "Se for 1015, abra o painel no navegador: seus leads estao na nuvem."
Write-Host ""
Write-Host "A copia anterior ficou guardada no servidor em /opt/leadpipe/data.old"
Write-Host "Depois que confirmar que esta tudo certo, da para apagar."
