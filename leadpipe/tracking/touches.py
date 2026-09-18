"""Registro de toques e fila diária.

Regras da sequência (config.TOUCH_SCHEDULE): dia relativo ao toque 1.
Um lead entra na fila quando está HERO_PRONTO (toque 1 devido) ou ENVIADO
(toques 2-4). Sai da fila ao responder (RESPONDEU+) ou ao completar 4 toques.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .. import config, db


def log_touch(con: sqlite3.Connection, lead_id: int, touch_number: int, channel: str,
              template: str | None = None, content: str | None = None, notes: str | None = None,
              sent_at: str | None = None) -> int:
    if channel not in db.CHANNELS:
        raise ValueError(f"canal inválido: {channel} (use {', '.join(db.CHANNELS)})")
    lead = db.get_lead(con, lead_id)
    if lead is None:
        raise KeyError(f"lead {lead_id} não existe")
    ts = sent_at or db.now_iso()
    cur = con.execute(
        "INSERT INTO touches (lead_id, touch_number, channel, sent_at, template, content, notes) VALUES (?,?,?,?,?,?,?)",
        (lead_id, touch_number, channel, ts, template, content, notes),
    )
    if lead["status"] in ("QUALIFICADO", "ENRIQUECIDO", "HERO_PRONTO"):
        db.transition(con, lead_id, "ENVIADO", note=f"toque {touch_number} via {channel}", at=ts)
    return int(cur.lastrowid)


def log_reply(con: sqlite3.Connection, lead_id: int, touch_number: int | None = None,
              replied_at: str | None = None, notes: str | None = None) -> int:
    """Marca resposta no toque indicado (ou no último enviado) e move para RESPONDEU."""
    ts = replied_at or db.now_iso()
    if touch_number is None:
        row = con.execute("SELECT touch_number FROM touches WHERE lead_id=? ORDER BY touch_number DESC LIMIT 1",
                          (lead_id,)).fetchone()
        if row is None:
            raise ValueError("lead sem toque registrado; informe --n")
        touch_number = row["touch_number"]
    con.execute("UPDATE touches SET replied_at=?, notes=COALESCE(?, notes) WHERE lead_id=? AND touch_number=?",
                (ts, notes, lead_id, touch_number))
    db.transition(con, lead_id, "RESPONDEU", note=f"resposta ao toque {touch_number}", at=ts)
    return touch_number


@dataclass
class QueueItem:
    lead_id: int
    name: str
    city: str | None
    state: str | None
    tz: str
    local_now: str
    utc_offset_h: float
    touch_number: int
    channel: str
    due_date: date
    days_overdue: int
    phone: str | None
    email: str | None
    facebook_url: str | None
    instagram_url: str | None
    hero_url: str | None
    status: str


def _local(dt_iso: str, tz: ZoneInfo) -> datetime:
    dt = datetime.fromisoformat(dt_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def daily_queue(con: sqlite3.Connection, today: date | None = None, include_future_days: int = 0) -> list[QueueItem]:
    """Leads devidos hoje (ou atrasados), ordenados do fuso mais adiantado para o
    mais atrasado (leste → oeste), para o envio das 6h ir na ordem certa."""
    now_utc = datetime.now(timezone.utc)
    rows = con.execute(
        "SELECT * FROM leads WHERE status IN ('HERO_PRONTO','ENVIADO') ORDER BY id").fetchall()
    items: list[QueueItem] = []
    for lead in rows:
        tzname = lead["timezone"] or "America/New_York"
        try:
            tz = ZoneInfo(tzname)
        except Exception:
            tz = ZoneInfo("America/New_York")
        local_now = now_utc.astimezone(tz)
        today_local = today or local_now.date()
        touches = con.execute("SELECT touch_number, sent_at, replied_at FROM touches WHERE lead_id=? ORDER BY touch_number",
                              (lead["id"],)).fetchall()
        if any(t["replied_at"] for t in touches):
            continue
        done = {t["touch_number"] for t in touches}
        nxt = max(done) + 1 if done else 1
        if nxt > 4:
            continue
        if nxt == 1:
            due = today_local
        else:
            t1 = next((t for t in touches if t["touch_number"] == 1), None)
            if t1 is None:
                due = today_local
            else:
                due = _local(t1["sent_at"], tz).date() + timedelta(days=config.TOUCH_SCHEDULE[nxt]["day"])
        if due > today_local + timedelta(days=include_future_days):
            continue
        offset = local_now.utcoffset() or timedelta(0)
        items.append(QueueItem(
            lead_id=lead["id"], name=lead["name"], city=lead["city"], state=lead["state"], tz=tzname,
            local_now=local_now.strftime("%H:%M"), utc_offset_h=offset.total_seconds() / 3600,
            touch_number=nxt, channel=config.TOUCH_SCHEDULE[nxt]["channel"], due_date=due,
            days_overdue=(today_local - due).days, phone=lead["phone_e164"], email=lead["email"],
            facebook_url=lead["facebook_url"], instagram_url=lead["instagram_url"], hero_url=lead["hero_url"],
            status=lead["status"],
        ))
    items.sort(key=lambda i: (-i.utc_offset_h, i.touch_number, -i.days_overdue, i.lead_id))
    return items
