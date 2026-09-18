"""Contrato comum de sourcing: qualquer provedor produz RawLead; o ingest
normaliza, deduplica e persiste um a um."""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any

from .. import db
from ..normalize import address_norm, phone_e164, split_us_address, timezone_for


@dataclass
class RawLead:
    name: str
    vertical: str
    source: str
    source_query: str | None = None
    phone_raw: str | None = None
    address_full: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    lat: float | None = None
    lng: float | None = None
    category: str | None = None
    website_url: str | None = None
    gbp_url: str | None = None
    gbp_place_id: str | None = None
    rating: float | None = None
    review_count: int | None = None
    last_review_at: str | None = None
    facebook_url: str | None = None
    instagram_url: str | None = None
    email: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestStats:
    found: int = 0
    inserted: int = 0
    duplicates: int = 0
    filled: int = 0  # campos preenchidos em duplicatas
    skipped: int = 0  # sem nome


def to_row(raw: RawLead) -> dict[str, Any]:
    parts = split_us_address(raw.address_full)
    city = raw.city or parts["city"]
    state = (raw.state or parts["state"] or "").upper() or None
    row = {
        "name": raw.name.strip(),
        "phone_raw": raw.phone_raw,
        "phone_e164": phone_e164(raw.phone_raw),
        "address_full": raw.address_full,
        "address_norm": address_norm(raw.address_full),
        "street": parts["street"],
        "city": city,
        "state": state,
        "zip": raw.zip or parts["zip"],
        "lat": raw.lat,
        "lng": raw.lng,
        "category": raw.category,
        "vertical": raw.vertical,
        "website_url": raw.website_url,
        "gbp_url": raw.gbp_url,
        "gbp_place_id": raw.gbp_place_id,
        "rating": raw.rating,
        "review_count": raw.review_count,
        "last_review_at": raw.last_review_at,
        "facebook_url": raw.facebook_url,
        "instagram_url": raw.instagram_url,
        "email": raw.email,
        "timezone": timezone_for(raw.lat, raw.lng, state),
        "source": raw.source,
        "source_query": raw.source_query,
    }
    return row


def ingest_one(con: sqlite3.Connection, raw: RawLead, stats: IngestStats) -> int | None:
    """Persiste um lead imediatamente. Retorna id (novo ou existente) ou None se ignorado."""
    stats.found += 1
    if not raw.name or not raw.name.strip():
        stats.skipped += 1
        return None
    row = to_row(raw)
    dup = db.find_duplicate(con, row["phone_e164"], row["address_norm"], row["gbp_place_id"])
    if dup:
        stats.duplicates += 1
        stats.filled += db.merge_missing(con, dup["id"], row)
        return int(dup["id"])
    lead_id = db.insert_lead(con, row)
    stats.inserted += 1
    return lead_id


def record_query(con: sqlite3.Connection, query: str, vertical: str, city: str | None,
                 state: str | None, stats: IngestStats, elapsed_s: float, error: str | None = None) -> None:
    con.execute(
        "INSERT INTO source_queries (query, vertical, city, state, ran_at, found, inserted, duplicates, elapsed_s, error)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (query, vertical, city, state, db.now_iso(), stats.found, stats.inserted, stats.duplicates,
         round(elapsed_s, 1), error),
    )


def raw_as_dict(raw: RawLead) -> dict[str, Any]:
    return asdict(raw)
