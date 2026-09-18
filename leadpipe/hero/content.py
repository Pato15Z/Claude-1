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
