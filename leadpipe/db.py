"""SQLite: schema, conexão, transições de funil.

Regras:
- Status atual fica em leads.status; TODA transição vira linha em
  lead_status_history (nunca sobrescrita). Tempo entre etapas sai daí.
- Escrita incremental: cada lead é commitado ao ser inserido/atualizado.
  Scraper morrer no meio não perde o que já entrou.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import config

FUNNEL_STATES = [
    "NOVO", "QUALIFICADO", "ENRIQUECIDO", "HERO_PRONTO", "ENVIADO",
    "RESPONDEU", "CALL_AGENDADA", "FECHADO", "PERDIDO", "DESCARTADO",
]
SITE_STATES = ["SEM_SITE", "SITE_QUEBRADO", "SITE_ANTIGO", "SITE_OK"]
# Status de site que seguem no funil (viram QUALIFICADO).
SITE_STATES_QUALIFIED = {"SEM_SITE", "SITE_QUEBRADO", "SITE_ANTIGO"}
CHANNELS = ["email", "facebook_page", "instagram", "ligacao"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    phone_e164      TEXT,
    phone_raw       TEXT,
    address_full    TEXT,
    address_norm    TEXT,
    street          TEXT,
    city            TEXT,
    state           TEXT,
    zip             TEXT,
    lat             REAL,
    lng             REAL,
    category        TEXT,
    vertical        TEXT NOT NULL,
    website_url     TEXT,
    gbp_url         TEXT,
    gbp_place_id    TEXT,
    rating          REAL,
    review_count    INTEGER,
    last_review_at  TEXT,            -- aproximado (Maps mostra "3 weeks ago")
    facebook_url    TEXT,
    instagram_url   TEXT,
    email           TEXT,
    email_source    TEXT,
    email_confidence TEXT,
    timezone        TEXT,
    source          TEXT NOT NULL,   -- google_maps | csv | manual | gosom
    source_query    TEXT,            -- query exata que gerou o lead
    sourced_at      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'NOVO',
    site_status     TEXT,            -- SEM_SITE | SITE_QUEBRADO | SITE_ANTIGO | SITE_OK
    site_reason     TEXT,            -- texto auditável
    site_checked_at TEXT,
    screenshot_path TEXT,
    priority        TEXT DEFAULT 'normal',  -- normal | baixa (sem imagem)
    hero_url        TEXT,
    hero_expires_at TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_leads_phone ON leads(phone_e164) WHERE phone_e164 IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_leads_addr ON leads(address_norm);
CREATE INDEX IF NOT EXISTS ix_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS ix_leads_region ON leads(state, city, vertical);
CREATE INDEX IF NOT EXISTS ix_leads_place ON leads(gbp_place_id);

CREATE TABLE IF NOT EXISTS lead_status_history (
    id          INTEGER PRIMARY KEY,
    lead_id     INTEGER NOT NULL REFERENCES leads(id),
    from_status TEXT,
    to_status   TEXT NOT NULL,
    at          TEXT NOT NULL,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS ix_hist_lead ON lead_status_history(lead_id, at);

CREATE TABLE IF NOT EXISTS touches (
    id            INTEGER PRIMARY KEY,
    lead_id       INTEGER NOT NULL REFERENCES leads(id),
    touch_number  INTEGER NOT NULL CHECK (touch_number BETWEEN 1 AND 4),
    channel       TEXT NOT NULL,
    sent_at       TEXT NOT NULL,
    replied_at    TEXT,
    template      TEXT,
    content       TEXT,
    notes         TEXT,
    UNIQUE(lead_id, touch_number)
);

CREATE TABLE IF NOT EXISTS site_checks (
    id            INTEGER PRIMARY KEY,
    lead_id       INTEGER NOT NULL REFERENCES leads(id),
    checked_at    TEXT NOT NULL,
    url           TEXT,
    final_url     TEXT,
    http_status   INTEGER,
    elapsed_ms    INTEGER,
    site_status   TEXT NOT NULL,
    reason        TEXT,
    signals_json  TEXT,
    screenshot_path TEXT
);

-- Cada execução de um módulo. Base para "minutos por lead por etapa".
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY,
    module      TEXT NOT NULL,       -- source | qualify | enrich | hero
    args        TEXT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    processed   INTEGER DEFAULT 0,
    produced    INTEGER DEFAULT 0,
    errors      INTEGER DEFAULT 0,
    notes       TEXT
);

-- Cobertura de sourcing por query (cidade x vertical), para saber onde repetir.
CREATE TABLE IF NOT EXISTS source_queries (
    id          INTEGER PRIMARY KEY,
    query       TEXT NOT NULL,
    vertical    TEXT NOT NULL,
    city        TEXT,
    state       TEXT,
    ran_at      TEXT NOT NULL,
    found       INTEGER DEFAULT 0,
    inserted    INTEGER DEFAULT 0,
    duplicates  INTEGER DEFAULT 0,
    elapsed_s   REAL,
    error       TEXT
);

-- Clientes fechados: base do churn.
CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY,
    lead_id     INTEGER NOT NULL UNIQUE REFERENCES leads(id),
    started_at  TEXT NOT NULL,
    churned_at  TEXT,
    setup_fee   REAL DEFAULT 1000,
    mrr         REAL DEFAULT 99,
    notes       TEXT
);

-- Imagens baixadas (módulo 3, tabela já criada para não migrar depois).
CREATE TABLE IF NOT EXISTS lead_images (
    id          INTEGER PRIMARY KEY,
    lead_id     INTEGER NOT NULL REFERENCES leads(id),
    path        TEXT NOT NULL,
    source      TEXT,
    width       INTEGER,
    height      INTEGER,
    kind        TEXT,   -- work | before | after | logo | rejected
    score       REAL,
    created_at  TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30, isolation_level=None)  # autocommit
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    con.executescript(SCHEMA)
    _migrate(con)
    return con


# Colunas adicionadas depois da v0.1. ALTER TABLE só se faltar.
_NEW_COLUMNS = {
    "source_queries": [("with_site", "INTEGER")],
    "leads": [("slug", "TEXT"), ("palette_json", "TEXT"), ("logo_path", "TEXT"), ("enriched_at", "TEXT"),
              ("enrich_notes", "TEXT"), ("hero_built_at", "TEXT"), ("hero_path", "TEXT")],
}


def _migrate(con: sqlite3.Connection) -> None:
    for table, cols in _NEW_COLUMNS.items():
        have = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        for name, typ in cols:
            if name not in have:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_leads_slug ON leads(slug) WHERE slug IS NOT NULL")


@contextmanager
def tx(con: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    con.execute("BEGIN")
    try:
        yield con
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


# ---------------------------------------------------------------- leads

def find_duplicate(con: sqlite3.Connection, phone_e164: str | None, address_norm: str | None,
                   gbp_place_id: str | None = None) -> sqlite3.Row | None:
    """Dedup em 3 níveis: place_id do Google, telefone E.164, endereço normalizado."""
    if gbp_place_id:
        r = con.execute("SELECT * FROM leads WHERE gbp_place_id=?", (gbp_place_id,)).fetchone()
        if r:
            return r
    if phone_e164:
        r = con.execute("SELECT * FROM leads WHERE phone_e164=?", (phone_e164,)).fetchone()
        if r:
            return r
    if address_norm:
        r = con.execute("SELECT * FROM leads WHERE address_norm=?", (address_norm,)).fetchone()
        if r:
            return r
    return None


def insert_lead(con: sqlite3.Connection, lead: dict[str, Any]) -> int:
    """Insere lead NOVO e registra transição inicial. Commit imediato."""
    ts = now_iso()
    lead = dict(lead)
    lead.setdefault("sourced_at", ts)
    lead.setdefault("status", "NOVO")
    lead["created_at"] = ts
    lead["updated_at"] = ts
    cols = [c for c in lead if c in LEAD_COLUMNS]
    with tx(con):
        cur = con.execute(
            f"INSERT INTO leads ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
            [lead[c] for c in cols],
        )
        lead_id = cur.lastrowid
        con.execute(
            "INSERT INTO lead_status_history (lead_id, from_status, to_status, at, note) VALUES (?,?,?,?,?)",
            (lead_id, None, lead["status"], ts, f"source={lead.get('source')}"),
        )
    return int(lead_id)


def update_lead(con: sqlite3.Connection, lead_id: int, **fields: Any) -> None:
    fields = {k: v for k, v in fields.items() if k in LEAD_COLUMNS}
    if not fields:
        return
    fields["updated_at"] = now_iso()
    sets = ",".join(f"{k}=?" for k in fields)
    con.execute(f"UPDATE leads SET {sets} WHERE id=?", [*fields.values(), lead_id])


def merge_missing(con: sqlite3.Connection, lead_id: int, incoming: dict[str, Any]) -> int:
    """Para duplicata: preenche só campos vazios do lead existente. Retorna nº de campos preenchidos."""
    row = con.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    fill = {}
    for k, v in incoming.items():
        if k in LEAD_COLUMNS and k not in ("id", "status", "source", "source_query", "sourced_at") \
                and v not in (None, "") and row[k] in (None, ""):
            fill[k] = v
    if fill:
        update_lead(con, lead_id, **fill)
    return len(fill)


def transition(con: sqlite3.Connection, lead_id: int, to_status: str, note: str | None = None,
               at: str | None = None) -> bool:
    """Muda status e grava histórico. Retorna False se já estava nesse status."""
    if to_status not in FUNNEL_STATES:
        raise ValueError(f"status inválido: {to_status}")
    row = con.execute("SELECT status FROM leads WHERE id=?", (lead_id,)).fetchone()
    if row is None:
        raise KeyError(f"lead {lead_id} não existe")
    if row["status"] == to_status:
        return False
    ts = at or now_iso()
    with tx(con):
        con.execute("UPDATE leads SET status=?, updated_at=? WHERE id=?", (to_status, ts, lead_id))
        con.execute(
            "INSERT INTO lead_status_history (lead_id, from_status, to_status, at, note) VALUES (?,?,?,?,?)",
            (lead_id, row["status"], to_status, ts, note),
        )
    return True


def get_lead(con: sqlite3.Connection, lead_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()


# ---------------------------------------------------------------- runs

def start_run(con: sqlite3.Connection, module: str, args: str = "") -> int:
    cur = con.execute("INSERT INTO runs (module, args, started_at) VALUES (?,?,?)",
                      (module, args, now_iso()))
    return int(cur.lastrowid)


def finish_run(con: sqlite3.Connection, run_id: int, processed: int = 0, produced: int = 0,
               errors: int = 0, notes: str | None = None) -> None:
    con.execute(
        "UPDATE runs SET finished_at=?, processed=?, produced=?, errors=?, notes=? WHERE id=?",
        (now_iso(), processed, produced, errors, notes, run_id),
    )


LEAD_COLUMNS = {
    "id", "name", "phone_e164", "phone_raw", "address_full", "address_norm", "street", "city",
    "state", "zip", "lat", "lng", "category", "vertical", "website_url", "gbp_url",
    "gbp_place_id", "rating", "review_count", "last_review_at", "facebook_url", "instagram_url",
    "email", "email_source", "email_confidence", "timezone", "source", "source_query",
    "sourced_at", "status", "site_status", "site_reason", "site_checked_at", "screenshot_path",
    "priority", "hero_url", "hero_expires_at", "notes", "created_at", "updated_at",
    "slug", "palette_json", "logo_path", "enriched_at", "enrich_notes", "hero_built_at", "hero_path",
}
