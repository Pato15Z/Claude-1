"""Relatórios. Cada função devolve (colunas, linhas) para a CLI e o HTML
usarem a mesma fonte. SQL direto; nada de ORM.

Regra de leitura: taxas de resposta/fechamento por LEAD, nunca por mensagem.
Contar por mensagem subestima por ~4x porque a sequência tem 4 toques."""
from __future__ import annotations

import sqlite3
from typing import Any

from .. import config

Table = tuple[list[str], list[list[Any]]]


def _pct(n: int | float, d: int | float) -> str:
    return f"{100 * n / d:.1f}%" if d else "-"


def qualified_per_day(con: sqlite3.Connection) -> Table:
    rows = con.execute("""
        SELECT date(at) AS dia,
               SUM(to_status='NOVO') AS novos,
               SUM(to_status='QUALIFICADO') AS qualificados,
               SUM(to_status='DESCARTADO') AS descartados,
               SUM(to_status='HERO_PRONTO') AS heros,
               SUM(to_status='ENVIADO') AS enviados
        FROM lead_status_history GROUP BY dia ORDER BY dia DESC LIMIT 30""").fetchall()
    return (["dia", "novos", "qualificados", "descartados", "heros", "enviados"], [list(r) for r in rows])


def minutes_per_lead_by_module(con: sqlite3.Connection) -> Table:
    """Minutos de máquina por lead, por módulo, a partir da tabela runs."""
    rows = con.execute("""
        SELECT module,
               COUNT(*) AS runs,
               SUM(processed) AS processados,
               SUM(produced) AS produzidos,
               SUM((julianday(finished_at) - julianday(started_at)) * 1440.0) AS minutos
        FROM runs WHERE finished_at IS NOT NULL GROUP BY module""").fetchall()
    out = []
    for r in rows:
        out.append([r["module"], r["runs"], r["processados"], r["produzidos"],
                    round(r["minutos"] or 0, 1),
                    round((r["minutos"] or 0) / r["processados"], 2) if r["processados"] else None,
                    round((r["minutos"] or 0) / r["produzidos"], 2) if r["produzidos"] else None])
    return (["módulo", "runs", "processados", "produzidos", "min total", "min/processado", "min/produzido"], out)


def stage_durations(con: sqlite3.Connection) -> Table:
    """Tempo médio (horas) que um lead levou para entrar em cada status, contado
    a partir da transição anterior. Base para 'tempo entre etapas'."""
    rows = con.execute("""
        WITH h AS (
            SELECT lead_id, to_status, at,
                   LAG(at) OVER (PARTITION BY lead_id ORDER BY at, id) AS prev_at
            FROM lead_status_history)
        SELECT to_status,
               COUNT(*) AS n,
               AVG((julianday(at) - julianday(prev_at)) * 24.0) AS horas_media,
               MIN((julianday(at) - julianday(prev_at)) * 24.0) AS horas_min,
               MAX((julianday(at) - julianday(prev_at)) * 24.0) AS horas_max
        FROM h WHERE prev_at IS NOT NULL GROUP BY to_status""").fetchall()
    order = {s: i for i, s in enumerate(["QUALIFICADO", "ENRIQUECIDO", "HERO_PRONTO", "ENVIADO", "RESPONDEU",
                                         "CALL_AGENDADA", "FECHADO", "PERDIDO", "DESCARTADO"])}
    out = sorted(([r["to_status"], r["n"], round(r["horas_media"], 2), round(r["horas_min"], 2), round(r["horas_max"], 2)]
                  for r in rows), key=lambda x: order.get(x[0], 99))
    return (["chegou em", "leads", "horas média", "min", "max"], out)


def response_by_channel(con: sqlite3.Connection) -> Table:
    rows = con.execute("""
        SELECT channel, COUNT(*) AS enviados, SUM(replied_at IS NOT NULL) AS respondidos,
               COUNT(DISTINCT lead_id) AS leads, COUNT(DISTINCT CASE WHEN replied_at IS NOT NULL THEN lead_id END) AS leads_resp
        FROM touches GROUP BY channel ORDER BY enviados DESC""").fetchall()
    return (["canal", "toques", "respostas", "taxa/toque", "leads", "leads resp.", "taxa/lead"],
            [[r["channel"], r["enviados"], r["respondidos"], _pct(r["respondidos"], r["enviados"]),
              r["leads"], r["leads_resp"], _pct(r["leads_resp"], r["leads"])] for r in rows])


def response_by_touch(con: sqlite3.Connection) -> Table:
    rows = con.execute("""
        SELECT touch_number, channel, COUNT(*) AS enviados, SUM(replied_at IS NOT NULL) AS respondidos
        FROM touches GROUP BY touch_number, channel ORDER BY touch_number""").fetchall()
    return (["toque", "canal", "enviados", "respostas", "taxa"],
            [[r["touch_number"], r["channel"], r["enviados"], r["respondidos"], _pct(r["respondidos"], r["enviados"])]
             for r in rows])


def funnel(con: sqlite3.Connection) -> Table:
    """Conversão por lead: quem JÁ PASSOU por cada etapa (histórico), não quem está nela agora."""
    reached = {}
    for st in ["NOVO", "QUALIFICADO", "ENRIQUECIDO", "HERO_PRONTO", "ENVIADO", "RESPONDEU", "CALL_AGENDADA", "FECHADO", "PERDIDO", "DESCARTADO"]:
        reached[st] = con.execute("SELECT COUNT(DISTINCT lead_id) FROM lead_status_history WHERE to_status=?", (st,)).fetchone()[0]
    sent, resp, call, closed = reached["ENVIADO"], reached["RESPONDEU"], reached["CALL_AGENDADA"], reached["FECHADO"]
    rows = [
        ["leads brutos", reached["NOVO"], "-"],
        ["qualificados", reached["QUALIFICADO"], _pct(reached["QUALIFICADO"], reached["NOVO"])],
        ["hero pronto", reached["HERO_PRONTO"], _pct(reached["HERO_PRONTO"], reached["QUALIFICADO"])],
        ["enviados (≥1 toque)", sent, _pct(sent, reached["HERO_PRONTO"])],
        ["responderam", resp, _pct(resp, sent) + " dos enviados"],
        ["call agendada", call, _pct(call, resp) + " das respostas"],
        ["fechados", closed, _pct(closed, call) + " das calls"],
        ["fechamento por lead enviado", closed, _pct(closed, sent)],
        ["perdidos", reached["PERDIDO"], _pct(reached["PERDIDO"], sent)],
    ]
    return (["etapa", "leads", "conversão"], rows)


def qualification_by_region(con: sqlite3.Connection, by: str = "city") -> Table:
    group = {"city": "state, city", "state": "state", "vertical": "vertical", "query": "source_query"}[by]
    rows = con.execute(f"""
        SELECT {group} AS regiao, vertical,
               COUNT(*) AS brutos,
               SUM(site_status IS NOT NULL) AS checados,
               SUM(site_status='SEM_SITE') AS sem_site,
               SUM(site_status='SITE_QUEBRADO') AS quebrado,
               SUM(site_status='SITE_ANTIGO') AS antigo,
               SUM(site_status='SITE_OK') AS ok
        FROM leads GROUP BY {group}, vertical ORDER BY brutos DESC""").fetchall()
    out = []
    for r in rows:
        q = (r["sem_site"] or 0) + (r["quebrado"] or 0) + (r["antigo"] or 0)
        rate = q / r["checados"] if r["checados"] else None
        if rate is None:
            flag = "não checado"
        elif rate < config.REGION_SATURATED_BELOW:
            flag = "SATURADA → trocar"
        elif rate > config.REGION_VIRGIN_ABOVE:
            flag = "VIRGEM → aumentar"
        else:
            flag = "ok"
        region = r["regiao"] if isinstance(r["regiao"], str) else str(r["regiao"])
        out.append([region, r["vertical"], r["brutos"], r["checados"], r["sem_site"], r["quebrado"], r["antigo"], r["ok"],
                    _pct(q, r["checados"]), flag])
    return (["região", "vertical", "brutos", "checados", "sem site", "quebrado", "antigo", "ok", "% qualif.", "leitura"], out)


def leads_per_query(con: sqlite3.Connection) -> Table:
    rows = con.execute("""
        SELECT query, found, inserted, duplicates, elapsed_s, ran_at, error
        FROM source_queries ORDER BY ran_at DESC LIMIT 200""").fetchall()
    out = [[r["query"], r["found"], r["inserted"], r["duplicates"], r["elapsed_s"],
            round(3600 * (r["inserted"] or 0) / r["elapsed_s"], 0) if r["elapsed_s"] else None,
            r["ran_at"][:16], (r["error"] or "")[:40]] for r in rows]
    return (["query", "achados", "novos", "dup", "seg", "novos/h", "quando", "erro"], out)


def churn_monthly(con: sqlite3.Connection) -> Table:
    """Churn mensal: clientes que saíram no mês / clientes ativos no início do mês."""
    months = con.execute("""
        WITH RECURSIVE m(d) AS (
            SELECT date(MIN(started_at), 'start of month') FROM clients
            UNION ALL SELECT date(d, '+1 month') FROM m WHERE d < date('now', 'start of month'))
        SELECT d FROM m WHERE d IS NOT NULL""").fetchall()
    out = []
    for i, (d,) in enumerate(months, start=1):
        active = con.execute("SELECT COUNT(*) FROM clients WHERE started_at < ? AND (churned_at IS NULL OR churned_at >= ?)", (d, d)).fetchone()[0]
        churned = con.execute("SELECT COUNT(*) FROM clients WHERE churned_at >= ? AND churned_at < date(?, '+1 month')", (d, d)).fetchone()[0]
        new = con.execute("SELECT COUNT(*) FROM clients WHERE started_at >= ? AND started_at < date(?, '+1 month')", (d, d)).fetchone()[0]
        mrr = con.execute("SELECT COALESCE(SUM(mrr),0) FROM clients WHERE started_at < date(?, '+1 month') AND (churned_at IS NULL OR churned_at >= date(?, '+1 month'))", (d, d)).fetchone()[0]
        out.append([d[:7], i, active, new, churned, _pct(churned, active) if i >= 3 else f"({_pct(churned, active)}) mês<3", round(mrr, 0)])
    return (["mês", "nº", "ativos início", "novos", "churn", "% churn", "MRR fim"], out)


def reply_time_distribution(con: sqlite3.Connection) -> Table:
    rows = con.execute("""
        SELECT (julianday(replied_at) - julianday(sent_at)) * 24.0 AS h FROM touches WHERE replied_at IS NOT NULL""").fetchall()
    buckets = [("< 1h", 0, 1), ("1-6h", 1, 6), ("6-24h", 6, 24), ("1-3 dias", 24, 72), ("3-7 dias", 72, 168), ("> 7 dias", 168, 1e9)]
    total = len(rows)
    out = []
    for label, lo, hi in buckets:
        n = sum(1 for r in rows if lo <= r["h"] < hi)
        out.append([label, n, _pct(n, total)])
    return (["tempo até resposta", "respostas", "%"], out)


def status_counts(con: sqlite3.Connection) -> Table:
    rows = con.execute("SELECT status, COUNT(*) FROM leads GROUP BY status").fetchall()
    order = {s: i for i, s in enumerate(["NOVO", "QUALIFICADO", "ENRIQUECIDO", "HERO_PRONTO", "ENVIADO", "RESPONDEU", "CALL_AGENDADA", "FECHADO", "PERDIDO", "DESCARTADO"])}
    return (["status", "leads"], sorted(([r[0], r[1]] for r in rows), key=lambda x: order.get(x[0], 99)))


ALL_REPORTS = [
    ("Status atual do funil", status_counts),
    ("Conversão por lead", funnel),
    ("Qualificação por região", qualification_by_region),
    ("Leads por dia", qualified_per_day),
    ("Minutos por lead por módulo (máquina)", minutes_per_lead_by_module),
    ("Tempo entre etapas", stage_durations),
    ("Resposta por canal", response_by_channel),
    ("Resposta por toque", response_by_touch),
    ("Tempo até resposta", reply_time_distribution),
    ("Churn mensal", churn_monthly),
    ("Rendimento por query de sourcing", leads_per_query),
]
