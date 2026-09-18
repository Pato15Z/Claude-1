import asyncio
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from leadpipe import db
from leadpipe.enrich.images import save_candidates
from leadpipe.enrich.palette import build_palette, contrast, ensure_contrast
from leadpipe.enrich.site_extract import extract
from leadpipe.sourcing.base import IngestStats, RawLead, ingest_one
from tests.conftest import FIX

IMG = FIX / "img"


def _photo(path: Path, w: int, h: int, color, seed=1):
    """Foto sintética com estrutura diferente por seed (o hash perceptual é em
    cinza, então cor sozinha não distingue duas imagens)."""
    import random
    rnd = random.Random(seed)
    im = Image.new("RGB", (w, h), color)
    d = ImageDraw.Draw(im)
    for _ in range(60):
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        r = rnd.randint(w // 20, w // 4)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255)))
    im.save(path, "JPEG", quality=95)


@pytest.fixture(scope="session", autouse=True)
def fixture_images():
    IMG.mkdir(exist_ok=True)
    _photo(IMG / "before.jpg", 1200, 900, (90, 90, 60), seed=1)
    _photo(IMG / "after.jpg", 1200, 900, (60, 110, 160), seed=2)
    _photo(IMG / "work1.jpg", 1600, 1067, (200, 60, 40), seed=3)
    _photo(IMG / "work1_dup.jpg", 1600, 1067, (200, 60, 40), seed=3)
    _photo(IMG / "small.jpg", 400, 300, (0, 120, 0), seed=4)
    _photo(IMG / "banner.jpg", 3000, 300, (0, 0, 120), seed=5)
    logo = Image.new("RGBA", (300, 120), (0, 0, 0, 0))
    ImageDraw.Draw(logo).rectangle([10, 10, 290, 110], fill=(220, 30, 30, 255))
    logo.save(IMG / "logo.png")
    Image.new("RGB", (32, 32), (0, 0, 0)).save(IMG / "icon-phone.png")


def test_extract_rich_site():
    html = (FIX / "rich_site.html").read_text()
    ex = extract(html, "http://x.test/index.html")
    assert ex.emails[0] == "hello@sunnyroof.com" and "owner@gmail.com" in ex.emails
    assert ex.facebook == "https://www.facebook.com/sunnyroofcleaning"
    assert ex.instagram == "https://instagram.com/sunny.roof"
    urls = [i["url"] for i in ex.images]
    assert "http://x.test/img/before.jpg" in urls and "http://x.test/img/logo.png" not in urls
    assert not any("icon-phone" in u or "tracking" in u for u in urls)
    assert ex.logos == ["http://x.test/img/logo.png"]
    assert ex.contact_links == ["http://x.test/contact.html"]


def test_image_filter(site_server, tmp_path):
    cands = [{"url": f"{site_server}/img/{n}", "alt": a, "source": "site"} for n, a in [
        ("before.jpg", "Roof before cleaning"), ("after.jpg", "after"), ("work1.jpg", "work"),
        ("work1_dup.jpg", "dup"), ("small.jpg", "s"), ("banner.jpg", "b"), ("nope.jpg", "x")]]
    saved, rejected = save_candidates(1, cands, tmp_path / "1")
    kinds = [s.kind for s in saved]
    assert kinds == ["before", "after", "work"]
    assert all(Path(s.path).exists() for s in saved)
    assert any("duplicata" in r for r in rejected) and any("< 800px" in r for r in rejected)
    assert any("proporção" in r for r in rejected) and any("download falhou" in r for r in rejected)


def test_palette_contrast():
    pal = build_palette("roof cleaning", IMG / "logo.png", [])
    assert pal["source"] == "logo"
    assert contrast(pal["primary"], "#ffffff") >= 4.5
    assert contrast(pal["accent"], pal["text_on_accent"]) >= 4.5
    fb = build_palette("window cleaning", None, [])
    assert fb["source"] == "fallback" and contrast(fb["primary"], "#ffffff") >= 4.5
    assert contrast(ensure_contrast("#ffff00", "#ffffff"), "#ffffff") >= 4.5


def test_enrich_runner(con, site_server, monkeypatch):
    from leadpipe import config
    from leadpipe.enrich.runner import run
    monkeypatch.setattr(config, "IMAGES_DIR", config.DATA_DIR / "images")
    lid = ingest_one(con, RawLead(name="Sunny Roof Cleaning", vertical="roof cleaning", source="csv", website_url=f"{site_server}/rich_site.html",
                                  phone_raw="614-555-0199", address_full="1 Sun St, Columbus, OH 43215"), IngestStats())
    db.transition(con, lid, "QUALIFICADO")
    lid2 = ingest_one(con, RawLead(name="No Site Guy", vertical="roof cleaning", source="csv", phone_raw="614-555-0198",
                                   address_full="2 Sun St, Columbus, OH 43215"), IngestStats())
    db.transition(con, lid2, "QUALIFICADO")
    agg = asyncio.run(run(con, web_search=False, gbp=False))
    assert agg["leads"] == 2 and agg["errors"] == 0 and agg["with_3_images"] == 1 and agg["with_email"] == 1
    lead = db.get_lead(con, lid)
    assert lead["status"] == "ENRIQUECIDO" and lead["email"] == "hello@sunnyroof.com" and lead["email_confidence"] == "media"  # host 127.0.0.1 ≠ sunnyroof.com
    assert lead["facebook_url"].endswith("sunnyroofcleaning") and lead["logo_path"] and lead["priority"] == "normal"
    assert json.loads(lead["palette_json"])["source"] == "logo"
    imgs = con.execute("SELECT kind FROM lead_images WHERE lead_id=? ORDER BY id", (lid,)).fetchall()
    assert {r["kind"] for r in imgs} >= {"before", "after", "work", "logo"}
    lead2 = db.get_lead(con, lid2)
    assert lead2["status"] == "ENRIQUECIDO" and lead2["priority"] == "baixa"
