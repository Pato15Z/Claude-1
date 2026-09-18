# leadpipe — prospecção para serviços locais nos EUA

Ferramenta interna, single-user, local. Sourcing (Google Maps) → qualificação
(site inexistente / quebrado / antigo) → enriquecimento (email, redes, fotos,
paleta) → hero (página mobile pronta) → tracking (funil, toques, relatórios).

Leia `docs/DECISIONS.md` para as decisões de stack, o que ainda precisa da sua
resposta, e o plano dos 7 dias.

## Instalação (uma vez)

Mac/Linux: `./setup.sh`. Windows (PowerShell): `.\setup.ps1`. O script cria o
ambiente, instala tudo, baixa o Chromium e roda `lp doctor`, que diz o que falta.

Manual, se preferir:

```bash
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
lp db init && lp doctor
```

Requer Python 3.11+. Banco em `data/leadpipe.db`; screenshots, imagens e heros
em `data/`. Tudo em `data/` está no `.gitignore`.

## Fluxo semanal (sourcing, ~1h de máquina para ~1.000 leads)

```bash
lp source cities OH --min-pop 20000                     # vê as cidades que vai iterar
lp source maps --vertical "roof cleaning" --state OH    # roda uma query por cidade
lp source maps --vertical "roof cleaning" --state OH --city Columbus --max-results 30 --debug   # teste pequeno
```

- Persiste lead a lead. Se morrer no meio, roda de novo: queries já feitas nos
  últimos 7 dias são puladas (`--force` repete).
- Dedup: place id do Google → telefone E.164 → endereço normalizado. Duplicata
  não é descartada: preenche campos vazios do lead existente.
- Captcha: rode com `--headful`, resolva na janela, o scraper continua.
  `--debug` salva o HTML em `data/debug/` para consertar seletores.
- Plano B se o Google mudar o DOM: [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper)
  (Docker, open source) e `lp source import-gosom out.json --vertical "roof cleaning"`.

Entrada manual (cai na mesma fila):

```bash
lp source add --name "Bob's Roof Cleaning" --vertical "roof cleaning" --phone "614-555-0100" --city Columbus --state OH --website bobsroof.com
lp source import-csv leads.csv --vertical "roof cleaning"     # colunas: name, phone, address, city, state, website, rating, reviews, facebook, instagram, email
```

## Fluxo diário (90 min)

```bash
lp qualify run                    # NOVO → QUALIFICADO / DESCARTADO (≈0.3–3 s/lead)
lp report region                  # <25% qualificação = região saturada; >40% = virgem
lp enrich run                     # QUALIFICADO → ENRIQUECIDO (email, FB/IG, 3–6 fotos, logo, paleta)
lp hero build                     # ENRIQUECIDO → HERO_PRONTO (uma pasta por lead em data/hero_site/)
lp hero serve                     # abre em http://localhost:8080/<slug>/ para gravar o vídeo
lp hero deploy                    # publica na Vercel (uma vez: npm i -g vercel && vercel login)

lp touch queue                    # quem contatar hoje, em qual toque, ordem leste→oeste
lp touch draft 123                # texto pronto do próximo toque (email / DM / roteiro de ligação)
lp touch draft --today --sender-name "Seu Nome" --sender-phone "+1..." --video-url "..."
lp touch log 123 --n 1 --channel email
lp touch reply 123                # → RESPONDEU
lp lead set-status 123 CALL_AGENDADA
lp client add 123                 # → FECHADO, entra no churn
lp hero expire                    # derruba heros com 30 dias sem resposta
lp report all                     # ou: lp report html && abrir data/report.html
```

Variáveis de ambiente úteis: `LEADPIPE_HERO_DOMAIN=seudominio.com` (as URLs
viram `{slug}.seudominio.com`), `LEADPIPE_WEB_SEARCH=0` (desliga a busca de
Facebook/Instagram no DuckDuckGo).

## Critérios de qualificação (todos em `leadpipe/config.py`)

| Status | Regra |
|---|---|
| SEM_SITE | campo vazio, ou domínio de rede social / agregador (lista `AGGREGATOR_DOMAINS`) |
| SITE_QUEBRADO | DNS não resolve, 4xx/5xx, timeout > 8 s, ou render mobile 390 px com overflow horizontal, >30% do texto abaixo de 12 px efetivos, ou nenhum botão ≥ 40 px |
| SITE_ANTIGO | ≥ 2 sinais: sem meta viewport, sem HTTPS/cert inválido, layout em `<table>`, Flash/applet, jQuery 1.x, © antes de 2020, builder legado, nenhum link `tel:` |
| SITE_OK | resto → DESCARTADO (fica no banco para a métrica de região) |

"Pixels efetivos": site sem `meta viewport` é renderizado a 980 px e encolhido
para 390 px, então texto de 20 px aparece com 8 px. A medição usa o tamanho
que o dono vê no celular.

## Enriquecimento e hero, em uma linha cada

- **Imagens**: fotos do Google Business Profile primeiro, depois o site. Só
  entra imagem com lado maior ≥ 800 px, proporção entre 0,5 e 2,4, sem
  duplicata. Facebook e Instagram exigem login para ver fotos: ficam de fora.
- **Email**: `mailto:` e texto do site + página de contato. Fonte e confiança
  (alta/média/baixa) gravadas.
- **Paleta**: cor dominante da logo (ou das fotos), ajustada até passar
  contraste WCAG AA; fallback fixo por vertical.
- **Hero**: HTML estático de uma página (Jinja2), mobile-first. Passa no mesmo
  teste de render que reprova o site do lead (há um teste garantindo isso).
- **Deploy**: `data/hero_site/` é um site só; `vercel.json` roteia
  `{slug}.dominio` → `/{slug}/`. Cloudflare Pages: `functions/_middleware.js`
  faz o mesmo.

## Comandos úteis

```bash
lp db export --status QUALIFICADO          # CSV para planilha
lp db sql "SELECT city, COUNT(*) FROM leads GROUP BY 1"
lp qualify show 123                        # motivo detalhado + métricas
lp enrich show 123                         # email, redes, imagens, paleta
lp hero list
lp report queries                          # leads/hora por query de sourcing
lp report enrich                           # % com ≥3 imagens, % com email
```

## Testes

```bash
pytest -q          # se o Chromium não for o do `playwright install`, defina LEADPIPE_CHROMIUM_PATH
```

## Skills do Claude Code neste repo

| Skill | O que faz | Como usar |
|---|---|---|
| [`llm-council`](.claude/skills/llm-council/) | Roda uma decisão por um conselho de 5 advisors. | "council this", "pressure-test this". |
