# Ligar para o lead pelo navegador (Twilio)

Botão de ligar ao lado do roteiro, dentro do painel. Sem celular, sem outro
aplicativo, sem o telefone tocar no seu número brasileiro.

**Ligação não exige registro A2P 10DLC.** Só SMS exige. Então a voz funciona no
mesmo dia em que você criar a conta; o texto espera o registro (veja o fim).

Custo: **~$1,15/mês** pelo número e **~$0,014 a $0,021 por minuto**. Mil ligações
de 3 minutos dão algo em torno de **$60**.

---

## Por que a instrução de discagem não fica no seu servidor

Quando o navegador pede para discar, a Twilio precisa perguntar a alguém *o que
fazer com essa ligação*. Esse "alguém" podia ser o seu servidor — mas a URL do
túnel do painel muda a cada reinício, e o webhook quebraria toda vez.

Por isso a instrução mora numa **Twilio Function**, hospedada pela própria
Twilio, num endereço fixo. O seu servidor só assina o token e **nunca precisa
ser alcançável de fora** — o firewall continua fechado.

```
navegador  --(SDK de voz)-->  Twilio  --(o que eu faço?)-->  Twilio Function
    ^                                                              |
    | token de 1h                                                  v
 leadpipe (assina)                                           disca o lead
```

---

## Passo a passo no painel da Twilio

### 1. Conta e número
Crie a conta em [twilio.com](https://www.twilio.com). Em **Phone Numbers → Buy
a number**, escolha um com DDD perto dos seus leads — **614** (Columbus) ou
**330** (Akron). Marque a capacidade **Voice**.

### 2. A Function que disca
**Functions & Assets → Services → Create Service**, nome `leadpipe`. Crie uma
função em `/dial`, cole:

```javascript
exports.handler = function (context, event, callback) {
  const twiml = new Twilio.twiml.VoiceResponse();
  // callerId e o numero que aparece para o lead; event.To vem do navegador.
  const dial = twiml.dial({ callerId: context.CALLER_ID });
  dial.number(event.To);
  callback(null, twiml);
};
```

Em **Environment Variables** do serviço, adicione `CALLER_ID` com o número que
você comprou, no formato `+16145550100`. Deixe a função como **Public** e
clique em **Deploy All**. Copie a URL que aparece (termina em `/dial`).

### 3. O TwiML App
**Voice → TwiML → TwiML Apps → Create**. Nome `leadpipe`. No campo
**Voice Request URL**, cole a URL da Function, método **POST**. Salve e copie o
**SID** (começa com `AP`).

### 4. A chave de API
**Account → API keys & tokens → Create API key**, tipo **Standard**. Copie o
**SID** (`SK...`) e o **Secret** — o segredo aparece **uma vez só**.

### 5. As variáveis no servidor

```bash
nano /opt/leadpipe/deploy/.env
```

```
TWILIO_ACCOUNT_SID=AC...        # Account → painel inicial
TWILIO_API_KEY_SID=SK...        # passo 4
TWILIO_API_KEY_SECRET=...       # passo 4, aparece uma vez
TWILIO_TWIML_APP_SID=AP...      # passo 3
TWILIO_CALLER_ID=+16145550100   # o número que você comprou
```

```bash
cd /opt/leadpipe/deploy && docker compose up -d app
```

### 6. Usar
Abra um lead → aba **☎ ligação + texto**. O botão **"ligar para +1..."**
aparece ao lado do roteiro. O navegador vai pedir permissão do microfone na
primeira vez.

Se o botão não aparecer: ou falta alguma variável (veja em
`/api/twilio/token`), ou o lead não tem telefone, ou o SDK não carregou.

---

## Antes de ligar para valer

**Registre o número** no [Free Caller Registry](https://www.freecallerregistry.com)
(grátis, leva ~1 semana). Sem isso ele tende a aparecer como "Spam Likely" e
ninguém atende.

**Disque à mão, uma de cada vez.** Discador automático e voz gravada caem na
regra de robocall, que exige consentimento prévio por escrito — US$500 a
US$1.500 por ligação. Uma pessoa discando um número por vez não é robocall.

---

## SMS: o que falta

O mesmo número manda SMS, mas só depois do registro **A2P 10DLC** — exigência
das operadoras americanas, não da Twilio. Empresa de fora dos EUA registra com
o identificador do próprio país, e no Brasil isso é o **CNPJ**.

Enquanto o registro não sai, a entrega do vídeo é por email pedido na ligação,
ou por DM no Facebook e Instagram.

E a regra que não muda com registro nenhum: **SMS frio continua ilegal.** Com o
"pode mandar" dito na ligação, está liberado.
