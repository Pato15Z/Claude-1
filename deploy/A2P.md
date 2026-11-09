# Registro na Twilio (A2P + SHAKEN/STIR), campo por campo

O que este arquivo resolve: o registro que libera o SMS e melhora a taxa de
atendimento das ligações, preenchido uma vez, direto na Twilio. Sem GoHighLevel.

**Antes de tudo, a ligação já funciona sem nada disto.** Isto é para o SMS e
para o número parar de aparecer como desconhecido.

---

## Por que não precisa de GoHighLevel (o que a engenharia reversa mostrou)

O módulo de telefonia do GoHighLevel (`phone-integration`, versão 2262, lido em
08/11/2026) é um formulário em cima de produtos públicos da Twilio:

| Tela do GHL | Produto da Twilio | Você faz direto? |
|---|---|---|
| Business Profile | Trust Hub, Customer Profile | sim |
| A2P Brand + Campaign | A2P 10DLC | sim |
| SHAKEN/STIR | Trust Product, vem com o perfil aprovado | sim |
| CNAM | Trust Product, exige EIN ou DUNS | talvez (veja abaixo) |
| Voice Integrity | Trust Product, exige endereço nos EUA | não |
| Verificação com selfie | Persona, exigência só do GHL | não precisa |

A diferença é que o GHL é **ISV**: registra os clientes dele em nome deles. A
própria Twilio diz que quem manda mensagem só em nome da própria empresa segue o
registro **direto**. É o seu caso.

---

## Passo 0. O site da empresa (a TCR rejeita sem ele)

A TCR (The Campaign Registry) olha o site da marca. Ele precisa estar no ar,
público, e ter **política de privacidade e termos no mesmo domínio**. As três
páginas estão prontas em `deploy/agency-site/`.

```bash
bash deploy/agency-site/fill.sh "NOME DA EMPRESA" voce@seudominio.com "+1 614 555 0100" 00.000.000/0001-00
```

Isso gera `deploy/agency-site/out/`. Publique de graça no **Cloudflare Pages**
(Workers & Pages → Create → Pages → Upload assets → arraste a pasta `out`) e
aponte o seu domínio para ele. Precisa abrir sem login:

- `https://seudominio.com/`
- `https://seudominio.com/privacy.html`
- `https://seudominio.com/terms.html`

Use um email **no mesmo domínio** (voce@seudominio.com) no registro. A TCR
desconfia de Gmail.

E no painel do leadpipe: **Painel → Configurações → Nome da empresa**, com o
nome exatamente igual ao do registro. É ele que aparece no SMS.

---

## Passo 1. Business Profile (Trust Hub → Customer Profiles → Create)

| Campo | O que colocar |
|---|---|
| Business name | a **razão social** do CNPJ, exatamente como está na Receita |
| Business type | `Limited Liability Corporation` para LTDA; `Sole Proprietorship` para MEI |
| Industry | `Technology` |
| Registration ID type | `CNPJ` se a lista oferecer; se não, o tipo de *international tax ID* (a doc da Twilio manda usar o campo `EIN` para ID fiscal internacional) |
| Registration number | o CNPJ |
| Region of operation | `USA and Canada` |
| Website | `https://seudominio.com` |
| Address | o endereço do CNPJ, país `Brazil` |
| Authorized representative | você, com email @seudominio.com e o seu celular |

**MEI com CNPJ não é Sole Proprietor no A2P.** A regra da TCR: quem tem ID fiscal
registra como Low-Volume Standard ou Standard. E o registro de Sole Proprietor
só existe para empresas dos EUA e do Canadá (confirmado no código do GHL).

Quando o perfil for aprovado, **associe o seu número a ele**. É isso que ativa o
SHAKEN/STIR: ligações autenticadas com atestado "A", que a Twilio diz serem
*"much more likely to be answered than unidentified numbers"*.

---

## Passo 2. Brand (Messaging → Regulatory Compliance → A2P 10DLC)

Escolha **Low-Volume Standard**: até 6.000 segmentos por dia, mais barato, e
você vai mandar entre 5 e 20. Use o perfil do passo 1.

---

## Passo 3. Campaign

**Use case:** `Marketing`. É mensagem de venda; declarar outra coisa é o motivo
mais comum de rejeição por incoerência.

**Campaign description** (cole):

```
NOME DA EMPRESA builds websites for local service businesses in the US. After a
phone call in which the business owner agrees to receive a text, we send one
message with a link to a short video and to the sample homepage we built for
their business, plus at most one follow-up. Messages are sent one at a time by
a person, not in bulk.
```

**Message flow / how do end users consent** (cole, trocando o domínio e o número):

```
End users opt in in one of two ways. (1) Verbally, during a one-to-one phone
call with NOME DA EMPRESA: our representative asks "Can I text you a 30-second
video of it from NOME DA EMPRESA? Just that and one follow-up." Only if the
owner says yes do we send a text. The consent, with date and time, is recorded
in our CRM for that contact. (2) By texting us first at +1 XXX XXX XXXX, as
described on https://seudominio.com. The first message identifies NOME DA
EMPRESA and says "Reply STOP to opt out". Message frequency varies, at most 4
messages per month. Message and data rates may apply. Reply HELP for help.
Privacy Policy: https://seudominio.com/privacy.html
Terms: https://seudominio.com/terms.html
```

**Sample messages** (2 a 5; a marca precisa estar em todas):

```
Hi [first name], [your name] with NOME DA EMPRESA, from our call. Here's the 30-sec video of [business]'s new homepage: [video link] Live page: [page link] $1,000 to launch it on your domain, $99/mo after. Reply YES and I'll set it up this week. Reply STOP to opt out.
```
```
Hi [first name], it's [your name] from NOME DA EMPRESA again. Did you get a chance to watch the video of [business]'s homepage? Happy to answer any question. Reply STOP to opt out.
```

**Opt-out keywords:** `STOP, UNSUBSCRIBE, CANCEL, END, QUIT`
**Opt-out message:** `NOME DA EMPRESA: you are unsubscribed and will not receive more messages.`
**Help keywords:** `HELP, INFO`
**Help message:** `NOME DA EMPRESA: websites for local businesses. Email voce@seudominio.com. Msg & data rates may apply. Reply STOP to opt out.`

**Embedded links:** sim. **Embedded phone:** não. **Age-gated / lending /
direct lending:** não.

O SMS do leadpipe já sai com o nome da empresa e o "Reply STOP to opt out". Se
um número respondeu STOP, a Twilio recusa o envio (erro 21610) e o painel marca
o lead como PERDIDO sozinho.

---

## Passo 4 (opcional). CNAM: o nome da empresa na tela de quem recebe

A Twilio exige que o perfil tenha **EIN ou DUNS**. Empresa brasileira não tem
EIN, mas pode tirar um **DUNS** de graça na Dun & Bradstreet. Ainda não está
confirmado que a Twilio aceita um DUNS de empresa estrangeira para CNAM. Tente
depois que o resto estiver aprovado; não trave nada por isso.

**Voice Integrity: não dá.** Exige endereço comercial nos EUA. O substituto
gratuito é o [Free Caller Registry](https://www.freecallerregistry.com).

---

## Prazos e custos

- Perfil: de minutos a 2 dias. Brand: idem. Campanha: até 5 dias úteis.
- As taxas (brand uma vez, campanha por mês) aparecem na tela antes de enviar.
  Na Low-Volume elas são as menores.
- O que mais atrasa: descrição vaga, exemplo diferente do que você manda de
  verdade, site sem privacidade/termos, nome diferente entre CNPJ, site e
  formulário.

## Fontes

- [Twilio: registro direto Standard e Low-Volume](https://www.twilio.com/docs/messaging/compliance/a2p-10dlc/direct-standard-onboarding)
- [Twilio: dados exigidos (brand, campanha, privacidade, exemplos)](https://www.twilio.com/docs/messaging/compliance/a2p-10dlc/collect-business-info)
- [Twilio: ISV (o modelo do GoHighLevel)](https://www.twilio.com/docs/messaging/compliance/a2p-10dlc/onboarding-isv)
- [Twilio: SHAKEN/STIR](https://www.twilio.com/docs/voice/trusted-calling-with-shakenstir)
- [Twilio: CNAM](https://www.twilio.com/docs/voice/brand-your-calls-using-cnam)
- [Twilio: Voice Integrity](https://www.twilio.com/docs/voice/spam-monitoring-with-voiceintegrity/voice-integrity-onboarding)
