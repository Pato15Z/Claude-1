# Decisões, suposições e o que falta

Você pediu para eu perguntar antes de escrever código e depois pediu para
fazer o máximo possível. Tomei as decisões abaixo com justificativa. Nenhuma é
cara de reverter.

## 0. Estado atual (o que está pronto e o que falta)

| Módulo | Estado | Validado como |
|---|---|---|
| 1 Sourcing (Maps, CSV, manual, gosom) | pronto | parser e dedup com testes; **DOM real do Maps não testado** (rede bloqueada aqui) |
| 2 Qualificação | pronto | sites de fixture locais: antigo, quebrado, ok, 404, Facebook, vazio |
| 3 Enriquecimento | pronto | site de fixture com fotos, logo, mailto, links sociais; **fotos do GBP e busca DuckDuckGo não testadas** (rede) |
| 4 Hero | pronto | gera, passa no próprio teste de render mobile, slug único, expiração |
| 5 Tracking | pronto | toques, fila por fuso, 12 relatórios, dashboard HTML |
| Rascunhos dos 4 toques | pronto | `lp touch draft` |
| Instalador + `lp doctor` | pronto | — |
| Deploy na Vercel | script pronto, **não executado** | precisa de conta, CLI e domínio seus |

**O que só você pode fazer** (ordem):
1. Rodar `setup.sh` / `setup.ps1` e o teste pequeno do Maps. Me mandar a saída.
2. Comprar/escolher um domínio e definir `LEADPIPE_HERO_DOMAIN`.
3. Criar conta Vercel, `npm i -g vercel`, `vercel login`, adicionar o domínio
   ao projeto com wildcard `*.seudominio.com` (Vercel mostra os registros DNS).
4. Escolher email/FB/IG de envio e colocar seu nome/telefone/link do vídeo em
   `lp touch draft` (ou editar `leadpipe/tracking/templates.py`).

## 1. Decisões tomadas

| Decisão | Escolha | Por quê | Alternativa e quando trocar |
|---|---|---|---|
| Linguagem / banco | Python 3.11 + SQLite (WAL) | single-user, zero setup | Postgres só se virar multi-máquina |
| Sourcing | Scraper próprio do Maps em Playwright | gratuito, self-hosted | Google Places API (New): ~US$35–40 por 1.000 leads, sem captcha. Trocar se captcha em >20% das queries |
| Plano B de sourcing | JSON do `gosom/google-maps-scraper` | Go, Docker, maduro | já implementado |
| Cidades por estado | `geonamescache` (offline, pop ≥ 15k) | itera por cidade sem rede | — |
| Qualificação | httpx (8 s) → Playwright mobile 390 px → sinais no HTML | separa "não responde" de "responde mal"; screenshot vira o "antes" do vídeo | — |
| Fuso | `timezonefinder` por coordenada, fallback por estado | TX e FL têm dois fusos | — |
| FB/IG no sourcing | não | Maps não tem; custaria 1 busca/lead em gente que será descartada | feito no módulo 3, só para QUALIFICADO |
| Fotos de FB/IG | não | exigem login; automação logada = risco de ban | GBP + site cobrem; lead sem foto vira prioridade baixa com hero genérico |
| Busca de FB/IG | DuckDuckGo HTML, 1 req/lead, pausa 1,5 s | sem API, sem chave | `LEADPIPE_WEB_SEARCH=0` desliga |
| **Hero: HTML estático via Jinja2, não Astro/Next** | resultado idêntico (uma página, zero JS além de 6 linhas), gera em ms, tira o Node da instalação | se o site pós-fechamento for Astro/Next, o hero vira componente lá; o `hero.json` é o contrato |
| Hosting | Vercel, 1 projeto, `vercel.json` roteia `{slug}.dominio → /{slug}/` | wildcard grátis em domínio próprio | Cloudflare Pages: `functions/_middleware.js` já gerado |
| Tagline/serviços | tabela fixa por vertical | zero custo, validável uma vez | — |
| Envio | manual, com rascunho pronto | escopo desta fase | ver §5 |

## 2. Perguntas ainda abertas (respondi com padrão; troque se quiser)

1. Hero: **HTML estático** (padrão). Astro/Next só se você quiser o site final na mesma stack.
2. Hosting: **Vercel** (padrão). Cloudflare Pages também já sai pronto.
3. Domínio: **falta**. Sugestões: algo neutro tipo `getmysite.pro`, `newhomepage.co` (verifique disponibilidade).
4. Email de envio: **falta**. Recomendo Gmail Workspace em domínio separado.
5. Google Places API como reserva: **não** (padrão, grátis). Diga "sim" e eu adiciono.
6. Contas FB/IG: **falta**.
7. Cobrança: Wise para setup + Stripe para o mensal (§6).

## 3. Gargalos e limites conhecidos

- **Maps satura em ~120 resultados por query** → iterar por cidade. Ohio ≥ 20k hab = 95 cidades ≈ 60–90 min.
- **Seletores do Maps e das fotos do GBP** estão em `SEL` no topo de
  `leadpipe/sourcing/google_maps.py` e `leadpipe/enrich/gbp_photos.py`. Não
  validados contra o Google real. `--debug` salva HTML para conserto rápido.
- **Captcha**: detecta `/sorry/`, espera 60/120/180 s, registra erro e segue. `--headful` para resolver na mão. Confiança de 95 queries sem captcha em IP residencial: ~70%.
- **Falso SITE_QUEBRADO por bloqueio de bot** (Cloudflare 403). Auditar com `lp qualify show`.
- **Imagens sintéticas nos testes**: o filtro de duplicata usa hash perceptual em cinza; fotos reais têm estrutura diferente, mas duas fotos do mesmo telhado de ângulos próximos podem ser tratadas como uma. Aceitável.
- **Hero sem foto** usa gradiente na cor da vertical. Converte menos; está marcado `priority=baixa` e só entra com `--include-low`.

## 4. Plano dos 7 dias

| Dia | O que | Saída |
|---|---|---|
| 1 | `setup.sh`; teste pequeno do Maps; me mandar a saída | scraper validado ou HTML de debug |
| 1–2 | sourcing completo OH + `lp qualify run` + `lp report region` | 500–1.000 brutos, % por cidade |
| 2–3 | 2ª vertical; domínio + Vercel | 200+ QUALIFICADO; `lp hero deploy` funcionando |
| 3 | `lp enrich run`; `lp hero build`; gravar 5 vídeos | primeiros heros no ar |
| 4–7 | `lp touch queue` / `draft` / `log` todo dia | números reais |

## 5. Automação da sequência (fase 2)

| Canal | Como | Custo | Risco | Veredito |
|---|---|---|---|---|
| Email (toques 1 e 4) | SMTP (Gmail Workspace API ou SES US$0,10/1.000) + cron 6h no fuso, lendo a fila | ~0 | reputação; CAN-SPAM (endereço físico + opt-out) | automatizar primeiro |
| Facebook Página→Página | API da Meta não permite iniciar conversa; só browser logado (viola termos) | 0 | ban | manual, fila mostra a URL |
| Instagram DM | idem, mais restrito | 0 | ban | manual |
| Ligação | click-to-call Twilio/Telnyx (~US$0,01/min) | ~0 | nenhum | automatizar discagem |
| SMS | fora de escopo (10DLC; cold SMS ilegal sem consentimento) | — | multa | não |

Próximo passo técnico: `lp touch send` que lê a fila, renderiza o template já
existente, envia via SMTP e chama `log_touch`. Tudo o que ele precisa já existe.

## 6. Wise vs Stripe

- **Wise Business**: recebe USD por ACH/wire, payment request com link. Não faz recorrência automática de cartão. Bom para o setup de US$1.000. Confiança ~75%; confirmar no painel se o link aceita cartão no seu país.
- **Stripe**: recorrência automática com retentativa; 2,9% + 30¢ (≈US$3,17 sobre US$99).
- Provável: Wise para setup, Stripe Billing para o mensal. Decidir no primeiro fechamento.

## 7. Contrato do hero (`data/hero_site/{slug}/hero.json`)

```json
{
  "slug": "bobs-roof-cleaning-columbus",
  "name": "Bob's Roof Cleaning", "city": "Columbus", "state": "OH",
  "phone_e164": "+16145550100", "phone_display": "(614) 555-0100",
  "vertical": "roof cleaning", "tagline": "Roof cleaning in Columbus, done right.",
  "services": ["Soft wash roof cleaning", "Moss & algae removal", "Black streak removal", "Gutter cleaning"],
  "rating": 4.7, "review_count": 88,
  "hero_image": "img/hero.jpg", "before": "img/before.jpg", "after": "img/after.jpg", "gallery": ["img/g1.jpg"],
  "logo": "img/logo.png",
  "palette": {"primary": "#1f4e79", "accent": "#f2b134", "text_on_primary": "#ffffff", "text_on_accent": "#111111", "source": "logo"},
  "expires_at": "2026-10-18"
}
```

## 8. Throughput estimado

| Etapa | Estimativa | Confiança |
|---|---|---|
| Sourcing | 600–900 brutos/hora (normal), 1.500+ com `--fast` | média (Maps real não testado) |
| Qualificação | ~1.000 leads em 10–15 min | alta |
| Enriquecimento | 2–8 s/lead (site + GBP), 4 em paralelo → 200 leads em ~10 min | média |
| Hero | milissegundos por lead; 200 heros em segundos | alta |
| Seu tempo por lead com hero | gravar 30 s de tela + colar rascunho ≈ 2 min | média |

Síntese: os cinco módulos existem e passam em 28 testes locais; o que resta é o que exige a sua máquina e as suas contas (Maps real, domínio, Vercel, email).
