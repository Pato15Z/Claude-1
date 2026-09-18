"""Download e filtro de imagens. Guarda local (URL de CDN expira).

Filtro: lado maior ≥ MIN_SIDE, proporção entre 0.5 e 2.4 (nem banner nem
tira), sem duplicata (hash perceptual simples), tamanho de arquivo mínimo.
Classifica before/after por palavras no nome/alt."""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image, ImageOps

from .. import config

MIN_SIDE = 800
MIN_BYTES = 25_000
MAX_IMAGES = 6
_BEFORE_RE = re.compile(r"\bbefore\b|\bantes\b|\bdirty\b", re.I)
_AFTER_RE = re.compile(r"\bafter\b|\bdepois\b|\bclean\b|\bresult", re.I)
_BA_RE = re.compile(r"before.{0,6}after|antes.{0,6}depois", re.I)


@dataclass
class SavedImage:
    path: str
    width: int
    height: int
    kind: str      # work | before | after | before_after | logo
    source: str
    score: float
    phash: str


def _phash(im: Image.Image) -> str:
    g = ImageOps.grayscale(im).resize((9, 8), Image.Resampling.LANCZOS)
    px = list(g.tobytes())
    bits = "".join("1" if px[r * 9 + c] > px[r * 9 + c + 1] else "0" for r in range(8) for c in range(8))
    return f"{int(bits, 2):016x}"


def _hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def fetch(url: str, timeout: float = 10.0) -> bytes | None:
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": config.MOBILE_UA}) as c:
            r = c.get(url)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                return r.content
            if r.status_code == 200 and len(r.content) > MIN_BYTES:
                return r.content
    except Exception:
        return None
    return None


def classify_kind(hint: str) -> str:
    if _BA_RE.search(hint):
        return "before_after"
    if _BEFORE_RE.search(hint):
        return "before"
    if _AFTER_RE.search(hint):
        return "after"
    return "work"


def save_candidates(lead_id: int, candidates: list[dict], out_dir: Path, existing_hashes: list[str] | None = None,
                    is_logo: bool = False, max_images: int = MAX_IMAGES) -> tuple[list[SavedImage], list[str]]:
    """candidates: [{url, alt, source}]. Retorna (salvas, motivos_de_rejeição)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[SavedImage] = []
    rejected: list[str] = []
    hashes = list(existing_hashes or [])
    for c in candidates:
        if len(saved) >= max_images:
            break
        data = fetch(c["url"])
        if not data:
            rejected.append(f"{c['url'][:80]}: download falhou"); continue
        try:
            im = Image.open(io.BytesIO(data)); im.load()
        except Exception:
            rejected.append(f"{c['url'][:80]}: não é imagem"); continue
        w, h = im.size
        if not is_logo:
            if max(w, h) < MIN_SIDE:
                rejected.append(f"{c['url'][:80]}: {w}x{h} < {MIN_SIDE}px"); continue
            ratio = w / h if h else 0
            if not (0.5 <= ratio <= 2.4):
                rejected.append(f"{c['url'][:80]}: proporção {ratio:.2f}"); continue
            if len(data) < MIN_BYTES:
                rejected.append(f"{c['url'][:80]}: arquivo pequeno (provável gráfico/stock leve)"); continue
        elif max(w, h) < 120:
            rejected.append(f"{c['url'][:80]}: logo {w}x{h} pequena demais"); continue
        ph = _phash(im.convert("RGB"))
        if any(_hamming(ph, x) <= 6 for x in hashes):
            rejected.append(f"{c['url'][:80]}: duplicata"); continue
        hashes.append(ph)
        kind = "logo" if is_logo else classify_kind(f"{c.get('alt', '')} {c['url']}")
        ext = "png" if is_logo and im.mode in ("RGBA", "P") else "jpg"
        name = f"{'logo' if is_logo else len(saved) + 1}_{hashlib.md5(c['url'].encode()).hexdigest()[:6]}.{ext}"
        p = out_dir / name
        if ext == "jpg":
            im = im.convert("RGB")
            if max(w, h) > 2000:
                im.thumbnail((2000, 2000))
            im.save(p, "JPEG", quality=88, optimize=True)
        else:
            im.save(p, "PNG", optimize=True)
        score = min(w, h) / MIN_SIDE + (0.5 if kind in ("before", "after", "before_after") else 0)
        saved.append(SavedImage(str(p), w, h, kind, c.get("source", "site"), round(score, 2), ph))
    return saved, rejected
