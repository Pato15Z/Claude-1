"""Fotos do Google Business Profile via Playwright. Abre a ficha, clica em
"Photos", coleta URLs lh3.googleusercontent.com e pede a versão grande
(=w1600). Seletores em SEL; mesmo aviso do scraper de sourcing."""
from __future__ import annotations

import re

from .. import config

SEL = {
    "photos_btn": 'button[aria-label*="Photo"], button[jsaction*="heroHeaderImage"], div[role="img"][aria-label*="Photo"]',
    "photo_imgs": 'div[role="img"][style*="googleusercontent"], img[src*="googleusercontent"]',
    "review_imgs": 'button[aria-label*="Photo"] img',
}
_URL_RE = re.compile(r"https://lh\d\.googleusercontent\.com/[^\s\"')]+")


def _big(url: str) -> str:
    # ...=w408-h306-k-no → =w1600-k-no ; sem sufixo → adiciona
    if "=" in url:
        return re.sub(r"=[^=]*$", "=w1600-k-no", url)
    return url + "=w1600-k-no"


async def collect(ctx, gbp_url: str, max_photos: int = 12) -> tuple[list[str], str | None]:
    """Retorna (urls de fotos, site declarado na ficha ou None). O site é lido
    aqui de novo porque o modo caça só olhou o card; a ficha é a fonte final."""
    page = await ctx.new_page()
    urls: list[str] = []
    website: str | None = None
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
    return urls, website
