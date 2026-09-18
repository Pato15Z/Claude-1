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
