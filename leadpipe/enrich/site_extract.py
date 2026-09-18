"""Extrai do HTML de um site: emails, links de Facebook/Instagram, candidatos a
imagem e a logo, e links para página de contato. Só parsing, sem rede."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_JUNK_EMAIL = re.compile(r"(sentry|wixpress|example\.|\.png$|\.jpg$|\.gif$|\.svg$|\.webp$|noreply|no-reply|donotreply|godaddy|wordpress|@w3\.org|@schema\.org|sitelock|domain\.com$)", re.I)
_FB_RE = re.compile(r"https?://(?:www\.|m\.)?facebook\.com/(?!sharer|share|plugins|dialog|login|policies|privacy|tr\b|hashtag)[A-Za-z0-9._\-/]+", re.I)
_IG_RE = re.compile(r"https?://(?:www\.)?instagram\.com/(?!p/|explore|accounts|share)[A-Za-z0-9._\-]+/?", re.I)
_CONTACT_WORDS = re.compile(r"contact|about|get.?a.?quote|estimate|reach", re.I)
_LOGO_WORDS = re.compile(r"logo|brand", re.I)
_IMG_EXT = re.compile(r"\.(jpe?g|png|webp)(\?|$)", re.I)
_BAD_IMG = re.compile(r"(pixel|tracking|analytics|spacer|icon|sprite|badge|button|arrow|loader|spinner|1x1|blank|placeholder|avatar|flag|payment|visa|mastercard|bbb|yelp|angie|google|facebook|instagram|captcha)", re.I)


@dataclass
class SiteExtract:
    emails: list[str] = field(default_factory=list)
    facebook: str | None = None
    instagram: str | None = None
    images: list[dict] = field(default_factory=list)   # {url, alt, hint}
    logos: list[str] = field(default_factory=list)
    contact_links: list[str] = field(default_factory=list)


def _abs(base: str, u: str | None) -> str | None:
    if not u:
        return None
    u = u.strip()
    if u.startswith("data:") or u.startswith("javascript:"):
        return None
    return urljoin(base, u)


def _srcset_best(srcset: str) -> str | None:
    best, best_w = None, -1
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        w = 0
        if len(bits) > 1 and bits[1].endswith("w"):
            try:
                w = int(bits[1][:-1])
            except ValueError:
                w = 0
        if w > best_w:
            best, best_w = bits[0], w
    return best


def extract(html: str, base_url: str) -> SiteExtract:
    out = SiteExtract()
    soup = BeautifulSoup(html, "lxml")

    # emails: mailto primeiro (confiança alta), depois texto
    seen = set()
    for a in soup.find_all("a", href=re.compile(r"^mailto:", re.I)):
        e = a["href"][7:].split("?")[0].strip().lower()
        if e and _EMAIL_RE.fullmatch(e) and not _JUNK_EMAIL.search(e) and e not in seen:
            seen.add(e); out.emails.append(e)
    for e in _EMAIL_RE.findall(html):
        e = e.lower()
        if not _JUNK_EMAIL.search(e) and e not in seen:
            seen.add(e); out.emails.append(e)

    # redes sociais
    for m in _FB_RE.finditer(html):
        out.facebook = m.group(0).rstrip("/").split("?")[0]; break
    for m in _IG_RE.finditer(html):
        out.instagram = m.group(0).rstrip("/").split("?")[0]; break

    # imagens
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        u = _abs(base_url, og["content"])
        if u:
            out.images.append({"url": u, "alt": "og:image", "hint": "og"})
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("data-lazy-src") or img.get("src")
        if img.get("srcset"):
            src = _srcset_best(img["srcset"]) or src
        u = _abs(base_url, src)
        if not u:
            continue
        alt = (img.get("alt") or "") + " " + (img.get("class") and " ".join(img.get("class")) or "") + " " + u.split("/")[-1]
        if _LOGO_WORDS.search(alt):
            out.logos.append(u); continue
        if _BAD_IMG.search(alt):
            continue
        try:
            w = int(str(img.get("width", "0")).rstrip("px") or 0)
        except ValueError:
            w = 0
        if 0 < w < 300:
            continue
        out.images.append({"url": u, "alt": img.get("alt") or "", "hint": "img"})
    for m in re.finditer(r"background(?:-image)?\s*:\s*url\((['\"]?)([^'\")]+)\1\)", html, re.I):
        u = _abs(base_url, m.group(2))
        if u and _IMG_EXT.search(u) and not _BAD_IMG.search(u):
            out.images.append({"url": u, "alt": "", "hint": "css"})

    # dedupe preservando ordem
    seen_u = set(); imgs = []
    for i in out.images:
        if i["url"] not in seen_u:
            seen_u.add(i["url"]); imgs.append(i)
    out.images = imgs

    # links de contato (mesmo domínio)
    host = urlparse(base_url).netloc
    for a in soup.find_all("a", href=True):
        txt = (a.get_text(" ", strip=True) or "") + " " + a["href"]
        if _CONTACT_WORDS.search(txt):
            u = _abs(base_url, a["href"])
            if u and urlparse(u).netloc == host and u not in out.contact_links and not u.startswith("mailto:"):
                out.contact_links.append(u)
    return out
