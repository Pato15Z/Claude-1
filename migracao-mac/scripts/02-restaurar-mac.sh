#!/usr/bin/env bash
#
# 02-restaurar-mac.sh - restaura no Mac o backup gerado por 01-inventario-windows.ps1
#                       (ou por 01-inventario-mac.sh).
#
# USO:
#   chmod +x 02-restaurar-mac.sh
#   ./02-restaurar-mac.sh --origem ~/Downloads/BackupAdobe            # dry-run (nao escreve)
#   ./02-restaurar-mac.sh --origem ~/Downloads/BackupAdobe --apply    # aplica classe A
#   ./02-restaurar-mac.sh --origem ~/Downloads/BackupAdobe --apply --prefs
#                                                                     # tambem tenta prefs (risco)
#
# PRE-REQUISITO NAO NEGOCIAVEL: abra e feche o After Effects e o Premiere Pro uma vez
# antes de rodar com --apply. O primeiro boot cria a arvore de preferencias; restaurar
# antes disso faz o app sobrescrever o que voce acabou de copiar.
#
# Classe A (sempre): scripts, presets, mogrt, epr, luts, fontes.
# Classe C (--prefs): preferencias e workspaces. Opt-in porque carrega estado de GPU/RAM
#                     do PC antigo. Tudo que for sobrescrito vai para uma pasta de backup
#                     com timestamp, e o caminho dela e impresso no fim.

set -uo pipefail

ORIGEM=""
APLICAR=0
PREFS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --origem) ORIGEM="${2:-}"; shift 2 ;;
    --apply)  APLICAR=1; shift ;;
    --prefs)  PREFS=1; shift ;;
    --dry-run) APLICAR=0; shift ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$ORIGEM" || ! -d "$ORIGEM" ]]; then
  echo "ERRO: passe --origem <pasta do backup>" >&2
  exit 2
fi

ORIGEM="$(cd "$ORIGEM" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$HOME/BackupAdobe-pre-restauracao-$STAMP"
RELATORIO="$HOME/relatorio-restauracao-$STAMP.txt"

C_AZUL=$'\033[36m'; C_VERDE=$'\033[32m'; C_AMAR=$'\033[33m'; C_CINZA=$'\033[90m'; C_OFF=$'\033[0m'

copiados=0; pulados=0; conflitos=0

log() { printf '%s\n' "$*" >> "$RELATORIO"; }

etapa() {
  printf '\n%s== %s%s\n' "$C_AZUL" "$*" "$C_OFF"
  log ""; log "== $*"
}

nota() {
  printf '   %s\n' "$*"
  log "   $*"
}

# ---------------------------------------------------------------- descoberta

# Versoes do AE instaladas: /Applications/Adobe After Effects 2025/...
ae_apps=()
while IFS= read -r d; do [[ -n "$d" ]] && ae_apps+=("$d"); done < <(
  find /Applications -maxdepth 1 -type d -name 'Adobe After Effects*' 2>/dev/null | sort
)

# Versoes com pasta de prefs: ~/Library/Preferences/Adobe/After Effects/<v>
ae_vers=()
if [[ -d "$HOME/Library/Preferences/Adobe/After Effects" ]]; then
  while IFS= read -r d; do [[ -n "$d" ]] && ae_vers+=("$(basename "$d")"); done < <(
    find "$HOME/Library/Preferences/Adobe/After Effects" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort
  )
fi

ppro_vers=()
if [[ -d "$HOME/Library/Preferences/Adobe/Premiere Pro" ]]; then
  while IFS= read -r d; do [[ -n "$d" ]] && ppro_vers+=("$(basename "$d")"); done < <(
    find "$HOME/Library/Preferences/Adobe/Premiere Pro" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort
  )
fi

echo "Origem   : $ORIGEM"
echo "Modo     : $([[ $APLICAR -eq 1 ]] && echo 'APLICAR' || echo 'DRY-RUN (nada sera escrito)')"
echo "Prefs    : $([[ $PREFS -eq 1 ]] && echo 'sim (classe C incluida)' || echo 'nao (somente classe A)')"
echo "Relatorio: $RELATORIO"
log "origem=$ORIGEM aplicar=$APLICAR prefs=$PREFS"

if [[ ${#ae_apps[@]} -eq 0 ]]; then
  printf '%s   aviso: nenhum After Effects encontrado em /Applications%s\n' "$C_AMAR" "$C_OFF"
fi
if [[ ${#ae_vers[@]} -eq 0 && ${#ppro_vers[@]} -eq 0 ]]; then
  printf '%s   aviso: nenhuma pasta de preferencias Adobe encontrada.%s\n' "$C_AMAR" "$C_OFF"
  printf '%s   Abra e feche o AE e o Premiere uma vez, e rode de novo.%s\n' "$C_AMAR" "$C_OFF"
fi

# ---------------------------------------------------------------- motor de copia

# copiar <pasta-origem> <pasta-destino> [precisa_sudo]
copiar() {
  local src="$1" dst="$2" sudoreq="${3:-0}"

  if [[ ! -d "$src" ]]; then
    nota "${C_CINZA}ausente na origem: ${src#$ORIGEM/}${C_OFF}"
    return 0
  fi

  local n
  n=$(find "$src" -type f ! -name '.DS_Store' 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$n" == "0" ]]; then
    nota "${C_CINZA}vazio: ${src#$ORIGEM/}${C_OFF}"
    return 0
  fi

  if [[ $APLICAR -eq 0 ]]; then
    nota "[dry-run] $n arquivo(s): ${src#$ORIGEM/}  ->  $dst"
    pulados=$((pulados + n))
    return 0
  fi

  # backup do que ja existe no destino, antes de sobrescrever
  if [[ -d "$dst" ]] && find "$dst" -type f -print -quit 2>/dev/null | grep -q .; then
    local rel="${dst#$HOME/}"
    mkdir -p "$BACKUP_DIR/$(dirname "$rel")" 2>/dev/null
    if cp -R "$dst" "$BACKUP_DIR/$rel" 2>/dev/null; then
      nota "backup do destino atual -> $BACKUP_DIR/$rel"
      conflitos=$((conflitos + 1))
    fi
  fi

  local cmd=(cp -R)
  if [[ "$sudoreq" == "1" ]]; then
    sudo mkdir -p "$dst" 2>/dev/null || { nota "${C_AMAR}sem permissao: $dst (rode com sudo)${C_OFF}"; return 0; }
    if ! sudo cp -R "$src"/. "$dst"/ 2>/dev/null; then
      nota "${C_AMAR}falhou (permissao): $dst${C_OFF}"
      return 0
    fi
  else
    mkdir -p "$dst" || { nota "${C_AMAR}nao criou: $dst${C_OFF}"; return 0; }
    if ! "${cmd[@]}" "$src"/. "$dst"/ 2>/dev/null; then
      nota "${C_AMAR}falhou: $dst${C_OFF}"
      return 0
    fi
  fi

  printf '   %s%s arquivo(s) -> %s%s\n' "$C_VERDE" "$n" "$dst" "$C_OFF"
  log "   OK $n -> $dst"
  copiados=$((copiados + n))
}

# ---------------------------------------------------------------- classe A

etapa 'After Effects: scripts e ScriptUI Panels'
if [[ -d "$ORIGEM/AfterEffects/Scripts" ]]; then
  for app in "${ae_apps[@]}"; do
    # usa o conteudo de todas as versoes de origem, achatado
    for srcver in "$ORIGEM/AfterEffects/Scripts"/*; do
      [[ -d "$srcver" ]] || continue
      copiar "$srcver" "$app/Scripts" 1
    done
  done
  [[ ${#ae_apps[@]} -eq 0 ]] && nota "${C_AMAR}nenhum AE instalado: scripts ficam em $ORIGEM/AfterEffects/Scripts${C_OFF}"
fi

etapa 'After Effects: presets de animacao (.ffx)'
for srcver in "$ORIGEM/AfterEffects/UserPresets"/*; do
  [[ -d "$srcver" ]] || continue
  nome="$(basename "$srcver")"
  copiar "$srcver" "$HOME/Documents/Adobe/$nome/User Presets"
done

etapa 'Premiere Pro: presets de efeito, .kys e afins'
for srcver in "$ORIGEM/PremierePro/Documents"/*; do
  [[ -d "$srcver" ]] || continue
  nome="$(basename "$srcver")"
  copiar "$srcver" "$HOME/Documents/Adobe/Premiere Pro/$nome"
done

etapa 'Motion Graphics Templates (.mogrt)'
copiar "$ORIGEM/Comum/MotionGraphicsTemplates" "$HOME/Documents/Adobe/Common/Motion Graphics Templates"

etapa 'Media Encoder: presets (.epr)'
for srcver in "$ORIGEM/MediaEncoder"/*; do
  [[ -d "$srcver" ]] || continue
  nome="$(basename "$srcver")"
  copiar "$srcver" "$HOME/Documents/Adobe/Adobe Media Encoder/$nome/Presets"
done

etapa 'LUTs / Looks do Lumetri'
for srcver in "$ORIGEM/Comum/LUTs"/*; do
  [[ -d "$srcver" ]] || continue
  nome="$(basename "$srcver")"
  copiar "$srcver" "/Library/Application Support/Adobe/Common/Plug-ins/$nome/MediaCore/Lumetri/LUTs/Creative" 1
done

etapa 'Fontes do usuario'
copiar "$ORIGEM/Fontes/usuario" "$HOME/Library/Fonts"

etapa 'Extensoes CEP (paineis)'
CEP_DST="$HOME/Library/Application Support/Adobe/CEP/extensions"
if [[ -d "$ORIGEM/CEP" ]]; then
  # a origem pode ter a extensao direto (contem CSXS/manifest.xml) ou dentro de um
  # container por local de instalacao (user/system). O nome da pasta da extensao
  # e o ID que o Adobe carrega, entao preservar esse nome nao e opcional.
  for srcdir in "$ORIGEM/CEP"/*; do
    [[ -d "$srcdir" ]] || continue
    if [[ -f "$srcdir/CSXS/manifest.xml" ]]; then
      copiar "$srcdir" "$CEP_DST/$(basename "$srcdir")"
    else
      for ext in "$srcdir"/*; do
        [[ -d "$ext" ]] || continue
        copiar "$ext" "$CEP_DST/$(basename "$ext")"
      done
    fi
  done
  nota "${C_AMAR}paineis com binario embutido (.node/.aex) nao funcionam: reinstale o .zxp${C_OFF}"
  nota "para paineis nao assinados, habilite PlayerDebugMode:"
  nota "  defaults write com.adobe.CSXS.11 PlayerDebugMode 1   # ajuste o numero da versao CSXS"
fi

# ---------------------------------------------------------------- classe C

if [[ $PREFS -eq 1 ]]; then
  etapa 'PREFERENCIAS E WORKSPACES (classe C - risco calculado)'
  nota "${C_AMAR}estes arquivos carregam estado de GPU/RAM/cache do PC antigo${C_OFF}"
  nota "${C_AMAR}se o AE abrir estranho, apague a pasta de prefs e restaure de $BACKUP_DIR${C_OFF}"

  for srcver in "$ORIGEM/AfterEffects/prefs"/*; do
    [[ -d "$srcver" ]] || continue
    nome="$(basename "$srcver")"
    destino="$HOME/Library/Preferences/Adobe/After Effects/$nome"
    if [[ ! -d "$destino" ]] && [[ ${#ae_vers[@]} -gt 0 ]]; then
      destino="$HOME/Library/Preferences/Adobe/After Effects/${ae_vers[$((${#ae_vers[@]}-1))]}"
      nota "versao $nome nao existe aqui; redirecionando para ${ae_vers[$((${#ae_vers[@]}-1))]}"
    fi
    copiar "$srcver" "$destino"
  done

  for srcver in "$ORIGEM/PremierePro/prefs"/*; do
    [[ -d "$srcver" ]] || continue
    nome="$(basename "$srcver")"
    destino="$HOME/Library/Preferences/Adobe/Premiere Pro/$nome"
    if [[ ! -d "$destino" ]] && [[ ${#ppro_vers[@]} -gt 0 ]]; then
      destino="$HOME/Library/Preferences/Adobe/Premiere Pro/${ppro_vers[$((${#ppro_vers[@]}-1))]}"
      nota "versao $nome nao existe aqui; redirecionando para ${ppro_vers[$((${#ppro_vers[@]}-1))]}"
    fi
    copiar "$srcver" "$destino"

    # Profile-<usuario-windows> precisa virar Profile-<usuario-mac>
    if [[ $APLICAR -eq 1 ]]; then
      for perfil in "$destino"/Profile-*; do
        [[ -d "$perfil" ]] || continue
        esperado="$destino/Profile-$(whoami)"
        if [[ "$perfil" != "$esperado" ]]; then
          if [[ ! -d "$esperado" ]]; then
            mv "$perfil" "$esperado" 2>/dev/null && nota "perfil renomeado: $(basename "$perfil") -> Profile-$(whoami)"
          else
            cp -R "$perfil"/. "$esperado"/ 2>/dev/null && nota "perfil mesclado em Profile-$(whoami)"
          fi
        fi
        # layouts do Windows ficam em Win/, o Mac le Mac/
        if [[ -d "$esperado/Win" ]]; then
          mkdir -p "$esperado/Mac"
          cp -R "$esperado/Win"/. "$esperado/Mac"/ 2>/dev/null \
            && nota "layouts Win/ copiados para Mac/ (teste; reverta se o Premiere nao abrir)"
        fi
      done
    fi
  done
else
  etapa 'PREFERENCIAS E WORKSPACES: nao restaurados'
  nota "rode de novo com --prefs se quiser tentar (ha backup automatico)"
  nota "alternativa de menor risco: recriar os workspaces a mao, uma vez"
fi

# ---------------------------------------------------------------- fecho

etapa 'Resumo'
if [[ $APLICAR -eq 0 ]]; then
  printf '   %s%s arquivo(s) seriam copiados. Nada foi escrito.%s\n' "$C_AMAR" "$pulados" "$C_OFF"
  printf '   Rode de novo com --apply para aplicar.\n'
else
  printf '   %s%s arquivo(s) copiados.%s\n' "$C_VERDE" "$copiados" "$C_OFF"
  if [[ $conflitos -gt 0 ]]; then
    printf '   %s%s destino(s) tinham conteudo: backup em %s%s\n' "$C_AMAR" "$conflitos" "$BACKUP_DIR" "$C_OFF"
  fi
fi
printf '   Relatorio: %s\n\n' "$RELATORIO"

cat <<'FIM'
Pendencias que nenhum script resolve:
  1. Plugins: reinstale a versao macOS de cada item em PLUGINS-ENCONTRADOS.csv.
     Em Apple Silicon, confira se cada plugin tem build nativo (arm64).
  2. Atalhos do After Effects: refaca a mao. O arquivo e nomeado por plataforma e
     os modificadores Ctrl/Cmd nao se traduzem.
  3. Cache de disco e alocacao de RAM: reconfigure em Preferences > Media & Disk Cache,
     porque os valores herdados apontam para discos que nao existem aqui.
  4. Fontes: abra um projeto antigo e confirme que nenhuma foi substituida.
FIM
