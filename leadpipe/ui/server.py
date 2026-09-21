"""Aplicativo local: `lp ui` sobe um servidor em http://127.0.0.1:8090 com uma
tela só (leadpipe/ui/index.html). Só biblioteca padrão, sem framework, sem IA.

`lp ui --public` abre também um túnel (cloudflared) e imprime uma URL pública
para usar no celular; com LEADPIPE_UI_TOKEN definido, a tela pede a senha.

API (JSON):
  GET  /api/summary                    contagens, região, funil, enriquecimento
  GET  /api/leads?status=&site=&q=     lista de leads
  GET  /api/lead/<id>                  detalhe + histórico + toques + rascunho
  GET  /api/queue                      fila do dia
  GET  /api/checklist                  leads com hero: vídeo / enviado / respondeu
  GET  /api/templates[?name=x]         lista de templates (ou o HTML de um)
  GET  /api/jobs                       saída dos comandos rodando
  GET  /api/public                     URL pública do túnel, se houver
  POST /api/action  {op, ...}          touch | reply | status | note | set | run |
                                       create_lead | save_template | delete_template |
                                       preview | video
  POST /api/video/<id>  (corpo = arquivo)  salva o vídeo do lead em data/videos
Arquivos: /shots/<id>.png, /hero/<slug>/..., /img/<lead>/<file>, /videos/<file>, /preview/<slug>/...
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import config, db
from ..qualify.runner import auto_qualify_no_site
from ..sourcing.base import IngestStats, RawLead, ingest_one
from ..tracking import reports
from ..tracking.templates import render as render_touch
from ..tracking.touches import daily_queue, log_reply, log_touch

HERE = Path(__file__).parent
_jobs: list[dict] = []
_jobs_lock = threading.Lock()
_public: dict = {"url": None, "status": "off"}
TOKEN = os.environ.get("LEADPIPE_UI_TOKEN") or ""


# ------------------------------------------------------------------ dados

def _rows(cols, rows):
    return [dict(zip(cols, r)) for r in rows]


def _summary(con):
    out = {}
    for key, fn in [("status", reports.status_counts), ("funnel", reports.funnel), ("enrich", reports.enrichment_quality),
                    ("daily", reports.qualified_per_day), ("channels", reports.response_by_channel),
                    ("touches", reports.response_by_touch), ("queries", reports.leads_per_query)]:
        cols, rows = fn(con)
        out[key] = _rows(cols, rows)
    cols, rows = reports.qualification_by_region(con, "city")
    out["region"] = _rows(cols, rows)
    out["hero_domain"] = config.HERO_DOMAIN
    out["verticals"] = config.HUNT_VERTICALS
    out["counts"] = {
        "sem_site": con.execute("SELECT COUNT(*) FROM leads WHERE site_status='SEM_SITE'").fetchone()[0],
        "heros": con.execute("SELECT COUNT(*) FROM leads WHERE hero_path IS NOT NULL").fetchone()[0],
        "videos": con.execute("SELECT COUNT(*) FROM leads WHERE video_done_at IS NOT NULL").fetchone()[0],
        "sent": con.execute("SELECT COUNT(DISTINCT lead_id) FROM touches").fetchone()[0],
        "replied": con.execute("SELECT COUNT(*) FROM leads WHERE status IN ('RESPONDEU','CALL_AGENDADA','FECHADO')").fetchone()[0],
        "closed": con.execute("SELECT COUNT(*) FROM leads WHERE status='FECHADO'").fetchone()[0],
    }
    return out


def _leads(con, q):
    where, args = ["1=1"], []
    if q.get("status"):
        where.append("status=?"); args.append(q["status"])
    if q.get("site"):
        where.append("site_status=?"); args.append(q["site"])
    if q.get("source"):
        where.append("source=?"); args.append(q["source"])
    if q.get("q"):
        where.append("(name LIKE ? OR city LIKE ? OR phone_e164 LIKE ?)"); args += [f"%{q['q']}%"] * 3
    rows = con.execute(f"""SELECT id, name, city, state, vertical, phone_e164, website_url, status, site_status, site_reason, rating,
                          review_count, email, facebook_url, instagram_url, hero_url, slug, priority, screenshot_path, source,
                          hero_template, video_done_at, video_url, video_path,
                          (SELECT COUNT(*) FROM lead_images i WHERE i.lead_id=leads.id AND i.kind<>'logo') AS n_images,
                          (SELECT COUNT(*) FROM touches t WHERE t.lead_id=leads.id) AS n_touches
                          FROM leads WHERE {' AND '.join(where)}
                          ORDER BY CASE site_status WHEN 'SEM_SITE' THEN 0 WHEN 'SITE_QUEBRADO' THEN 1 WHEN 'SITE_ANTIGO' THEN 2 ELSE 3 END, id DESC
                          LIMIT 800""", args).fetchall()
    return [dict(r) for r in rows]


def _lead(con, lead_id):
    lead = db.get_lead(con, lead_id)
    if not lead:
        return None
    d = dict(lead)
    d["history"] = [dict(r) for r in con.execute("SELECT from_status, to_status, at, note FROM lead_status_history WHERE lead_id=? ORDER BY at", (lead_id,))]
    d["touches"] = [dict(r) for r in con.execute("SELECT touch_number, channel, sent_at, replied_at, template FROM touches WHERE lead_id=? ORDER BY touch_number", (lead_id,))]
    d["images"] = [dict(r) for r in con.execute("SELECT path, kind, width, height, source FROM lead_images WHERE lead_id=? ORDER BY score DESC", (lead_id,))]
    d["reviews"] = [dict(r) for r in con.execute("SELECT author, rating, text FROM lead_reviews WHERE lead_id=? ORDER BY rating DESC LIMIT 5", (lead_id,))]
    nxt = min((max([t["touch_number"] for t in d["touches"]] or [0]) + 1), 4)
    t1 = next((t for t in d["touches"] if t["touch_number"] == 1), None)
    d["next_touch"] = nxt
    d["draft"] = render_touch(nxt, lead, t1["sent_at"][:10] if t1 else None)
    d["checks"] = [dict(r) for r in con.execute("SELECT checked_at, site_status, reason, http_status, elapsed_ms FROM site_checks WHERE lead_id=? ORDER BY checked_at DESC LIMIT 3", (lead_id,))]
    return d


def _queue(con):
    return [i.__dict__ | {"due_date": str(i.due_date)} for i in daily_queue(con, include_future_days=0)]


def _checklist(con):
    rows = con.execute("""
        SELECT l.id, l.name, l.city, l.state, l.status, l.slug, l.hero_path, l.hero_url, l.video_done_at, l.video_url, l.video_path,
               l.phone_e164, l.email, l.facebook_url,
               (SELECT MIN(sent_at) FROM touches t WHERE t.lead_id=l.id) AS first_sent,
               (SELECT COUNT(*) FROM touches t WHERE t.lead_id=l.id) AS n_touches,
               (SELECT MAX(replied_at) FROM touches t WHERE t.lead_id=l.id) AS replied_at
        FROM leads l WHERE l.hero_path IS NOT NULL
        ORDER BY CASE WHEN l.video_done_at IS NULL THEN 0 ELSE 1 END, l.hero_built_at DESC""").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["hero"] = True
        d["video"] = bool(r["video_done_at"])
        d["sent"] = bool(r["first_sent"])
        d["replied"] = r["status"] in ("RESPONDEU", "CALL_AGENDADA", "FECHADO") or bool(r["replied_at"])
        d["call"] = r["status"] in ("CALL_AGENDADA", "FECHADO")
        d["closed"] = r["status"] == "FECHADO"
        out.append(d)
    return out


def _create_lead(con, b: dict) -> dict:
    name = (b.get("name") or "").strip()
    if not name:
        return {"error": "nome obrigatório"}
    raw = RawLead(name=name, vertical=(b.get("vertical") or "roof cleaning").strip(), source=b.get("source") or "manual",
                  source_query=b.get("source_query") or "manual", phone_raw=b.get("phone") or None,
                  address_full=b.get("address") or None, city=b.get("city") or None, state=(b.get("state") or None),
                  website_url=b.get("website") or None, gbp_url=b.get("gbp_url") or None,
                  rating=float(b["rating"]) if b.get("rating") else None,
                  review_count=int(b["reviews"]) if b.get("reviews") else None,
                  facebook_url=b.get("facebook") or None, instagram_url=b.get("instagram") or None,
                  email=b.get("email") or None, category=b.get("category") or None)
    st = IngestStats()
    lead_id = ingest_one(con, raw, st)
    if lead_id and b.get("notes"):
        db.update_lead(con, lead_id, notes=b["notes"])
    if lead_id:
        auto_qualify_no_site(con, lead_id)
    return {"ok": True, "lead_id": lead_id, "created": bool(st.inserted)}


# ------------------------------------------------------------------ jobs

def _run_job(args: list[str]) -> dict:
    job = {"cmd": " ".join(args), "status": "rodando", "log": ""}
    with _jobs_lock:
        _jobs.append(job)
        if len(_jobs) > 12:
            _jobs.pop(0)

    def worker():
        try:
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            p = subprocess.Popen([sys.executable, "-m", "leadpipe", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace", cwd=str(config.ROOT), env=env)
            for line in p.stdout:
                job["log"] += line
            p.wait()
            job["status"] = "ok" if p.returncode == 0 else f"erro ({p.returncode})"
        except Exception as e:
            job["status"] = f"erro: {e}"
    threading.Thread(target=worker, daemon=True).start()
    return job


def _cities(v: str | None) -> list[str]:
    return sum([["--city", c.strip()] for c in (v or "").split(",") if c.strip()], [])


def _run_action(body: dict) -> dict:
    what = body.get("what")
    v, st = body.get("vertical") or "roof cleaning", body.get("state") or "OH"
    allowed = {
        "qualify": ["qualify", "run"],
        "qualify-recheck": ["qualify", "run", "--recheck"],
        "enrich": ["enrich", "run"],
        "enrich-nosite": ["enrich", "run", "--only", "SEM_SITE"],
        "hero": ["hero", "build"],
        "hero-all": ["hero", "build", "--include-low"],
        "source": ["source", "maps", "--vertical", v, "--state", st] + _cities(body.get("cities"))
                  + (["--max-results", str(int(body["max_results"]))] if body.get("max_results") else []),
        "pipeline": ["pipeline", "--vertical", v, "--state", st] + _cities(body.get("cities")),
        "hunt": ["hunt", "--state", st, "--by", body.get("by") or "county"]
                + sum([["--vertical", x.strip()] for x in (body.get("vertical") or "").split(",") if x.strip()], [])
                + (["--max-places", str(int(body["max_places"]))] if body.get("max_places") else []),
        "expire": ["hero", "expire"],
    }
    if what == "lead-hero":  # enriquecer (se preciso) + gerar hero de um lead, com template
        lid = str(int(body["lead_id"]))
        args = ["hero", "build", "--id", lid]
        if body.get("template"):
            args += ["--template", body["template"]]
        return {"job": _run_job(args)}
    if what == "lead-enrich":
        return {"job": _run_job(["enrich", "run", "--id", str(int(body["lead_id"]))])}
    if what == "batch":
        ids = [str(int(i)) for i in (body.get("ids") or [])]
        if not ids:
            return {"error": "selecione pelo menos um lead"}
        tpl = ["--template", body["template"]] if body.get("template") else []
        return {"job": _run_job(["hero", "batch", "--ids", ",".join(ids), *tpl])}
    if what == "batch-all":
        return {"job": _run_job(["hero", "batch", "--all-no-site"])}
    if what == "lead-full":
        lid = str(int(body["lead_id"]))
        tpl = ["--template", body["template"]] if body.get("template") else []
        return {"job": _run_job(["hero", "one", "--id", lid, *tpl])}
    if what not in allowed:
        return {"error": "comando desconhecido"}
    return {"job": _run_job(allowed[what])}


def _preview(con, body: dict) -> dict:
    """Renderiza um template com os dados de um lead numa pasta separada (não mexe no hero oficial)."""
    from ..hero.build import hero_data, render
    name = body.get("template") or config.HERO_TEMPLATE_DEFAULT
    lid = int(body.get("lead_id") or 0)
    lead = db.get_lead(con, lid) if lid else con.execute("SELECT * FROM leads WHERE hero_path IS NOT NULL ORDER BY hero_built_at DESC LIMIT 1").fetchone()
    if lead is None:
        lead = con.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 1").fetchone()
    if lead is None:
        return {"error": "nenhum lead no banco para pré-visualizar"}
    pdir = config.DATA_DIR / "hero_preview"
    pdir.mkdir(parents=True, exist_ok=True)
    data = hero_data(con, lead, pdir)
    html = render(data, template=name)
    (pdir / data["slug"] / "index.html").write_text(html, encoding="utf-8")
    return {"ok": True, "url": f"/preview/{data['slug']}/", "lead_id": lead["id"]}


def _action(con, body: dict) -> dict:
    from ..hero.build import list_templates, save_user_template
    op = body.get("op")
    lid = int(body.get("lead_id", 0) or 0)
    if op == "touch":
        log_touch(con, lid, int(body["n"]), body["channel"], template=body.get("template"))
    elif op == "reply":
        log_reply(con, lid)
    elif op == "status":
        db.transition(con, lid, body["status"].upper(), body.get("note"))
    elif op == "note":
        db.update_lead(con, lid, notes=body.get("notes", ""))
    elif op == "set":
        field = body.get("field")
        if field not in db.LEAD_COLUMNS or field in ("id", "status"):
            return {"error": "campo inválido"}
        db.update_lead(con, lid, **{field: body.get("value")})
    elif op == "video":
        fields = {}
        if "done" in body:
            fields["video_done_at"] = db.now_iso() if body["done"] else None
        if "url" in body:
            fields["video_url"] = body["url"] or None
        db.update_lead(con, lid, **fields)
    elif op == "create_lead":
        return _create_lead(con, body)
    elif op == "save_template":
        p = save_user_template(body.get("name") or "custom", body.get("html") or "")
        return {"ok": True, "path": str(p), "templates": list_templates()}
    elif op == "delete_template":
        f = config.USER_TEMPLATES_DIR / f"{re.sub(r'[^a-z0-9_-]', '', (body.get('name') or '').lower())}.html"
        if f.exists():
            f.unlink()
        return {"ok": True, "templates": list_templates()}
    elif op == "preview":
        return _preview(con, body)
    elif op == "run":
        return _run_action(body)
    else:
        return {"error": "op desconhecida"}
    return {"ok": True}


# ------------------------------------------------------------------ http

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    # -- auth simples por token (cookie), só quando LEADPIPE_UI_TOKEN existe
    def _authed(self) -> bool:
        if not TOKEN:
            return True
        q = parse_qs(urlparse(self.path).query)
        if q.get("token", [""])[0] == TOKEN:
            return True
        c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return "lp_token" in c and c["lp_token"].value == TOKEN

    def _json(self, obj, code=200, extra_headers=None):
        data = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path: Path, ctype: str | None = None):
        if not path.exists() or not path.is_file():
            self.send_error(404); return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or self.guess_type(str(path)))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _login_page(self):
        html = (HERE / "index.html").read_text(encoding="utf-8")
        body = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
                "<title>leadpipe</title><body style='font-family:system-ui;background:#0f1115;color:#e6e8ee;display:grid;place-items:center;height:100vh;margin:0'>"
                "<form method=get style='background:#171a21;padding:24px;border-radius:14px;min-width:280px'><h2 style='margin:0 0 12px'>leadpipe</h2>"
                "<input name=token type=password placeholder='senha' style='width:100%;padding:12px;border-radius:10px;border:1px solid #333;background:#0f1115;color:#fff;font-size:16px'>"
                "<button style='margin-top:10px;width:100%;padding:12px;border:0;border-radius:10px;background:#7c6cff;color:#fff;font-weight:700;font-size:16px'>Entrar</button></form></body>")
        data = body.encode("utf-8")
        self.send_response(401)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if not self._authed():
            if u.path in ("/", "/index.html"):
                return self._login_page()
            return self.send_error(401)
        con = db.connect()
        try:
            if u.path in ("/", "/index.html"):
                data = (HERE / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                if TOKEN and q.get("token") == TOKEN:
                    self.send_header("Set-Cookie", f"lp_token={TOKEN}; Path=/; Max-Age=2592000; SameSite=Lax")
                self.end_headers()
                return self.wfile.write(data)
            if u.path == "/manifest.json":
                return self._json({"name": "leadpipe", "short_name": "leadpipe", "start_url": "/", "display": "standalone",
                                   "background_color": "#0f1115", "theme_color": "#0f1115",
                                   "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]})
            if u.path == "/icon.svg":
                svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#7c6cff"/><text x="32" y="42" font-size="30" text-anchor="middle" fill="#fff" font-family="sans-serif" font-weight="800">lp</text></svg>'
                self.send_response(200); self.send_header("Content-Type", "image/svg+xml"); self.send_header("Content-Length", str(len(svg))); self.end_headers()
                return self.wfile.write(svg)
            if u.path == "/api/summary":
                return self._json(_summary(con))
            if u.path == "/api/leads":
                return self._json(_leads(con, q))
            if u.path.startswith("/api/lead/"):
                d = _lead(con, int(u.path.rsplit("/", 1)[1]))
                return self._json(d or {"error": "não existe"}, 200 if d else 404)
            if u.path == "/api/queue":
                return self._json(_queue(con))
            if u.path == "/api/checklist":
                return self._json(_checklist(con))
            if u.path == "/api/templates":
                from ..hero.build import list_templates, template_source
                if q.get("name"):
                    try:
                        return self._json({"name": q["name"], "html": template_source(q["name"])})
                    except FileNotFoundError:
                        return self._json({"error": "template não existe"}, 404)
                return self._json({"templates": list_templates(), "default": config.HERO_TEMPLATE_DEFAULT})
            if u.path == "/api/jobs":
                with _jobs_lock:
                    return self._json(list(reversed(_jobs)))
            if u.path == "/api/public":
                return self._json(_public)
            if u.path.startswith("/shots/"):
                return self._file(config.SCREENSHOT_DIR / Path(u.path).name)
            if u.path.startswith("/videos/"):
                return self._file(config.VIDEOS_DIR / Path(u.path).name)
            if u.path.startswith("/img/"):
                parts = Path(u.path).parts[2:]
                return self._file(config.IMAGES_DIR.joinpath(*parts))
            if u.path.startswith("/hero/") or u.path.startswith("/preview/"):
                base = config.HERO_SITE_DIR if u.path.startswith("/hero/") else config.DATA_DIR / "hero_preview"
                rel = Path(*Path(u.path).parts[2:]) if len(Path(u.path).parts) > 2 else Path(".")
                target = base / rel
                if target.is_dir():
                    target = target / "index.html"
                return self._file(target)
            self.send_error(404)
        finally:
            con.close()

    def do_POST(self):
        u = urlparse(self.path)
        if not self._authed():
            return self.send_error(401)
        n = int(self.headers.get("Content-Length") or 0)
        if u.path.startswith("/api/video/"):
            lid = int(u.path.rsplit("/", 1)[1])
            ext = (self.headers.get("X-File-Ext") or "mp4").strip(". ").lower()[:5] or "mp4"
            config.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
            out = config.VIDEOS_DIR / f"{lid}.{ext}"
            with open(out, "wb") as f:
                remaining = n
                while remaining > 0:
                    chunk = self.rfile.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    f.write(chunk); remaining -= len(chunk)
            con = db.connect()
            try:
                db.update_lead(con, lid, video_path=str(out), video_done_at=db.now_iso())
            finally:
                con.close()
            return self._json({"ok": True, "path": str(out), "url": f"/videos/{out.name}"})
        body = json.loads(self.rfile.read(n) or b"{}")
        if u.path != "/api/action":
            return self.send_error(404)
        con = db.connect()
        try:
            try:
                return self._json(_action(con, body))
            except Exception as e:
                return self._json({"error": f"{type(e).__name__}: {e}"}, 400)
        finally:
            con.close()


# ------------------------------------------------------------------ túnel público

def _cloudflared_path() -> str | None:
    found = shutil.which("cloudflared")
    if found:
        return found
    bin_dir = config.DATA_DIR / "bin"
    exe = bin_dir / ("cloudflared.exe" if os.name == "nt" else "cloudflared")
    if exe.exists():
        return str(exe)
    # download único (~30 MB) do release oficial
    import platform
    import urllib.request
    sysname, arch = platform.system().lower(), platform.machine().lower()
    if sysname == "windows":
        name = "cloudflared-windows-amd64.exe"
    elif sysname == "darwin":
        name = "cloudflared-darwin-arm64.tgz" if "arm" in arch else "cloudflared-darwin-amd64.tgz"
    else:
        name = "cloudflared-linux-arm64" if "aarch64" in arch or "arm" in arch else "cloudflared-linux-amd64"
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{name}"
    bin_dir.mkdir(parents=True, exist_ok=True)
    print(f"baixando cloudflared ({name})...")
    try:
        tmp = bin_dir / name
        urllib.request.urlretrieve(url, tmp)
        if name.endswith(".tgz"):
            import tarfile
            with tarfile.open(tmp) as t:
                t.extract("cloudflared", bin_dir)
            tmp.unlink()
        else:
            tmp.rename(exe)
        if os.name != "nt":
            exe.chmod(0o755)
        return str(exe)
    except Exception as e:
        print(f"não consegui baixar o cloudflared: {e}")
        return None


def start_tunnel(port: int) -> None:
    exe = _cloudflared_path()
    if not exe:
        _public["status"] = "cloudflared indisponível"
        return
    _public["status"] = "iniciando"
    p = subprocess.Popen([exe, "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    rx = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

    def reader():
        for line in p.stdout:
            m = rx.search(line)
            if m and not _public["url"]:
                _public["url"] = m.group(0)
                _public["status"] = "ok"
                extra = f"?token={TOKEN}" if TOKEN else ""
                print(f"\nURL PÚBLICA (celular): {m.group(0)}{extra}\n")
        _public["status"] = "encerrado"
    threading.Thread(target=reader, daemon=True).start()


def serve(port: int = 8090, open_browser: bool = True, public: bool = False) -> None:
    config.ensure_dirs()
    srv = ThreadingHTTPServer(("0.0.0.0" if public else "127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"painel: {url}   (Ctrl+C para parar)")
    if TOKEN:
        print("senha ativa (LEADPIPE_UI_TOKEN)")
    elif public:
        print("AVISO: túnel público sem senha. Defina LEADPIPE_UI_TOKEN para proteger.")
    if public:
        threading.Thread(target=start_tunnel, args=(port,), daemon=True).start()
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
