"""Painel local: `lp ui` sobe um servidor em http://127.0.0.1:8090 com uma
tela só (leadpipe/ui/index.html). Só biblioteca padrão, sem framework.

API (JSON):
  GET  /api/summary                  contagens, região, enriquecimento
  GET  /api/leads?status=&site=&q=   lista de leads
  GET  /api/lead/<id>                detalhe + histórico + toques + rascunho
  GET  /api/queue                    fila do dia
  GET  /api/jobs                     saída dos comandos rodando
  POST /api/action  {op, ...}        touch | reply | status | note | run
Arquivos: /shots/<id>.png, /hero/<slug>/..., /img/<lead>/<file>
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import config, db
from ..tracking import reports
from ..tracking.templates import render as render_touch
from ..tracking.touches import daily_queue, log_reply, log_touch

HERE = Path(__file__).parent
_jobs: list[dict] = []
_jobs_lock = threading.Lock()


def _rows(con, cols, rows):
    return [dict(zip(cols, r)) for r in rows]


def _summary(con):
    out = {}
    for key, fn in [("status", reports.status_counts), ("funnel", reports.funnel), ("enrich", reports.enrichment_quality),
                    ("daily", reports.qualified_per_day), ("channels", reports.response_by_channel), ("touches", reports.response_by_touch)]:
        cols, rows = fn(con)
        out[key] = _rows(con, cols, rows)
    cols, rows = reports.qualification_by_region(con, "city")
    out["region"] = _rows(con, cols, rows)
    out["hero_domain"] = config.HERO_DOMAIN
    return out


def _leads(con, q):
    where, args = ["1=1"], []
    if q.get("status"):
        where.append("status=?"); args.append(q["status"])
    if q.get("site"):
        where.append("site_status=?"); args.append(q["site"])
    if q.get("q"):
        where.append("(name LIKE ? OR city LIKE ? OR phone_e164 LIKE ?)"); args += [f"%{q['q']}%"] * 3
    rows = con.execute(f"""SELECT id, name, city, state, phone_e164, website_url, status, site_status, site_reason, rating,
                          review_count, email, facebook_url, instagram_url, hero_url, slug, priority, screenshot_path,
                          (SELECT COUNT(*) FROM lead_images i WHERE i.lead_id=leads.id AND i.kind<>'logo') AS n_images
                          FROM leads WHERE {' AND '.join(where)}
                          ORDER BY CASE site_status WHEN 'SEM_SITE' THEN 0 WHEN 'SITE_QUEBRADO' THEN 1 WHEN 'SITE_ANTIGO' THEN 2 ELSE 3 END, id DESC
                          LIMIT 500""", args).fetchall()
    return [dict(r) for r in rows]


def _lead(con, lead_id):
    lead = db.get_lead(con, lead_id)
    if not lead:
        return None
    d = dict(lead)
    d["history"] = [dict(r) for r in con.execute("SELECT from_status, to_status, at, note FROM lead_status_history WHERE lead_id=? ORDER BY at", (lead_id,))]
    d["touches"] = [dict(r) for r in con.execute("SELECT touch_number, channel, sent_at, replied_at, template FROM touches WHERE lead_id=? ORDER BY touch_number", (lead_id,))]
    d["images"] = [dict(r) for r in con.execute("SELECT path, kind, width, height, source FROM lead_images WHERE lead_id=? ORDER BY score DESC", (lead_id,))]
    nxt = min((max([t["touch_number"] for t in d["touches"]] or [0]) + 1), 4)
    t1 = next((t for t in d["touches"] if t["touch_number"] == 1), None)
    d["next_touch"] = nxt
    d["draft"] = render_touch(nxt, lead, t1["sent_at"][:10] if t1 else None)
    checks = con.execute("SELECT checked_at, site_status, reason, http_status, elapsed_ms FROM site_checks WHERE lead_id=? ORDER BY checked_at DESC LIMIT 3", (lead_id,)).fetchall()
    d["checks"] = [dict(r) for r in checks]
    return d


def _queue(con):
    out = []
    for i in daily_queue(con, include_future_days=0):
        out.append(i.__dict__ | {"due_date": str(i.due_date)})
    return out


def _run_job(args: list[str]) -> dict:
    job = {"cmd": " ".join(args), "status": "rodando", "log": ""}
    with _jobs_lock:
        _jobs.append(job)
        if len(_jobs) > 10:
            _jobs.pop(0)

    def worker():
        try:
            p = subprocess.Popen([sys.executable, "-m", "leadpipe", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace", cwd=str(config.ROOT))
            for line in p.stdout:
                job["log"] += line
            p.wait()
            job["status"] = "ok" if p.returncode == 0 else f"erro ({p.returncode})"
        except Exception as e:
            job["status"] = f"erro: {e}"
    threading.Thread(target=worker, daemon=True).start()
    return job


def _action(con, body: dict) -> dict:
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
    elif op == "run":
        allowed = {
            "qualify": ["qualify", "run"],
            "qualify-recheck": ["qualify", "run", "--recheck"],
            "enrich": ["enrich", "run"],
            "enrich-nosite": ["enrich", "run", "--only", "SEM_SITE"],
            "hero": ["hero", "build"],
            "hero-all": ["hero", "build", "--include-low"],
            "source": ["source", "maps", "--vertical", body.get("vertical", "roof cleaning"), "--state", body.get("state", "OH")]
                      + sum([["--city", c.strip()] for c in (body.get("cities") or "").split(",") if c.strip()], [])
                      + (["--max-results", str(int(body["max_results"]))] if body.get("max_results") else []),
            "pipeline": ["pipeline", "--vertical", body.get("vertical", "roof cleaning"), "--state", body.get("state", "OH")]
                        + sum([["--city", c.strip()] for c in (body.get("cities") or "").split(",") if c.strip()], []),
        }
        if body.get("what") not in allowed:
            return {"error": "comando desconhecido"}
        return {"job": _run_job(allowed[body["what"]])}
    else:
        return {"error": "op desconhecida"}
    return {"ok": True}


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):  # silencioso
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path: Path, ctype: str | None = None):
        if not path.exists() or not path.is_file():
            self.send_error(404); return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or self.guess_type(str(path)))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        con = db.connect()
        try:
            if u.path in ("/", "/index.html"):
                return self._file(HERE / "index.html", "text/html; charset=utf-8")
            if u.path == "/api/summary":
                return self._json(_summary(con))
            if u.path == "/api/leads":
                return self._json(_leads(con, q))
            if u.path.startswith("/api/lead/"):
                d = _lead(con, int(u.path.rsplit("/", 1)[1]))
                return self._json(d or {"error": "não existe"}, 200 if d else 404)
            if u.path == "/api/queue":
                return self._json(_queue(con))
            if u.path == "/api/jobs":
                with _jobs_lock:
                    return self._json(list(reversed(_jobs)))
            if u.path.startswith("/shots/"):
                return self._file(config.SCREENSHOT_DIR / Path(u.path).name)
            if u.path.startswith("/img/"):
                parts = Path(u.path).parts[2:]
                return self._file(config.IMAGES_DIR.joinpath(*parts))
            if u.path.startswith("/hero/"):
                rel = Path(*Path(u.path).parts[2:]) if len(Path(u.path).parts) > 2 else Path(".")
                target = config.HERO_SITE_DIR / rel
                if target.is_dir():
                    target = target / "index.html"
                return self._file(target)
            self.send_error(404)
        finally:
            con.close()

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
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


def serve(port: int = 8090, open_browser: bool = True) -> None:
    config.ensure_dirs()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"painel: {url}   (Ctrl+C para parar)")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
