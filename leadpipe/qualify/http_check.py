"""Estágio 1 da qualificação: o site existe e responde?

Devolve um HttpResult sempre (nunca levanta). Tenta https primeiro; se falhar
por certificado, tenta sem verificar (sinal bad_cert); se https não conecta,
tenta http (sinal no_https)."""
from __future__ import annotations

import socket
import ssl
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse

import httpx

from .. import config

UA = config.MOBILE_UA


@dataclass
class HttpResult:
    input_url: str
    url: str | None = None           # URL efetivamente usada
    final_url: str | None = None     # após redirects
    ok: bool = False
    status: int | None = None
    elapsed_ms: int | None = None
    html: str | None = None
    headers: dict = field(default_factory=dict)
    https: bool = False
    bad_cert: bool = False
    error: str | None = None         # dns | timeout | connect | http_4xx | http_5xx | ...


def normalize_url(u: str) -> str:
    u = u.strip()
    if not u:
        return u
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    p = urlparse(u)
    return urlunparse((p.scheme, p.netloc.lower(), p.path or "/", p.params, p.query, ""))


def host_of(u: str) -> str:
    h = urlparse(normalize_url(u)).hostname or ""
    return h[4:] if h.startswith("www.") else h


def _resolves(host: str) -> bool:
    try:
        socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        return True
    except socket.gaierror:
        return False


def _fetch(url: str, verify: bool, timeout: float) -> httpx.Response:
    with httpx.Client(follow_redirects=True, timeout=timeout, verify=verify,
                      headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"}) as c:
        return c.get(url)


def check(url: str, timeout: float = config.SITE_TIMEOUT_S) -> HttpResult:
    res = HttpResult(input_url=url)
    u = normalize_url(url)
    host = urlparse(u).hostname or ""
    if not host:
        res.error = "invalid_url"
        return res
    if not _resolves(host):
        res.error = "dns"
        return res

    attempts = [(u, True)]
    if u.startswith("https://"):
        attempts += [(u, False), ("http://" + u[len("https://"):], True)]
    t0 = time.monotonic()
    for attempt_url, verify in attempts:
        remaining = timeout - (time.monotonic() - t0)
        if remaining <= 0.5:
            res.error = "timeout"
            break
        try:
            r = _fetch(attempt_url, verify, remaining)
        except httpx.TimeoutException:
            res.error = "timeout"
            break  # timeout é sentença: não vale tentar http depois
        except (httpx.ConnectError, ssl.SSLError, httpx.RemoteProtocolError) as e:
            msg = str(e).lower()
            if "certificate" in msg or "ssl" in msg or "tls" in msg:
                res.bad_cert = True
                res.error = "bad_cert"
                continue
            res.error = "connect"
            continue
        except Exception as e:
            res.error = type(e).__name__.lower()
            continue
        res.url = attempt_url
        res.final_url = str(r.url)
        res.status = r.status_code
        res.elapsed_ms = int((time.monotonic() - t0) * 1000)
        res.headers = {k.lower(): v for k, v in r.headers.items()}
        res.https = res.final_url.startswith("https://")
        if not verify:
            res.bad_cert = True
        if 400 <= r.status_code < 500:
            res.error = "http_4xx"
        elif r.status_code >= 500:
            res.error = "http_5xx"
        else:
            res.ok = True
            res.error = None
            res.html = r.text[:2_000_000]
        break
    if res.elapsed_ms is None:
        res.elapsed_ms = int((time.monotonic() - t0) * 1000)
    return res
