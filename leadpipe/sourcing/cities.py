"""Lista de cidades por estado (offline, via geonamescache: cidades com
população ≥ 15.000). Sourcing por cidade, não por estado: o Maps satura por
query, então "roof cleaning Ohio" rende muito menos que a soma por cidade."""
from __future__ import annotations

from functools import lru_cache

# geonames usa código FIPS-like para estado dentro de admin1code ("OH").


@lru_cache(maxsize=1)
def _us_cities() -> list[dict]:
    import geonamescache
    gc = geonamescache.GeonamesCache()
    out = []
    for c in gc.get_cities().values():
        if c.get("countrycode") == "US":
            out.append({"name": c["name"], "state": c["admin1code"], "population": c["population"],
                        "lat": c["latitude"], "lng": c["longitude"]})
    return out


def cities_for_state(state: str, min_pop: int = 15_000, limit: int | None = None) -> list[dict]:
    st = state.upper()
    rows = [c for c in _us_cities() if c["state"] == st and c["population"] >= min_pop]
    rows.sort(key=lambda c: -c["population"])
    return rows[:limit] if limit else rows


@lru_cache(maxsize=1)
def _us_counties() -> list[dict]:
    import geonamescache
    return geonamescache.GeonamesCache().get_us_counties()


def counties_for_state(state: str) -> list[str]:
    """Nomes de condado ("Licking County") — cobre a zona rural, onde mais falta site."""
    st = state.upper()
    return sorted(c["name"] for c in _us_counties() if c["state"] == st)


def places_for_state(state: str, by: str = "city", min_pop: int = 15_000, limit: int | None = None) -> list[str]:
    if by == "county":
        out = counties_for_state(state)
        return out[:limit] if limit else out
    return [c["name"] for c in cities_for_state(state, min_pop, limit)]
