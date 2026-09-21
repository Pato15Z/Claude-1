from datetime import date, datetime, timedelta, timezone

from leadpipe import db
from leadpipe.sourcing.base import IngestStats, RawLead, ingest_one
from leadpipe.tracking import reports
from leadpipe.tracking.touches import daily_queue, log_reply, log_touch


_seq = [0]


def _lead(con, name, state="OH", lat=None, lng=None, status="HERO_PRONTO"):
    _seq[0] += 1
    lid = ingest_one(con, RawLead(name=name, vertical="roof cleaning", source="manual", state=state, city="X", lat=lat, lng=lng,
                                  address_full=f"{name} St, X, {state} 43215", email=f"{name}@x.com", phone_raw=f"614-555-{_seq[0]:04d}"), IngestStats())
    db.transition(con, lid, "QUALIFICADO")
    if status != "QUALIFICADO":
        db.transition(con, lid, status)
    return lid


def test_queue_and_touches(con):
    east = _lead(con, "East", "OH")
    west = _lead(con, "West", "CA", lat=34.05, lng=-118.24)
    q = daily_queue(con)
    assert [i.lead_id for i in q] == [east, west]  # leste antes de oeste
    assert all(i.touch_number == 1 and i.channel == "email" for i in q)

    # sem Facebook nem Instagram: depois do email só resta o follow-up (toque 4, dia 6)
    d0 = datetime.now(timezone.utc) - timedelta(days=3)
    log_touch(con, east, 1, "email", template="t1", sent_at=d0.isoformat())
    assert db.get_lead(con, east)["status"] == "ENVIADO"
    q = {i.lead_id: i for i in daily_queue(con)}
    assert east not in q
    assert daily_queue(con, include_future_days=3)[0].touch_number == 4

    # com Facebook: toque 2 devido no dia 2 (já atrasado 1 dia)
    db.update_lead(con, east, facebook_url="https://facebook.com/east", instagram_url="https://instagram.com/east")
    q = {i.lead_id: i for i in daily_queue(con)}
    assert q[east].touch_number == 2 and q[east].channel == "facebook_page" and q[east].days_overdue == 1

    log_touch(con, east, 2, "facebook_page")
    q = {i.lead_id: i for i in daily_queue(con)}
    assert q[east].touch_number == 3 and q[east].channel == "instagram"   # dia 3 = hoje
    log_touch(con, east, 3, "instagram")
    assert east not in {i.lead_id for i in daily_queue(con)}              # follow-up só no dia 6
    assert daily_queue(con, include_future_days=3)[0].lead_id in (east, west)

    log_reply(con, east)
    assert db.get_lead(con, east)["status"] == "RESPONDEU"
    assert east not in {i.lead_id for i in daily_queue(con)}

    cols, rows = reports.response_by_channel(con)
    by = {r[0]: r for r in rows}
    assert by["instagram"][2] == 1 and by["email"][2] == 0 and by["facebook_page"][2] == 0
    cols, rows = reports.response_by_touch(con)
    assert rows[2][0] == 3 and rows[2][4] == "100.0%"


def test_funnel_and_region_reports(con):
    a = _lead(con, "A"); b = _lead(con, "B", status="QUALIFICADO")
    c = ingest_one(con, RawLead(name="C", vertical="roof cleaning", source="manual", state="OH", city="X", website_url="https://ok.example",
                                address_full="C St, X, OH 43215"), IngestStats())
    for lid, ss in [(a, "SEM_SITE"), (b, "SITE_ANTIGO"), (c, "SITE_OK")]:
        con.execute("UPDATE leads SET site_status=? WHERE id=?", (ss, lid))
    db.transition(con, c, "DESCARTADO")
    log_touch(con, a, 1, "email")
    log_reply(con, a)
    db.transition(con, a, "CALL_AGENDADA")
    con.execute("INSERT INTO clients (lead_id, started_at) VALUES (?, ?)", (a, db.now_iso()))
    db.transition(con, a, "FECHADO")

    cols, rows = reports.funnel(con)
    f = {r[0]: r for r in rows}
    assert f["leads brutos"][1] == 3 and f["qualificados"][2] == "66.7%"
    assert f["responderam"][1] == 1 and f["fechados"][1] == 1 and f["fechamento por lead enviado"][2] == "100.0%"

    cols, rows = reports.qualification_by_region(con, "state")
    assert rows[0][0] == "OH" and rows[0][8] == "66.7%" and "VIRGEM" in rows[0][9]

    cols, rows = reports.churn_monthly(con)
    assert rows and rows[-1][3] == 1  # 1 novo cliente este mês
    cols, rows = reports.stage_durations(con)
    assert any(r[0] == "FECHADO" for r in rows)
    cols, rows = reports.reply_time_distribution(con)
    assert rows[0][1] == 1  # respondeu em < 1h


def test_html_report(con, tmp_path):
    from leadpipe.tracking.html_report import write
    _lead(con, "A")
    p = write(con, tmp_path / "r.html")
    txt = p.read_text()
    assert "Conversão por lead" in txt and "<table>" in txt
