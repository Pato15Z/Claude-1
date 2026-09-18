"""Entrada manual: CSV com cabeçalho livre (mapeado por nome de coluna) ou
um lead avulso pela CLI. Tudo cai no mesmo ingest, mesmo dedup, mesma fila."""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from .base import IngestStats, RawLead, ingest_one

# aliases aceitos no cabeçalho → campo do RawLead
_ALIASES = {
    "name": ["name", "business", "business_name", "nome", "title"],
    "phone_raw": ["phone", "phone_raw", "telefone", "tel"],
    "address_full": ["address", "address_full", "endereco", "endereço", "full_address"],
    "city": ["city", "cidade"],
    "state": ["state", "estado", "uf"],
    "zip": ["zip", "zipcode", "postal_code", "cep"],
    "lat": ["lat", "latitude"],
    "lng": ["lng", "lon", "longitude"],
    "category": ["category", "categoria", "main_category"],
    "website_url": ["website", "website_url", "site", "url"],
    "gbp_url": ["gbp_url", "google_url", "maps_url", "link"],
    "gbp_place_id": ["place_id", "gbp_place_id", "cid"],
    "rating": ["rating", "nota", "review_rating"],
    "review_count": ["reviews", "review_count", "reviews_count"],
    "facebook_url": ["facebook", "facebook_url", "fb"],
    "instagram_url": ["instagram", "instagram_url", "ig"],
    "email": ["email", "e-mail"],
    "vertical": ["vertical", "query", "keyword"],
}


def _pick(row: dict, field: str) -> str | None:
    for alias in _ALIASES[field]:
        for k in row:
            if k and k.strip().lower() == alias:
                v = row[k]
                return v.strip() if isinstance(v, str) and v.strip() else None
    return None


def _num(v: str | None, cast):
    if v is None:
        return None
    try:
        return cast(v.replace(",", "."))
    except ValueError:
        return None


def import_csv(con: sqlite3.Connection, path: Path, vertical: str | None, source_query: str | None = None) -> IngestStats:
    stats = IngestStats()
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            v = vertical or _pick(row, "vertical")
            if not v:
                raise ValueError("CSV sem coluna 'vertical' e --vertical não informado")
            raw = RawLead(
                name=_pick(row, "name") or "",
                vertical=v,
                source="csv",
                source_query=source_query or f"csv:{path.name}",
                phone_raw=_pick(row, "phone_raw"),
                address_full=_pick(row, "address_full"),
                city=_pick(row, "city"),
                state=_pick(row, "state"),
                zip=_pick(row, "zip"),
                lat=_num(_pick(row, "lat"), float),
                lng=_num(_pick(row, "lng"), float),
                category=_pick(row, "category"),
                website_url=_pick(row, "website_url"),
                gbp_url=_pick(row, "gbp_url"),
                gbp_place_id=_pick(row, "gbp_place_id"),
                rating=_num(_pick(row, "rating"), float),
                review_count=_num(_pick(row, "review_count"), int),
                facebook_url=_pick(row, "facebook_url"),
                instagram_url=_pick(row, "instagram_url"),
                email=_pick(row, "email"),
            )
            ingest_one(con, raw, stats)
    return stats
