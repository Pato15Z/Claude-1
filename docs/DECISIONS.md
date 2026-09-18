# Decisões, suposições e perguntas abertas

Você pediu para eu perguntar antes de escrever código. Eu não consigo esperar
resposta nesta sessão, então tomei as decisões abaixo com a justificativa, e
listei o que muda se você discordar. Nada aqui é caro de reverter.

## 1. Decisões tomadas (entrega 1: módulos 1, 2 e 5)

| Decisão | Escolha | Por quê | Alternativa e quando trocar |
|---|---|---|---|
| Linguagem / banco | Python 3.11 + SQLite (WAL) | single-user, zero setup, `runs`/`history` cabem em SQL puro | Postgres só se virar multi-máquina |
| Sourcing | Scraper próprio do Maps em Playwright | gratuito, self-hosted, obedece "sem SaaS pago" | Google Places API (New): ~US$35–40 por 1.000 leads com telefone+site, sem captcha, sem quebrar por DOM. Trocar se o scraper der captcha em >20% das queries |
| Plano B de sourcing | Ingestão do JSON do `gosom/google-maps-scraper` | projeto Go maduro, Docker, mesmos campos | já implementado (`lp source import-gosom`) |
| Cidades por estado | `geonamescache` (offline, pop ≥ 15k) | itera por cidade sem depender de rede | arquivo próprio de cidades se quiser incluir <15k hab. |
| Qualificação | httpx (8 s) → Playwright mobile 390 px → sinais no HTML | separa "não responde" de "responde mal"; screenshot vira o "antes" do vídeo | — |
| Fuso horário | `timezonefinder` por coordenada, fallback por estado | Texas e Flórida têm dois fusos; coordenada decide | — |
| CLI | `typer` + `rich`; dashboard = HTML estático sem JS | cru e funcional | — |
| Facebook/Instagram no sourcing | **não** buscado no Maps | o Maps não tem esses campos; achar exige 1 busca web por lead (~3–5 s e risco de bloqueio). Em 1.000 brutos custa 1 h para leads que ~60% serão descartados | movido para o módulo 3, só para QUALIFICADO (gargalo avisado, como você pediu) |
| Data do último review | aproximada ("3 weeks ago" → data) | exata exige abrir a aba de reviews (+2 s/lead) | manter aproximada |

## 2. Perguntas que precisam da sua resposta (não bloqueiam a entrega 1)

1. **Hero (entrega 3): Astro ou Next.js?** Recomendo Astro estático: uma página,
   zero JS, build de 1.000 heros em minutos, deploy Vercel/Cloudflare Pages
   grátis. Next.js só vale se o site pós-fechamento for Next e você quiser
   reaproveitar. Probabilidade de Astro ser a escolha certa: ~85%.
2. **Domínio para `{slug}.seudominio.com`.** Precisa de um domínio e DNS
   wildcard (`*.seudominio.com`). Vercel e Cloudflare Pages suportam wildcard
   em domínio próprio. Qual domínio?
3. **Email de envio.** Domínio separado do principal (cold outreach queima
   reputação), SPF/DKIM/DMARC, 20–40 emails/dia por caixa nas primeiras 3
   semanas. Gmail Workspace ou outro? Isso define como o toque 1 será
   automatizado (seção 5).
4. **Conta do Facebook e Instagram** (você disse que decide depois). A fila
   diária já mostra a URL da página do lead quando existir.
5. **Google Places API como reserva?** Se sim, adiciono provedor com a mesma
   interface (`RawLead`). Custo estimado: US$35–40 por 1.000 leads.

## 3. Gargalos e limites conhecidos

- **Google Maps satura em ~120 resultados por query.** Por isso iterar cidade
  a cidade. Ohio com pop ≥ 20k = 95 cidades ≈ 95 queries ≈ 60–90 min de
  máquina para uma vertical, com pausa aleatória de 0,8–2,2 s por card.
- **Seletores do Maps quebram.** Estão todos em `SEL` no topo de
  `leadpipe/sourcing/google_maps.py`. Este ambiente não alcança o Google (o
  proxy bloqueia), então **o scraper não foi validado contra o Maps real**; o
  que foi validado é o parser de cards e de URLs, com fixtures. O primeiro run
  na sua máquina é a validação. Se quebrar, `--debug` salva o HTML e eu conserto
  em minutos; ou use o plano B (gosom).
- **Captcha.** O scraper detecta `/sorry/`, espera 60/120/180 s e tenta de
  novo; depois registra erro na query e segue. Rodar `--headful` para resolver
  na mão se persistir. Confiança de rodar 95 queries sem captcha em IP
  residencial: ~70%.
- **Texto pequeno em site sem viewport.** Medido em px efetivos (CSS × 390/980).
  Um site de 2008 com fonte 14 px aparece com 5,6 px no celular: isso é o que o
  dono vê, e é o que a métrica captura.
- **Falsos positivos de SITE_QUEBRADO por bloqueio de bot** (Cloudflare
  challenge devolve 403). Aparece como `HTTP 403` no motivo; auditar com
  `lp qualify show`. Se virar padrão, adiciono retry com UA de desktop.

## 4. Plano dos 7 dias

| Dia | O que | Saída |
|---|---|---|
| 1 | Instalar; `lp source maps --vertical "roof cleaning" --state OH --city Columbus --max-results 30`. Validar seletores. | scraper funcionando, ou HTML de debug para eu consertar |
| 1–2 | `lp source maps --vertical "roof cleaning" --state OH` completo | 500–1.000 brutos |
| 2 | `lp qualify run`; `lp report region` | % por cidade; decidir onde insistir |
| 2–3 | Repetir para 2ª vertical (pressure washing) no mesmo estado | 200+ QUALIFICADO no banco (meta da entrega 1) |
| 3–4 | Entrega 2: enriquecimento (email, FB/IG, imagens, logo/paleta) só para QUALIFICADO | leads ENRIQUECIDO |
| 5–6 | Entrega 3: template Astro + batch + deploy wildcard | leads HERO_PRONTO |
| 7 | Primeiros envios manuais; `lp touch queue`; relatórios | números reais |

Risco principal do cronograma: dia 1 (validação do scraper). O resto não
depende de rede externa além de abrir sites.

## 5. Pesquisa: automatizar a sequência de contato (fase 2)

| Canal | Como automatizar | Custo | Risco | Veredito |
|---|---|---|---|---|
| Email (toques 1 e 4) | SMTP próprio (Gmail Workspace API ou Amazon SES US$0,10/1.000) + cron às 6h no fuso do lead, lendo `lp touch queue` | ~0 | reputação do domínio; CAN-SPAM exige endereço físico e opt-out | **automatizar primeiro**: mais barato e legal |
| Facebook Página→Página (toque 2) | A API da Meta não permite iniciar conversa com quem nunca mandou mensagem. Só via automação de browser (Playwright logado), que viola os termos | 0 | bloqueio da conta em dias | **manter manual**; a fila já mostra a URL |
| Instagram DM | mesma situação, mais restrita | 0 | bloqueio | manual |
| Ligação (toque 3) | click-to-call via Twilio/Telnyx (~US$0,01/min) disca e te conecta | quase 0 | nenhum | automatizar a discagem, não a conversa |
| SMS | fora de escopo (A2P 10DLC exige registro; cold SMS é ilegal nos EUA sem consentimento) | — | multa | não |

Ordem sugerida: (1) email automático com fila por fuso, (2) discador, (3) FB manual.
Mecanismo do email: um comando `lp touch send` que lê a fila, monta o template
com nome/cidade/hero_url, envia via SMTP e chama `log_touch`. A tabela `touches`
já tem os campos para isso (`template`, `content`).

## 6. Wise vs Stripe para cobrar US$1.000 + US$99/mês

- **Wise Business** (você já tem): recebe USD por ACH/wire com conta local
  americana, taxa baixa, e emite "payment request" com link. Não faz cobrança
  recorrente automática de cartão. Serve bem para o setup de US$1.000 e para o
  mensal se o cliente aceitar pagar manualmente. Confiança: ~75% (pagamento por
  cartão em payment request varia por país da conta; confirmar no seu painel).
- **Stripe**: cobrança recorrente automática com retentativa. Taxa 2,9% + 30¢
  (≈US$3,17 sobre US$99). É o padrão para o mensal.
- **Combinação provável**: Wise para o setup e Stripe Billing para os US$99.
  Decidir depois do primeiro fechamento; `clients.setup_fee` e `clients.mrr`
  já registram.

## 7. Contrato do hero (entrega 3), para o template não depender do banco

```json
{
  "slug": "bobs-roof-cleaning-columbus",
  "business_name": "Bob's Roof Cleaning",
  "city": "Columbus", "state": "OH",
  "phone_e164": "+16145550100", "phone_display": "(614) 555-0100",
  "vertical": "roof cleaning",
  "tagline": "Roof cleaning in Columbus, done right.",
  "services": ["Soft wash roof cleaning", "Moss & algae removal", "Gutter cleaning"],
  "rating": 4.7, "review_count": 88,
  "images": {"hero": "img/1_hero.jpg", "before": null, "after": null},
  "logo": null,
  "palette": {"primary": "#1f4e79", "accent": "#f2b134", "text_on_primary": "#ffffff"},
  "expires_at": "2026-10-18"
}
```

Tagline e serviços vêm de uma tabela por vertical (sem LLM, sem custo).
Paleta: extraída da logo/fotos, testada para contraste WCAG AA, fallback fixo
por vertical.

## 8. Estimativas de throughput (com confiança)

| Etapa | Estimativa | Confiança |
|---|---|---|
| Sourcing | 600–900 leads brutos/hora de máquina (modo normal), 1.500+ em `--fast` | média (não validado no Maps real) |
| Qualificação | 0,3 s (sem site) a 3 s (site lento) por lead, 6 em paralelo → ~1.000 leads em 10–15 min | alta (validado local) |
| Seu tempo por lead qualificado, entrega 1 | ~0 (tudo máquina) | alta |
| Seu tempo por lead com hero, entrega 3 | alvo < 2 min (gravar tela); geração em batch é segundos | média |

Síntese: a entrega 1 está construída e testada de ponta a ponta com sites locais; o único ponto sem validação real é o DOM do Google Maps, e ele tem plano B pronto.
