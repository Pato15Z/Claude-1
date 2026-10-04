# Inventário de plugins e extensões

Duas listas separadas, porque têm confiabilidade diferente:

- **Lista A — evidência remota (já levantada).** Reconstruída desta sessão a partir do seu
  Gmail e do seu Google Drive. É parcial por construção: só aparece aqui o que deixou rastro
  de compra ou de arquivo no Drive.
- **Lista B — evidência local (só o PC antigo produz).** O `01-inventario-windows.ps1` varre
  as pastas de plugin e gera `PLUGINS-ENCONTRADOS.csv` com tudo que está realmente instalado.
  Essa é a lista completa.

Rodar a Lista B é o que fecha o inventário. A Lista A existe para você já começar a baixar.

---

## Lista A — confirmado por evidência remota

| Plugin / extensão | Fornecedor | Versão vista | Evidência | Licença |
|---|---|---|---|---|
| **Deep Glow 2** | aescripts (Sander van Dijk) | 1.1.0 | pasta no Drive com `win/DeepGlow2.aex` **e** `macOS/DeepGlow2.plugin`; preset `Tone Mapping DG2.ffx`; `Deep Glow Upgrader v1.0.1.jsx` | pago — sem e-mail de compra |
| **Quick Chromatic Aberration 3** | aescripts | 3.2 | pedidos `#103217312` e `#103217318`, 08/10/2025; `QCA3.aex` + `QCA3.plugin` no Drive | gratuito, na sua conta |
| **FXAA** | aescripts | 1.1 | pedido `#1003931748`, 03/09/2026 (SKU `PEFXAA-FREE`) | gratuito, na sua conta |
| **Save Objects 2** | aescripts | 2.2.1 | extensão CEP `com.aescripts.saveobjects2` no Drive, com `CSXS/manifest.xml` | pago — sem e-mail de compra |
| **Premiere Composer** | MisterHorse | — | pastas `Premiere Composer Files` dentro de vários projetos seus de 2025–2026 | não verificada |
| conta **Maxon** (Red Giant / C4D / Redshift / Universe) | Maxon | — | conta MyMaxon criada 04/08/2026; carrinho abandonado; só newsletters depois | **provavelmente sem licença paga** |

Confiança: Deep Glow 2, QCA3, FXAA e Save Objects 2 — 0.95 (arquivo ou nota fiscal).
Premiere Composer — 0.85 (a pasta de cache só é criada pelo plugin em execução).
Maxon com licença paga — 0.20 (há conta e carrinho, não há confirmação de pedido).

### O caminho mais curto para os quatro da aescripts

Instale o **aescripts + aeplugins manager** no Mac e entre com `abreufernades036@gmail.com`.
Ele lê os pedidos da conta e baixa automaticamente o build macOS correto de cada produto,
já licenciado. Isso resolve QCA3 e FXAA direto (são gratuitos e estão na conta) e resolve
Deep Glow 2 e Save Objects 2 **se** as licenças estiverem na mesma conta.

Se não estiverem: as cópias que você tem no Drive vieram de redistribuição não oficial —
as pastas trazem `downloadpirate.com.txt`, `1nv3rt.nfo`, `INTRO-HD.NET.url` e `Add Keys.reg`.
Isso importa de forma prática, não moral: builds assim não atualizam, não passam pelo
Gatekeeper do macOS sem intervenção manual e, em Apple Silicon, costumam ser x86_64 apenas.
Para ter esses dois funcionando de forma estável no Mac, o caminho é comprar na aescripts.

---

## Lista B — como gerar a lista completa

No PC antigo:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\scripts\01-inventario-windows.ps1
```

Saída relevante:

| Arquivo | Conteúdo |
|---|---|
| `PLUGINS-ENCONTRADOS.csv` | todo `.aex`/`.dll`/`.aix` nas pastas de plugin, com tamanho e data |
| `EXTENSOES-CEP.csv` | painéis instalados, com o nome lido do `CSXS/manifest.xml` |
| `INVENTARIO.csv` | cada categoria, quantos arquivos, quantos MB, qual classe |

O CSV de plugins lista arquivos, não produtos: um produto pode gerar vários `.aex`
(Trapcode Suite, Sapphire e Universe fazem isso). Agrupar por pasta resolve — a pasta
normalmente carrega o nome do fabricante.

---

## Apple Silicon: o filtro que decide se vale reinstalar

Mac novo, em 2026, é Apple Silicon (arm64). Isso cria uma triagem que não existia no Windows.

O After Effects 2023 e posteriores rodam nativos em arm64. Um plugin compilado só para
x86_64 **não carrega** num AE nativo — o efeito simplesmente não aparece na lista, sem
mensagem de erro. Dá para forçar o AE a rodar sob Rosetta (Get Info no app → *Open using
Rosetta*), mas o custo é alto: todos os plugins passam a precisar ser x86_64, você perde
parte do ganho de performance e o Multi-Frame Rendering fica menos eficiente. Confiança
nessa descrição: 0.85 — o comportamento exato varia por versão do AE.

Decisão prática, por plugin:

```
   plugin tem build universal/arm64?
            |
     sim ---+--- não
      |            |
   instale      é essencial para um projeto aberto?
   nativo            |
               sim --+-- não
                |          |
          AE sob Rosetta   descarte / procure substituto nativo
          (só se for      (quase sempre a escolha certa)
           inevitável)
```

Para o seu caso específico: Deep Glow 2 1.1.0 tem build universal (confiança 0.8, pela data
de lançamento). QCA3 3.2 é de 2023 e o build Mac que você tem pode ser só Intel — o
instalador oficial atual resolve. FXAA 1.1 é recente, provavelmente universal.
Save Objects 2 é extensão CEP: roda em HTML/JS, logo é indiferente à arquitetura, exceto
se o pacote embutir binário `.node`.

---

## O que não entra nesta lista

Três coisas que parecem plugin e não são, e por isso não precisam de reinstalação manual:

**Fontes Adobe** ativadas pela Creative Cloud voltam sozinhas no login. Não copie, não
reinstale — duplicar causa conflito de nome de família.

**CC Libraries** (cores, estilos, gráficos) sincronizam pela conta. Idem.

**Efeitos nativos** do AE e do Premiere (Lumetri, Warp Stabilizer, Essential Graphics)
vêm com o app. Se um projeto antigo reclamar de "efeito ausente" e o nome for nativo, o
problema é versão do app, não plugin faltando.

---

Plugin é a única categoria em que a migração correta é não migrar: listar, comprar o build certo e reinstalar.
