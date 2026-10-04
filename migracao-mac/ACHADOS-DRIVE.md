# Achados: o que já está no seu Google Drive

Levantamento feito nesta sessão na conta `abreufernades036@gmail.com`. Serve a dois
propósitos: você já tem coisa recuperável sem depender do PC antigo, e dá para medir o
que o PC antigo ainda precisa entregar.

---

## 1. Builds macOS que você já possui

Isso é o achado mais útil: dois dos seus plugins estão no Drive **com o bundle macOS
incluído**, não só o `.aex` do Windows.

| Item | O que tem | Link |
|---|---|---|
| `Deep Glow 2 v1.1.0` | `Plugin/macOS/DeepGlow2.plugin` e `Plugin/win/DeepGlow2.aex`, mais `Preset/Tone Mapping DG2.ffx` e `Script/Deep Glow Upgrader v1.0.1.jsx` | [pasta](https://drive.google.com/drive/folders/1pGX0x4d9SgDDFTr1paZApNbx01tz_1l-) |
| `QCA_v3.2` | `QCA3.plugin` (macOS) e `QCA3.aex` (Windows) | [pasta](https://drive.google.com/drive/folders/1PUFN_BM1rtpfbUsRZ_2PGeCNM5VmfjuD) |
| `Saveobjects v2.2.1` | extensão CEP completa `com.aescripts.saveobjects2` + `SaveObjects_Assets` + tutorial | [pasta](https://drive.google.com/drive/folders/1Z6ct2JewpQj8vfj2FW0f15mDp9bEoSFK) |

Ressalva material, não moral: essas pastas trazem `downloadpirate.com.txt`, `1nv3rt.nfo`,
`INTRO-HD.NET.url` e `Add Keys.reg` — são redistribuições, não downloads do fabricante.
Consequência prática em Mac: não atualizam, o Gatekeeper bloqueia na primeira execução
(exige liberar em Privacy & Security a cada binário) e, em Apple Silicon, builds de 2023
costumam ser x86_64, que o AE nativo ignora sem mostrar erro. Para QCA3 e FXAA não há
motivo para usar essas cópias: são gratuitos e estão na sua conta aescripts.

## 2. Projetos e auto-saves já no Drive

A varredura encontrou dezenas de pastas `Adobe After Effects Auto-Save` e
`Adobe Premiere Pro Auto-Save` espalhadas em projetos de 2022 a 2026, além de
`Adobe Premiere Pro Video Previews` e `Audio Previews`.

Implicação para a migração: **auto-saves e previews não precisam ir para o Mac.**
Previews são cache regenerável e ocupam a maior parte do volume; auto-saves são cópias
redundantes do `.aep` principal. Levar os dois multiplica o tamanho da transferência sem
ganho. O `01-inventario-windows.ps1` por isso só lista projetos, não os copia — você
escolhe quais levar.

Projetos nomeados identificados no Drive, como amostra: `TEMAPLATE NODE.aep`,
`Shapes1/Shapes11`, `Loading1/2/31`, `Star3`, `Circles1/2/3`, `lines/lines1`, `ALines`,
`Pointer1`, `T10/T12/T18`.

## 3. Compras confirmadas na aescripts

| Pedido | Data | Item |
|---|---|---|
| `#103217312` | 08/10/2025 | Quick Chromatic Aberration 3 (`PEQCA-FREE`) |
| `#103217318` | 08/10/2025 | Quick Chromatic Aberration 3 (`PEQCA-FREE`, qtd 2) |
| `#1003931748` | 03/09/2026 | FXAA 1.1 (`PEFXAA-FREE`) |

Conta aescripts criada em 08/10/2025 no mesmo e-mail. Instalar o **aescripts manager** no
Mac e entrar com essa conta traz esses itens no build macOS correto, automaticamente.

## 4. Conta Maxon

MyMaxon criada em 04/08/2026. Depois disso: um carrinho abandonado (via Verifone/2Checkout),
newsletters e uma atualização de EULA em 01/10/2026. **Nenhuma confirmação de pedido.**
Leitura provável (confiança 0.8): conta criada para trial ou para avaliar preço, sem
licença ativa de Red Giant / Cinema 4D / Redshift / Universe. Se você acha que tem licença,
verifique em `MyMaxon → Licenses` antes de contar com ela no Mac.

## 5. O que o Drive **não** tem, e só o PC antigo pode dar

| Faltando | Por que importa |
|---|---|
| prefs e workspaces do AE | seus layouts de janela vivem aí |
| prefs, `Profile-<usuário>` e `.kys` do Premiere | layouts e atalhos |
| pasta `Scripts` e `ScriptUI Panels` do AE | seus scripts instalados, principal item do seu pedido |
| `User Presets` (`.ffx`) | presets de animação próprios |
| presets do Media Encoder (`.epr`) | suas configurações de exportação |
| MOGRTs (`.mogrt`) | Essential Graphics |
| LUTs do Lumetri | looks de cor |
| lista completa de plugins instalados | o Drive mostra 3; o PC tem o conjunto real |

Nada disso é recuperável remotamente. É exatamente o que o `01-inventario-windows.ps1`
coleta — razão pela qual ele é o primeiro passo obrigatório.

---

O Drive já te entrega os plugins; o que só o PC antigo tem é justamente o que você mais quer, que são os layouts e os scripts.
