from leadpipe.normalize import address_norm, phone_e164, relative_date_to_iso, slug, split_us_address, timezone_for


def test_phone():
    assert phone_e164("(614) 555-0100") == "+16145550100"
    assert phone_e164("614.555.0100") == "+16145550100"
    assert phone_e164("+1 614-555-0100") == "+16145550100"
    assert phone_e164("abc") is None
    assert phone_e164(None) is None


def test_address_norm_collides_variants():
    a = address_norm("123 North Main Street, Suite 4, Columbus, OH 43215, United States")
    b = address_norm("123 N. Main St., Columbus, OH 43215")
    assert a == b == "123 n main st columbus oh 43215"


def test_split_us_address():
    p = split_us_address("123 Main St, Columbus, OH 43215, United States")
    assert p == {"street": "123 Main St", "city": "Columbus", "state": "OH", "zip": "43215"}
    p = split_us_address("Columbus, OH")
    assert p["city"] == "Columbus" and p["state"] == "OH" and p["street"] is None


def test_timezone():
    assert timezone_for(39.96, -82.99, "OH") == "America/New_York"
    assert timezone_for(30.27, -97.74, "TX") == "America/Chicago"
    assert timezone_for(31.76, -106.48, "TX") == "America/Denver"  # El Paso: coordenada vence o estado
    assert timezone_for(None, None, "TX") == "America/Chicago"
    assert timezone_for(None, None, "az") == "America/Phoenix"


def test_relative_date():
    from datetime import datetime, timezone
    now = datetime(2026, 9, 18, tzinfo=timezone.utc)
    assert relative_date_to_iso("3 weeks ago", now) == "2026-08-28"
    assert relative_date_to_iso("a month ago", now) == "2026-08-19"
    assert relative_date_to_iso("garbage", now) is None


def test_slug():
    assert slug("Bob's Roof Cleaning & Co.", "Columbus") == "bob-s-roof-cleaning-co-columbus"
