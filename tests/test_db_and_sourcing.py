from pathlib import Path

from leadpipe import db
from leadpipe.sourcing.base import IngestStats, RawLead, ingest_one
from leadpipe.sourcing.csv_import import import_csv
from leadpipe.sourcing.google_maps import parse_card_text, _place_id, _coords


def _raw(**kw):
    base = dict(name="Bob's Roof Cleaning", vertical="roof cleaning", source="google_maps", source_query="roof cleaning Columbus OH",
                phone_raw="(614) 555-0100", address_full="123 Main St, Columbus, OH 43215, United States", lat=39.96, lng=-82.99)
    base.update(kw)
    return RawLead(**base)


def test_ingest_dedup_by_phone_then_address(con):
    st = IngestStats()
    a = ingest_one(con, _raw(), st)
    b = ingest_one(con, _raw(name="Bobs Roof Cleaning LLC", phone_raw="614.555.0100", address_full=None, website_url="https://bobs.example"), st)
    c = ingest_one(con, _raw(phone_raw=None, address_full="123 Main Street, Columbus, OH 43215"), st)
    d = ingest_one(con, _raw(phone_raw="614-555-0199", address_full="9 Elm St, Dayton, OH 45402"), st)
    assert a == b == c and d != a
    assert st.inserted == 2 and st.duplicates == 2
    lead = db.get_lead(con, a)
    assert lead["website_url"] == "https://bobs.example"  # duplicata preencheu campo vazio
    assert lead["name"] == "Bob's Roof Cleaning"          # mas não sobrescreveu
    assert lead["timezone"] == "America/New_York" and lead["city"] == "Columbus" and lead["zip"] == "43215"
    assert lead["status"] == "NOVO"
    hist = con.execute("SELECT * FROM lead_status_history WHERE lead_id=?", (a,)).fetchall()
    assert len(hist) == 1 and hist[0]["to_status"] == "NOVO"


def test_transition_history_never_overwritten(con):
    lid = ingest_one(con, _raw(), IngestStats())
    assert db.transition(con, lid, "QUALIFICADO", "sem site")
    assert not db.transition(con, lid, "QUALIFICADO")
    db.transition(con, lid, "HERO_PRONTO")
    hist = [h["to_status"] for h in con.execute("SELECT * FROM lead_status_history WHERE lead_id=? ORDER BY id", (lid,))]
    assert hist == ["NOVO", "QUALIFICADO", "HERO_PRONTO"]
    assert db.get_lead(con, lid)["status"] == "HERO_PRONTO"


def test_csv_import(con, tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("Business,Phone,Address,Website,Rating,Reviews\n"
                 "Ace Wash,(937) 555-0102,\"9 Elm St, Dayton, OH 45402\",facebook.com/acewash,4.9,12\n"
                 "No Name Corp,,,,,\n", encoding="utf-8")
    st = import_csv(con, p, vertical="pressure washing")
    assert st.inserted == 2 and st.found == 2
    lead = con.execute("SELECT * FROM leads WHERE name='Ace Wash'").fetchone()
    assert lead["phone_e164"] == "+19375550102" and lead["state"] == "OH" and lead["review_count"] == 12


def test_parse_card_text():
    txt = "Bob's Roof Cleaning\n4.8(132)\nRoof cleaning service · 123 Main St\nOpen ⋅ Closes 6 PM\n(614) 555-0100\n"
    p = parse_card_text(txt)
    assert p["rating"] == 4.8 and p["review_count"] == 132
    assert p["category"] == "Roof cleaning service" and p["street"] == "123 Main St"
    assert p["phone"] == "(614) 555-0100"
    txt2 = "X\n4.5 stars 20 Reviews\nPressure washing service · Serves Columbus\n"
    p2 = parse_card_text(txt2)
    assert p2["rating"] == 4.5 and p2["review_count"] == 20


def test_href_parsing():
    href = "https://www.google.com/maps/place/Bob/data=!4m7!3m6!1s0x8838f1a2b3c4d5e6:0x1a2b3c4d5e6f7a8b!8m2!3d39.961176!4d-82.998794!16s"
    assert _place_id(href) == "0x8838f1a2b3c4d5e6:0x1a2b3c4d5e6f7a8b"
    assert _coords(href) == (39.961176, -82.998794)


def test_auto_qualify_no_site(con):
    from leadpipe.qualify.runner import auto_qualify_no_site
    a = ingest_one(con, _raw(website_url=None), IngestStats())
    b = ingest_one(con, _raw(phone_raw="614-555-0777", address_full="7 Elm St, Dayton, OH 45402", website_url="https://facebook.com/x"), IngestStats())
    c = ingest_one(con, _raw(phone_raw="614-555-0888", address_full="8 Elm St, Dayton, OH 45402", website_url="https://real.example"), IngestStats())
    assert auto_qualify_no_site(con, a) and auto_qualify_no_site(con, b) and not auto_qualify_no_site(con, c)
    assert db.get_lead(con, a)["status"] == "QUALIFICADO" and db.get_lead(con, a)["site_status"] == "SEM_SITE"
    assert db.get_lead(con, b)["site_status"] == "SEM_SITE" and db.get_lead(con, c)["status"] == "NOVO"
    assert not auto_qualify_no_site(con, a)  # já qualificado: não repete


def test_places_for_state():
    from leadpipe.sourcing.cities import places_for_state
    counties = places_for_state("OH", "county")
    assert len(counties) == 88 and "Licking County" in counties
    assert len(places_for_state("OH", "city", 20000)) > 50


def test_geo_fence():
    from leadpipe.sourcing.geo import accept, in_state, is_us_phone, state_center
    assert in_state(39.96, -82.99, "OH") is True and in_state(-23.5, -46.6, "OH") is False and in_state(None, None, "OH") is None
    assert is_us_phone("614-555-0100") is True
    assert is_us_phone("43 3329-8894") is False          # DDD brasileiro parseado como EUA: área 433 não existe
    assert is_us_phone("+55 11 99999-0000") is False
    assert accept(-23.5, -46.6, None, "OH") == (False, "fora do estado")
    assert accept(None, None, "4333298894", "OH")[0] is False
    assert accept(40.4, -82.9, "216-555-0100", "OH")[0] is True
    lat, lng = state_center("OH"); assert 39 < lat < 41 and -84 < lng < -81
