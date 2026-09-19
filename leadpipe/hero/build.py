"""Módulo 4: gera o hero (uma página estática, mobile-first) por lead, em
batch, a partir do banco. Sem Node: Jinja2 → HTML puro. Deploy = uma pasta
estática com vercel.json que roteia {slug}.DOMINIO → /{slug}/.

Por que HTML estático e não Astro/Next: o resultado é o mesmo (uma página sem
JS), gera em milissegundos, e tira o Node da instalação. Se depois o site
completo for em Astro/Next, o hero vira um componente lá; o JSON de entrada é
o contrato (docs/DECISIONS.md §7)."""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

import phonenumbers
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import config, db
from ..normalize import slug as make_slug
from .content import content_for, place_labels

PKG_TEMPLATES = Path(__file__).parent / "templates"
ASSETS = Path(__file__).parent / "assets"


def _env() -> Environment:
    # data/templates (seus) tem prioridade sobre os do pacote com o mesmo nome
    return Environment(loader=FileSystemLoader([str(config.USER_TEMPLATES_DIR), str(PKG_TEMPLATES)]),
                       autoescape=select_autoescape(["html"]))


def list_templates() -> list[dict]:
    out = {}
    for d, src in ((PKG_TEMPLATES, "pacote"), (config.USER_TEMPLATES_DIR, "seu")):
        if d.exists():
            for f in sorted(d.glob("*.html")):
                out[f.stem] = {"name": f.stem, "source": src, "path": str(f)}
    return list(out.values())


def template_source(name: str) -> str:
    for d in (config.USER_TEMPLATES_DIR, PKG_TEMPLATES):
        f = d / f"{name}.html"
        if f.exists():
            return f.read_text(encoding="utf-8")
    raise FileNotFoundError(name)


def save_user_template(name: str, html: str) -> Path:
    name = re.sub(r"[^a-z0-9_-]", "", name.lower()) or "custom"
    config.USER_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    f = config.USER_TEMPLATES_DIR / f"{name}.html"
    f.write_text(html, encoding="utf-8")
    return f


def phone_display(e164: str | None) -> str:
    if not e164:
        return ""
    try:
        return phonenumbers.format_number(phonenumbers.parse(e164, "US"), phonenumbers.PhoneNumberFormat.NATIONAL)
    except Exception:
        return e164


def unique_slug(con: sqlite3.Connection, lead: sqlite3.Row) -> str:
    if lead["slug"]:
        return lead["slug"]
    base = make_slug(lead["name"], lead["city"])
    cand, n = base, 1
    while con.execute("SELECT 1 FROM leads WHERE slug=? AND id<>?", (cand, lead["id"])).fetchone():
        n += 1
        cand = f"{base}-{n}"
    return cand


def hero_data(con: sqlite3.Connection, lead: sqlite3.Row, site_dir: Path) -> dict:
    """Monta o JSON do hero (contrato §7) e copia imagens para a pasta do slug."""
    slug = unique_slug(con, lead)
    out = site_dir / slug
    img_out = out / "img"
    if out.exists():
        shutil.rmtree(out)
    img_out.mkdir(parents=True)
    imgs = con.execute("SELECT * FROM lead_images WHERE lead_id=? ORDER BY score DESC, id", (lead["id"],)).fetchall()
    # só fotos horizontais (largura > altura): a faixa lateral é uniforme e sem corte
    work = [i for i in imgs if i["kind"] != "logo" and Path(i["path"]).exists() and (i["width"] or 0) > (i["height"] or 0)]
    logo = next((i for i in imgs if i["kind"] == "logo" and Path(i["path"]).exists()), None)

    def copy(row, name):
        src = Path(row["path"]); dst = img_out / f"{name}{src.suffix}"
        shutil.copy2(src, dst); return f"img/{dst.name}"

    before = next((i for i in work if i["kind"] == "before"), None)
    after = next((i for i in work if i["kind"] == "after"), None)
    hero_img = next((i for i in work if i["kind"] in ("before_after", "work")), None) or (after if not before else None) or (work[0] if work else None)
    used = {id(x) for x in (before, after, hero_img) if x}
    gallery = [i for i in work if id(i) not in used][:4]
    pal = json.loads(lead["palette_json"]) if lead["palette_json"] else None
    if not pal:
        from ..enrich.palette import build_palette
        pal = build_palette(lead["vertical"], None, [])
    c = content_for(lead["vertical"], lead["city"])
    # 3 melhores avaliações: 5 estrelas primeiro, depois as mais longas (até 260 chars)
    revs = con.execute("SELECT author, rating, date_text, text FROM lead_reviews WHERE lead_id=? AND text IS NOT NULL AND length(text) > 15", (lead["id"],)).fetchall()
    revs = sorted((dict(r) for r in revs), key=lambda r: (-(r["rating"] or 0), -min(len(r["text"]), 260)))[:3]
    for r in revs:
        r["text"] = (r["text"][:257] + "…") if len(r["text"]) > 260 else r["text"]
        r["initial"] = (r["author"] or "G")[0].upper()
    # mapa: embed do Google sem chave de API. Empresa SEM endereço físico (atende
    # uma região) recebe do Google uma coordenada no centro da área declarada,
    # às vezes o estado inteiro. Nesse caso usa o lugar da busca (cidade/condado).
    place = ", ".join(x for x in (lead["city"] or "", lead["state"] or "") if x) or None
    has_street = bool(lead["street"]) or bool(lead["address_full"] and any(ch.isdigit() for ch in (lead["address_full"] or "")[:8]))
    if has_street and lead["lat"] is not None and lead["lng"] is not None:
        map_q = f"{lead['lat']},{lead['lng']}"
    else:
        map_q = place
    map_embed = f"https://www.google.com/maps?q={quote_plus(map_q, safe=',')}&z=11&output=embed" if map_q else None
    data = {
        "slug": slug,
        "name": lead["name"], "city": lead["city"] or "", "state": lead["state"] or "",
        "vertical": lead["vertical"], "vertical_title": lead["vertical"].title(),
        "phone_e164": lead["phone_e164"] or "", "phone_display": phone_display(lead["phone_e164"]),
        "rating": lead["rating"], "review_count": lead["review_count"],
        "stars": round(lead["rating"] or 0), "reviews": revs,
        "map_embed": map_embed, "map_link": lead["gbp_url"] or (f"https://www.google.com/maps/search/{quote_plus(map_q, safe=',')}" if map_q else None),
        "service_area": lead["city"] or "",
        "tagline": c["tagline"], "sub": c["sub"], "services": c["services"], "cta": c["cta"],
        "hero_image": copy(hero_img, "hero") if hero_img else None,
        "before": copy(before, "before") if before else None,
        "after": copy(after, "after") if after else None,
        "gallery": [copy(g, f"g{i + 1}") for i, g in enumerate(gallery)],
        "logo": copy(logo, "logo") if logo else None,
        "palette": pal,
        "year": datetime.now().year,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=config.HERO_TTL_DAYS)).date().isoformat(),
    }
    # casa com etiquetas de serviço (imagem fixa de referência + cor do negócio)
    house_src = ASSETS / "house.webp"
    if house_src.exists():
        shutil.copy2(house_src, img_out / "house.webp")
        data["house_image"] = "img/house.webp"
        data["house_labels"] = place_labels(c["services"])
    data["template"] = lead["hero_template"] or config.HERO_TEMPLATE_DEFAULT
    (out / "hero.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def render(data: dict, template: str | None = None) -> str:
    name = template or data.get("template") or config.HERO_TEMPLATE_DEFAULT
    return _env().get_template(f"{name}.html").render(**data)


def write_site_scaffold(site_dir: Path, domain: str) -> None:
    """vercel.json: {slug}.dominio/qualquer → /{slug}/qualquer. Também serve
    /{slug}/ direto (útil antes do DNS wildcard existir)."""
    site_dir.mkdir(parents=True, exist_ok=True)
    dom = re.escape(domain)
    vercel = {
        "cleanUrls": True,
        "trailingSlash": True,
        "rewrites": [
            {"source": "/(.*)", "has": [{"type": "host", "value": f"(?<slug>[^.]+)\\.{dom}"}], "destination": "/:slug/$1"},
        ],
        "headers": [{"source": "/(.*)", "headers": [{"key": "X-Robots-Tag", "value": "noindex"}]}],
    }
    (site_dir / "vercel.json").write_text(json.dumps(vercel, indent=2), encoding="utf-8")
    (site_dir / "_redirects").write_text("# Cloudflare Pages: usa functions/_middleware.js para o mesmo roteamento por host\n", encoding="utf-8")
    fn = site_dir / "functions"; fn.mkdir(exist_ok=True)
    (fn / "_middleware.js").write_text(
        "// Cloudflare Pages: {slug}.DOMINIO → /{slug}/\n"
        "export async function onRequest({ request, next }) {\n"
        "  const url = new URL(request.url);\n"
        f"  const m = url.hostname.match(/^([^.]+)\\.{dom}$/);\n"
        "  if (m && !url.pathname.startsWith('/' + m[1] + '/')) { url.pathname = '/' + m[1] + url.pathname; return fetch(new Request(url, request)); }\n"
        "  return next();\n}\n", encoding="utf-8")
    if not (site_dir / "index.html").exists():
        (site_dir / "index.html").write_text("<!doctype html><meta name=robots content=noindex><title>—</title>", encoding="utf-8")
    (site_dir / "deploy.sh").write_text(
        "#!/usr/bin/env bash\n# Publica a pasta inteira. Requer: npm i -g vercel && vercel login (uma vez).\n"
        "set -e\ncd \"$(dirname \"$0\")\"\nvercel deploy --prod --yes\n", encoding="utf-8")


def build(con: sqlite3.Connection, limit: int | None = None, include_low_priority: bool = False, rebuild: bool = False,
          progress=None, site_status: str | None = None, lead_id: int | None = None, template: str | None = None) -> dict:
    site_dir = config.HERO_SITE_DIR
    write_site_scaffold(site_dir, config.HERO_DOMAIN)
    where = "status IN ('ENRIQUECIDO','HERO_PRONTO')" if rebuild else "status='ENRIQUECIDO'"
    if not include_low_priority:
        where += " AND COALESCE(priority,'normal')<>'baixa'"
    if site_status:
        where += f" AND site_status='{site_status}'"
    if lead_id:
        where += f" AND id={int(lead_id)}"
    sql = f"SELECT * FROM leads WHERE {where} AND phone_e164 IS NOT NULL ORDER BY CASE site_status WHEN 'SEM_SITE' THEN 0 ELSE 1 END, id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    leads = con.execute(sql).fetchall()
    if not leads:
        return {}
    run_id = db.start_run(con, "hero", f"n={len(leads)}")
    t0 = time.time(); built = 0; errors = 0; urls = []
    for lead in leads:
        try:
            if template:
                db.update_lead(con, lead["id"], hero_template=template)
                lead = db.get_lead(con, lead["id"])
            data = hero_data(con, lead, site_dir)
            html = render(data)
            (site_dir / data["slug"] / "index.html").write_text(html, encoding="utf-8")
            url = f"https://{data['slug']}.{config.HERO_DOMAIN}"
            db.update_lead(con, lead["id"], slug=data["slug"], hero_url=url, hero_path=str(site_dir / data["slug"]),
                           hero_built_at=db.now_iso(), hero_expires_at=data["expires_at"])
            db.transition(con, lead["id"], "HERO_PRONTO", note=f"hero {url}")
            built += 1; urls.append(url)
            if progress:
                progress(lead, url, bool(data["hero_image"]))
        except Exception as e:
            errors += 1
            if progress:
                progress(lead, f"ERRO {type(e).__name__}: {str(e)[:100]}", False)
    db.finish_run(con, run_id, processed=len(leads), produced=built, errors=errors)
    return {"built": built, "errors": errors, "urls": urls, "_elapsed_s": round(time.time() - t0, 1), "site_dir": str(site_dir)}


def expire(con: sqlite3.Connection, dry_run: bool = False) -> list[dict]:
    """Derruba heros vencidos (30 dias) de leads sem resposta. ENVIADO → PERDIDO;
    HERO_PRONTO (nunca enviado) só perde o hero."""
    today = datetime.now(timezone.utc).date().isoformat()
    rows = con.execute("SELECT * FROM leads WHERE hero_url IS NOT NULL AND hero_expires_at <= ? AND status IN ('HERO_PRONTO','ENVIADO')", (today,)).fetchall()
    out = []
    for lead in rows:
        out.append({"id": lead["id"], "name": lead["name"], "url": lead["hero_url"], "status": lead["status"]})
        if dry_run:
            continue
        if lead["hero_path"] and Path(lead["hero_path"]).exists():
            shutil.rmtree(lead["hero_path"])
        db.update_lead(con, lead["id"], hero_url=None, hero_path=None)
        if lead["status"] == "ENVIADO":
            db.transition(con, lead["id"], "PERDIDO", note="hero expirou sem resposta")
    return out
