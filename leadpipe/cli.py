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
enrich_app = typer.Typer(no_args_is_help=True, help="Módulo 3: enriquecimento (email, redes, imagens, paleta)")
hero_app = typer.Typer(no_args_is_help=True, help="Módulo 4: gerar e publicar heros")
for name, sub in [("source", source_app), ("qualify", qualify_app), ("enrich", enrich_app), ("hero", hero_app),
                  ("lead", lead_app), ("touch", touch_app), ("client", client_app), ("report", report_app), ("db", db_app)]:
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
    extra = f" [dim]com site pulados={st.with_site}[/dim]" if st.with_site else ""
    return f"{prefix}: achados={st.found} novos={st.inserted} duplicados={st.duplicates} campos preenchidos={st.filled}{extra}"


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
    no_site_only: bool = typer.Option(False, help="modo caça: só quem NÃO tem site (10x mais rápido)"),
    by: str = typer.Option("city", help="city | county (condado cobre zona rural)"),
):
    """Scrape do Google Maps, iterando por cidade ou condado. Persiste lead a lead."""
    from .sourcing.google_maps import ScrapeOptions, scrape_many

    con = _con()
    st = state.upper()
    from .sourcing.cities import places_for_state
    cities = list(city) if city else places_for_state(st, by, min_pop, max_cities)
    if not cities:
        con_.print("[red]nenhuma cidade encontrada[/red]")
        raise typer.Exit(1)
    queries = [(f"{vertical} {c} {st}", vertical, c, st) for c in cities]
    con_.print(f"{len(queries)} queries para '{vertical}' em {st}" + (" [modo caça: só sem site]" if no_site_only else ""))
    run_id = db.start_run(con, "source", json.dumps({"vertical": vertical, "state": st, "cities": len(cities), "no_site_only": no_site_only}))

    def progress(q, stats, skipped=False):
        if skipped:
            con_.print(f"  [dim]pulado (já rodou):[/dim] {q}")
        else:
            con_.print("  " + _stats_line(q, stats))

    total = asyncio.run(scrape_many(con, queries, ScrapeOptions(headless=not headful, fast=fast, max_results=max_results, debug=debug,
                                                                no_site_only=no_site_only), force=force, progress=progress))
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


@qualify_app.command("audit")
def qualify_audit(site_status: Optional[str] = typer.Option(None, "--site", help="ex: SITE_QUEBRADO"), limit: int = 200):
    """Lista id, status, motivo e URL de todos os checados — para caçar falso positivo."""
    con = _con()
    where, args = ["site_status IS NOT NULL"], []
    if site_status:
        where.append("site_status=?"); args.append(site_status.upper())
    rows = con.execute(f"SELECT id, name, site_status, site_reason, website_url FROM leads WHERE {' AND '.join(where)} ORDER BY site_status, id LIMIT ?", [*args, limit]).fetchall()
    _print_table("auditoria", ["id", "nome", "status", "motivo", "site"], [[r["id"], r["name"][:30], r["site_status"], (r["site_reason"] or "")[:70], (r["website_url"] or "")[:40]] for r in rows])
    counts = con.execute("SELECT site_status, COUNT(*) FROM leads WHERE site_status IS NOT NULL GROUP BY 1").fetchall()
    con_.print("  ".join(f"{r[0]}={r[1]}" for r in counts))


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
_report_cmd("enrich", reports.enrichment_quality, "Qualidade do enriquecimento")


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


# ============================================================== enrich

@enrich_app.command("run")
def enrich_run(
    limit: Optional[int] = typer.Option(None, help="máximo de leads"),
    redo: bool = typer.Option(False, help="refaz também leads já ENRIQUECIDO"),
    no_search: bool = typer.Option(False, help="não busca Facebook/Instagram na web"),
    no_gbp: bool = typer.Option(False, help="não abre o Google Maps para fotos"),
    only: Optional[str] = typer.Option(None, help="só leads com este site_status, ex: SEM_SITE"),
    id: Optional[int] = typer.Option(None, "--id", help="só este lead (refaz mesmo se já ENRIQUECIDO)"),
):
    """Para leads QUALIFICADO: email, Facebook/Instagram, 3–6 imagens, logo, paleta → ENRIQUECIDO."""
    from .enrich.runner import run

    con = _con()

    def progress(lead, r):
        if "error" in r:
            con_.print(f"  #{lead['id']:<5} [red]erro[/red] {lead['name'][:40]} {r['error']}")
        else:
            con_.print(f"  #{lead['id']:<5} img={r['images']} email={'✓' if r['email'] else '·'} fb={'✓' if r['fb'] else '·'} logo={'✓' if r['logo'] else '·'}  {lead['name'][:40]}")

    agg = asyncio.run(run(con, limit=limit, redo=redo or id is not None, web_search=not no_search, gbp=not no_gbp, progress=progress,
                          site_status=only.upper() if only else None, lead_id=id))
    if not agg:
        con_.print("nada a enriquecer (nenhum lead QUALIFICADO)"); return
    n = agg["leads"] or 1
    con_.print(f"[bold]{agg['leads']} leads em {agg['_elapsed_s']}s ({agg['_elapsed_s'] / n:.1f}s/lead) — "
               f"≥3 imagens {100 * agg['with_3_images'] / n:.0f}% · email {100 * agg['with_email'] / n:.0f}% · fb {100 * agg['with_fb'] / n:.0f}% · erros {agg['errors']}"
               f" · tinham site e foram descartados: {agg.get('requalified_with_site', 0)}[/bold]")


@enrich_app.command("show")
def enrich_show(lead_id: int):
    con = _con()
    lead = db.get_lead(con, lead_id)
    if not lead:
        con_.print("[red]não existe[/red]"); raise typer.Exit(1)
    for k in ("email", "email_source", "email_confidence", "facebook_url", "instagram_url", "logo_path", "palette_json", "priority", "enrich_notes"):
        con_.print(f"[bold]{k:<16}[/bold] {lead[k]}")
    rows = con.execute("SELECT * FROM lead_images WHERE lead_id=? ORDER BY score DESC", (lead_id,)).fetchall()
    _print_table("imagens", ["kind", "WxH", "source", "score", "path"], [[r["kind"], f"{r['width']}x{r['height']}", r["source"], r["score"], r["path"]] for r in rows])


# ============================================================== hero

@hero_app.command("build")
def hero_build(
    limit: Optional[int] = typer.Option(None),
    include_low: bool = typer.Option(False, help="inclui leads sem imagem (hero com fundo genérico)"),
    rebuild: bool = typer.Option(False, help="regenera também os já HERO_PRONTO"),
    only: Optional[str] = typer.Option(None, help="só leads com este site_status, ex: SEM_SITE"),
    id: Optional[int] = typer.Option(None, "--id", help="só este lead (regenera)"),
    template: Optional[str] = typer.Option(None, help="nome do template (lp hero templates)"),
):
    """Gera os heros em batch em data/hero_site/{slug}/ e marca HERO_PRONTO."""
    from .hero.build import build

    con = _con()
    if config.HERO_DOMAIN.startswith("SEUDOMINIO"):
        con_.print("[yellow]LEADPIPE_HERO_DOMAIN não definido: as URLs vão sair como {slug}.SEUDOMINIO.com. Defina a variável e rode --rebuild depois.[/yellow]")

    def progress(lead, url, has_img):
        con_.print(f"  #{lead['id']:<5} {'🖼' if has_img else '▫'} {url}")

    r = build(con, limit=limit, include_low_priority=include_low or id is not None, rebuild=rebuild or id is not None, progress=progress,
              site_status=only.upper() if only else None, lead_id=id, template=template)
    if not r:
        con_.print("nada a gerar (nenhum lead ENRIQUECIDO com prioridade normal; use --include-low)"); return
    con_.print(f"[bold]{r['built']} heros em {r['_elapsed_s']}s → {r['site_dir']}  (erros: {r['errors']})[/bold]")
    con_.print("publicar: lp hero deploy   (ou abrir localmente: lp hero serve)")


@hero_app.command("serve")
def hero_serve(port: int = 8080):
    """Serve data/hero_site localmente para gravar o vídeo antes do deploy: http://localhost:8080/<slug>/"""
    import http.server, functools
    config.ensure_dirs()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(config.HERO_SITE_DIR))
    con_.print(f"http://localhost:{port}/<slug>/   (Ctrl+C para parar)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


@hero_app.command("deploy")
def hero_deploy():
    """Publica data/hero_site na Vercel (precisa de `npm i -g vercel` e `vercel login` uma vez)."""
    import shutil, subprocess
    if not shutil.which("vercel"):
        con_.print("[red]CLI da Vercel não encontrada.[/red] Instale: npm i -g vercel && vercel login. Depois: lp hero deploy")
        raise typer.Exit(1)
    r = subprocess.run(["vercel", "deploy", "--prod", "--yes"], cwd=str(config.HERO_SITE_DIR))
    raise typer.Exit(r.returncode)


@hero_app.command("expire")
def hero_expire(dry_run: bool = typer.Option(False, help="só lista")):
    """Derruba heros com mais de 30 dias sem resposta."""
    from .hero.build import expire
    con = _con()
    rows = expire(con, dry_run)
    _print_table("heros expirados" + (" (simulação)" if dry_run else ""), ["id", "nome", "url", "status"], [[r["id"], r["name"], r["url"], r["status"]] for r in rows])
    if rows and not dry_run:
        con_.print("rode `lp hero deploy` para refletir a remoção")


@hero_app.command("one")
def hero_one(id: int = typer.Option(..., "--id"), template: Optional[str] = None, no_gbp: bool = False):
    """Um lead do início ao fim: enriquece (se ainda não), gera o hero e tira a foto."""
    from .enrich.runner import run as enrich_run_
    from .hero.build import build

    con = _con()
    lead = db.get_lead(con, id)
    if not lead:
        con_.print("[red]lead não existe[/red]"); raise typer.Exit(1)
    if lead["status"] == "NOVO":
        from .qualify.runner import auto_qualify_no_site
        auto_qualify_no_site(con, id)
    if not lead["enriched_at"]:
        con_.print("enriquecendo...")
        asyncio.run(enrich_run_(con, lead_id=id, redo=True, gbp=not no_gbp, web_search=config.ENRICH_WEB_SEARCH,
                                progress=lambda l, r: con_.print(f"  {r}")))
    r = build(con, include_low_priority=True, rebuild=True, lead_id=id, template=template,
              progress=lambda l, u, img: con_.print(f"  {'🖼' if img else '▫'} {u}"))
    if r.get("built"):
        hero_shot(id)
    con_.print("pronto")


@hero_app.command("batch")
def hero_batch(ids: Optional[str] = typer.Option(None, help="ids separados por vírgula"),
               all_no_site: bool = typer.Option(False, help="todos os SEM SITE ainda sem hero"),
               template: Optional[str] = None, no_gbp: bool = False):
    """Gera o site de vários leads: busca fotos/avaliações de quem ainda não tem, depois gera todos."""
    from .enrich.runner import run as enrich_run_
    from .hero.build import build
    from .qualify.runner import auto_qualify_no_site

    con = _con()
    if all_no_site:
        rows = con.execute("SELECT id FROM leads WHERE site_status='SEM_SITE' AND hero_path IS NULL AND status IN ('QUALIFICADO','ENRIQUECIDO','NOVO')").fetchall()
        id_list = [r["id"] for r in rows]
    else:
        id_list = [int(x) for x in (ids or "").replace(";", ",").split(",") if x.strip()]
    if not id_list:
        con_.print("nenhum lead selecionado"); raise typer.Exit(1)
    for i in id_list:
        auto_qualify_no_site(con, i)
    need = [r["id"] for r in con.execute(f"SELECT id FROM leads WHERE enriched_at IS NULL AND id IN ({','.join(map(str, id_list))})")]
    con_.rule(f"1/2 fotos e avaliações: {len(need)} de {len(id_list)} leads")
    if need:
        asyncio.run(enrich_run_(con, redo=True, gbp=not no_gbp, web_search=config.ENRICH_WEB_SEARCH, lead_ids=need,
                                progress=lambda l, r: con_.print(f"  #{l['id']} {l['name'][:35]}: fotos={r.get('images', 0)} email={'sim' if r.get('email') else 'não'}")))
    con_.rule(f"2/2 gerando {len(id_list)} sites")
    r = build(con, include_low_priority=True, rebuild=True, lead_ids=id_list, template=template,
              progress=lambda l, u, img: con_.print(f"  #{l['id']} {'com foto' if img else 'sem foto'}  {l['name'][:35]}"))
    con_.print(f"[bold]{r.get('built', 0)} sites gerados. Veja na aba Leads (ver site ↗) ou Checklist.[/bold]")


@hero_app.command("templates")
def hero_templates():
    """Lista os templates disponíveis (pacote + data/templates)."""
    from .hero.build import list_templates
    _print_table("templates", ["nome", "origem", "arquivo"], [[t["name"], t["source"], t["path"]] for t in list_templates()])


@hero_app.command("shot")
def hero_shot(lead_id: Optional[int] = typer.Argument(None, help="vazio = todos os HERO_PRONTO")):
    """Tira uma foto do hero em tamanho de celular (390px, página inteira) → data/hero_site/<slug>/preview.png"""
    from .qualify.render_check import new_browser
    from playwright.async_api import async_playwright

    con = _con()
    q = "SELECT id, slug, hero_path FROM leads WHERE hero_path IS NOT NULL" + (" AND id=?" if lead_id else "")
    rows = con.execute(q, (lead_id,) if lead_id else ()).fetchall()
    if not rows:
        con_.print("nenhum hero gerado (rode lp hero build)"); raise typer.Exit(1)

    async def go():
        async with async_playwright() as pw:
            b = await new_browser(pw)
            ctxm = await b.new_context(viewport=config.MOBILE_VIEWPORT, device_scale_factor=2, is_mobile=True, user_agent=config.MOBILE_UA)
            ctxd = await b.new_context(viewport={"width": 1280, "height": 800})
            try:
                for r in rows:
                    for ctx, name in ((ctxm, "preview.png"), (ctxd, "preview_desktop.png")):
                        pg = await ctx.new_page()
                        await pg.goto(Path(r["hero_path"], "index.html").resolve().as_uri())
                        await pg.wait_for_timeout(600)
                        await pg.evaluate("var b=document.getElementById('bottom'); if(b) b.remove(); document.body.classList.remove('pad')")
                        out = Path(r["hero_path"]) / name
                        await pg.screenshot(path=str(out), full_page=True)
                        await pg.close()
                        con_.print(f"  #{r['id']} {out}")
            finally:
                await b.close()
    asyncio.run(go())


@hero_app.command("list")
def hero_list():
    con = _con()
    rows = con.execute("SELECT id, name, city, status, hero_url, hero_expires_at, priority FROM leads WHERE hero_url IS NOT NULL ORDER BY hero_built_at DESC").fetchall()
    _print_table("heros", ["id", "nome", "cidade", "status", "url", "expira", "prio"], [list(r) for r in rows])


# ============================================================== touch draft

@touch_app.command("draft")
def touch_draft(lead_id: Optional[int] = typer.Argument(None), n: Optional[int] = typer.Option(None, "--n"),
                today: bool = typer.Option(False, help="rascunhos de toda a fila de hoje"),
                sender_name: Optional[str] = None, sender_phone: Optional[str] = None, video_url: Optional[str] = None):
    """Imprime o texto pronto do próximo toque (ou --n) para copiar e colar."""
    from .tracking.templates import render
    con = _con()
    sender = {k: v for k, v in {"sender_name": sender_name, "sender_phone": sender_phone, "video_url": video_url}.items() if v}
    targets = []
    if today:
        for i in daily_queue(con):
            targets.append((i.lead_id, i.touch_number))
    elif lead_id is not None:
        if n is None:
            row = con.execute("SELECT COALESCE(MAX(touch_number),0)+1 FROM touches WHERE lead_id=?", (lead_id,)).fetchone()
            n = min(int(row[0]), 4)
        targets.append((lead_id, n))
    else:
        con_.print("informe um lead_id ou --today"); raise typer.Exit(1)
    for lid, tn in targets:
        lead = db.get_lead(con, lid)
        t1 = con.execute("SELECT sent_at FROM touches WHERE lead_id=? AND touch_number=1", (lid,)).fetchone()
        d = render(tn, lead, (t1["sent_at"][:10] if t1 else None), sender)
        con_.rule(f"#{lid} {lead['name']} — toque {tn} ({d['channel']})")
        if d["subject"]:
            con_.print(f"[bold]Subject:[/bold] {d['subject']}")
        con_.print(d["body"])
        con_.print(f"[dim]registrar: lp touch log {lid} --n {tn} --channel {d['channel']}[/dim]")


# ============================================================== ui / pipeline

@app.command("ui")
def ui(port: int = 8090, no_browser: bool = typer.Option(False, help="não abre o navegador"),
       public: bool = typer.Option(False, help="abre túnel público (cloudflared) para acessar do celular")):
    """Aplicativo: painel, leads, novo lead, templates, vídeos, fila, rodar. --public = URL para o celular."""
    from .ui.server import serve
    serve(port, open_browser=not no_browser, public=public)


@app.command("pipeline")
def pipeline(
    vertical: str = typer.Option(...), state: str = typer.Option(...),
    city: list[str] = typer.Option(None, "--city"), min_pop: int = 20000, max_cities: Optional[int] = None,
    max_results: Optional[int] = None,
    only: str = typer.Option("SEM_SITE", help="enriquecer/gerar hero só para este site_status; 'all' = todos"),
    no_search: bool = False, no_gbp: bool = False, headful: bool = False,
):
    """Esteira completa: busca → qualifica → enriquece → gera heros. Um comando."""
    from .enrich.runner import run as enrich_run_
    from .hero.build import build
    from .qualify.runner import run as qualify_run_
    from .sourcing.google_maps import ScrapeOptions, scrape_many

    con = _con()
    st = state.upper()
    cities = list(city) if city else [c["name"] for c in cities_for_state(st, min_pop, max_cities)]
    queries = [(f"{vertical} {c} {st}", vertical, c, st) for c in cities]
    con_.rule(f"1/4 sourcing: {len(queries)} cidades")
    total = asyncio.run(scrape_many(con, queries, ScrapeOptions(headless=not headful, max_results=max_results),
                                    progress=lambda q, s, skipped=False: con_.print("  " + (f"[dim]pulado[/dim] {q}" if skipped else _stats_line(q, s)))))
    con_.print("[bold]" + _stats_line("TOTAL", total) + "[/bold]")
    con_.rule("2/4 qualificação")
    counts = asyncio.run(qualify_run_(con, vertical=vertical, state=st))
    counts.pop("_elapsed_s", None)
    con_.print(f"  {counts}")
    filt = None if only.lower() == "all" else only.upper()
    con_.rule(f"3/4 enriquecimento ({filt or 'todos'})")
    agg = asyncio.run(enrich_run_(con, web_search=not no_search, gbp=not no_gbp, site_status=filt,
                                  progress=lambda l, r: con_.print(f"  #{l['id']} {l['name'][:35]} {r}")))
    con_.print(f"  {agg}")
    con_.rule(f"4/4 heros ({filt or 'todos'})")
    r = build(con, include_low_priority=True, site_status=filt, progress=lambda l, u, img: con_.print(f"  #{l['id']} {'🖼' if img else '▫'} {u}"))
    con_.print(f"  {r.get('built', 0)} heros em {r.get('site_dir', '')}")
    con_.rule("resumo")
    cols, rows = reports.qualification_by_region(con, "city")
    _print_table("Qualificação por cidade", cols, rows, max_rows=30)
    con_.print("próximo: [bold]lp ui[/bold] para ver tudo numa tela")


@app.command("hunt")
def hunt(
    state: str = typer.Option(..., help="sigla, ex: OH"),
    vertical: list[str] = typer.Option(None, "--vertical", help="repetível; padrão = as 5 verticais"),
    by: str = typer.Option("county", help="county (zona rural, padrão) | city"),
    min_pop: int = 10000, max_places: Optional[int] = None,
    headful: bool = False, force: bool = False,
):
    """CAÇA SEM SITE: varre verticais × condados (ou cidades) pegando só quem não tem
    site. Cada lead já entra como SEM_SITE / QUALIFICADO. Depois: lp enrich run, lp hero build."""
    from .sourcing.cities import places_for_state
    from .sourcing.google_maps import ScrapeOptions, scrape_many

    con = _con()
    st = state.upper()
    verticals = list(vertical) if vertical else config.HUNT_VERTICALS
    places = places_for_state(st, by, min_pop, max_places)
    queries = [(f"{v} {pl} {st}", v, pl, st) for pl in places for v in verticals]
    con_.print(f"[bold]caça em {st}: {len(places)} {by}s × {len(verticals)} verticais = {len(queries)} buscas[/bold] (~20–40 s cada)")
    run_id = db.start_run(con, "hunt", json.dumps({"state": st, "by": by, "places": len(places), "verticals": verticals}))
    before = con.execute("SELECT COUNT(*) FROM leads WHERE site_status='SEM_SITE'").fetchone()[0]

    def progress(q, stats, skipped=False):
        if skipped:
            con_.print(f"  [dim]pulado (já rodou):[/dim] {q}")
        else:
            con_.print(f"  {q}: [green]sem site novos={stats.inserted}[/green]  dup={stats.duplicates}  com site pulados={stats.with_site}")

    total = asyncio.run(scrape_many(con, queries, ScrapeOptions(headless=not headful, no_site_only=True), force=force, progress=progress))
    after = con.execute("SELECT COUNT(*) FROM leads WHERE site_status='SEM_SITE'").fetchone()[0]
    db.finish_run(con, run_id, processed=total.found + total.with_site, produced=total.inserted)
    con_.print(f"[bold]SEM SITE no banco: {before} → {after} (+{after - before}); com site descartados na hora: {total.with_site}[/bold]")
    cols, rows = reports.leads_per_query(con)
    _print_table("rendimento por busca (novos = sem site)", cols, rows, max_rows=25)
    con_.print("próximo: [bold]lp enrich run --only SEM_SITE[/bold] → [bold]lp hero build --include-low[/bold] → [bold]lp ui[/bold]")


# ============================================================== doctor

@app.command("doctor")
def doctor():
    """Checa a máquina: Python, Playwright, Chromium, banco, internet, Vercel, domínio."""
    import shutil, sys as _sys
    ok = lambda b: "[green]ok[/green]" if b else "[red]FALTA[/red]"
    con_.print(f"python {_sys.version.split()[0]}  {ok(_sys.version_info >= (3, 10))}")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            kw = {"headless": True}
            if config.CHROMIUM_PATH:
                kw["executable_path"] = config.CHROMIUM_PATH
            b = pw.chromium.launch(**kw); v = b.version; b.close()
        con_.print(f"chromium {v}  {ok(True)}")
    except Exception as e:
        con_.print(f"chromium  {ok(False)}  → rode: playwright install chromium   ({str(e)[:80]})")
    try:
        c = _con(); n = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        con_.print(f"banco {config.DB_PATH} ({n} leads)  {ok(True)}")
    except Exception as e:
        con_.print(f"banco  {ok(False)} {e}")
    import httpx
    for label, url in [("google maps", "https://www.google.com/maps"), ("duckduckgo", "https://html.duckduckgo.com/html/?q=x")]:
        try:
            r = httpx.get(url, timeout=8, follow_redirects=True, headers={"User-Agent": config.MOBILE_UA}); good = r.status_code < 400
        except Exception:
            good = False
        con_.print(f"internet → {label}  {ok(good)}")
    con_.print(f"vercel cli  {'[green]ok[/green]' if shutil.which('vercel') else '[dim]ausente[/dim]'}  (opcional, só para publicar depois do fechamento)")
    dom = "[dim]não definido (opcional; heros ficam locais em data/hero_site)[/dim]" if config.HERO_DOMAIN.startswith("SEUDOMINIO") else f"[green]{config.HERO_DOMAIN}[/green]"
    con_.print(f"domínio dos heros: {dom}")


if __name__ == "__main__":
    app()
