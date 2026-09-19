"""Texto por vertical: tagline e faixa de serviços. Sem LLM: tabela fixa,
validada uma vez, custo zero por hero. Chave = vertical em minúsculas."""
from __future__ import annotations

CONTENT = {
    "roof cleaning": {
        "tagline": "Roof cleaning in {city}, done right.",
        "sub": "Soft wash that removes moss, algae and black streaks without damaging your shingles.",
        "services": ["Soft wash roof cleaning", "Moss & algae removal", "Black streak removal", "Gutter cleaning"],
        "cta": "Get a free roof quote",
    },
    "pressure washing": {
        "tagline": "Pressure washing in {city} that makes it look new again.",
        "sub": "Driveways, siding, decks and patios. Licensed, insured, and done in a day.",
        "services": ["Driveway & concrete", "House siding", "Decks & fences", "Patios & walkways"],
        "cta": "Get a free quote",
    },
    "house cleaning": {
        "tagline": "House cleaning in {city} you can count on.",
        "sub": "Recurring, deep and move-out cleaning by a trusted local team.",
        "services": ["Recurring cleaning", "Deep cleaning", "Move in / move out", "Kitchens & bathrooms"],
        "cta": "Get a free estimate",
    },
    "gutter cleaning": {
        "tagline": "Gutter cleaning in {city}, before the next storm.",
        "sub": "Clogged gutters ruin foundations and roofs. We clear, flush and check every downspout.",
        "services": ["Gutter cleaning", "Downspout flushing", "Gutter guards", "Minor repairs"],
        "cta": "Book a cleaning",
    },
    "window cleaning": {
        "tagline": "Streak-free windows in {city}.",
        "sub": "Interior and exterior window cleaning for homes and storefronts.",
        "services": ["Residential windows", "Storefronts", "Screens & tracks", "Skylights"],
        "cta": "Get a free quote",
    },
}
DEFAULT = {
    "tagline": "{vertical_title} in {city}.",
    "sub": "Local, licensed and insured. Call for a free estimate.",
    "services": ["Free estimates", "Licensed & insured", "Same-week scheduling"],
    "cta": "Get a free quote",
}


def content_for(vertical: str, city: str | None) -> dict:
    c = CONTENT.get((vertical or "").lower(), DEFAULT)
    city = city or "your area"
    return {
        "tagline": c["tagline"].format(city=city, vertical_title=(vertical or "Service").title()),
        "sub": c["sub"],
        "services": c["services"],
        "cta": c["cta"],
    }


# ---------------------------------------------------------------- casa com etiquetas
# Pontos da imagem fixa de referência (assets/house.webp, 1344x752), em fração
# da largura/altura. Cada serviço vira uma etiqueta apontando para o ponto que
# faz sentido (telhado, calha, janela...). Sem IA: casamento por palavra-chave.
import re as _re

ANCHORS = {
    "roof":     [(0.44, 0.09), (0.19, 0.22), (0.83, 0.19)],
    "gutter":   [(0.14, 0.35), (0.90, 0.36), (0.63, 0.54)],
    "window":   [(0.38, 0.44), (0.79, 0.47), (0.22, 0.70)],
    "siding":   [(0.16, 0.57), (0.92, 0.62)],
    "driveway": [(0.70, 0.93)],
    "door":     [(0.45, 0.78)],
    "garage":   [(0.76, 0.80)],
    "yard":     [(0.10, 0.88), (0.34, 0.93)],
}
_KEYS = [
    ("roof", _re.compile(r"roof|shingle|moss|algae|streak|soft ?wash", _re.I)),
    ("gutter", _re.compile(r"gutter|downspout|guard", _re.I)),
    ("window", _re.compile(r"window|screen|skylight|glass|storefront|track", _re.I)),
    ("driveway", _re.compile(r"driveway|concrete|patio|walkway|sidewalk|pavers?", _re.I)),
    ("siding", _re.compile(r"siding|house|exterior|pressure|power|wash", _re.I)),
    ("garage", _re.compile(r"garage|deck|fence", _re.I)),
    ("door", _re.compile(r"door|entry|kitchen|bath|deep|recurring|move", _re.I)),
    ("yard", _re.compile(r"lawn|yard|landscap|estimate|insured", _re.I)),
]


def place_labels(services: list[str], max_labels: int = 6) -> list[dict]:
    """Devolve [{text, x, y, side}] com posições em %, sem repetir âncora."""
    used: set[tuple] = set()
    out: list[dict] = []
    order = list(ANCHORS)
    for svc in services[:max_labels]:
        group = next((g for g, rx in _KEYS if rx.search(svc)), None)
        cands = (ANCHORS[group] if group else []) + [a for g in order for a in ANCHORS[g]]
        pt = next((a for a in cands if a not in used), None)
        if pt is None:
            break
        used.add(pt)
        x, y = pt
        out.append({"n": len(out) + 1, "text": svc, "x": round(x * 100, 1), "y": round(y * 100, 1), "side": "left" if x < 0.5 else "right"})
    return out
