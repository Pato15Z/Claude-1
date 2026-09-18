"""Acha página do Facebook/Instagram por busca web (DuckDuckGo HTML, sem API).
Best-effort, com pausa; 1 requisição por lead e só para lead que não tem o
link no próprio site."""
from __future__ import annotations

import re
import time
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

import httpx

from .. import config

_LINK_RE = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"', re.I)
_FB_OK = re.compile(r"^https?://(www\.)?facebook\.com/[A-Za-z0-9.\-]+/?$", re.I)
_IG_OK = re.compile(r"^https?://(www\.)?instagram\.com/[A-Za-z0-9._]+/?$", re.I)


def _ddg(query: str) -> list[str]:
    try:
        with httpx.Client(timeout=10, follow_redirects=True, headers={"User-Agent": config.MOBILE_UA}) as c:
            r = c.get(f"https://html.duckduckgo.com/html/?q={quote_plus(query)}")
            if r.status_code != 200:
                return []
    except Exception:
        return []
    out = []
    for href in _LINK_RE.findall(r.text):
        if "duckduckgo.com/l/?" in href:
            qs = parse_qs(urlparse(href).query)
            href = unquote(qs.get("uddg", [href])[0])
        out.append(href)
    return out


def find_social(name: str, city: str | None, state: str | None, want_fb: bool, want_ig: bool) -> dict:
    res: dict = {}
    loc = " ".join(x for x in (city, state) if x)
    if want_fb:
        for u in _ddg(f'"{name}" {loc} site:facebook.com'):
            if _FB_OK.match(u):
                res["facebook_url"] = u.rstrip("/"); break
        time.sleep(1.5)
    if want_ig:
        for u in _ddg(f'"{name}" {loc} site:instagram.com'):
            if _IG_OK.match(u):
                res["instagram_url"] = u.rstrip("/"); break
        time.sleep(1.5)
    return res
