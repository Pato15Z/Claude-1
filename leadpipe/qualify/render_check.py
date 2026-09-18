"""Estágio 2: renderiza em viewport mobile (390px), tira screenshot e mede:
- overflow horizontal (scrollWidth > viewport)
- fração de texto visível abaixo de 12px
- alvos de toque (botões/CTAs) abaixo de 40px
- versão do jQuery em runtime (mais confiável que regex no HTML)
Devolve também o HTML renderizado (para sinais que dependem de JS)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .. import config

_METRICS_JS = r"""
() => {
  const vw = window.innerWidth;
  // Sem <meta viewport>, o Chrome mobile monta a página a 980px e encolhe para
  // caber na tela. O que o usuário vê é o tamanho CSS × esse fator. Medimos
  // texto e botões em px EFETIVOS de tela, não em px CSS.
  const scale = Math.min(1, __SCREEN_W__ / vw);
  const doc = document.documentElement;
  // Overflow só faz sentido para site que DECLARA ser mobile (meta viewport) e
  // mesmo assim precisa de layout mais largo que o aparelho. Sem meta viewport
  // o layout de 980px é esperado e já conta como sinal de site antigo.
  const hasViewportMeta = !!document.querySelector('meta[name="viewport" i]');
  const contentW = Math.max(vw, doc.scrollWidth, document.body ? document.body.scrollWidth : 0);
  // Duas formas de "estourar" que o usuário realmente vê:
  //  (a) o Chrome mobile alargou a viewport para caber o conteúdo (tudo encolhe);
  //  (b) a página rola para o lado. Menu escondido fora da tela com
  //      overflow-x:hidden NÃO rola, e por isso não conta (era falso positivo).
  let canScrollX = false;
  try { window.scrollTo(80, 0); canScrollX = (window.scrollX || (document.scrollingElement||doc).scrollLeft) >= 30; window.scrollTo(0, 0); } catch (e) {}
  const overflowPx = hasViewportMeta ? ((vw > __SCREEN_W__ ? vw - __SCREEN_W__ : 0) || (canScrollX ? contentW - __SCREEN_W__ : 0)) : 0;

  // texto: percorre nós de texto visíveis, pesa por nº de caracteres
  const walker = document.createTreeWalker(document.body || doc, NodeFilter.SHOW_TEXT);
  let total = 0, small = 0;
  const seen = new Map();
  while (walker.nextNode()) {
    const n = walker.currentNode;
    const s = n.textContent.replace(/\s+/g, ' ').trim();
    if (!s) continue;
    const el = n.parentElement;
    if (!el) continue;
    const tag = el.tagName;
    if (['SCRIPT','STYLE','NOSCRIPT','TEMPLATE','TITLE'].includes(tag)) continue;
    let cs = seen.get(el);
    if (!cs) { cs = getComputedStyle(el); seen.set(el, cs); }
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const fs = parseFloat(cs.fontSize) || 16;
    total += s.length;
    if (fs * scale < __MIN_FONT__) small += s.length;
  }

  // alvos de toque: botões e links "de ação"
  const ctaSel = 'button, input[type=submit], input[type=button], a[href^="tel:"], a[class*="btn"], a[class*="button"], a[role="button"]';
  const ctas = Array.from(document.querySelectorAll(ctaSel)).filter(e => {
    const r = e.getBoundingClientRect();
    const cs = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden';
  });
  const ctaSizes = ctas.map(e => { const r = e.getBoundingClientRect(); return Math.round(Math.min(r.width, r.height) * scale); });
  const ctaOk = ctaSizes.filter(s => s >= __MIN_TAP__).length;

  const jq = (window.jQuery && window.jQuery.fn && window.jQuery.fn.jquery) || null;
  const hasTel = !!document.querySelector('a[href^="tel:"]');
  return { vw, hasViewportMeta, contentW, canScrollX, scale: Math.round(scale * 100) / 100, overflowPx, textChars: total, smallTextChars: small,
           smallTextRatio: total ? small / total : 0,
           ctaCount: ctas.length, ctaOk, ctaMin: ctaSizes.length ? Math.min(...ctaSizes) : null,
           jquery: jq, hasTel };
}
"""


@dataclass
class RenderResult:
    ok: bool = False
    error: str | None = None
    final_url: str | None = None
    status: int | None = None
    html: str | None = None
    screenshot_path: str | None = None
    metrics: dict = field(default_factory=dict)
    broken_reasons: list[str] = field(default_factory=list)


def _metrics_js() -> str:
    return (_METRICS_JS.replace("__MIN_FONT__", str(config.SMALL_TEXT_MIN_PX))
            .replace("__MIN_TAP__", str(config.TAP_TARGET_MIN_PX))
            .replace("__SCREEN_W__", str(config.MOBILE_VIEWPORT["width"])))


async def new_browser(pw, headless: bool = True):
    kwargs = {"headless": headless}
    if config.CHROMIUM_PATH:
        kwargs["executable_path"] = config.CHROMIUM_PATH
    return await pw.chromium.launch(**kwargs)


async def render(browser, url: str, screenshot_path: Path, timeout_s: float = config.SITE_TIMEOUT_S,
                 ignore_https_errors: bool = True) -> RenderResult:
    res = RenderResult()
    ctx = await browser.new_context(
        viewport=config.MOBILE_VIEWPORT, device_scale_factor=2, is_mobile=True, has_touch=True,
        user_agent=config.MOBILE_UA, locale="en-US", ignore_https_errors=ignore_https_errors,
    )
    page = await ctx.new_page()
    try:
        try:
            resp = await page.goto(url, timeout=int(timeout_s * 1000), wait_until="domcontentloaded")
            res.status = resp.status if resp else None
        except Exception as e:
            res.error = "timeout" if "Timeout" in type(e).__name__ or "timeout" in str(e).lower() else "nav_error"
            return res
        # dá um tempo curto para CSS/JS assentarem, sem estourar o orçamento
        try:
            await page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        await page.wait_for_timeout(300)
        res.final_url = page.url
        try:
            res.metrics = await page.evaluate(_metrics_js())
        except Exception as e:
            res.metrics = {"error": str(e)[:200]}
        try:
            res.html = await page.content()
        except Exception:
            res.html = None
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            await page.screenshot(path=str(screenshot_path), full_page=False)
            res.screenshot_path = str(screenshot_path)
        except Exception:
            pass
        m = res.metrics
        if m.get("overflowPx", 0) > config.OVERFLOW_TOLERANCE_PX:
            res.broken_reasons.append(f"overflow horizontal +{int(m['overflowPx'])}px")
        if m.get("textChars", 0) > 400 and m.get("smallTextRatio", 0) > config.SMALL_TEXT_RATIO_BROKEN:
            res.broken_reasons.append(f"{int(100 * m['smallTextRatio'])}% do texto <{config.SMALL_TEXT_MIN_PX}px")
        # Só reprova se há botões de verdade (≥3) e NENHUM tem alvo de toque
        # decente. 1–2 botões pequenos costumam ser o hambúrguer do menu.
        if m.get("ctaCount", 0) >= 3 and m.get("ctaOk", 0) == 0:
            res.broken_reasons.append(f"todos os {m['ctaCount']} botões <{config.TAP_TARGET_MIN_PX}px (menor: {m.get('ctaMin')}px)")
        res.ok = True
        return res
    finally:
        await ctx.close()
