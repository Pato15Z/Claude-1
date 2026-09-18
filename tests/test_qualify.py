import asyncio

import pytest

from leadpipe import db
from leadpipe.qualify.classify import classify_no_site, is_aggregator
from leadpipe.qualify.http_check import check
from leadpipe.qualify.signals import detect
from leadpipe.sourcing.base import IngestStats, RawLead, ingest_one
from tests.conftest import FIX


def test_aggregator_detection():
    assert is_aggregator("https://www.facebook.com/bobsroof") == "facebook.com"
    assert is_aggregator("m.facebook.com/x") == "facebook.com"
    assert is_aggregator("https://bobsroof.com") is None
    assert classify_no_site(None).site_status == "SEM_SITE"
    assert "yelp" in classify_no_site("https://yelp.com/biz/x").reason


def test_signals_old_site():
    html = (FIX / "old_site.html").read_text()
    rep = detect(html, https_ok=False, bad_cert=False)
    assert {"no_viewport", "no_https", "table_layout", "jquery_lt2", "old_copyright", "legacy_builder", "no_tel_link"} <= set(rep.fired)
    assert rep.fired["legacy_builder"] == "dreamweaver"
    assert rep.fired["old_copyright"] == "© 2011"


def test_signals_ok_site():
    html = (FIX / "ok_site.html").read_text()
    rep = detect(html, https_ok=True, bad_cert=False)
    assert rep.count == 0  # "© 2015-2025" pega o maior ano


def test_http_check_dns_fail():
    r = check("https://this-domain-does-not-exist-abcxyz.invalid")
    assert not r.ok and r.error == "dns"


def test_http_check_local(site_server):
    r = check(f"{site_server}/ok_site.html")
    assert r.ok and r.status == 200 and not r.https and r.html and "Modern Gutter" in r.html
    r404 = check(f"{site_server}/nope.html")
    assert not r404.ok and r404.error == "http_4xx" and r404.status == 404


def _add(con, name, url):
    return ingest_one(con, RawLead(name=name, vertical="roof cleaning", source="csv", website_url=url,
                                   address_full=f"{name} St, Columbus, OH 43215"), IngestStats())


def test_full_qualification_pipeline(con, site_server):
    from leadpipe.qualify.runner import run
    ids = {
        "old": _add(con, "Old", f"{site_server}/old_site.html"),
        "broken": _add(con, "Broken", f"{site_server}/broken_mobile.html"),
        "ok": _add(con, "Ok", f"{site_server}/ok_site.html"),
        "missing": _add(con, "Missing", f"{site_server}/missing.html"),
        "fb": _add(con, "Fb", "https://facebook.com/fbonly"),
        "none": _add(con, "None", None),
    }
    counts = asyncio.run(run(con))
    got = {k: db.get_lead(con, v) for k, v in ids.items()}
    assert got["old"]["site_status"] == "SITE_ANTIGO" and got["old"]["status"] == "QUALIFICADO"
    assert got["broken"]["site_status"] == "SITE_QUEBRADO" and "overflow" in got["broken"]["site_reason"]
    assert got["ok"]["site_status"] == "SITE_OK" and got["ok"]["status"] == "DESCARTADO"
    assert got["missing"]["site_status"] == "SITE_QUEBRADO" and "404" in got["missing"]["site_reason"]
    assert got["fb"]["site_status"] == "SEM_SITE" and got["none"]["site_status"] == "SEM_SITE"
    for k in ("old", "broken", "ok"):
        assert got[k]["screenshot_path"] and got[k]["screenshot_path"].endswith(f"{ids[k]}.png")
    assert counts["SEM_SITE"] == 2 and counts["SITE_QUEBRADO"] == 2
    assert con.execute("SELECT COUNT(*) FROM site_checks").fetchone()[0] == 6
    run_row = con.execute("SELECT * FROM runs WHERE module='qualify'").fetchone()
    assert run_row["processed"] == 6 and run_row["produced"] == 5
    # segunda rodada: nada NOVO sobrando
    assert asyncio.run(run(con)) == {}
