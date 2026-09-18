"""Cor dominante da logo/fotos → paleta que passa WCAG AA (4.5:1) contra o
texto. Fallback fixo por vertical."""
from __future__ import annotations

import colorsys
from pathlib import Path

from PIL import Image

FALLBACK = {
    "roof cleaning": ("#1f4e79", "#f2b134"),
    "pressure washing": ("#0b6e99", "#ffb703"),
    "house cleaning": ("#2a9d8f", "#e9c46a"),
    "gutter cleaning": ("#3a5a40", "#dda15e"),
    "window cleaning": ("#1d6fa5", "#8ecae6"),
}
DEFAULT = ("#1f3a5f", "#f4a261")


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(round(c)) for c in rgb)


def _rgb(hexs: str):
    h = hexs.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(rgb) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(_rgb(a)), luminance(_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def dominant_color(path: Path, ignore_neutral: bool = True) -> str | None:
    """Cor mais frequente após quantização, ignorando quase-branco/preto/cinza."""
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return None
    im.thumbnail((200, 200))
    q = im.quantize(colors=12, method=Image.Quantize.MEDIANCUT).convert("RGB")
    counts = sorted(q.getcolors(200 * 200) or [], reverse=True)
    for n, rgb in counts:
        h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
        if ignore_neutral and (s < 0.25 or l < 0.12 or l > 0.9):
            continue
        return _hex(rgb)
    return _hex(counts[0][1]) if counts else None


def ensure_contrast(bg: str, text: str = "#ffffff", target: float = 4.5) -> str:
    """Escurece (ou clareia) o fundo até o texto passar AA. Mantém o matiz."""
    r, g, b = (c / 255 for c in _rgb(bg))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    step = -0.03 if luminance(_rgb(text)) > 0.5 else 0.03
    for _ in range(40):
        if contrast(_hex(tuple(c * 255 for c in colorsys.hls_to_rgb(h, l, s))), text) >= target:
            break
        l = min(1.0, max(0.0, l + step))
    return _hex(tuple(c * 255 for c in colorsys.hls_to_rgb(h, l, s)))


def build_palette(vertical: str, logo_path: Path | None, photo_paths: list[Path]) -> dict:
    primary = None
    source = "fallback"
    if logo_path:
        primary = dominant_color(logo_path); source = "logo" if primary else source
    if not primary:
        for p in photo_paths[:3]:
            primary = dominant_color(p)
            if primary:
                source = "photo"; break
    fb_primary, fb_accent = FALLBACK.get(vertical.lower(), DEFAULT)
    if not primary:
        primary = fb_primary
    primary = ensure_contrast(primary, "#ffffff")
    accent = fb_accent
    text_on_accent = "#111111" if contrast(accent, "#111111") >= contrast(accent, "#ffffff") else "#ffffff"
    accent = ensure_contrast(accent, text_on_accent) if contrast(accent, text_on_accent) < 4.5 else accent
    return {"primary": primary, "accent": accent, "text_on_primary": "#ffffff", "text_on_accent": text_on_accent,
            "source": source, "contrast_primary": round(contrast(primary, "#ffffff"), 2)}
