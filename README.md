# leadpipe — prospecção para serviços locais nos EUA

Ferramenta interna, single-user, local. Sourcing (Google Maps) → qualificação
(site inexistente / quebrado / antigo) → tracking (funil, toques, relatórios).
Módulos 3 (enriquecimento) e 4 (hero) vêm nas próximas entregas; o banco já
tem as tabelas para eles.

Leia `docs/DECISIONS.md` antes de rodar: tem as decisões de stack, o que ainda
precisa da sua resposta, e o plano dos 7 dias.

## Instalação (uma vez)

```bash
git clone <este repo> && cd Claude-1
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
lp db init
```

Requer Python 3.11+. O banco fica em `data/leadpipe.db`; screenshots em
`data/screenshots/`. Tudo em `data/` está no `.gitignore`.

## Fluxo semanal (sourcing, ~1h de máquina para ~1.000 leads)

```bash
lp source cities OH --min-pop 20000                     # vê as cidades que vai iterar
lp source maps --vertical "roof cleaning" --state OH    # roda uma query por cidade
lp source maps --vertical "roof cleaning" --state OH --city Columbus --city Dayton --max-results 40   # teste pequeno
```

- Persiste lead a lead. Se morrer no meio, roda de novo: queries já feitas nos
  últimos 7 dias são puladas (`--force` repete).
- Dedup: place id do Google → telefone E.164 → endereço normalizado. Duplicata
  não é descartada: preenche campos vazios do lead existente.
- Se aparecer captcha, rode com `--headful`, resolva na janela, e o scraper
  continua. `--debug` salva o HTML em `data/debug/` para consertar seletores.
- Plano B se o Google mudar o DOM: [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper)
  (Docker, open source) e `lp source import-gosom out.json --vertical "roof cleaning"`.

Entrada manual (cai na mesma fila):

```bash
lp source add --name "Bob's Roof Cleaning" --vertical "roof cleaning" --phone "614-555-0100" --city Columbus --state OH --website bobsroof.com
lp source import-csv leads.csv --vertical "roof cleaning"     # colunas: name, phone, address, city, state, website, rating, reviews, facebook, instagram, email
```

## Fluxo diário (90 min)

```bash
lp qualify run                    # classifica todos os NOVO (≈0.3–3 s/lead, 6 em paralelo)
lp report region                  # <25% qualificação = região saturada; >40% = virgem
lp lead list --status QUALIFICADO --site-status SEM_SITE
lp qualify show 123               # motivo detalhado + métricas (auditar falso positivo)

lp touch queue                    # quem está devido em qual toque hoje, ordem leste→oeste
lp touch log 123 --n 1 --channel email --template t1
lp touch reply 123                # move para RESPONDEU
lp lead set-status 123 CALL_AGENDADA
lp client add 123                 # FECHADO + entra no churn
lp report all                     # ou: lp report html && abrir data/report.html
```

Status de site → funil: `SEM_SITE`, `SITE_QUEBRADO`, `SITE_ANTIGO` viram
`QUALIFICADO`; `SITE_OK` vira `DESCARTADO` (fica no banco para a métrica de região).

## Critérios (todos em `leadpipe/config.py`)

| Status | Regra |
|---|---|
| SEM_SITE | campo vazio, ou domínio de rede social / agregador (lista `AGGREGATOR_DOMAINS`) |
| SITE_QUEBRADO | DNS não resolve, 4xx/5xx, timeout > 8 s, ou render mobile 390 px com overflow horizontal, >30% do texto abaixo de 12 px efetivos, ou nenhum botão ≥ 40 px |
| SITE_ANTIGO | ≥ 2 sinais: sem meta viewport, sem HTTPS/cert inválido, layout em `<table>`, Flash/applet, jQuery 1.x, © antes de 2020, builder legado, nenhum link `tel:` |
| SITE_OK | resto |

"Pixels efetivos": site sem `meta viewport` é renderizado a 980 px e encolhido
para 390 px, então texto de 20 px aparece com 8 px. A medição usa o tamanho
que o dono vê no celular, não o do CSS.

## Comandos úteis

```bash
lp db export --status QUALIFICADO          # CSV para planilha
lp db sql "SELECT city, COUNT(*) FROM leads GROUP BY 1"
lp report queries                          # leads/hora por query de sourcing
lp report stages                           # horas entre etapas do funil
```

## Testes

```bash
pytest -q          # se o Chromium não for o do `playwright install`, defina LEADPIPE_CHROMIUM_PATH
```

## Skills do Claude Code neste repo

| Skill | O que faz | Como usar |
|---|---|---|
| [`llm-council`](.claude/skills/llm-council/) | Roda uma decisão por um conselho de 5 advisors. | "council this", "pressure-test this". |
