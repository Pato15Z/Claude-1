# Mapa de caminhos: Windows ↔ macOS

`<v>` = número da versão (ex. `24.0`, `25.0`, `26.0`). `<u>` = nome do usuário.
Os scripts descobrem `<v>` e `<u>` por glob; a tabela existe para você conferir e
intervir manualmente quando quiser.

## After Effects

| O que é | Windows | macOS | Classe |
|---|---|---|---|
| Prefs + workspaces | `%APPDATA%\Adobe\After Effects\<v>\` | `~/Library/Preferences/Adobe/After Effects/<v>/` | C |
| Atalhos de teclado | `...\<v>\Adobe After Effects <v> Win Shortcuts.txt` | `.../<v>/Adobe After Effects <v> Mac Shortcuts.txt` | C |
| Scripts | `C:\Program Files\Adobe\Adobe After Effects <v>\Support Files\Scripts\` | `/Applications/Adobe After Effects <v>/Scripts/` | A |
| Painéis de script | `...\Support Files\Scripts\ScriptUI Panels\` | `/Applications/Adobe After Effects <v>/Scripts/ScriptUI Panels/` | A |
| Presets de animação | `%USERPROFILE%\Documents\Adobe\After Effects <v>\User Presets\` | `~/Documents/Adobe/After Effects <v>/User Presets/` | A |
| Plugins (do app) | `...\Support Files\Plug-ins\` | `/Applications/Adobe After Effects <v>/Plug-ins/` | **B** |
| Plugins (comuns) | `C:\Program Files\Adobe\Common\Plug-ins\<v>\MediaCore\` | `/Library/Application Support/Adobe/Common/Plug-ins/<v>/MediaCore/` | **B** |
| Extensões CEP (usuário) | `%APPDATA%\Adobe\CEP\extensions\` | `~/Library/Application Support/Adobe/CEP/extensions/` | B/C |
| Extensões CEP (sistema) | `C:\Program Files (x86)\Common Files\Adobe\CEP\extensions\` | `/Library/Application Support/Adobe/CEP/extensions/` | B/C |
| Expressões salvas | dentro dos `.aep` / dos presets | idem | A |

Nota sobre atalhos do AE: o nome do arquivo contém a plataforma. Renomear `Win Shortcuts`
para `Mac Shortcuts` faz o AE ler o arquivo, mas os códigos de modificador não são
reinterpretados — `Ctrl` não vira `Cmd`. Resultado provável: parte dos atalhos funciona,
parte conflita com atalhos do sistema. Reconstruir à mão custa menos que depurar isso.

## Premiere Pro

| O que é | Windows | macOS | Classe |
|---|---|---|---|
| Prefs | `%APPDATA%\Adobe\Premiere Pro\<v>\` | `~/Library/Preferences/Adobe/Premiere Pro/<v>/` | C |
| Workspaces / layouts | `...\<v>\Profile-<u>\Win\` | `.../<v>/Profile-<u>/Mac/` | C |
| Atalhos `.kys` | `...\<v>\Profile-<u>\Win\*.kys` | `.../<v>/Profile-<u>/Mac/*.kys` | C |
| Presets de efeito | `%USERPROFILE%\Documents\Adobe\Premiere Pro\<v>\Profile-<u>\Effect Presets\` | `~/Documents/Adobe/Premiere Pro/<v>/Profile-<u>/Effect Presets/` | A |
| MOGRT (Essential Graphics) | `%USERPROFILE%\Documents\Adobe\Common\Motion Graphics Templates\` | `~/Documents/Adobe/Common/Motion Graphics Templates/` | A |
| LUTs / Looks do Lumetri | `C:\Program Files\Adobe\Common\Plug-ins\<v>\MediaCore\Lumetri\LUTs\Creative\` | `/Library/Application Support/Adobe/Common/Plug-ins/<v>/MediaCore/Lumetri/LUTs/Creative/` | A |
| Extensões CEP | igual ao AE | igual ao AE | B/C |

A pasta `Profile-<u>` é a razão pela qual copiar literalmente falha: no Mac o seu nome de
usuário é outro. Os scripts resolvem isso lendo o nome real do destino.

## Media Encoder e transversais

| O que é | Windows | macOS | Classe |
|---|---|---|---|
| Presets de exportação `.epr` | `%USERPROFILE%\Documents\Adobe\Adobe Media Encoder\<v>\Presets\` | `~/Documents/Adobe/Adobe Media Encoder/<v>/Presets/` | A |
| Fontes instaladas | `C:\Windows\Fonts\`, `%LOCALAPPDATA%\Microsoft\Windows\Fonts\` | `~/Library/Fonts/` | A |
| Adobe Fonts (ativadas via CC) | sincroniza pela conta | sincroniza pela conta | — |
| CC Libraries | sincroniza pela conta | sincroniza pela conta | — |

As duas últimas linhas são o motivo de não se mexer em fontes Adobe nem em bibliotecas CC:
elas chegam sozinhas no login. Mexer manualmente só cria duplicata.

## Fontes: a armadilha

Fontes `.otf`/`.ttf` copiam e funcionam. Fontes `.fon` e `.ttc` legadas do Windows não.
Mais relevante: se um `.aep` referencia uma fonte por nome exato e a versão no Mac diferir
(mesmo nome, foundry diferente), o AE substitui silenciosamente e o layout de texto muda.
Verificar cada projeto crítico depois de migrar é mais barato que descobrir no render.

---

Caminho errado não dá erro, dá ausência: o app ignora o arquivo e você culpa o plugin.
