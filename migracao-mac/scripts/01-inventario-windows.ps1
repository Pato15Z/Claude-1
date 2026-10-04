<#
    01-inventario-windows.ps1
    Inventaria e empacota configuracoes do After Effects / Premiere Pro / Media Encoder
    de um PC Windows, para restauracao em Mac.

    USO (PowerShell como Administrador, na pasta onde quiser o backup):
        Set-ExecutionPolicy -Scope Process Bypass -Force
        .\01-inventario-windows.ps1

    Opcional:
        .\01-inventario-windows.ps1 -Destino "D:\BackupAdobe"
        .\01-inventario-windows.ps1 -SemFontes      # nao copia fontes (economiza GB)

    O script NAO copia plugins binarios (.aex/.dll) - apenas os LISTA no inventario,
    porque binario Windows nao roda no Mac. Reinstalacao e manual, por design.
#>

[CmdletBinding()]
param(
    [string] $Destino = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'BackupAdobe'),
    [switch] $SemFontes
)

$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'

# ---------------------------------------------------------------- infraestrutura

$script:Inventario = [System.Collections.Generic.List[object]]::new()
$script:Log        = [System.Collections.Generic.List[string]]::new()

function Write-Etapa([string] $texto) {
    Write-Host ''
    Write-Host "== $texto" -ForegroundColor Cyan
    $script:Log.Add("== $texto")
}

function Write-Nota([string] $texto, [string] $cor = 'Gray') {
    Write-Host "   $texto" -ForegroundColor $cor
    $script:Log.Add("   $texto")
}

function Add-Inventario {
    param(
        [string] $Categoria,
        [string] $Caminho,
        [string] $Classe,       # A = portavel, B = binario, C = prefs com estado
        [string] $Observacao = ''
    )
    if (-not (Test-Path -LiteralPath $Caminho)) { return }

    $itens = @(Get-ChildItem -LiteralPath $Caminho -Recurse -File -Force -ErrorAction SilentlyContinue)
    $bytes = ($itens | Measure-Object -Property Length -Sum).Sum
    if (-not $bytes) { $bytes = 0 }

    $script:Inventario.Add([pscustomobject]@{
        Categoria  = $Categoria
        Classe     = $Classe
        Origem     = $Caminho
        Arquivos   = $itens.Count
        MB         = [math]::Round($bytes / 1MB, 2)
        Observacao = $Observacao
    })
}

function Copiar-Pasta {
    param(
        [string] $Origem,
        [string] $SubDestino,
        [string[]] $Incluir = @(),      # vazio = tudo
        [string[]] $Excluir = @()
    )
    if (-not (Test-Path -LiteralPath $Origem)) {
        Write-Nota "ausente: $Origem" 'DarkGray'
        return $false
    }

    $alvo = Join-Path $Destino $SubDestino
    New-Item -ItemType Directory -Path $alvo -Force | Out-Null

    $arquivos = @(Get-ChildItem -LiteralPath $Origem -Recurse -File -Force -ErrorAction SilentlyContinue)
    if ($Incluir.Count -gt 0) {
        $arquivos = @($arquivos | Where-Object {
            $ext = $_.Extension.TrimStart('.').ToLower()
            $Incluir -contains $ext
        })
    }
    if ($Excluir.Count -gt 0) {
        $arquivos = @($arquivos | Where-Object {
            $ext = $_.Extension.TrimStart('.').ToLower()
            $Excluir -notcontains $ext
        })
    }

    $n = 0
    foreach ($a in $arquivos) {
        $rel = $a.FullName.Substring($Origem.Length).TrimStart('\')
        $dst = Join-Path $alvo $rel
        $dir = Split-Path -Parent $dst
        if (-not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
        try {
            Copy-Item -LiteralPath $a.FullName -Destination $dst -Force -ErrorAction Stop
            $n++
        } catch {
            Write-Nota "FALHOU $rel : $($_.Exception.Message)" 'Yellow'
        }
    }
    Write-Nota "$n arquivo(s) -> $SubDestino" 'Green'
    return $true
}

# Resolve pastas de versao (24.0, 25.0, ...) sob uma raiz
function Get-VersoesAdobe([string] $raiz) {
    if (-not (Test-Path -LiteralPath $raiz)) { return @() }
    Get-ChildItem -LiteralPath $raiz -Directory -Force -ErrorAction SilentlyContinue |
        Sort-Object Name
}

# ---------------------------------------------------------------- setup

New-Item -ItemType Directory -Path $Destino -Force | Out-Null
Write-Host ''
Write-Host "Backup Adobe -> $Destino" -ForegroundColor White

$APPDATA  = $env:APPDATA
$LOCALAPP = $env:LOCALAPPDATA
$DOCS     = [Environment]::GetFolderPath('MyDocuments')
$PF       = ${env:ProgramFiles}
$PF86     = ${env:ProgramFiles(x86)}

# ---------------------------------------------------------------- After Effects

Write-Etapa 'After Effects - preferencias, workspaces e atalhos (classe C)'
foreach ($v in (Get-VersoesAdobe (Join-Path $APPDATA 'Adobe\After Effects'))) {
    Copiar-Pasta -Origem $v.FullName -SubDestino "AfterEffects\prefs\$($v.Name)" | Out-Null
    Add-Inventario -Categoria "AE prefs $($v.Name)" -Caminho $v.FullName -Classe 'C' `
        -Observacao 'contem workspaces + estado de GPU/RAM; restaurar com backup'
}

Write-Etapa 'After Effects - scripts e ScriptUI Panels (classe A)'
foreach ($raiz in @($PF, $PF86)) {
    if (-not $raiz) { continue }
    $base = Join-Path $raiz 'Adobe'
    if (-not (Test-Path -LiteralPath $base)) { continue }
    Get-ChildItem -LiteralPath $base -Directory -Filter 'Adobe After Effects*' -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $ver = $_.Name -replace '^Adobe After Effects\s*', ''
        $s = Join-Path $_.FullName 'Support Files\Scripts'
        Copiar-Pasta -Origem $s -SubDestino "AfterEffects\Scripts\$ver" | Out-Null
        Add-Inventario -Categoria "AE scripts $ver" -Caminho $s -Classe 'A' `
            -Observacao 'jsx/jsxbin: portavel direto'
    }
}

Write-Etapa 'After Effects - presets de animacao .ffx (classe A)'
foreach ($d in (Get-ChildItem -LiteralPath (Join-Path $DOCS 'Adobe') -Directory -Filter 'After Effects*' -Force -ErrorAction SilentlyContinue)) {
    $p = Join-Path $d.FullName 'User Presets'
    Copiar-Pasta -Origem $p -SubDestino "AfterEffects\UserPresets\$($d.Name)" | Out-Null
    Add-Inventario -Categoria "AE user presets ($($d.Name))" -Caminho $p -Classe 'A'
}

Write-Etapa 'After Effects - plugins: SOMENTE INVENTARIO (classe B, nao copiados)'
$pastasPlugin = @()
foreach ($raiz in @($PF, $PF86)) {
    if (-not $raiz) { continue }
    $base = Join-Path $raiz 'Adobe'
    if (-not (Test-Path -LiteralPath $base)) { continue }
    Get-ChildItem -LiteralPath $base -Directory -Filter 'Adobe After Effects*' -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $pastasPlugin += (Join-Path $_.FullName 'Support Files\Plug-ins')
    }
    $comum = Join-Path $base 'Common\Plug-ins'
    foreach ($v in (Get-VersoesAdobe $comum)) {
        $pastasPlugin += (Join-Path $v.FullName 'MediaCore')
    }
}

$listaPlugins = [System.Collections.Generic.List[object]]::new()
foreach ($pp in ($pastasPlugin | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $pp)) { continue }
    Write-Nota "varrendo $pp"
    Get-ChildItem -LiteralPath $pp -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @('.aex', '.plugin', '.bundle', '.dll', '.aix') } |
        ForEach-Object {
            $listaPlugins.Add([pscustomobject]@{
                Nome      = $_.Name
                Extensao  = $_.Extension
                MB        = [math]::Round($_.Length / 1MB, 2)
                Modificado= $_.LastWriteTime.ToString('yyyy-MM-dd')
                Pasta     = $_.DirectoryName
            })
        }
    Add-Inventario -Categoria 'AE plug-ins' -Caminho $pp -Classe 'B' `
        -Observacao 'NAO copiado: binario Windows. Reinstalar versao Mac.'
}

Write-Etapa 'Extensoes CEP (paineis) - copiadas e inventariadas (classe B/C)'
$cepDirs = @(
    (Join-Path $APPDATA 'Adobe\CEP\extensions'),
    (Join-Path $PF86    'Common Files\Adobe\CEP\extensions'),
    (Join-Path $PF      'Common Files\Adobe\CEP\extensions')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

$listaCep = [System.Collections.Generic.List[object]]::new()
foreach ($c in $cepDirs) {
    Get-ChildItem -LiteralPath $c -Directory -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $manifesto = Join-Path $_.FullName 'CSXS\manifest.xml'
        $bundle = ''
        if (Test-Path -LiteralPath $manifesto) {
            try {
                $x = [xml](Get-Content -LiteralPath $manifesto -Raw -ErrorAction Stop)
                $bundle = $x.ExtensionManifest.ExtensionBundleName
                if (-not $bundle) { $bundle = $x.ExtensionManifest.ExtensionBundleId }
            } catch { $bundle = '(manifest ilegivel)' }
        }
        $listaCep.Add([pscustomobject]@{
            Pasta  = $_.Name
            Nome   = $bundle
            Local  = $c
        })
    }
    $rotulo = if ($c -like "$APPDATA*") { 'usuario' } else { 'sistema' }
    Copiar-Pasta -Origem $c -SubDestino "CEP\$rotulo" -Excluir @('exe','dll','node','aex') | Out-Null
    Add-Inventario -Categoria 'CEP extensions' -Caminho $c -Classe 'B' `
        -Observacao 'HTML/JS/JSX portavel; binarios embutidos nao'
}

# ---------------------------------------------------------------- Premiere Pro

Write-Etapa 'Premiere Pro - prefs, workspaces e atalhos (classe C)'
foreach ($v in (Get-VersoesAdobe (Join-Path $APPDATA 'Adobe\Premiere Pro'))) {
    Copiar-Pasta -Origem $v.FullName -SubDestino "PremierePro\prefs\$($v.Name)" | Out-Null
    Add-Inventario -Categoria "PPro prefs $($v.Name)" -Caminho $v.FullName -Classe 'C' `
        -Observacao 'inclui Profile-<usuario>\Win com layouts e .kys'
}

Write-Etapa 'Premiere Pro - presets de efeito (classe A)'
foreach ($d in (Get-ChildItem -LiteralPath (Join-Path $DOCS 'Adobe\Premiere Pro') -Directory -Force -ErrorAction SilentlyContinue)) {
    Copiar-Pasta -Origem $d.FullName -SubDestino "PremierePro\Documents\$($d.Name)" -Incluir @('prfpset','epr','xml','kys') | Out-Null
    Add-Inventario -Categoria "PPro documents $($d.Name)" -Caminho $d.FullName -Classe 'A'
}

Write-Etapa 'Motion Graphics Templates (.mogrt) (classe A)'
$mogrt = Join-Path $DOCS 'Adobe\Common\Motion Graphics Templates'
Copiar-Pasta -Origem $mogrt -SubDestino 'Comum\MotionGraphicsTemplates' | Out-Null
Add-Inventario -Categoria 'MOGRT' -Caminho $mogrt -Classe 'A'

Write-Etapa 'Media Encoder - presets .epr (classe A)'
foreach ($v in (Get-VersoesAdobe (Join-Path $DOCS 'Adobe\Adobe Media Encoder'))) {
    $p = Join-Path $v.FullName 'Presets'
    Copiar-Pasta -Origem $p -SubDestino "MediaEncoder\$($v.Name)" | Out-Null
    Add-Inventario -Categoria "AME presets $($v.Name)" -Caminho $p -Classe 'A'
}

Write-Etapa 'LUTs e Looks do Lumetri (classe A)'
foreach ($raiz in @($PF, $PF86)) {
    if (-not $raiz) { continue }
    foreach ($v in (Get-VersoesAdobe (Join-Path $raiz 'Adobe\Common\Plug-ins'))) {
        $lut = Join-Path $v.FullName 'MediaCore\Lumetri\LUTs\Creative'
        Copiar-Pasta -Origem $lut -SubDestino "Comum\LUTs\$($v.Name)" | Out-Null
        Add-Inventario -Categoria "LUTs $($v.Name)" -Caminho $lut -Classe 'A'
    }
}

# ---------------------------------------------------------------- fontes

if ($SemFontes) {
    Write-Etapa 'Fontes - IGNORADAS (-SemFontes)'
} else {
    Write-Etapa 'Fontes do usuario (classe A)'
    $fu = Join-Path $LOCALAPP 'Microsoft\Windows\Fonts'
    Copiar-Pasta -Origem $fu -SubDestino 'Fontes\usuario' -Incluir @('otf','ttf') | Out-Null
    Add-Inventario -Categoria 'Fontes usuario' -Caminho $fu -Classe 'A'

    Write-Etapa 'Fontes do sistema - somente lista (muitas sao da Microsoft)'
    Add-Inventario -Categoria 'Fontes sistema' -Caminho "$env:WINDIR\Fonts" -Classe 'A' `
        -Observacao 'nao copiadas: copie manualmente as suas, nao as da Microsoft'
    Get-ChildItem -LiteralPath "$env:WINDIR\Fonts" -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @('.otf', '.ttf') } |
        Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,2)}} |
        Export-Csv -Path (Join-Path $Destino 'fontes-sistema.csv') -NoTypeInformation -Encoding UTF8
}

# ---------------------------------------------------------------- projetos

Write-Etapa 'Localizando projetos .aep / .prproj (somente lista, nao copia)'
$unidades = Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue |
            Where-Object { $_.Used -gt 0 }
$projetos = [System.Collections.Generic.List[object]]::new()
foreach ($u in $unidades) {
    Write-Nota "varrendo $($u.Root) (pode demorar)"
    Get-ChildItem -LiteralPath $u.Root -Recurse -File -Force -ErrorAction SilentlyContinue -Include '*.aep','*.prproj','*.aet' |
        ForEach-Object {
            $projetos.Add([pscustomobject]@{
                Nome       = $_.Name
                MB         = [math]::Round($_.Length / 1MB, 2)
                Modificado = $_.LastWriteTime.ToString('yyyy-MM-dd')
                Caminho    = $_.FullName
            })
        }
}

# ---------------------------------------------------------------- saida

Write-Etapa 'Gravando manifestos'

$listaPlugins | Sort-Object Nome | Export-Csv (Join-Path $Destino 'PLUGINS-ENCONTRADOS.csv') -NoTypeInformation -Encoding UTF8
$listaCep     | Sort-Object Nome | Export-Csv (Join-Path $Destino 'EXTENSOES-CEP.csv')       -NoTypeInformation -Encoding UTF8
$projetos     | Sort-Object Modificado -Descending | Export-Csv (Join-Path $Destino 'PROJETOS.csv') -NoTypeInformation -Encoding UTF8
$script:Inventario | Export-Csv (Join-Path $Destino 'INVENTARIO.csv') -NoTypeInformation -Encoding UTF8

[pscustomobject]@{
    GeradoEm     = (Get-Date).ToString('s')
    Maquina      = $env:COMPUTERNAME
    Usuario      = $env:USERNAME
    Windows      = (Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue).Caption
    Destino      = $Destino
    Inventario   = $script:Inventario
    Plugins      = $listaPlugins
    ExtensoesCEP = $listaCep
    TotalProjetos= $projetos.Count
} | ConvertTo-Json -Depth 6 | Set-Content -Path (Join-Path $Destino 'manifesto.json') -Encoding UTF8

$script:Log | Set-Content -Path (Join-Path $Destino 'log.txt') -Encoding UTF8

$totalMB = [math]::Round(((Get-ChildItem -LiteralPath $Destino -Recurse -File -Force -ErrorAction SilentlyContinue |
            Measure-Object Length -Sum).Sum / 1MB), 2)

Write-Host ''
Write-Host '--------------------------------------------------' -ForegroundColor White
Write-Host " Backup pronto: $Destino" -ForegroundColor Green
Write-Host " Tamanho: $totalMB MB" -ForegroundColor Green
Write-Host " Plugins encontrados (reinstalar no Mac): $($listaPlugins.Count)" -ForegroundColor Yellow
Write-Host " Extensoes CEP: $($listaCep.Count)" -ForegroundColor Yellow
Write-Host " Projetos localizados: $($projetos.Count)" -ForegroundColor Yellow
Write-Host '--------------------------------------------------' -ForegroundColor White
Write-Host ''
Write-Host 'Proximo passo: leve a pasta inteira para o Mac e rode 02-restaurar-mac.sh'
Write-Host 'Leia PLUGINS-ENCONTRADOS.csv: e a sua lista de reinstalacao.'
