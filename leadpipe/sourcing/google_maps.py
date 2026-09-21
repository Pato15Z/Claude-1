"""Scraper do Google Maps via Playwright.

Fluxo por query ("roof cleaning Columbus OH"):
  1. abre /maps/search/<query>, aceita consentimento se aparecer
  2. rola o feed de resultados até o fim (ou até MAPS_MAX_SCROLLS)
  3. lê cada card do feed (nome, rating, reviews, categoria, telefone, site,
     coordenadas e place id vêm do próprio card / href — barato)
  4. para cards novos (place id ainda não no banco), clica e lê o painel de
     detalhe para pegar endereço completo e data do último review — caro
     (~1-2s cada), por isso pula quem já está no banco
  5. persiste cada lead na hora (ingest_one), nunca acumula em memória

Seletores ficam todos em SEL. Quando o Google mudar o DOM (acontece), é aqui
que se conserta. Rode com --debug para salvar o HTML em data/debug/.

Limites conhecidos:
- Maps devolve no máximo ~120 resultados por query. Por isso iterar cidades.
- Facebook/Instagram não existem no Maps; ficam para o enriquecimento.
- "Último review" vem como "3 weeks ago" → data aproximada.
- Tráfego alto → página /sorry/ (captcha). O scraper detecta, espera e tenta
  de novo; se persistir, aborta a query e segue (o que já entrou está salvo).
"""
from __future__ import annotations

import asyncio
import random
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote

from .. import config, db
from ..normalize import relative_date_to_iso
from .base import IngestStats, RawLead, ingest_one, record_query
from .geo import STATE_BBOX, accept, state_center

SEL = {
    "consent_btn": 'button[aria-label*="Accept all"], button[aria-label*="Accept"], form[action*="consent"] button',
    "feed": 'div[role="feed"]',
    "card_link": 'div[role="feed"] a[href*="/maps/place/"]',
    "end_of_list": "text=/reached the end of the list/i",
    "card_rating": 'span[role="img"][aria-label*="star"]',
    "card_website": 'a[data-value="Website"]',
    "detail_title": "h1",
    "detail_address": 'button[data-item-id="address"]',
    "detail_website": 'a[data-item-id="authority"]',
    "detail_phone": 'button[data-item-id^="phone:tel:"]',
    "detail_category": 'button[jsaction*="category"]',
    "detail_review_date": "span.rsqaWe",
    "detail_rating": 'div.F7nice span[aria-hidden="true"]',
    "detail_reviews": 'div.F7nice span[aria-label*="review"]',
}

_COORD_RE = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")
_PLACE_ID_RE = re.compile(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)")
_AT_COORD_RE = re.compile(r"/@(-?\d+\.\d+),(-?\d+\.\d+)")
_PHONE_RE = re.compile(r"\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
_RATING_RE = re.compile(r"(\d+(?:\.\d+)?)\s*stars?\s*(?:\(?([\d,]+)\)?\s*reviews?)?", re.I)


class Blocked(Exception):
    """Google mostrou captcha / página 'unusual traffic'."""


@dataclass
class ScrapeOptions:
    headless: bool = True
    fast: bool = False          # não clica em cada card (sem endereço completo)
    skip_known: bool = True     # não clica em card cujo place id já está no banco
    max_results: int | None = None
    debug: bool = False
    no_site_only: bool = False  # modo caça: descarta no card quem tem site; só clica se faltar telefone


def _place_id(href: str) -> str | None:
    m = _PLACE_ID_RE.search(href)
    return m.group(1) if m else None


def _coords(href: str) -> tuple[float | None, float | None]:
    m = _COORD_RE.search(href)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def _clean_gbp_url(href: str) -> str:
    # Remove a parte gigante de estado da UI; mantém /maps/place/<nome>/data=...!1s<id>
    return href.split("?")[0]


def parse_card_text(text: str) -> dict:
    """Card do feed vira linhas; extrai rating/reviews/categoria/endereço/telefone
    a partir do texto, que é mais estável que classes CSS."""
    out: dict = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for l in lines:
        m = _RATING_RE.search(l)
        if m and "rating" not in out:
            out["rating"] = float(m.group(1))
            if m.group(2):
                out["review_count"] = int(m.group(2).replace(",", ""))
        elif re.match(r"^\d+(\.\d+)?\(\s*[\d,]+\)$", l.replace(" ", "")):
            # "4.8(132)"
            r, c = l.replace(" ", "").split("(")
            out.setdefault("rating", float(r))
            out.setdefault("review_count", int(c.rstrip(")").replace(",", "")))
        if "·" in l and "category" not in out:
            parts = [p.strip() for p in l.split("·") if p.strip()]
            if parts and not _PHONE_RE.search(parts[0]) and not re.match(r"^(Open|Closed|Opens|Closes)", parts[0]):
                out["category"] = parts[0]
                if len(parts) > 1 and not re.match(r"^(Open|Closed|Opens|Closes)", parts[1]):
                    out["street"] = parts[1]
        pm = _PHONE_RE.search(l)
        if pm and "phone" not in out:
            out["phone"] = pm.group(0)
    return out


async def _launch(pw, headless: bool, state: str | None = None):
    """Navegador 'morando' no estado pedido: geolocalização forçada + locale en-US.
    Sem isso o Google Maps puxa resultados perto de onde o usuário realmente está."""
    kwargs = {"headless": headless}
    if config.CHROMIUM_PATH:
        kwargs["executable_path"] = config.CHROMIUM_PATH
    browser = await pw.chromium.launch(**kwargs)
    geo = None
    if state and state.upper() in STATE_BBOX:
        lat, lng = state_center(state)
        geo = {"latitude": lat, "longitude": lng, "accuracy": 500}
    ctx = await browser.new_context(
        locale="en-US", timezone_id="America/New_York",
        viewport={"width": 1280, "height": 900},
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        geolocation=geo, permissions=["geolocation"] if geo else [],
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    return browser, ctx


async def _check_blocked(page) -> None:
    url = page.url
    if "/sorry/" in url or "consent.google" in url and "maps" not in url:
        raise Blocked(url)
    try:
        if await page.locator("text=/unusual traffic/i").count():
            raise Blocked("unusual traffic")
    except Blocked:
        raise
    except Exception:
        pass


async def _dismiss_consent(page) -> None:
    try:
        btn = page.locator(SEL["consent_btn"]).first
        if await btn.count() and await btn.is_visible():
            await btn.click(timeout=3000)
            await page.wait_for_timeout(800)
    except Exception:
        pass


async def _scroll_feed(page, max_results: int | None) -> int:
    feed = page.locator(SEL["feed"])
    await feed.first.wait_for(timeout=config.MAPS_NAV_TIMEOUT_MS)
    last = -1
    stable = 0
    for _ in range(config.MAPS_MAX_SCROLLS):
        count = await page.locator(SEL["card_link"]).count()
        if max_results and count >= max_results:
            break
        if await page.locator(SEL["end_of_list"]).count():
            break
        if count == last:
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
        last = count
        await feed.first.evaluate("el => el.scrollTo(0, el.scrollHeight)")
        await page.wait_for_timeout(random.uniform(900, 1600))
    return await page.locator(SEL["card_link"]).count()


async def _read_card(link) -> dict:
    href = await link.get_attribute("href") or ""
    name = await link.get_attribute("aria-label") or ""
    card = link.locator("xpath=..")
    text = ""
    try:
        text = await card.inner_text(timeout=2000)
    except Exception:
        pass
    parsed = parse_card_text(text)
    website = None
    try:
        w = card.locator(SEL["card_website"]).first
        if await w.count():
            website = await w.get_attribute("href")
    except Exception:
        pass
    lat, lng = _coords(href)
    return {
        "name": name.strip(), "href": href, "place_id": _place_id(href), "lat": lat, "lng": lng,
        "website": website, **parsed,
    }


async def _read_detail(page, link, name: str) -> dict:
    """Clica no card e lê o painel. Retorna campos extras (endereço completo etc.)."""
    out: dict = {}
    await link.click(timeout=5000)
    try:
        await page.locator(SEL["detail_address"]).first.wait_for(timeout=8000)
    except Exception:
        # alguns negócios (service-area) não têm endereço; espera só o título
        try:
            await page.locator(SEL["detail_title"]).first.wait_for(timeout=4000)
        except Exception:
            return out
    await _check_blocked(page)

    async def attr(sel, a="aria-label"):
        try:
            loc = page.locator(sel).first
            if await loc.count():
                return await loc.get_attribute(a)
        except Exception:
            return None
        return None

    async def text(sel):
        try:
            loc = page.locator(sel).first
            if await loc.count():
                return (await loc.inner_text(timeout=1500)).strip()
        except Exception:
            return None
        return None

    addr = await attr(SEL["detail_address"])
    if addr:
        out["address_full"] = re.sub(r"^Address:\s*", "", addr).strip()
    phone = await attr(SEL["detail_phone"])
    if phone:
        out["phone"] = re.sub(r"^Phone:\s*", "", phone).strip()
    site = await attr(SEL["detail_website"], "href")
    if site:
        out["website"] = site
    cat = await text(SEL["detail_category"])
    if cat:
        out["category"] = cat
    rd = await text(SEL["detail_review_date"])
    if rd:
        out["last_review_at"] = relative_date_to_iso(rd)
    rating = await text(SEL["detail_rating"])
    if rating:
        try:
            out["rating"] = float(rating.replace(",", "."))
        except ValueError:
            pass
    rc = await attr(SEL["detail_reviews"])
    if rc:
        m = re.search(r"([\d,]+)", rc)
        if m:
            out["review_count"] = int(m.group(1).replace(",", ""))
    m = _AT_COORD_RE.search(page.url)
    if m and "lat" not in out:
        pass  # coordenada do card (do href) é mais precisa que a da câmera
    return out


async def scrape_query(con: sqlite3.Connection, ctx, query: str, vertical: str, city: str | None,
                       state: str | None, opts: ScrapeOptions) -> IngestStats:
    stats = IngestStats()
    t0 = time.time()
    page = await ctx.new_page()
    error = None
    try:
        for attempt in range(1, config.MAPS_RETRIES + 1):
            try:
                # @lat,lng,9z ancora o mapa no estado; gl=us força o país
                anchor = ""
                if state and state.upper() in STATE_BBOX:
                    clat, clng = state_center(state)
                    anchor = f"/@{clat:.4f},{clng:.4f},9z"
                await page.goto(f"https://www.google.com/maps/search/{quote(query)}{anchor}?hl=en&gl=us",
                                timeout=config.MAPS_NAV_TIMEOUT_MS, wait_until="domcontentloaded")
                await _dismiss_consent(page)
                await _check_blocked(page)
                n = await _scroll_feed(page, opts.max_results)
                break
            except Blocked:
                wait = 60 * attempt
                print(f"  [bloqueado] esperando {wait}s antes de tentar de novo ({attempt}/{config.MAPS_RETRIES})")
                await asyncio.sleep(wait)
                if attempt == config.MAPS_RETRIES:
                    raise
            except Exception as e:  # timeout de navegação etc.
                if attempt == config.MAPS_RETRIES:
                    raise
                await asyncio.sleep(2 ** attempt)
        if opts.debug:
            config.ensure_dirs()
            (config.DEBUG_DIR / f"feed_{re.sub(r'[^a-z0-9]+', '_', query.lower())}.html").write_text(
                await page.content(), encoding="utf-8")

        links = page.locator(SEL["card_link"])
        n = await links.count()
        if opts.max_results:
            n = min(n, opts.max_results)
        seen: set[str] = set()
        from ..qualify.classify import is_aggregator
        for i in range(n):
            link = links.nth(i)
            try:
                card = await _read_card(link)
            except Exception:
                continue
            if not card["name"] or card["href"] in seen:
                continue
            seen.add(card["href"])
            if opts.no_site_only and card.get("website") and not is_aggregator(card["website"]):
                stats.with_site += 1
                continue  # tem site: não é nosso cliente, nem gasta clique
            known = card["place_id"] and con.execute(
                "SELECT 1 FROM leads WHERE gbp_place_id=?", (card["place_id"],)).fetchone()
            detail: dict = {}
            need_detail = not opts.fast and not (opts.skip_known and known)
            if opts.no_site_only and card.get("phone"):
                need_detail = False  # já temos o que importa: nome, telefone, nota, cidade
            if need_detail:
                try:
                    detail = await _read_detail(page, link, card["name"])
                except Blocked:
                    raise
                except Exception as e:
                    detail = {}
                await asyncio.sleep(random.uniform(*config.MAPS_DELAY_RANGE))
            merged = {**card, **detail}
            if state:
                ok, why = accept(merged.get("lat"), merged.get("lng"), merged.get("phone"), state)
                if not ok:
                    stats.rejected += 1
                    continue
            raw = RawLead(
                name=merged["name"],
                vertical=vertical,
                source="google_maps",
                source_query=query,
                phone_raw=merged.get("phone"),
                address_full=merged.get("address_full") or (
                    f"{merged['street']}, {city}, {state}" if merged.get("street") and city and state else None),
                city=city, state=state,
                lat=merged.get("lat"), lng=merged.get("lng"),
                category=merged.get("category"),
                website_url=merged.get("website"),
                gbp_url=_clean_gbp_url(merged["href"]),
                gbp_place_id=merged.get("place_id"),
                rating=merged.get("rating"),
                review_count=merged.get("review_count"),
                last_review_at=merged.get("last_review_at"),
            )
            lead_id = ingest_one(con, raw, stats)
            if opts.no_site_only and lead_id:
                from ..qualify.runner import auto_qualify_no_site
                auto_qualify_no_site(con, lead_id)
    except Blocked as e:
        error = f"blocked: {e}"
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)[:200]}"
        if opts.debug:
            config.ensure_dirs()
            try:
                await page.screenshot(path=str(config.DEBUG_DIR / "last_error.png"))
            except Exception:
                pass
    finally:
        await page.close()
    record_query(con, query, vertical, city, state, stats, time.time() - t0, error)
    if error:
        print(f"  [erro] {query}: {error}")
    return stats


def already_ran(con: sqlite3.Connection, query: str, within_days: int = 7) -> bool:
    row = con.execute(
        "SELECT 1 FROM source_queries WHERE query=? AND error IS NULL "
        "AND ran_at >= datetime('now', ?)", (query, f"-{within_days} days")).fetchone()
    return row is not None


async def scrape_many(con: sqlite3.Connection, queries: list[tuple[str, str, str | None, str | None]],
                      opts: ScrapeOptions, force: bool = False, progress=None) -> IngestStats:
    """queries: lista de (query, vertical, city, state). Persistência por lead;
    query já rodada nos últimos 7 dias é pulada (a não ser com force)."""
    from playwright.async_api import async_playwright

    total = IngestStats()
    async with async_playwright() as pw:
        browser, ctx = await _launch(pw, opts.headless, queries[0][3] if queries else None)
        try:
            for q, vertical, city, state in queries:
                if not force and already_ran(con, q):
                    if progress:
                        progress(q, None, skipped=True)
                    continue
                st = await scrape_query(con, ctx, q, vertical, city, state, opts)
                for k in ("found", "inserted", "duplicates", "filled", "skipped", "with_site", "rejected"):
                    setattr(total, k, getattr(total, k) + getattr(st, k))
                if progress:
                    progress(q, st)
                await asyncio.sleep(random.uniform(1.5, 4.0))
        finally:
            await browser.close()
    return total
