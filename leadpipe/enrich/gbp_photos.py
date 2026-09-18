"""Ficha do Google Business Profile via Playwright: fotos (versão grande
=w1600), site declarado e avaliações com texto. Seletores em SEL; mesmo
aviso do scraper de sourcing: se o Google mudar o DOM, conserta-se aqui."""
from __future__ import annotations

import re

from .. import config

SEL = {
    "photos_btn": 'button[aria-label*="Photo"], button[jsaction*="heroHeaderImage"], div[role="img"][aria-label*="Photo"]',
    "photo_imgs": 'div[role="img"][style*="googleusercontent"], img[src*="googleusercontent"]',
    "review_imgs": 'button[aria-label*="Photo"] img',
    "reviews_tab": 'button[role="tab"][aria-label*="Reviews"], button[aria-label*="Reviews for"]',
    "review_card": 'div[data-review-id]',
    "review_author": '.d4r55, [class*="d4r55"]',
    "review_stars": 'span[role="img"][aria-label*="star"]',
    "review_date": 'span.rsqaWe',
    "review_text": 'span.wiI7pd',
    "review_more": 'button[aria-label*="See more"]',
}
_STARS_RE = re.compile(r"(\d)\s*star", re.I)


async def _read_reviews(page, max_reviews: int = 6) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    try:
        cards = page.locator(SEL["review_card"])
        n = min(await cards.count(), 12)
        for i in range(n):
            c = cards.nth(i)
            try:
                more = c.locator(SEL["review_more"]).first
                if await more.count():
                    await more.click(timeout=800)
            except Exception:
                pass
            async def _t(sel):
                try:
                    l = c.locator(sel).first
                    return (await l.inner_text(timeout=800)).strip() if await l.count() else ""
                except Exception:
                    return ""
            text = await _t(SEL["review_text"])
            if not text or text in seen:
                continue
            seen.add(text)
            author = await _t(SEL["review_author"]) or "Google user"
            rating = None
            try:
                st = c.locator(SEL["review_stars"]).first
                if await st.count():
                    m = _STARS_RE.search(await st.get_attribute("aria-label") or "")
                    rating = int(m.group(1)) if m else None
            except Exception:
                pass
            out.append({"author": author.split("\n")[0][:60], "rating": rating, "date_text": await _t(SEL["review_date"]),
                        "text": text[:600]})
            if len(out) >= max_reviews:
                break
    except Exception:
        pass
    return out
_URL_RE = re.compile(r"https://lh\d\.googleusercontent\.com/[^\s\"')]+")


def _big(url: str) -> str:
    # ...=w408-h306-k-no → =w1600-k-no ; sem sufixo → adiciona
    if "=" in url:
        return re.sub(r"=[^=]*$", "=w1600-k-no", url)
    return url + "=w1600-k-no"


async def collect(ctx, gbp_url: str, max_photos: int = 12) -> dict:
    """Retorna {"photos": [...], "website": str|None, "reviews": [...]}. O site é
    lido de novo aqui porque o modo caça só olhou o card; a ficha é a fonte final."""
    page = await ctx.new_page()
    urls: list[str] = []
    website: str | None = None
    reviews: list[dict] = []
    try:
        await page.goto(gbp_url + ("&hl=en" if "?" in gbp_url else "?hl=en"), timeout=config.MAPS_NAV_TIMEOUT_MS,
                        wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        try:
            w = page.locator('a[data-item-id="authority"]').first
            if await w.count():
                website = await w.get_attribute("href")
        except Exception:
            pass
        # avaliações: as visíveis na visão geral; se poucas, abre a aba Reviews
        reviews = await _read_reviews(page)
        if len(reviews) < 3:
            try:
                tab = page.locator(SEL["reviews_tab"]).first
                if await tab.count():
                    await tab.click(timeout=3000)
                    await page.wait_for_timeout(1500)
                    reviews = await _read_reviews(page) or reviews
                    await page.go_back(timeout=5000)
                    await page.wait_for_timeout(800)
            except Exception:
                pass
        try:
            btn = page.locator(SEL["photos_btn"]).first
            if await btn.count():
                await btn.click(timeout=4000)
                await page.wait_for_timeout(2000)
                for _ in range(3):
                    await page.mouse.wheel(0, 2000)
                    await page.wait_for_timeout(800)
        except Exception:
            pass
        html = await page.content()
        seen = set()
        for m in _URL_RE.finditer(html):
            u = m.group(0)
            key = u.split("=")[0]
            if key in seen or "/a-/" in u or "/a/" in u:  # avatares de usuários
                continue
            seen.add(key)
            urls.append(_big(u))
            if len(urls) >= max_photos:
                break
    except Exception:
        pass
    finally:
        await page.close()
    return {"photos": urls, "website": website, "reviews": reviews}
