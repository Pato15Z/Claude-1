# Migração Windows → Mac: After Effects + Premiere Pro

Kit executável para transferir **layouts, scripts, presets e configurações** do PC antigo
para o Mac novo, e inventário dos **plugins** para reinstalação manual.

---

## 1. Limitação estrutural desta sessão (leia antes de tudo)

Esta sessão do Claude roda num container Linux isolado na nuvem. Ela **não tem acesso ao
disco do PC antigo nem ao Mac**. Verificado: nenhum volume externo montado, zero arquivos
Adobe no filesystem (`find / -iname "*.aep" -o -iname "*.jsx"` → vazio).

Consequência: a varredura dos seus arquivos **tem que rodar na máquina que os contém**.
O que esta sessão produziu são os scripts que fazem isso, mais o que foi possível extrair
remotamente do Gmail e do Google Drive.

Divisão de trabalho:

| Etapa | Onde roda | Arquivo |
|---|---|---|
| 1. Inventariar + empacotar | PC antigo (Windows) | `scripts/01-inventario-windows.ps1` |
| 1b. Idem, se a origem for Mac | Mac antigo | `scripts/01-inventario-mac.sh` |
| 2. Transferir | Drive / HD externo | — |
| 3. Restaurar | Mac novo | `scripts/02-restaurar-mac.sh` |
| 4. Reinstalar plugins | Mac novo, manual | `PLUGINS.md` |

O Claude Code no Mac consegue conduzir a etapa 3: cole `PROMPT-MAC.md`.

---

## 2. O eixo que decide tudo: o que é portável e o que não é

Não existe "copiar o After do Windows para o Mac". Existem três classes de arquivo com
comportamentos diferentes, e tratar as três igual é a causa de quase toda migração quebrada.

**Classe A — texto/interpretado, portável sem perda.** Scripts `.jsx`/`.jsxbin`, presets de
efeito `.ffx` e `.prfpset`, MOGRTs `.mogrt`, presets do Media Encoder `.epr`, LUTs `.cube`,
expressões, fontes `.otf`/`.ttf`. São lidos pelo app, não executados pelo sistema
operacional. Copiar byte a byte funciona.

**Classe B — binário nativo, não portável.** Plugins `.aex` (Windows) versus bundles
`.plugin` (macOS); `.dll` auxiliares. São código de máquina compilado para outro SO e outra
arquitetura. Copiar não produz erro visível — o AE simplesmente ignora o arquivo e o efeito
não aparece na lista. Por isso plugin **sempre** significa reinstalar, nunca copiar. É exatamente
o que você pediu: lista, não transferência.

**Classe C — preferências com estado de hardware, portável com risco.** Os arquivos de prefs
do AE e do Premiere carregam, no mesmo blob dos seus layouts, caminhos absolutos
(`C:\...`), configuração de GPU, alocação de RAM, Multi-Frame Rendering e cache de disco.
O layout que você quer e o lixo que você não quer vivem juntos.

```
                    portabilidade
                         ^
       alta  |  .jsx .ffx .mogrt .epr .cube .prfpset      <- copie direto
             |
       média |  CEP extensions (HTML+JSX ok, binário não)
             |
       baixa |  prefs do AE/PPro (layouts + estado de HW)  <- copie, teste, reverta
             |
       zero  |  .aex / .dll / .plugin                      <- reinstale
             +------------------------------------------>
                   esforço de validação necessário
```

### Probabilidades calibradas (não são certezas)

| Afirmação | Confiança | Base |
|---|---|---|
| Scripts, `.ffx`, `.mogrt`, `.epr`, LUTs migram sem ajuste | 0.95 | formatos independentes de plataforma por design |
| Plugins `.aex` são inúteis no Mac | ~1.0 | binário PE do Windows |
| Workspaces do **Premiere** migram via pasta `Profile-<user>` | 0.70 | layouts ficam em arquivo separado, mas Adobe nunca documentou cross-platform |
| Prefs do **After** migram limpo Win→Mac | 0.35 | AE grava workspace dentro do blob de prefs junto com estado de GPU; Adobe não suporta |
| Atalhos de teclado do Premiere (`.kys`) migram | 0.55 | o arquivo é XML, mas modificadores Ctrl↔Cmd não se traduzem sozinhos |
| Atalhos do After migram | 0.20 | arquivo é nomeado por plataforma (`Win Shortcuts` vs `Mac Shortcuts`) |
| Sua máquina de origem é Windows | 0.90 | evidência no Drive: `.lnk`, `Add Keys.reg`, `QCA3.aex`, pasta `Windows-Preset` |

Onde a confiança é baixa, a resposta correta não é "não tente" — é **tente com backup e
protocolo de reversão**, que é o que o `02-restaurar-mac.sh` implementa: ele salva o estado
original antes de sobrescrever qualquer coisa.

---

## 3. Por que o roteiro é "inventariar, depois restaurar" e não "copiar a pasta"

Três mecanismos causais forçam a separação em duas etapas.

Primeiro, o número de versão está no caminho. O AE guarda tudo em pastas como `24.0`, `25.0`,
`26.0`; o Premiere igual. Se a versão do Mac novo for diferente da do PC, copiar para o
caminho antigo cria uma pasta órfã que nenhum app lê. O script de restauração **descobre** a
versão instalada no Mac e redireciona, em vez de assumir.

Segundo, o nome do usuário está no caminho. O Premiere cria `Profile-<seu-usuário-Windows>`.
No Mac o usuário tem outro nome, então a pasta precisa ser renomeada no destino — por isso o
restore procura por `Profile-*` com glob em vez de literal.

Terceiro, parte do conteúdo exige permissão de administrador (`/Library/...`,
`/Applications/...`) e parte não (`~/Library/...`, `~/Documents/...`). Rodar tudo com `sudo`
cria arquivos pertencentes ao root dentro da sua home, que o Adobe depois não consegue
reescrever — um modo de falha silenciosa clássico. O script separa os dois domínios.

---

## 4. Ordem de execução

```
PC antigo                        transporte           Mac novo
---------                        ----------           --------
PowerShell (admin)                                    instalar Creative Cloud
  01-inventario-windows.ps1  ->  BackupAdobe\  ->      instalar AE + Premiere
                                 (zip/Drive)           abrir e fechar cada um 1x  <- essencial
                                                       02-restaurar-mac.sh --dry-run
                                                       02-restaurar-mac.sh --apply
                                                       reinstalar plugins (PLUGINS.md)
```

"Abrir e fechar cada app uma vez antes de restaurar" não é cerimônia: o primeiro boot é o que
cria a árvore de pastas de preferências com as permissões corretas. Restaurar antes disso faz
o app sobrescrever o que você acabou de copiar.

---

## 5. Arquivos deste kit

| Arquivo | Conteúdo |
|---|---|
| `MAPA-CAMINHOS.md` | tabela caminho-a-caminho Windows ↔ macOS de cada categoria |
| `PLUGINS.md` | inventário de plugins com evidência, + Apple Silicon |
| `PROMPT-PC-ANTIGO.md` | texto para colar no Claude Code do PC antigo |
| `PROMPT-MAC.md` | texto para colar no Claude Code do Mac |
| `scripts/01-inventario-windows.ps1` | varre, copia e gera manifesto |
| `scripts/01-inventario-mac.sh` | idem, origem macOS |
| `scripts/02-restaurar-mac.sh` | restaura no Mac, dry-run por padrão, com backup |

---

Plugin não se migra, se reinstala; layout se migra com rede de segurança; script se migra sem pensar.
