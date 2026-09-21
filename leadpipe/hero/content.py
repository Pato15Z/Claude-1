"""Texto por vertical: tagline e faixa de serviços. Sem LLM: tabela fixa,
validada uma vez, custo zero por hero. Chave = vertical em minúsculas."""
from __future__ import annotations

CONTENT = {
    "roof cleaning": {
        "tagline": "Roof cleaning in {city}, done right.",
        "sub": "Soft wash that removes moss, algae and black streaks without damaging your shingles.",
        "services": ["Soft wash roof cleaning", "Moss & algae removal", "Black streak removal", "Gutter cleaning"],
        "cards": ["Low-pressure wash that's safe for shingles and tile.", "Kills growth at the root so it doesn't come back next season.",
                  "Removes the dark stains that make a roof look 20 years older.", "Cleared and flushed while we're already up there."],
        "cta": "Get a free roof quote",
    },
    "pressure washing": {
        "tagline": "Pressure washing in {city} that makes it look new again.",
        "sub": "Driveways, siding, decks and patios. Licensed, insured, and done in a day.",
        "services": ["Driveway & concrete", "House siding", "Decks & fences", "Patios & walkways"],
        "cards": ["Oil, tire marks and years of grime gone in an afternoon.", "Soft wash for vinyl, brick and stucco. No damage, no streaks.",
                  "Wood and composite cleaned and ready for stain or sealer.", "Safe, slip-free surfaces for the whole family."],
        "cta": "Get a free quote",
    },
    "house cleaning": {
        "tagline": "House cleaning in {city} you can count on.",
        "sub": "Recurring, deep and move-out cleaning by a trusted local team.",
        "services": ["Recurring cleaning", "Deep cleaning", "Move in / move out", "Kitchens & bathrooms"],
        "cards": ["Weekly, bi-weekly or monthly. Same team every time.", "Baseboards, blinds, inside appliances. The works.",
                  "Deposit-ready clean for renters and sellers.", "The rooms that matter most, spotless."],
        "cta": "Get a free estimate",
    },
    "gutter cleaning": {
        "tagline": "Gutter cleaning in {city}, before the next storm.",
        "sub": "Clogged gutters ruin foundations and roofs. We clear, flush and check every downspout.",
        "services": ["Gutter cleaning", "Downspout flushing", "Gutter guards", "Minor repairs"],
        "cards": ["Hand-cleared and bagged. Nothing left on your lawn.", "Every downspout flushed and tested with water.",
                  "Keep leaves out for good. Several styles available.", "Loose hangers, leaks and sagging sections fixed on the spot."],
        "cta": "Book a cleaning",
    },
    "window cleaning": {
        "tagline": "Streak-free windows in {city}.",
        "sub": "Interior and exterior window cleaning for homes and storefronts.",
        "services": ["Residential windows", "Storefronts", "Screens & tracks", "Skylights"],
        "cards": ["Inside and out, frames wiped, sills cleaned.", "Regular schedules that keep your business looking sharp.",
                  "Screens washed and tracks vacuumed with every visit.", "Hard-to-reach glass done safely with pro equipment."],
        "cta": "Get a free quote",
    },
    "moving": {
        "tagline": "Movers in {city} who show up on time and treat your stuff like their own.",
        "sub": "Local and long-distance moves, packing, loading and unloading. Licensed and insured.",
        "services": ["Local moves", "Long-distance moves", "Packing & unpacking", "Loading & unloading"],
        "cards": ["Apartments, houses and offices, priced by the hour or flat rate.", "Across the state or across the country, one crew start to finish.",
                  "We bring the boxes, wrap the fragile stuff and label every room.", "Already have a truck or pod? We do the heavy lifting."],
        "cta": "Get a free moving quote",
    },
    "landscaping": {
        "tagline": "Landscaping and lawn care in {city}.",
        "sub": "Mowing, mulch, beds, cleanups and hardscape. A yard you're proud of, without the weekends.",
        "services": ["Lawn mowing", "Mulch & garden beds", "Spring & fall cleanup", "Patios & hardscape"],
        "cards": ["Weekly or bi-weekly, edged and blown clean every visit.", "Fresh mulch, defined edges and healthy plants.",
                  "Leaves, branches and debris gone before the season turns.", "Patios, walkways and retaining walls built to last."],
        "cta": "Get a free estimate",
    },
    "car detailing": {
        "tagline": "Car detailing in {city} that brings the shine back.",
        "sub": "Interior, exterior, paint correction and ceramic coating. We come to you.",
        "services": ["Interior detail", "Exterior detail", "Paint correction", "Ceramic coating"],
        "cards": ["Deep vacuum, shampoo, leather and every vent and crevice.", "Hand wash, clay bar, wax and tire shine.",
                  "Swirls and scratches polished out for a mirror finish.", "Years of protection and a shine that stays."],
        "cta": "Book a detail",
    },
    "carpet cleaning": {
        "tagline": "Carpet cleaning in {city}, dry in hours.",
        "sub": "Hot water extraction for carpets, rugs, upholstery and tile. Pet stains and odors gone.",
        "services": ["Carpet cleaning", "Upholstery cleaning", "Pet stain & odor removal", "Tile & grout"],
        "cards": ["Truck-mounted steam cleaning that pulls out what vacuums leave behind.", "Sofas, chairs and mattresses refreshed.",
                  "Enzyme treatment that removes the smell, not just the spot.", "Grout lines brought back to the original color."],
        "cta": "Get a free quote",
    },
    "pest control": {
        "tagline": "Pest control in {city} that keeps them out.",
        "sub": "Ants, spiders, rodents, termites, bed bugs and mosquitoes. One-time or quarterly plans.",
        "services": ["General pest control", "Rodent control", "Termite treatment", "Mosquito & tick control"],
        "cards": ["Interior and exterior treatment with a quarterly guarantee.", "Trapping, sealing entry points and follow-up visits.",
                  "Inspections, treatment and protection for your biggest investment.", "Enjoy your yard again all summer long."],
        "cta": "Get a free inspection",
    },
    "tree service": {
        "tagline": "Tree service in {city}, safe and fully insured.",
        "sub": "Trimming, removal, stump grinding and storm cleanup by a licensed crew.",
        "services": ["Tree trimming", "Tree removal", "Stump grinding", "Storm cleanup"],
        "cards": ["Healthier trees and more light, without butchering the shape.", "Dead, leaning or too-close trees taken down safely.",
                  "Stumps ground below grade so you can plant or lay sod.", "Fast response when a storm leaves limbs on your roof."],
        "cta": "Get a free estimate",
    },
    "handyman": {
        "tagline": "Your handyman in {city}. One call, done right.",
        "sub": "Repairs, installs and the to-do list you never get to. Licensed and insured.",
        "services": ["Repairs", "Installations", "Drywall & paint", "Doors, fixtures & more"],
        "cards": ["Leaky faucets, broken fences, squeaky doors, the whole list.", "TVs, shelves, ceiling fans, lights and appliances.",
                  "Holes patched, walls painted, ready for guests.", "If it's on your list, it's probably on ours."],
        "cta": "Get a free quote",
    },
}
ALIASES = {
    "movers": "moving", "moving company": "moving", "junk removal": "moving",
    "lawn care": "landscaping", "lawn mowing": "landscaping", "landscaper": "landscaping",
    "auto detailing": "car detailing", "mobile detailing": "car detailing",
    "upholstery cleaning": "carpet cleaning",
    "exterminator": "pest control",
    "tree removal": "tree service", "tree trimming": "tree service", "arborist": "tree service",
    "power washing": "pressure washing", "soft washing": "roof cleaning",
    "maid service": "house cleaning", "cleaning service": "house cleaning",
}
# fallback quando a vertical não está na tabela: pelo estilo detectado
STYLE_VERTICAL = {"movers": "moving", "pest": "pest control", "tree": "tree service", "carpet": "carpet cleaning",
                  "detailing": "car detailing", "landscaping": "landscaping", "gutter": "gutter cleaning", "handyman": "handyman"}
DEFAULT = {
    "tagline": "{vertical_title} in {city}.",
    "sub": "Local, licensed and insured. Call for a free estimate.",
    "services": ["Free estimates", "Licensed & insured", "Same-week scheduling"],
    "cards": ["Clear pricing before any work starts.", "Fully covered, so you're never on the hook.", "Most jobs booked within the week."],
    "cta": "Get a free quote",
}


def content_for(vertical: str, city: str | None, style: str | None = None, force_style: bool = False) -> dict:
    """Texto pela vertical. `style` é o fallback quando a vertical não está na
    tabela; com force_style (estilo fixado à mão no lead) o estilo manda no
    texto também: um "pressure washing" que na verdade é mudança vira movers."""
    v = (vertical or "").lower().strip()
    key = ALIASES.get(v, v)
    by_style = CONTENT.get(STYLE_VERTICAL.get(style or "", ""))
    c = (by_style if force_style and by_style else None) or CONTENT.get(key) or by_style or DEFAULT
    city = city or "your area"
    services = c["services"]
    cards = [{"title": t, "desc": d} for t, d in zip(services, c.get("cards", []))]
    return {
        "tagline": c["tagline"].format(city=city, vertical_title=(vertical or "Service").title()),
        "sub": c["sub"],
        "services": services,
        "cards": cards,
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
