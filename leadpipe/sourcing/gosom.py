"""Ingestão do JSON gerado por gosom/google-maps-scraper (Go, open source,
self-hosted). Plano B se o scraper Playwright quebrar por mudança de DOM:
    docker run -v $PWD:/data gosom/google-maps-scraper -input /data/queries.txt -results /data/out.json -json -exit-on-inactivity 3m
Cada linha do arquivo é um objeto JSON (JSONL) com os campos abaixo."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .base import IngestStats, RawLead, ingest_one


def import_gosom(con: sqlite3.Connection, path: Path, vertical: str) -> IngestStats:
    stats = IngestStats()
    text = path.read_text(encoding="utf-8")
    items: list[dict]
    if text.lstrip().startswith("["):
        items = json.loads(text)
    else:
        items = [json.loads(l) for l in text.splitlines() if l.strip()]
    for it in items:
        addr = it.get("address") or ""
        if isinstance(addr, dict):
            addr = ", ".join(str(addr.get(k, "")) for k in ("street", "city", "state", "postal_code") if addr.get(k))
        raw = RawLead(
            name=it.get("title") or it.get("name") or "",
            vertical=vertical,
            source="gosom",
            source_query=it.get("input_id") or it.get("query"),
            phone_raw=it.get("phone"),
            address_full=addr or None,
            lat=it.get("latitude"),
            lng=it.get("longitude"),
            category=it.get("category") or (it.get("categories") or [None])[0],
            website_url=it.get("website") or None,
            gbp_url=it.get("link"),
            gbp_place_id=it.get("place_id") or it.get("cid"),
            rating=it.get("review_rating"),
            review_count=it.get("review_count"),
            email=(it.get("emails") or [None])[0] if isinstance(it.get("emails"), list) else it.get("emails"),
        )
        ingest_one(con, raw, stats)
    return stats
