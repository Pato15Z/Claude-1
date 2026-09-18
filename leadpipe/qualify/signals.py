"""Sinais de SITE_ANTIGO extraídos do HTML (bruto e/ou renderizado).

Cada função devolve (nome_do_sinal, evidência) ou None. O classificador conta
quantos dispararam. Evidência vai para o campo site_reason (auditável)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from .. import config

_LEGACY_BUILDERS = [
    ("godaddy_website_builder", re.compile(r"websitebuilder\.godaddy|Website Builder\s*7|img1\.wsimg\.com/isteam|godaddy\.com/websites", re.I)),
    ("homestead", re.compile(r"homestead\.com|intuitwebsites|homesteadcloud", re.I)),
    ("webcom", re.compile(r"web\.com/|websitetonight|netsolhost|networksolutions\.com/website", re.I)),
    ("wix_old_html", re.compile(r"static\.parastorage\.com/services/(?:wix-html-editor|third-party)|wix\.com/website-template|X-Wix-Html", re.I)),
    ("frontpage", re.compile(r'name="GENERATOR"\s+content="Microsoft FrontPage', re.I)),
    ("dreamweaver", re.compile(r"MM_preloadImages|MM_swapImage|MM_swapImgRestore", re.I)),
    ("yahoo_sitebuilder", re.compile(r"Yahoo!? SiteBuilder|sitebuilder\.yahoo", re.I)),
    ("weebly_legacy", re.compile(r"cdn2\.editmysite\.com/js/site/main-legacy|weebly\.com/weebly/apps", re.I)),
    ("vistaprint", re.compile(r"vistaprint\.com/websites|vpweb\.com", re.I)),
    ("wordpress_old", re.compile(r'name="generator"\s+content="WordPress\s+[2-4]\.', re.I)),
    ("joomla_old", re.compile(r'name="generator"\s+content="Joomla!\s+1\.', re.I)),
]

_JQ_SRC_RE = re.compile(r"jquery[-.](1\.\d+(?:\.\d+)?)(?:\.min)?\.js", re.I)
_JQ_INLINE_RE = re.compile(r"jQuery (?:JavaScript Library )?v(1\.\d+(?:\.\d+)?)", re.I)
_COPYRIGHT_RE = re.compile(r"(?:©|&copy;|&#169;|copyright)\s*(?:\(c\)\s*)?((?:19|20)\d{2})(?:\s*[-–]\s*((?:19|20)\d{2}))?", re.I)


@dataclass
class SignalReport:
    fired: dict[str, str]
    checked: list[str]

    @property
    def count(self) -> int:
        return len(self.fired)


def _visible_text(soup: BeautifulSoup) -> str:
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    return soup.get_text(" ", strip=True)


def detect(html: str, https_ok: bool, bad_cert: bool, jquery_version: str | None = None) -> SignalReport:
    fired: dict[str, str] = {}
    checked = ["no_viewport", "no_https", "table_layout", "flash_or_applet", "jquery_lt2",
               "old_copyright", "legacy_builder", "no_tel_link"]
    soup = BeautifulSoup(html, "lxml")

    # 1. meta viewport
    if not soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)}):
        fired["no_viewport"] = "sem <meta name=viewport>"

    # 2. https
    if not https_ok:
        fired["no_https"] = "não serve https"
    elif bad_cert:
        fired["no_https"] = "certificado inválido"

    # 3. layout em tabela: tabela segura mais da metade do texto visível
    body = soup.body or soup
    total_text = len(_visible_text(BeautifulSoup(str(body), "lxml")))
    tables = body.find_all("table")
    if tables and total_text:
        top = [t for t in tables if not t.find_parent("table")]
        in_tables = sum(len(BeautifulSoup(str(t), "lxml").get_text(" ", strip=True)) for t in top)
        if in_tables / total_text > 0.5:
            fired["table_layout"] = f"{int(100 * in_tables / total_text)}% do texto dentro de <table>"

    # 4. flash / applet
    if soup.find("applet") or re.search(r"\.swf\b|application/x-shockwave-flash|clsid:D27CDB6E", html, re.I):
        fired["flash_or_applet"] = "flash/applet no HTML"

    # 5. jquery < 2
    jqv = jquery_version
    if not jqv:
        m = _JQ_SRC_RE.search(html) or _JQ_INLINE_RE.search(html)
        jqv = m.group(1) if m else None
    if jqv and jqv.startswith("1."):
        fired["jquery_lt2"] = f"jQuery {jqv}"

    # 6. copyright antigo: pega o maior ano em qualquer "© YYYY" / "© YYYY-YYYY"
    years = []
    for m in _COPYRIGHT_RE.finditer(html):
        years.append(int(m.group(2) or m.group(1)))
    if years and max(years) < config.OLD_COPYRIGHT_BEFORE:
        fired["old_copyright"] = f"© {max(years)}"

    # 7. builder legado
    for name, rx in _LEGACY_BUILDERS:
        if rx.search(html):
            fired["legacy_builder"] = name
            break

    # 8. sem tel: link
    if not soup.find("a", href=re.compile(r"^tel:", re.I)):
        fired["no_tel_link"] = "nenhum link tel:"

    return SignalReport(fired=fired, checked=checked)
