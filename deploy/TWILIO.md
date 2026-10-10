# Ligar para o lead pelo navegador (Twilio)

Botão de ligar ao lado do roteiro, dentro do painel. Sem celular, sem outro
aplicativo, sem o telefone tocar no seu número brasileiro.

**Ligação não exige registro A2P 10DLC.** Só SMS exige. Então a voz funciona no
mesmo dia em que você criar a conta; o texto espera o registro (veja o fim).

Custo: **~$1,15/mês** pelo número e **~$0,018 por minuto conectado** — são duas
pernas cobradas ao mesmo tempo, $0,0140 a saída para o celular americano e
$0,0040 a do navegador. A Twilio arredonda para cima, por minuto inteiro.

Na prática o que pesa é quantas ligações são atendidas, não quantas são
discadas: tocar e ninguém atender não gera minuto. Varrer os 1.016 leads uma
vez, com 25% a 30% atendendo e 2 minutos de média, fica em torno de **$15 a
$25** no mês. O custo do canal é irrelevante; o seu tempo é o custo.

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

O botão **"✉ mandar esse texto por SMS"** já está na mesma aba, embaixo do
roteiro. O texto na tela é editável antes de mandar, e o que foi enviado fica
guardado no campo de notas do lead.

Ele só vai entregar depois do registro **A2P 10DLC**. Antes disso a Twilio
responde com o erro **30034** e o painel mostra a mensagem dela inteira.

### O que é o A2P 10DLC (e o que não é)

Não é processo de governo. Quem exige são as três operadoras americanas
(AT&T, T-Mobile, Verizon), e o cadastro vive no **The Campaign Registry**, uma
empresa privada. Não existe pedido a órgão público, nem permissão federal a
conseguir. Não há como pular: toda plataforma que manda SMS para os EUA passa
por ali, inclusive as que vendem o contrário.

São duas etapas, feitas de dentro do painel da Twilio:

| Etapa | O que é | Prazo típico |
|---|---|---|
| **Brand** | identificar a empresa | minutos a 2 dias |
| **Campaign** | descrever o uso e dar exemplos de mensagem | 1 a 5 dias úteis |

Empresa de fora dos EUA registra com o identificador do próprio país — no
Brasil, o **CNPJ**. Sem CNPJ existe a campanha de *sole proprietor*, com
volume baixo; para este uso, volume baixo basta (veja abaixo).

**O que atrasa de verdade:** descrição vaga do uso, mensagens de exemplo
diferentes do que você vai mandar, e não dizer como o contato deu permissão.
Escreva que a permissão é verbal, dada na ligação, e cole como exemplo o texto
exato que o painel gera.

**Toll-free não é atalho.** A verificação dele leva 2 a 3 semanas — mais que o
10DLC. Short code, 6 a 10 semanas.

### Por que o volume baixo basta

O SMS aqui só sai depois do "pode mandar" dito na ligação. Ou seja, o número de
mensagens por dia é igual ao número de ligações que foram atendidas e deram
certo — algo entre 5 e 20. Qualquer faixa de registro, inclusive a mais barata,
cobre isso com folga. Capacidade não é o gargalo; a ligação é.

E a regra que não muda com registro nenhum: **SMS frio continua ilegal**
(TCPA, US$500 a US$1.500 por mensagem). Com o "pode mandar" na ligação, está
liberado — e é por isso que o botão avisa.
