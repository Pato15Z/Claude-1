"""Configuração central. Tudo que é "número mágico" fica aqui, com comentário,
para poder ser auditado e ajustado sem caçar no código.

Sobrescrever via variáveis de ambiente LEADPIPE_*.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("LEADPIPE_ROOT", Path(__file__).resolve().parent.parent))
DATA_DIR = Path(os.environ.get("LEADPIPE_DATA", ROOT / "data"))
DB_PATH = Path(os.environ.get("LEADPIPE_DB", DATA_DIR / "leadpipe.db"))
SCREENSHOT_DIR = DATA_DIR / "screenshots"
DEBUG_DIR = DATA_DIR / "debug"

# Navegador. Ordem: LEADPIPE_CHROMIUM_PATH → Chromium do Playwright (se
# instalado) → Chrome/Edge do sistema. Assim funciona sem download extra.
_SYSTEM_BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
]


def _playwright_chromium_installed() -> bool:
    try:
        from playwright._impl._driver import compute_driver_executable  # noqa: F401
        import json as _json
        import playwright as _pw
        base = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or (
            Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright" if os.name == "nt"
            else Path.home() / ".cache" / "ms-playwright"))
        pkg = Path(_pw.__file__).parent / "driver" / "package" / "browsers.json"
        rev = next(b["revision"] for b in _json.loads(pkg.read_text())["browsers"] if b["name"] == "chromium")
        return (base / f"chromium-{rev}").exists()
    except Exception:
        return False


def _detect_browser() -> str | None:
    env = os.environ.get("LEADPIPE_CHROMIUM_PATH")
    if env:
        return env
    if _playwright_chromium_installed():
        return None  # Playwright usa o dele
    for p in _SYSTEM_BROWSERS:
        if p and os.path.exists(p):
            return p
    return None


CHROMIUM_PATH = _detect_browser()

# ---------------------------------------------------------------- sourcing
# Pausa entre listagens no Google Maps (segundos, faixa aleatória). Muito
# rápido = captcha; muito lento = batch de 1000 vira 3 horas.
MAPS_DELAY_RANGE = (0.8, 2.2)
# Quantas vezes rolar o feed de resultados antes de desistir (cada rolagem
# carrega ~20 resultados; Maps satura em ~120 por query de qualquer forma).
MAPS_MAX_SCROLLS = 30
MAPS_RETRIES = 3
MAPS_NAV_TIMEOUT_MS = 25_000

# Verticais varridas pelo `lp hunt` quando não se passa --vertical.
HUNT_VERTICALS = ["roof cleaning", "pressure washing", "gutter cleaning", "window cleaning", "house cleaning"]

# ------------------------------------------------------------ qualificação
# Site que demora mais que isso é SITE_QUEBRADO por definição do critério.
SITE_TIMEOUT_S = 8.0
# Viewport mobile usado para render e screenshot.
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
# Quantos sites verificar em paralelo. Cada um abre uma aba de browser.
QUALIFY_CONCURRENCY = 6
# Overflow horizontal: scrollWidth > viewport + esta folga (px).
OVERFLOW_TOLERANCE_PX = 8
# Fração dos caracteres visíveis com fonte < 12px acima da qual o render é
# considerado quebrado. 100% dos sites têm algum texto miúdo (rodapé), por
# isso não é "qualquer texto".
SMALL_TEXT_MIN_PX = 12
SMALL_TEXT_RATIO_BROKEN = 0.30
# Alvo de toque mínimo (px) para botões/CTAs. Quebrado se NENHUM CTA visível
# atinge o mínimo (todos pequenos), não se algum é pequeno.
TAP_TARGET_MIN_PX = 40
# Sinais de SITE_ANTIGO necessários para classificar como antigo.
OLD_SITE_MIN_SIGNALS = 2
# Ano de copyright abaixo do qual conta como sinal.
OLD_COPYRIGHT_BEFORE = 2020

# Domínios que contam como "sem site": rede social, agregador, page builder
# gratuito que o Google lista como website.
AGGREGATOR_DOMAINS = {
    "facebook.com", "fb.com", "fb.me", "m.me", "instagram.com", "yelp.com",
    "nextdoor.com", "angi.com", "angieslist.com", "thumbtack.com",
    "homeadvisor.com", "houzz.com", "bark.com", "porch.com", "yellowpages.com",
    "bbb.org", "mapquest.com", "alignable.com", "linktr.ee", "business.site",
    "google.com", "goo.gl", "g.page", "wa.me", "tiktok.com", "twitter.com",
    "x.com", "youtube.com", "linkedin.com", "nicelocal.com", "manta.com",
    "superpages.com", "citysearch.com", "merchantcircle.com", "networx.com",
    "craigslist.org", "square.site", "godaddysites.com", "sites.google.com",
}

# ---------------------------------------------------------- enriquecimento
IMAGES_DIR = DATA_DIR / "images"
ENRICH_CONCURRENCY = 4
ENRICH_MAX_IMAGES = 6
# Busca web (DuckDuckGo) para achar Facebook/Instagram quando o site não tem o link.
ENRICH_WEB_SEARCH = os.environ.get("LEADPIPE_WEB_SEARCH", "1") != "0"

# ------------------------------------------------------------------- hero
# Domínio onde os heros são publicados: {slug}.HERO_DOMAIN
HERO_DOMAIN = os.environ.get("LEADPIPE_HERO_DOMAIN", "SEUDOMINIO.com")
HERO_SITE_DIR = DATA_DIR / "hero_site"
HERO_TTL_DAYS = 30
# Templates: os do pacote (leadpipe/hero/templates) + os seus em data/templates.
# O nome (sem .html) é o que se escolhe por lead ou no build.
HERO_TEMPLATE_DEFAULT = os.environ.get("LEADPIPE_HERO_TEMPLATE", "classic")
USER_TEMPLATES_DIR = DATA_DIR / "templates"
VIDEOS_DIR = DATA_DIR / "videos"

# ------------------------------------------------------------- sequência
# Dia relativo ao toque 1 em que cada toque vence, e canal de cada um.
TOUCH_SCHEDULE = {
    1: {"day": 0, "channel": "email"},
    2: {"day": 3, "channel": "facebook_page"},
    3: {"day": 5, "channel": "ligacao"},
    4: {"day": 8, "channel": "email"},
}
SEND_LOCAL_HOUR = 6  # toque 1 e 4 vão às 6h no fuso do lead

# ------------------------------------------------------------- decisão
# Regra de leitura da região: abaixo de 25% de qualificação = saturada,
# acima de 40% = virgem.
REGION_SATURATED_BELOW = 0.25
REGION_VIRGIN_ABOVE = 0.40


def ensure_dirs() -> None:
    for d in (DATA_DIR, SCREENSHOT_DIR, DEBUG_DIR, IMAGES_DIR, HERO_SITE_DIR, USER_TEMPLATES_DIR, VIDEOS_DIR):
        d.mkdir(parents=True, exist_ok=True)
