"""Orquestra a qualificação em paralelo com pool limitado. Persiste lead a lead."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time

from .. import config, db
from .classify import Verdict, classify, classify_no_site, is_aggregator
from .http_check import check as http_check
from .render_check import new_browser, render
from .signals import detect


def _apply(con: sqlite3.Connection, lead_id: int, v: Verdict, url: str | None, http=None,
           screenshot: str | None = None) -> None:
    ts = db.now_iso()
    with db.tx(con):
        con.execute(
            "INSERT INTO site_checks (lead_id, checked_at, url, final_url, http_status, elapsed_ms, site_status, reason, signals_json, screenshot_path)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (lead_id, ts, url, getattr(http, "final_url", None), getattr(http, "status", None),
             getattr(http, "elapsed_ms", None), v.site_status, v.reason, json.dumps(v.signals, default=str), screenshot),
        )
        con.execute(
            "UPDATE leads SET site_status=?, site_reason=?, site_checked_at=?, screenshot_path=COALESCE(?, screenshot_path), updated_at=? WHERE id=?",
            (v.site_status, v.reason, ts, screenshot, ts, lead_id),
        )
    target = "QUALIFICADO" if v.site_status in db.SITE_STATES_QUALIFIED else "DESCARTADO"
    db.transition(con, lead_id, target, note=f"{v.site_status}: {v.reason}"[:300])


async def qualify_lead(con: sqlite3.Connection, browser, lead: sqlite3.Row, sem: asyncio.Semaphore) -> str:
    url = (lead["website_url"] or "").strip() or None
    if not url or is_aggregator(url):
        v = classify_no_site(url)
        _apply(con, lead["id"], v, url)
        return v.site_status
    async with sem:
        http = await asyncio.to_thread(http_check, url)
        rend = None
        sig = None
        shot = None
        if http.ok:
            shot_path = config.SCREENSHOT_DIR / f"{lead['id']}.png"
            rend = await render(browser, http.final_url or http.url or url, shot_path)
            shot = rend.screenshot_path
            html = rend.html or http.html or ""
            jq = (rend.metrics or {}).get("jquery")
            sig = detect(html, https_ok=http.https and not http.bad_cert, bad_cert=http.bad_cert, jquery_version=jq)
        v = classify(http, rend, sig)
    _apply(con, lead["id"], v, url, http, shot)
    return v.site_status


async def run(con: sqlite3.Connection, limit: int | None = None, recheck: bool = False,
              vertical: str | None = None, state: str | None = None, progress=None) -> dict:
    from playwright.async_api import async_playwright

    where = ["status = 'NOVO'"] if not recheck else ["status IN ('NOVO','QUALIFICADO','DESCARTADO')"]
    args: list = []
    if vertical:
        where.append("vertical=?"); args.append(vertical)
    if state:
        where.append("state=?"); args.append(state.upper())
    sql = f"SELECT * FROM leads WHERE {' AND '.join(where)} ORDER BY id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    leads = con.execute(sql, args).fetchall()
    counts: dict[str, int] = {}
    if not leads:
        return counts
    config.ensure_dirs()
    run_id = db.start_run(con, "qualify", f"n={len(leads)} recheck={recheck}")
    t0 = time.time()
    errors = 0
    sem = asyncio.Semaphore(config.QUALIFY_CONCURRENCY)
    async with async_playwright() as pw:
        browser = await new_browser(pw)
        try:
            async def one(lead):
                nonlocal errors
                try:
                    st = await qualify_lead(con, browser, lead, sem)
                except Exception as e:  # nunca derruba o batch
                    errors += 1
                    st = "SITE_QUEBRADO"
                    _apply(con, lead["id"], Verdict(st, f"erro interno: {type(e).__name__}: {str(e)[:150]}"), lead["website_url"])
                counts[st] = counts.get(st, 0) + 1
                if progress:
                    progress(lead, st)
            await asyncio.gather(*(one(l) for l in leads))
        finally:
            await browser.close()
    db.finish_run(con, run_id, processed=len(leads),
                  produced=sum(v for k, v in counts.items() if k in db.SITE_STATES_QUALIFIED),
                  errors=errors, notes=json.dumps(counts))
    counts["_elapsed_s"] = round(time.time() - t0, 1)
    return counts
