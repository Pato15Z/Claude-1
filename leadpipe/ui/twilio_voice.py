"""Ligar para o lead pelo navegador, pelo Twilio.

Por que existe: o canal principal é a ligação, e o painel já tem o roteiro e o
lead na tela. Abrir outro aplicativo para discar quebra o ritmo e perde o
registro do toque. Com isto, o botão de ligar fica ao lado do roteiro.

Como funciona, em três peças:

  navegador  --(SDK de voz)-->  Twilio  --(pede instrução)-->  Twilio Function
     ^                                                               |
     |                     token assinado aqui                       v
  este arquivo                                                   disca o lead

A instrução de discagem (o TwiML) fica numa Twilio Function, hospedada pela
própria Twilio, e NÃO neste servidor. Isso é de propósito: o túnel do painel
troca de URL quando reinicia, e um webhook apontando para ele quebraria toda
vez. Assim o servidor só assina o token e nunca precisa ser alcançável de fora.

Ligação não exige registro A2P 10DLC; só SMS exige. Por isso a voz funciona no
primeiro dia e o texto espera o registro.

Variáveis de ambiente (todas obrigatórias para o botão aparecer):
    TWILIO_ACCOUNT_SID     AC...   conta
    TWILIO_API_KEY_SID     SK...   chave de API (não é o auth token)
    TWILIO_API_KEY_SECRET          segredo da chave
    TWILIO_TWIML_APP_SID   AP...   TwiML App que aponta para a Function
    TWILIO_CALLER_ID       +1614...  número que aparece para o lead
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

REQUIRED = ("TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET",
            "TWILIO_TWIML_APP_SID", "TWILIO_CALLER_ID")


def configured() -> bool:
    """Todas as variáveis presentes? A interface esconde o botão quando não."""
    return all(os.environ.get(k) for k in REQUIRED)


def missing() -> list[str]:
    return [k for k in REQUIRED if not os.environ.get(k)]


def _b64(raw: bytes) -> str:
    # base64url sem o '=' de preenchimento, como manda o JWT.
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def access_token(identity: str = "leadpipe", ttl_s: int = 3600) -> str:
    """JWT de acesso à voz, no formato que o SDK do Twilio espera.

    Assinado com o segredo da chave de API, que nunca sai do servidor: o
    navegador recebe só este token, que expira em uma hora e serve apenas
    para discar pelo TwiML App indicado.
    """
    if not configured():
        raise RuntimeError(f"faltam variáveis do Twilio: {', '.join(missing())}")

    key_sid = os.environ["TWILIO_API_KEY_SID"]
    secret = os.environ["TWILIO_API_KEY_SECRET"]
    now = int(time.time())

    header = {"typ": "JWT", "alg": "HS256", "cty": "twilio-fpa;v=1"}
    payload = {
        "jti": f"{key_sid}-{now}",
        "iss": key_sid,
        "sub": os.environ["TWILIO_ACCOUNT_SID"],
        "iat": now,
        "exp": now + ttl_s,
        "grants": {
            "identity": identity,
            "voice": {
                "outgoing": {"application_sid": os.environ["TWILIO_TWIML_APP_SID"]},
                # Sem isto o lead não consegue retornar a ligação para o navegador.
                "incoming": {"allow": True},
            },
        },
    }

    signing_input = (
        _b64(json.dumps(header, separators=(",", ":"), sort_keys=True).encode())
        + "."
        + _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    )
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return signing_input + "." + _b64(sig)


def caller_id() -> str:
    return os.environ.get("TWILIO_CALLER_ID", "")


# ------------------------------------------------------------------ texto (SMS)
#
# Mandar o link do vídeo pelo mesmo número de onde a ligação saiu, sem sair do
# painel. A API da Twilio é um POST de formulário com autenticação básica, então
# não entra biblioteca nenhuma: urllib da biblioteca padrão resolve.
#
# Importante, e a regra não muda com registro nenhum: SMS frio para celular
# americano é ilegal (TCPA, US$500 a US$1.500 por mensagem). Este botão existe
# para o depois do "pode mandar" dito na ligação. O registro A2P 10DLC libera a
# entrega pelas operadoras; não libera a mensagem não pedida.

SMS_REQUIRED = ("TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET",
                "TWILIO_CALLER_ID")


def sms_configured() -> bool:
    return all(os.environ.get(k) for k in SMS_REQUIRED)


def sms_missing() -> list[str]:
    return [k for k in SMS_REQUIRED if not os.environ.get(k)]


def send_sms(to: str, body: str) -> dict:
    """Manda um SMS e devolve o que a Twilio respondeu.

    Autentica com a chave de API (SK.../segredo), a mesma da voz, e não com o
    auth token da conta: se a chave vazar, dá para revogar só ela.
    """
    import urllib.error
    import urllib.parse
    import urllib.request

    if not sms_configured():
        raise RuntimeError(f"faltam variáveis do Twilio: {', '.join(sms_missing())}")
    to = (to or "").strip()
    body = (body or "").strip()
    if not to.startswith("+"):
        raise ValueError(f"número precisa estar em formato internacional (+1...), veio '{to}'")
    if not body:
        raise ValueError("mensagem vazia")

    sid = os.environ["TWILIO_ACCOUNT_SID"]
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = urllib.parse.urlencode({"To": to, "From": caller_id(), "Body": body}).encode()
    auth = base64.b64encode(
        f"{os.environ['TWILIO_API_KEY_SID']}:{os.environ['TWILIO_API_KEY_SECRET']}".encode()
    ).decode("ascii")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        # O corpo do erro da Twilio é o que interessa: traz o código (ex. 30034,
        # número sem registro A2P) e a URL da explicação. Sem isto o painel só
        # mostraria "HTTP 400" e ninguém saberia o que fazer.
        try:
            err = json.loads(e.read() or b"{}")
        except Exception:
            err = {}
        raise RuntimeError(
            f"Twilio recusou ({e.code}): {err.get('message') or 'sem detalhe'}"
            + (f" [código {err['code']}]" if err.get("code") else "")
            + (f" {err['more_info']}" if err.get("more_info") else "")
        ) from None
    return {"sid": out.get("sid", ""), "status": out.get("status", ""),
            "to": out.get("to", to), "price": out.get("price")}
