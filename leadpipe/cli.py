"""CLI `lp`. Grupos: source, qualify, lead, touch, client, report, db."""
from __future__ import annotations

import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import config, db
from .sourcing.base import IngestStats, RawLead, ingest_one
from .sourcing.cities import cities_for_state
from .sourcing.csv_import import import_csv
from .sourcing.gosom import import_gosom
from .tracking import html_report, reports
from .tracking.touches import daily_queue, log_reply, log_touch

app = typer.Typer(no_args_is_help=True, add_completion=False, help="leadpipe: sourcing → qualificação → tracking")
source_app = typer.Typer(no_args_is_help=True, help="Módulo 1: sourcing")
qualify_app = typer.Typer(no_args_is_help=True, help="Módulo 2: qualificação")
lead_app = typer.Typer(no_args_is_help=True, help="Leads: ver, listar, mudar status")
touch_app = typer.Typer(no_args_is_help=True, help="Sequência de contato: registrar toques, fila do dia")
client_app = typer.Typer(no_args_is_help=True, help="Clientes fechados (churn)")
report_app = typer.Typer(no_args_is_help=True, help="Módulo 5: relatórios")
db_app = typer.Typer(no_args_is_help=True, help="Banco")
for name, sub in [("source", source_app), ("qualify", qualify_app), ("lead", lead_app), ("touch", touch_app),
                  ("client", client_app), ("report", report_app), ("db", db_app)]:
    app.add_typer(sub, name=name)

con_ = Console()


def _con():
    config.ensure_dirs()
    return db.connect()


def _print_table(title: str, cols, rows, max_rows: int | None = None) -> None:
    t = Table(title=title, show_lines=False, header_style="bold")
    for c in cols:
        t.add_column(str(c))
    shown = rows[:max_rows] if max_rows else rows
    for r in shown:
        t.add_row(*["" if v is None else str(v) for v in r])
    if max_rows and len(rows) > max_rows:
        t.caption = f"{len(rows) - max_rows} linhas omitidas"
    con_.print(t)


def _stats_line(prefix: str, st: IngestStats) -> str:
    return f"{prefix}: achados={st.found} novos={st.inserted} duplicados={st.duplicates} campos preenchidos={st.filled}"


# ============================================================== source

@source_app.command("cities")
def source_cities(state: str, min_pop: int = 15000, limit: Optional[int] = None):
    """Lista cidades do estado (base para iterar queries)."""
    rows = cities_for_state(state, min_pop, limit)
    _print_table(f"Cidades de {state.upper()} (pop ≥ {min_pop})", ["cidade", "população"],
                 [[c["name"], c["population"]] for c in rows])


@source_app.command("maps")
def source_maps(
    vertical: str = typer.Option(..., help='ex: "roof cleaning"'),
    state: str = typer.Option(..., help="sigla, ex: OH"),
    city: list[str] = typer.Option(None, "--city", help="cidade(s); sem isso, usa todas do estado"),
    min_pop: int = typer.Option(20000, help="população mínima das cidades quando --city não é dado"),
    max_cities: Optional[int] = typer.Option(None, help="limita nº de cidades (maiores primeiro)"),
    max_results: Optional[int] = typer.Option(None, help="limita resultados por query"),
    fast: bool = typer.Option(False, help="não abre detalhe de cada card (sem endereço completo)"),
    headful: bool = typer.Option(False, help="mostra o browser (útil para captcha)"),
    force: bool = typer.Option(False, help="repete queries já rodadas nos últimos 7 dias"),
    debug: bool = typer.Option(False, help="salva HTML em data/debug/"),
):
    """Scrape do Google Maps, iterando por cidade. Persiste lead a lead."""
    from .sourcing.google_maps import ScrapeOptions, scrape_many

    con = _con()
    st = state.upper()
    cities = list(city) if city else [c["name"] for c in cities_for_state(st, min_pop, max_cities)]
    if not cities:
        con_.print("[red]nenhuma cidade encontrada[/red]")
        raise typer.Exit(1)
    queries = [(f"{vertical} {c} {st}", vertical, c, st) for c in cities]
    con_.print(f"{len(queries)} queries para '{vertical}' em {st}")
    run_id = db.start_run(con, "source", json.dumps({"vertical": vertical, "state": st, "cities": len(cities)}))

    def progress(q, stats, skipped=False):
        if skipped:
            con_.print(f"  [dim]pulado (já rodou):[/dim] {q}")
        else:
            con_.print("  " + _stats_line(q, stats))

    total = asyncio.run(scrape_many(con, queries, ScrapeOptions(headless=not headful, fast=fast, max_results=max_results, debug=debug), force=force, progress=progress))
    db.finish_run(con, run_id, processed=total.found, produced=total.inserted)
    con_.print("[bold]" + _stats_line("TOTAL", total) + "[/bold]")


@source_app.command("import-csv")
def source_import_csv(path: Path, vertical: Optional[str] = typer.Option(None, help="se o CSV não tiver coluna vertical")):
    """Entrada manual em lote: CSV com cabeçalho (name, phone, address, city, state, website, ...)."""
    con = _con()
    st = import_csv(con, path, vertical)
    con_.print(_stats_line(f"csv {path.name}", st))


@source_app.command("import-gosom")
def source_import_gosom(path: Path, vertical: str = typer.Option(...)):
    """Ingere JSON/JSONL do gosom/google-maps-scraper (plano B ao scraper Playwright)."""
    con = _con()
    st = import_gosom(con, path, vertical)
    con_.print(_stats_line(f"gosom {path.name}", st))


@source_app.command("add")
def source_add(
    name: str = typer.Option(...), vertical: str = typer.Option(...),
    phone: Optional[str] = None, address: Optional[str] = None, city: Optional[str] = None,
    state: Optional[str] = None, zip: Optional[str] = None, website: Optional[str] = None,
    gbp_url: Optional[str] = None, rating: Optional[float] = None, reviews: Optional[int] = None,
    facebook: Optional[str] = None, instagram: Optional[str] = None, email: Optional[str] = None,
    category: Optional[str] = None, note: Optional[str] = None,
):
    """Entrada manual de um lead. Cai na mesma fila que os do scraper."""
    con = _con()
    st = IngestStats()
    raw = RawLead(name=name, vertical=vertical, source="manual", source_query="manual", phone_raw=phone,
                  address_full=address, city=city, state=state, zip=zip, website_url=website, gbp_url=gbp_url,
                  rating=rating, review_count=reviews, facebook_url=facebook, instagram_url=instagram,
                  email=email, category=category)
    lead_id = ingest_one(con, raw, st)
    if note and lead_id:
        db.update_lead(con, lead_id, notes=note)
    con_.print(f"lead #{lead_id} " + ("criado" if st.inserted else "já existia (campos vazios preenchidos)"))


# ============================================================== qualify

@qualify_app.command("run")
def qualify_run(
    limit: Optional[int] = typer.Option(None, help="máximo de leads"),
    vertical: Optional[str] = None, state: Optional[str] = None,
    recheck: bool = typer.Option(False, help="reavalia também leads já classificados"),
):
    """Classifica leads NOVO em SEM_SITE / SITE_QUEBRADO / SITE_ANTIGO / SITE_OK."""
    from .qualify.runner import run

    con = _con()

    def progress(lead, st):
        color = {"SEM_SITE": "green", "SITE_QUEBRADO": "yellow", "SITE_ANTIGO": "cyan", "SITE_OK": "dim"}.get(st, "white")
        con_.print(f"  #{lead['id']:<5} [{color}]{st:<14}[/{color}] {lead['name'][:40]:<40} {lead['website_url'] or ''}")

    counts = asyncio.run(run(con, limit=limit, recheck=recheck, vertical=vertical, state=state, progress=progress))
    if not counts:
        con_.print("nada a qualificar (nenhum lead NOVO)")
        return
    elapsed = counts.pop("_elapsed_s", 0)
    n = sum(counts.values())
    q = sum(v for k, v in counts.items() if k in db.SITE_STATES_QUALIFIED)
    con_.print(f"[bold]{n} leads em {elapsed}s ({elapsed / n:.1f}s/lead) — qualificados {q} ({100 * q / n:.0f}%)[/bold] {counts}")


@qualify_app.command("show")
def qualify_show(lead_id: int):
    """Mostra o histórico de checagens de um lead (auditoria de falso positivo)."""
    con = _con()
    rows = con.execute("SELECT * FROM site_checks WHERE lead_id=? ORDER BY checked_at DESC", (lead_id,)).fetchall()
    for r in rows:
        con_.print(f"[bold]{r['checked_at']}[/bold] {r['site_status']} — {r['reason']}")
        con_.print(f"  url={r['url']} final={r['final_url']} http={r['http_status']} {r['elapsed_ms']}ms shot={r['screenshot_path']}")
        con_.print("  " + (r["signals_json"] or "")[:600])


# ============================================================== lead

@lead_app.command("show")
def lead_show(lead_id: int):
    con = _con()
    lead = db.get_lead(con, lead_id)
    if not lead:
        con_.print("[red]não existe[/red]"); raise typer.Exit(1)
    for k in lead.keys():
        if lead[k] not in (None, ""):
            con_.print(f"[bold]{k:<16}[/bold] {lead[k]}")
    con_.print("[bold]histórico[/bold]")
    for h in con.execute("SELECT * FROM lead_status_history WHERE lead_id=? ORDER BY at", (lead_id,)):
        con_.print(f"  {h['at']}  {h['from_status'] or '-':<12} → {h['to_status']:<12} {h['note'] or ''}")
    for t in con.execute("SELECT * FROM touches WHERE lead_id=? ORDER BY touch_number", (lead_id,)):
        con_.print(f"  toque {t['touch_number']} {t['channel']} enviado {t['sent_at']} resposta {t['replied_at'] or '-'}")


@lead_app.command("list")
def lead_list(status: Optional[str] = None, site_status: Optional[str] = None, state: Optional[str] = None,
              city: Optional[str] = None, vertical: Optional[str] = None, limit: int = 50):
    con = _con()
    where, args = ["1=1"], []
    for col, val in [("status", status), ("site_status", site_status), ("state", state and state.upper()),
                     ("city", city), ("vertical", vertical)]:
        if val:
            where.append(f"{col}=?"); args.append(val)
    rows = con.execute(f"SELECT id,name,city,state,phone_e164,website_url,status,site_status,rating,review_count FROM leads WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT ?", [*args, limit]).fetchall()
    _print_table("leads", ["id", "nome", "cidade", "uf", "tel", "site", "status", "site_status", "nota", "rev"], [list(r) for r in rows])


@lead_app.command("set-status")
def lead_set_status(lead_id: int, status: str, note: Optional[str] = None):
    """Transição manual (CALL_AGENDADA, FECHADO, PERDIDO, HERO_PRONTO...). Sempre grava histórico."""
    con = _con()
    ok = db.transition(con, lead_id, status.upper(), note)
    con_.print("ok" if ok else "já estava nesse status")


@lead_app.command("set")
def lead_set(lead_id: int, field: str, value: str):
    """Edita um campo (email, facebook_url, instagram_url, hero_url, notes, timezone...)."""
    con = _con()
    if field not in db.LEAD_COLUMNS or field in ("id", "status"):
        con_.print(f"[red]campo inválido[/red]"); raise typer.Exit(1)
    db.update_lead(con, lead_id, **{field: value})
    con_.print("ok")


# ============================================================== touch

@touch_app.command("queue")
def touch_queue(days_ahead: int = typer.Option(0, help="incluir toques que vencem nos próximos N dias")):
    """Fila do dia: quem está devido em qual toque, ordenado por fuso (leste → oeste)."""
    con = _con()
    items = daily_queue(con, include_future_days=days_ahead)
    rows = []
    for i in items:
        contact = {"email": i.email, "facebook_page": i.facebook_url or i.instagram_url, "instagram": i.instagram_url, "ligacao": i.phone}.get(i.channel) or "-"
        rows.append([i.lead_id, i.name[:32], f"{i.city}, {i.state}", i.tz.split("/")[-1], i.local_now, i.touch_number, i.channel,
                     str(i.due_date), i.days_overdue if i.days_overdue > 0 else "", contact, i.hero_url or ""])
    _print_table(f"fila de hoje ({len(items)})", ["id", "nome", "cidade", "fuso", "hora local", "toque", "canal", "vence", "atraso", "contato", "hero"], rows)


@touch_app.command("log")
def touch_log(lead_id: int, n: int = typer.Option(..., "--n", min=1, max=4), channel: str = typer.Option(...),
              template: Optional[str] = None, content: Optional[str] = None, note: Optional[str] = None):
    """Registra que o toque N foi enviado. Toque 1 move o lead para ENVIADO."""
    con = _con()
    tid = log_touch(con, lead_id, n, channel, template, content, note)
    con_.print(f"toque #{tid} registrado")


@touch_app.command("reply")
def touch_reply(lead_id: int, n: Optional[int] = typer.Option(None, "--n"), note: Optional[str] = None):
    """Registra resposta (no toque N ou no último). Move para RESPONDEU."""
    con = _con()
    t = log_reply(con, lead_id, n, notes=note)
    con_.print(f"resposta registrada no toque {t}")


# ============================================================== client

@client_app.command("add")
def client_add(lead_id: int, setup_fee: float = 1000, mrr: float = 99, started: Optional[str] = None):
    con = _con()
    con.execute("INSERT INTO clients (lead_id, started_at, setup_fee, mrr) VALUES (?,?,?,?)",
                (lead_id, started or db.now_iso(), setup_fee, mrr))
    db.transition(con, lead_id, "FECHADO", note="client add")
    con_.print("ok")


@client_app.command("churn")
def client_churn(lead_id: int, when: Optional[str] = None, note: Optional[str] = None):
    con = _con()
    con.execute("UPDATE clients SET churned_at=?, notes=? WHERE lead_id=?", (when or db.now_iso(), note, lead_id))
    con_.print("ok")


# ============================================================== report

def _report_cmd(name: str, fn, title: str):
    def cmd():
        con = _con()
        cols, rows = fn(con)
        _print_table(title, cols, rows)
    cmd.__name__ = name
    report_app.command(name)(cmd)


_report_cmd("status", reports.status_counts, "Status do funil")
_report_cmd("funnel", reports.funnel, "Conversão por lead")
_report_cmd("daily", reports.qualified_per_day, "Leads por dia")
_report_cmd("minutes", reports.minutes_per_lead_by_module, "Minutos por lead por módulo")
_report_cmd("stages", reports.stage_durations, "Tempo entre etapas")
_report_cmd("channels", reports.response_by_channel, "Resposta por canal")
_report_cmd("touches", reports.response_by_touch, "Resposta por toque")
_report_cmd("reply-time", reports.reply_time_distribution, "Tempo até resposta")
_report_cmd("churn", reports.churn_monthly, "Churn mensal")
_report_cmd("queries", reports.leads_per_query, "Rendimento por query")


@report_app.command("region")
def report_region(by: str = typer.Option("city", help="city | state | vertical | query")):
    con = _con()
    cols, rows = reports.qualification_by_region(con, by)
    _print_table(f"Qualificação por {by}", cols, rows)


@report_app.command("all")
def report_all():
    con = _con()
    for title, fn in reports.ALL_REPORTS:
        cols, rows = fn(con)
        _print_table(title, cols, rows, max_rows=40)


@report_app.command("html")
def report_html(out: Path = typer.Option(config.DATA_DIR / "report.html")):
    """Gera o dashboard estático."""
    con = _con()
    p = html_report.write(con, out)
    con_.print(f"gerado: {p}")


# ============================================================== db

@db_app.command("init")
def db_init():
    _con(); con_.print(f"banco em {config.DB_PATH}")


@db_app.command("export")
def db_export(out: Path = typer.Option(config.DATA_DIR / "leads.csv"), status: Optional[str] = None):
    """Exporta leads para CSV (para planilha / revisão manual)."""
    con = _con()
    q = "SELECT * FROM leads" + (" WHERE status=?" if status else "") + " ORDER BY id"
    rows = con.execute(q, (status,) if status else ()).fetchall()
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if rows:
            w.writerow(rows[0].keys())
            w.writerows([list(r) for r in rows])
    con_.print(f"{len(rows)} leads → {out}")


@db_app.command("sql")
def db_sql(query: str):
    """Roda SQL livre (leitura)."""
    con = _con()
    cur = con.execute(query)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    _print_table("sql", cols, [list(r) for r in rows], max_rows=200)


if __name__ == "__main__":
    app()
