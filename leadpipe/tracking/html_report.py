"""Dashboard de leitura: um HTML estático, sem JS, gerado a partir dos mesmos
relatórios da CLI. Abre no navegador e pronto."""
from __future__ import annotations

import html
import sqlite3
from datetime import datetime
from pathlib import Path

from .reports import ALL_REPORTS

_CSS = """
body{font-family:system-ui,sans-serif;max-width:1200px;margin:24px auto;padding:0 16px;color:#111;background:#fafafa}
h1{font-size:20px}h2{font-size:15px;margin:28px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px}
table{border-collapse:collapse;font-size:13px;width:100%}th,td{padding:4px 8px;border-bottom:1px solid #eee;text-align:left;white-space:nowrap}
th{background:#f0f0f0;position:sticky;top:0}tr:hover td{background:#f5f5ff}
.warn{color:#b00}.good{color:#080}.muted{color:#777;font-size:12px}
"""


def _table(cols, rows) -> str:
    if not rows:
        return '<p class="muted">sem dados</p>'
    h = "<table><thead><tr>" + "".join(f"<th>{html.escape(str(c))}</th>" for c in cols) + "</tr></thead><tbody>"
    for r in rows:
        cells = []
        for v in r:
            s = "" if v is None else str(v)
            cls = ""
            if "SATURADA" in s:
                cls = ' class="warn"'
            elif "VIRGEM" in s:
                cls = ' class="good"'
            cells.append(f"<td{cls}>{html.escape(s)}</td>")
        h += "<tr>" + "".join(cells) + "</tr>"
    return h + "</tbody></table>"


def build(con: sqlite3.Connection) -> str:
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
             f"<title>leadpipe</title><style>{_CSS}</style></head><body>",
             f"<h1>leadpipe — relatórios</h1><p class='muted'>gerado {datetime.now():%Y-%m-%d %H:%M}</p>"]
    for title, fn in ALL_REPORTS:
        cols, rows = fn(con)
        parts.append(f"<h2>{html.escape(title)}</h2>{_table(cols, rows)}")
    parts.append("</body></html>")
    return "".join(parts)


def write(con: sqlite3.Connection, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(con), encoding="utf-8")
    return out
