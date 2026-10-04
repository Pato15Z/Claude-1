#!/usr/bin/env bash
#
# 01-inventario-mac.sh - mesma funcao do 01-inventario-windows.ps1, quando a maquina
#                        de ORIGEM tambem e um Mac (migracao Mac -> Mac).
#
# USO:
#   chmod +x 01-inventario-mac.sh
#   ./01-inventario-mac.sh                       # grava em ~/Desktop/BackupAdobe
#   ./01-inventario-mac.sh --destino /Volumes/HD/BackupAdobe
#
# Mac -> Mac e o caso facil: os plugins .plugin SAO portaveis entre Macs da mesma
# arquitetura, e as prefs migram sem o problema de caminho Windows. Ainda assim o
# script LISTA os plugins em vez de copiar, porque licenca presa a machine ID so
# reativa pelo instalador do fabricante.

set -uo pipefail

DEST="$HOME/Desktop/BackupAdobe"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --destino) DEST="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$DEST"
INV="$DEST/INVENTARIO.csv"
PLG="$DEST/PLUGINS-ENCONTRADOS.csv"
CEP_CSV="$DEST/EXTENSOES-CEP.csv"
PRJ="$DEST/PROJETOS.csv"

echo 'Categoria,Classe,Origem,Arquivos,MB' > "$INV"
echo 'Nome,Tipo,MB,Modificado,Pasta' > "$PLG"
echo 'Pasta,Nome,Local' > "$CEP_CSV"
echo 'Nome,MB,Modificado,Caminho' > "$PRJ"

csv() { printf '%s' "$1" | sed 's/"/""/g; s/^/"/; s/$/"/'; }

contar() { find "$1" -type f ! -name '.DS_Store' 2>/dev/null | wc -l | tr -d ' '; }
tamanho_mb() {
  local b
  b=$(find "$1" -type f -print0 2>/dev/null | xargs -0 stat -f '%z' 2>/dev/null | awk '{s+=$1} END {print s+0}')
  awk -v b="${b:-0}" 'BEGIN {printf "%.2f", b/1048576}'
}

inventariar() { # categoria classe caminho
  [[ -d "$3" ]] || return 0
  printf '%s,%s,%s,%s,%s\n' "$(csv "$1")" "$2" "$(csv "$3")" "$(contar "$3")" "$(tamanho_mb "$3")" >> "$INV"
}

copiar() { # origem sub-destino [glob de inclusao]
  local src="$1" sub="$2" inc="${3:-}"
  [[ -d "$src" ]] || { echo "   ausente: $src"; return 0; }
  local dst="$DEST/$sub"
  mkdir -p "$dst"
  local n=0
  if [[ -n "$inc" ]]; then
    while IFS= read -r f; do
      local rel="${f#$src/}"
      mkdir -p "$dst/$(dirname "$rel")"
      cp "$f" "$dst/$rel" 2>/dev/null && n=$((n+1))
    done < <(find "$src" -type f \( $inc \) 2>/dev/null)
  else
    cp -R "$src"/. "$dst"/ 2>/dev/null && n=$(contar "$dst")
  fi
  echo "   $n arquivo(s) -> $sub"
}

echo "Backup Adobe -> $DEST"

echo; echo "== After Effects: prefs e workspaces (classe C)"
for d in "$HOME/Library/Preferences/Adobe/After Effects"/*; do
  [[ -d "$d" ]] || continue
  v="$(basename "$d")"
  copiar "$d" "AfterEffects/prefs/$v"
  inventariar "AE prefs $v" C "$d"
done

echo; echo "== After Effects: scripts (classe A)"
for app in /Applications/Adobe\ After\ Effects*; do
  [[ -d "$app" ]] || continue
  v="${app##*After Effects }"
  copiar "$app/Scripts" "AfterEffects/Scripts/$v"
  inventariar "AE scripts $v" A "$app/Scripts"
done

echo; echo "== After Effects: presets .ffx (classe A)"
for d in "$HOME/Documents/Adobe/After Effects"*; do
  [[ -d "$d/User Presets" ]] || continue
  copiar "$d/User Presets" "AfterEffects/UserPresets/$(basename "$d")"
  inventariar "AE user presets $(basename "$d")" A "$d/User Presets"
done

echo; echo "== After Effects: plugins (classe B - SOMENTE LISTADOS)"
plugin_dirs=()
for app in /Applications/Adobe\ After\ Effects*; do
  [[ -d "$app/Plug-ins" ]] && plugin_dirs+=("$app/Plug-ins")
done
for d in "/Library/Application Support/Adobe/Common/Plug-ins"/*; do
  [[ -d "$d/MediaCore" ]] && plugin_dirs+=("$d/MediaCore")
done
for pd in "${plugin_dirs[@]:-}"; do
  [[ -n "${pd:-}" && -d "$pd" ]] || continue
  echo "   varrendo $pd"
  while IFS= read -r f; do
    mb=$(awk -v b="$(stat -f '%z' "$f" 2>/dev/null || echo 0)" 'BEGIN{printf "%.2f", b/1048576}')
    mod=$(stat -f '%Sm' -t '%Y-%m-%d' "$f" 2>/dev/null)
    printf '%s,%s,%s,%s,%s\n' "$(csv "$(basename "$f")")" "${f##*.}" "$mb" "$mod" "$(csv "$(dirname "$f")")" >> "$PLG"
  done < <(find "$pd" -maxdepth 2 \( -name '*.plugin' -o -name '*.bundle' -o -name '*.aex' -o -name '*.aix' \) 2>/dev/null)
  inventariar 'AE plug-ins' B "$pd"
done

echo; echo "== Extensoes CEP (classe B/C)"
for c in "$HOME/Library/Application Support/Adobe/CEP/extensions" "/Library/Application Support/Adobe/CEP/extensions"; do
  [[ -d "$c" ]] || continue
  rotulo=usuario; [[ "$c" == /Library* ]] && rotulo=sistema
  for e in "$c"/*; do
    [[ -d "$e" ]] || continue
    nome=''
    if [[ -f "$e/CSXS/manifest.xml" ]]; then
      nome=$(sed -n 's/.*ExtensionBundleName="\([^"]*\)".*/\1/p' "$e/CSXS/manifest.xml" | head -1)
    fi
    printf '%s,%s,%s\n' "$(csv "$(basename "$e")")" "$(csv "$nome")" "$(csv "$c")" >> "$CEP_CSV"
  done
  copiar "$c" "CEP/$rotulo"
  inventariar 'CEP extensions' B "$c"
done

echo; echo "== Premiere Pro: prefs, workspaces, .kys (classe C)"
for d in "$HOME/Library/Preferences/Adobe/Premiere Pro"/*; do
  [[ -d "$d" ]] || continue
  v="$(basename "$d")"
  copiar "$d" "PremierePro/prefs/$v"
  inventariar "PPro prefs $v" C "$d"
done

echo; echo "== Premiere Pro: presets de efeito (classe A)"
for d in "$HOME/Documents/Adobe/Premiere Pro"/*; do
  [[ -d "$d" ]] || continue
  copiar "$d" "PremierePro/Documents/$(basename "$d")" "-name *.prfpset -o -name *.epr -o -name *.kys -o -name *.xml"
  inventariar "PPro documents $(basename "$d")" A "$d"
done

echo; echo "== Motion Graphics Templates (classe A)"
copiar "$HOME/Documents/Adobe/Common/Motion Graphics Templates" "Comum/MotionGraphicsTemplates"
inventariar 'MOGRT' A "$HOME/Documents/Adobe/Common/Motion Graphics Templates"

echo; echo "== Media Encoder: presets (classe A)"
for d in "$HOME/Documents/Adobe/Adobe Media Encoder"/*; do
  [[ -d "$d/Presets" ]] || continue
  copiar "$d/Presets" "MediaEncoder/$(basename "$d")"
  inventariar "AME presets $(basename "$d")" A "$d/Presets"
done

echo; echo "== LUTs do Lumetri (classe A)"
for d in "/Library/Application Support/Adobe/Common/Plug-ins"/*; do
  lut="$d/MediaCore/Lumetri/LUTs/Creative"
  [[ -d "$lut" ]] || continue
  copiar "$lut" "Comum/LUTs/$(basename "$d")"
  inventariar "LUTs $(basename "$d")" A "$lut"
done

echo; echo "== Fontes do usuario (classe A)"
copiar "$HOME/Library/Fonts" "Fontes/usuario" "-name *.otf -o -name *.ttf"
inventariar 'Fontes usuario' A "$HOME/Library/Fonts"

echo; echo "== Projetos (somente lista)"
while IFS= read -r f; do
  mb=$(awk -v b="$(stat -f '%z' "$f" 2>/dev/null || echo 0)" 'BEGIN{printf "%.2f", b/1048576}')
  mod=$(stat -f '%Sm' -t '%Y-%m-%d' "$f" 2>/dev/null)
  printf '%s,%s,%s,%s\n' "$(csv "$(basename "$f")")" "$mb" "$mod" "$(csv "$f")" >> "$PRJ"
done < <(find "$HOME" /Volumes -type f \( -name '*.aep' -o -name '*.prproj' -o -name '*.aet' \) 2>/dev/null)

echo
echo "--------------------------------------------------"
echo " Backup pronto: $DEST"
echo " Plugins listados : $(( $(wc -l < "$PLG") - 1 ))"
echo " Extensoes CEP    : $(( $(wc -l < "$CEP_CSV") - 1 ))"
echo " Projetos         : $(( $(wc -l < "$PRJ") - 1 ))"
echo "--------------------------------------------------"
echo " Proximo passo: no Mac novo, rode 02-restaurar-mac.sh --origem \"$DEST\""
