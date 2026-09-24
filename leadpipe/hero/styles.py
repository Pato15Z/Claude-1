"""Estilo visual por tipo de negócio: qual imagem de referência entra na
página e se a seção de serviços vira "cards".

Sem IA: o estilo é detectado por palavra-chave na vertical, na categoria
do Google e no nome. Pode ser fixado por lead (leads.hero_style) e cada
seção pode ser ligada/desligada por lead (leads.hero_opts, JSON).

Imagens: `data/styles/<estilo>.webp` (suas, importadas com `lp style import
PASTA` ou pela aba Modelos) têm prioridade sobre `leadpipe/hero/assets/`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .. import config

ASSETS = Path(__file__).parent / "assets"
USER_STYLES_DIR = config.DATA_DIR / "styles"

# ordem = prioridade na detecção (o primeiro que casar ganha); "house" é o padrão
STYLES: dict[str, dict] = {
    "movers":      {"label": "Mudanças (movers)",            "cards": True,  "rx": r"\bmov(?:ers?|ing)\b|relocat|mudan|haul|junk"},
    "pest":        {"label": "Controle de pragas",           "cards": True,  "rx": r"\bpest|exterminat|termite|bed ?bug|rodent|mosquito|wildlife"},
    "tree":        {"label": "Árvores (tree service)",       "cards": False, "rx": r"\btrees?\b|arborist|stump|\blimb"},
    "carpet":      {"label": "Carpete e estofados",          "cards": False, "rx": r"carpet|upholster|\brugs?\b|steam clean"},
    "detailing":   {"label": "Car detailing",                "cards": True,  "rx": r"detail|car ?wash|auto ?spa|ceramic|window tint"},
    "landscaping": {"label": "Jardinagem (landscaping)",     "cards": True,  "rx": r"landscap|lawn|\bmow|yard|garden|paisag|hardscape|mulch|\bsod\b"},
    "gutter":      {"label": "Calhas (gutter)",              "cards": True,  "rx": r"gutter|downspout"},
    "handyman":    {"label": "Handyman",                     "cards": False, "rx": r"handy ?man|home repair|remodel|\bfix\b|maintenance"},
    "house":       {"label": "Casa (telhado, pressão, janelas, limpeza)", "cards": False, "rx": r"roof|pressure|power ?wash|soft ?wash|window|house|home|maid|clean"},
}
DEFAULT_STYLE = "house"

# nomes de arquivo aceitos na importação (minúsculas, sem extensão)
FILE_KEYS = [(k, re.compile(v["rx"], re.I)) for k, v in STYLES.items()]

# opções por seção; None = usa o padrão do estilo
OPTS = ["show_cards", "show_scene", "show_reviews", "show_map", "show_gallery", "show_labels"]
# etiquetas sobre a imagem quando o estilo não tem âncoras próprias: 6 pontos
# espalhados (fração da largura/altura). Ajuste por estilo em Modelos → Imagens
# (clique na imagem) ou por lead na gaveta.
GENERIC_ANCHORS = [(0.22, 0.20), (0.78, 0.20), (0.16, 0.50), (0.84, 0.50), (0.26, 0.82), (0.74, 0.82)]


def detect_style(vertical: str | None, category: str | None = None, name: str | None = None) -> str:
    # a vertical (o que você buscou) decide; categoria do Google e nome só
    # entram quando a vertical não diz nada
    for text in (vertical, category, name):
        if not text:
            continue
        for key, rx in FILE_KEYS:
            if rx.search(text):
                return key
    return DEFAULT_STYLE


def style_image(key: str) -> Path | None:
    for d in (USER_STYLES_DIR, ASSETS):
        for ext in ("webp", "jpg", "jpeg", "png"):
            f = d / f"{key}.{ext}"
            if f.exists():
                return f
    return None


def resolve_opts(style: str, opts_json: str | None) -> dict:
    """Mescla o padrão do estilo com o JSON salvo no lead."""
    base = {"show_cards": STYLES.get(style, STYLES[DEFAULT_STYLE])["cards"], "show_scene": True,
            "show_reviews": True, "show_map": True, "show_gallery": True, "show_labels": True}
    try:
        saved = json.loads(opts_json) if opts_json else {}
    except Exception:
        saved = {}
    for k in OPTS:
        if k in saved and saved[k] is not None:
            base[k] = bool(saved[k])
    # extras por lead: posições das etiquetas, textos dos serviços, imagem própria
    for k in ("labels", "services", "scene_path"):
        if saved.get(k):
            base[k] = saved[k]
    return base


def style_anchors(key: str) -> list[tuple[float, float]] | None:
    """Âncoras salvas para o estilo (data/styles/<key>.json), se houver."""
    f = USER_STYLES_DIR / f"{key}.json"
    if f.exists():
        try:
            pts = json.loads(f.read_text(encoding="utf-8")).get("anchors") or []
            return [(float(x), float(y)) for x, y in pts]
        except Exception:
            return None
    return None


def save_style_anchors(key: str, anchors: list) -> Path:
    if key not in STYLES:
        raise ValueError("estilo desconhecido")
    USER_STYLES_DIR.mkdir(parents=True, exist_ok=True)
    f = USER_STYLES_DIR / f"{key}.json"
    f.write_text(json.dumps({"anchors": [[round(float(x), 4), round(float(y), 4)] for x, y in anchors]}), encoding="utf-8")
    return f


def labels_for(services: list[str], anchors: list | None) -> list[dict]:
    """Etiquetas [{n,text,x,y,side}] a partir de pontos (fração) ou dos genéricos."""
    pts = list(anchors or GENERIC_ANCHORS)
    out = []
    for i, svc in enumerate(services[:6]):
        x, y = pts[i] if i < len(pts) else GENERIC_ANCHORS[i % len(GENERIC_ANCHORS)]
        out.append({"n": i + 1, "text": svc, "x": round(x * 100, 1), "y": round(y * 100, 1), "side": "left" if x < 0.5 else "right"})
    return out


def list_styles() -> list[dict]:
    out = []
    for k, v in STYLES.items():
        img = style_image(k)
        out.append({"key": k, "label": v["label"], "cards": v["cards"], "has_image": img is not None,
                    "image": f"/styles/{img.name}" if img else None, "user_image": bool(img and img.parent == USER_STYLES_DIR),
                    "anchors": style_anchors(k), "generic": [list(a) for a in GENERIC_ANCHORS]})
    return out


def save_style_image(key: str, src: Path | bytes, max_w: int = 1600) -> Path:
    """Converte para webp (máx. 1600 px de largura) em data/styles/<key>.webp."""
    from io import BytesIO
    from PIL import Image
    if key not in STYLES:
        raise ValueError(f"estilo desconhecido: {key} (use {', '.join(STYLES)})")
    USER_STYLES_DIR.mkdir(parents=True, exist_ok=True)
    im = Image.open(BytesIO(src) if isinstance(src, bytes) else src)
    im = im.convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    out = USER_STYLES_DIR / f"{key}.webp"
    for stale in USER_STYLES_DIR.glob(f"{key}.*"):
        if stale != out:
            stale.unlink()
    im.save(out, "WEBP", quality=84, method=6)
    return out


def import_folder(folder: Path) -> list[tuple[str, str | None]]:
    """Cada arquivo de imagem da pasta vira a imagem do estilo cujo nome ele
    contém (Handyman1.png → handyman, Car Detailing3.jpg → detailing...).
    Retorna [(arquivo, estilo ou None)]."""
    out = []
    for f in sorted(Path(folder).iterdir()):
        if f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        stem = re.sub(r"[\d_\-]+", " ", f.stem)
        key = next((k for k, rx in FILE_KEYS if rx.search(stem)), None)
        if key:
            save_style_image(key, f)
        out.append((f.name, key))
    return out
