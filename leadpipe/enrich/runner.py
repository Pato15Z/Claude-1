"""Módulo 3: para cada lead QUALIFICADO, reúne email, Facebook/Instagram,
3–6 imagens do trabalho, logo e paleta. Persiste por lead; move para
ENRIQUECIDO. Sem imagem utilizável → priority='baixa' (não descarta).

Fontes de imagem por prioridade: fotos do Google Business Profile → site.
Facebook e Instagram exigem login para ver fotos; ficam de fora (avisado)."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path

from .. import config, db
from ..qualify.classify import is_aggregator
from ..qualify.http_check import check as http_check, host_of
from . import gbp_photos
from .images import save_candidates
from .palette import build_palette
from .site_extract import extract
from .social_search import find_social


def _email_confidence(email: str, site_host: str | None, via_mailto: bool) -> str:
    dom = email.split("@")[-1]
    if via_mailto and site_host and dom.endswith(site_host):
        return "alta"
    if site_host and dom.endswith(site_host):
        return "alta" if via_mailto else "media"
    return "media" if via_mailto else "baixa"


def _from_site(lead: sqlite3.Row) -> dict:
    """Home + até 2 páginas de contato. Retorna emails, sociais, imagens, logos."""
    url = (lead["website_url"] or "").strip()
    out = {"emails": [], "facebook": None, "instagram": None, "images": [], "logos": [], "pages": 0}
    if not url or is_aggregator(url):
        if url and "facebook.com" in url:
            out["facebook"] = url
        if url and "instagram.com" in url:
            out["instagram"] = url
        return out
    r = http_check(url)
    if not r.ok or not r.html:
        return out
    host = host_of(r.final_url or url)
    out["host"] = host
    ex = extract(r.html, r.final_url or url)
    out["pages"] = 1
    out["emails"] = [(e, True) for e in ex.emails[:1]] + [(e, False) for e in ex.emails[1:3]]
    out["facebook"], out["instagram"] = ex.facebook, ex.instagram
    out["images"] = [{**i, "source": "site"} for i in ex.images]
    out["logos"] = ex.logos
    for cu in ex.contact_links[:2]:
        rc = http_check(cu)
        if rc.ok and rc.html:
            out["pages"] += 1
            ex2 = extract(rc.html, rc.final_url or cu)
            for e in ex2.emails:
                if e not in [x for x, _ in out["emails"]]:
                    out["emails"].append((e, True))
            out["facebook"] = out["facebook"] or ex2.facebook
            out["instagram"] = out["instagram"] or ex2.instagram
            out["images"] += [{**i, "source": "site"} for i in ex2.images]
    return out


async def enrich_lead(con: sqlite3.Connection, ctx, lead: sqlite3.Row, sem: asyncio.Semaphore,
                      web_search: bool = True, gbp: bool = True) -> dict:
    notes: list[str] = []
    async with sem:
        site = await asyncio.to_thread(_from_site, lead)
        fields: dict = {}
        # email
        if not lead["email"] and site["emails"]:
            e, via_mailto = site["emails"][0]
            fields.update(email=e, email_source="site", email_confidence=_email_confidence(e, site.get("host"), via_mailto))
        # sociais
        fb = lead["facebook_url"] or site["facebook"]
        ig = lead["instagram_url"] or site["instagram"]
        if web_search and (not fb or not ig):
            found = await asyncio.to_thread(find_social, lead["name"], lead["city"], lead["state"], not fb, not ig)
            fb = fb or found.get("facebook_url"); ig = ig or found.get("instagram_url")
            if found:
                notes.append(f"social via busca: {list(found)}")
        if fb: fields["facebook_url"] = fb
        if ig: fields["instagram_url"] = ig
        # imagens: GBP primeiro, depois site
        candidates: list[dict] = []
        if gbp and ctx is not None and lead["gbp_url"]:
            urls = await gbp_photos.collect(ctx, lead["gbp_url"])
            candidates += [{"url": u, "alt": "gbp photo", "source": "gbp"} for u in urls]
            notes.append(f"gbp: {len(urls)} fotos")
        candidates += site["images"]
        img_dir = config.IMAGES_DIR / str(lead["id"])
        saved, rejected = await asyncio.to_thread(save_candidates, lead["id"], candidates, img_dir, None, False, config.ENRICH_MAX_IMAGES)
        logos, _ = await asyncio.to_thread(save_candidates, lead["id"], [{"url": u, "alt": "logo", "source": "site"} for u in site["logos"][:3]], img_dir, None, True, 1)
        notes.append(f"imagens: {len(saved)} ok / {len(rejected)} rejeitadas de {len(candidates)}")
        # paleta
        pal = build_palette(lead["vertical"], Path(logos[0].path) if logos else None, [Path(s.path) for s in saved])
        fields["palette_json"] = json.dumps(pal)
        if logos:
            fields["logo_path"] = logos[0].path
        fields["priority"] = "normal" if saved else "baixa"
        fields["enriched_at"] = db.now_iso()
        fields["enrich_notes"] = "; ".join(notes)[:500]
    with db.tx(con):
        con.execute("DELETE FROM lead_images WHERE lead_id=?", (lead["id"],))
        for s in saved + logos:
            con.execute("INSERT INTO lead_images (lead_id, path, source, width, height, kind, score, created_at) VALUES (?,?,?,?,?,?,?,?)",
                        (lead["id"], s.path, s.source, s.width, s.height, s.kind, s.score, db.now_iso()))
        db.update_lead(con, lead["id"], **fields)
    db.transition(con, lead["id"], "ENRIQUECIDO", note=f"{len(saved)} imagens, email={'sim' if fields.get('email') or lead['email'] else 'não'}")
    return {"images": len(saved), "email": bool(fields.get("email") or lead["email"]), "fb": bool(fb), "logo": bool(logos)}


async def run(con: sqlite3.Connection, limit: int | None = None, redo: bool = False, web_search: bool | None = None,
              gbp: bool = True, progress=None, site_status: str | None = None) -> dict:
    from playwright.async_api import async_playwright

    web_search = config.ENRICH_WEB_SEARCH if web_search is None else web_search
    st = "('QUALIFICADO','ENRIQUECIDO')" if redo else "('QUALIFICADO')"
    sql = f"SELECT * FROM leads WHERE status IN {st}"
    if site_status:
        sql += f" AND site_status='{site_status}'"
    sql += " ORDER BY CASE site_status WHEN 'SEM_SITE' THEN 0 ELSE 1 END, id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    leads = con.execute(sql).fetchall()
    if not leads:
        return {}
    config.ensure_dirs()
    run_id = db.start_run(con, "enrich", f"n={len(leads)}")
    t0 = time.time()
    agg = {"leads": 0, "with_3_images": 0, "with_email": 0, "with_fb": 0, "errors": 0}
    sem = asyncio.Semaphore(config.ENRICH_CONCURRENCY)
    async with async_playwright() as pw:
        browser = None; ctx = None
        if gbp:
            kwargs = {"headless": True}
            if config.CHROMIUM_PATH:
                kwargs["executable_path"] = config.CHROMIUM_PATH
            browser = await pw.chromium.launch(**kwargs)
            ctx = await browser.new_context(locale="en-US")
        try:
            async def one(lead):
                try:
                    r = await enrich_lead(con, ctx, lead, sem, web_search, gbp)
                    agg["leads"] += 1
                    agg["with_3_images"] += r["images"] >= 3
                    agg["with_email"] += r["email"]
                    agg["with_fb"] += r["fb"]
                except Exception as e:
                    agg["errors"] += 1
                    r = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
                    db.update_lead(con, lead["id"], enrich_notes=r["error"])
                if progress:
                    progress(lead, r)
            await asyncio.gather(*(one(l) for l in leads))
        finally:
            if browser:
                await browser.close()
    db.finish_run(con, run_id, processed=len(leads), produced=agg["leads"], errors=agg["errors"], notes=json.dumps(agg))
    agg["_elapsed_s"] = round(time.time() - t0, 1)
    return agg
