import asyncio
from datetime import date, timedelta
from pathlib import Path

from leadpipe import config, db
from leadpipe.hero.build import build, expire, render, hero_data
from leadpipe.sourcing.base import IngestStats, RawLead, ingest_one
from leadpipe.tracking.templates import render as render_touch


def _enriched(con, name, phone, with_images=True):
    lid = ingest_one(con, RawLead(name=name, vertical="roof cleaning", source="csv", phone_raw=phone, city="Columbus", state="OH",
                                  address_full=f"{phone} St, Columbus, OH 43215", rating=4.8, review_count=57), IngestStats())
    db.transition(con, lid, "QUALIFICADO")
    if with_images:
        from tests.test_enrich import IMG
        for f, kind in [("before.jpg", "before"), ("after.jpg", "after"), ("work1.jpg", "work")]:
            con.execute("INSERT INTO lead_images (lead_id, path, source, width, height, kind, score, created_at) VALUES (?,?,?,?,?,?,?,?)",
                        (lid, str(IMG / f), "site", 1200, 900, kind, 1.0, db.now_iso()))
        con.execute("INSERT INTO lead_images (lead_id, path, source, width, height, kind, score, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (lid, str(IMG / "logo.png"), "site", 300, 120, "logo", 1.0, db.now_iso()))
        db.update_lead(con, lid, priority="normal")
    else:
        db.update_lead(con, lid, priority="baixa")
    db.transition(con, lid, "ENRIQUECIDO")
    return lid


def test_build_and_slug_dedup(con, monkeypatch):
    monkeypatch.setattr(config, "HERO_SITE_DIR", config.DATA_DIR / "hero_site")
    monkeypatch.setattr(config, "HERO_DOMAIN", "heros.test")
    a = _enriched(con, "Bob's Roof Cleaning", "614-555-0101")
    b = _enriched(con, "Bob's Roof Cleaning", "614-555-0102")
    c = _enriched(con, "No Pics LLC", "614-555-0103", with_images=False)
    r = build(con)
    assert r["built"] == 2 and r["errors"] == 0
    la, lb, lc = (db.get_lead(con, x) for x in (a, b, c))
    assert la["slug"] == "bob-s-roof-cleaning-columbus" and lb["slug"] == "bob-s-roof-cleaning-columbus-2"
    assert la["hero_url"] == "https://bob-s-roof-cleaning-columbus.heros.test" and la["status"] == "HERO_PRONTO"
    assert lc["status"] == "ENRIQUECIDO"  # prioridade baixa não entra sem --include-low
    html = Path(la["hero_path"], "index.html").read_text()
    assert 'href="tel:+16145550101"' in html and "Bob&#39;s Roof Cleaning" in html and "Before" in html and "4.8" in html
    assert (Path(la["hero_path"]) / "img" / "before.jpg").exists() and (Path(la["hero_path"]) / "hero.json").exists()
    assert (config.HERO_SITE_DIR / "vercel.json").exists()
    r2 = build(con, include_low_priority=True)
    assert r2["built"] == 1 and db.get_lead(con, c)["status"] == "HERO_PRONTO"
    assert "img gen" in Path(db.get_lead(con, c)["hero_path"], "index.html").read_text()


def test_hero_passes_own_mobile_check(con, monkeypatch, site_server):
    """O hero tem que passar no mesmo critério que usamos para reprovar o site do lead."""
    monkeypatch.setattr(config, "HERO_SITE_DIR", config.DATA_DIR / "hero_site")
    monkeypatch.setattr(config, "HERO_DOMAIN", "heros.test")
    a = _enriched(con, "Bob's Roof Cleaning", "614-555-0101")
    build(con)
    lead = db.get_lead(con, a)
    from leadpipe.qualify.render_check import new_browser, render as mobile_render
    from leadpipe.qualify.signals import detect
    from playwright.async_api import async_playwright

    async def go():
        async with async_playwright() as pw:
            b = await new_browser(pw)
            try:
                return await mobile_render(b, Path(lead["hero_path"], "index.html").as_uri(), config.DATA_DIR / "hero_shot.png")
            finally:
                await b.close()
    res = asyncio.run(go())
    assert res.ok and res.broken_reasons == [], res.metrics
    assert res.metrics["ctaOk"] >= 2 and res.metrics["overflowPx"] <= 0
    sig = detect(res.html, https_ok=True, bad_cert=False)
    assert sig.count == 0, sig.fired


def test_expire(con, monkeypatch):
    monkeypatch.setattr(config, "HERO_SITE_DIR", config.DATA_DIR / "hero_site")
    a = _enriched(con, "Old Hero", "614-555-0111")
    build(con)
    db.transition(con, a, "ENVIADO")
    db.update_lead(con, a, hero_expires_at=(date.today() - timedelta(days=1)).isoformat())
    path = db.get_lead(con, a)["hero_path"]
    assert expire(con, dry_run=True) and Path(path).exists()
    gone = expire(con)
    assert gone[0]["id"] == a and not Path(path).exists()
    lead = db.get_lead(con, a)
    assert lead["status"] == "PERDIDO" and lead["hero_url"] is None


def test_touch_templates(con):
    a = _enriched(con, "Bob's Roof Cleaning", "614-555-0101")
    db.update_lead(con, a, hero_url="https://bobs.heros.test", site_status="SEM_SITE")
    lead = db.get_lead(con, a)
    for n in (1, 2, 3, 4):
        d = render_touch(n, lead, "2026-09-20", {"sender_name": "Pato"})
        assert "https://bobs.heros.test" in d["body"] and "{" not in d["body"]
    d1 = render_touch(1, lead)
    assert "Hi there" in d1["body"] and "don't have a website" in d1["body"] and "4.8 stars from 57 reviews" in d1["body"]
