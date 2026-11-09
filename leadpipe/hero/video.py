"""Vídeo de cada site, gerado sozinho: rolagem de celular com legenda por cima.

Por que existe: o vídeo é a mensagem, e gravar 982 vídeos à mão é o passo que
nunca acontece. Isto abre o site do lead num celular simulado, rola do topo ao
fim com legenda em inglês, e salva um MP4 de ~22 s.

Decisões que importam:
  - Sem voz. O Playwright grava a tela, não o som, e voz sintética soa como
    robô justamente no primeiro contato. A legenda carrega a mensagem; quem
    quiser voz grava por cima depois.
  - O MP4 fica DENTRO da pasta do site (data/hero_site/<slug>/video.mp4). Assim
    ele sobe junto quando os sites forem publicados e ganha um link público
    (https://<slug>.<domínio>/video.mp4) sem hospedagem nova. O servidor do
    painel não serve para isso: tudo nele exige senha.
  - H.264 + yuv420p + faststart: é o que abre direto no iPhone, sem baixar.
  - Um vídeo que você gravou à mão (video_url já preenchido) nunca é trocado,
    a não ser com force=True.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .. import config, db

# Tempo de cada fase, em segundos. A soma dá a duração do vídeo.
HOLD_TOP_S = 2.5
SCROLL_S = 15.0
HOLD_END_S = 4.5

# Resolução gravada: viewport de celular com densidade 2, para não sair borrado
# na tela de quem recebe.
SCALE = 2


def captions(business: str) -> list[tuple[float, str]]:
    """(segundo em que entra, texto). Curtas: precisam ser lidas rolando.

    Sem "Hi {nome}": o nome do dono não está nos dados, e a primeira palavra do
    nome da empresa ("Buckeye Roofing Co" → "Hi Buckeye") chamaria o dono por
    um nome que não é o dele, no primeiro segundo do vídeo.
    """
    return [
        (0.0, f"I built this for {business}"),
        (5.5, "Made from your own Google photos and reviews"),
        (11.5, "Your services, your map, tap to call"),
        (HOLD_TOP_S + SCROLL_S, "Want it live on your domain this week? Reply YES"),
    ]


# Roda dentro da página: põe a legenda, troca o texto na hora certa e rola com
# aceleração suave. Resolve quando termina, para o Python saber quando parar.
_PAGE_SCRIPT = r"""
async ({caps, holdTop, scroll, holdEnd}) => {
  const bar = document.createElement('div');
  bar.id = 'lp-caption';
  bar.style.cssText = [
    'position:fixed', 'left:12px', 'right:12px', 'top:62px', 'z-index:2147483647',
    'background:rgba(12,14,18,.86)', 'color:#fff', 'border-radius:14px',
    'padding:12px 14px', 'font:600 17px/1.3 -apple-system,system-ui,Segoe UI,Roboto,sans-serif',
    'box-shadow:0 6px 24px rgba(0,0,0,.25)', 'transition:opacity .35s', 'text-align:center'
  ].join(';');
  document.body.appendChild(bar);
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const t0 = performance.now();
  caps.forEach(([at, text]) => setTimeout(() => {
    bar.style.opacity = '0';
    setTimeout(() => { bar.textContent = text; bar.style.opacity = '1'; }, 180);
  }, at * 1000));
  bar.textContent = caps[0][1];

  await sleep(holdTop * 1000);
  const max = Math.max(0, document.documentElement.scrollHeight - innerHeight);
  const ease = x => x < .5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
  await new Promise(done => {
    const start = performance.now();
    const step = now => {
      const k = Math.min(1, (now - start) / (scroll * 1000));
      scrollTo(0, max * ease(k));
      k < 1 ? requestAnimationFrame(step) : done();
    };
    requestAnimationFrame(step);
  });
  await sleep(holdEnd * 1000);
  return Math.round(performance.now() - t0);
}
"""

# Espera as imagens carregarem (com teto), para o vídeo não mostrar caixas vazias.
_WAIT_IMAGES = r"""
() => Promise.race([
  Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; }))),
  new Promise(r => setTimeout(r, 4000))
])
"""


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg não encontrado (no servidor ele vem na imagem; no PC: winget install ffmpeg)")
    return exe


def to_mp4(webm: Path, mp4: Path, skip_s: float, duration_s: float) -> None:
    """WebM do Playwright → MP4 que abre no iPhone. Corta o carregamento do início."""
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{skip_s:.2f}", "-i", str(webm),
           "-t", f"{duration_s:.2f}",
           "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=30",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "26",
           "-movflags", "+faststart", "-an", str(mp4)]
    subprocess.run(cmd, check=True)


def poster(mp4: Path, jpg: Path) -> None:
    """Primeiro quadro com legenda: serve de miniatura no email."""
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-ss", "1.2", "-i", str(mp4),
                    "-frames:v", "1", "-q:v", "3", str(jpg)], check=True)


async def record(browser, lead) -> tuple[Path, float]:
    """Grava um lead. Devolve (mp4, segundos)."""
    site = Path(lead["hero_path"])
    index = site / "index.html"
    if not index.exists():
        raise FileNotFoundError(f"site não encontrado: {index}")
    vp = config.MOBILE_VIEWPORT
    tmp = Path(tempfile.mkdtemp(prefix="lpvid_"))
    try:
        ctx = await browser.new_context(
            viewport=vp, device_scale_factor=SCALE, is_mobile=True, has_touch=True,
            user_agent=config.MOBILE_UA, locale="en-US",
            record_video_dir=str(tmp),
            record_video_size={"width": vp["width"] * SCALE, "height": vp["height"] * SCALE},
        )
        t_page = time.monotonic()
        page = await ctx.new_page()
        await page.goto(index.resolve().as_uri())
        await page.evaluate(_WAIT_IMAGES)
        await page.wait_for_timeout(300)
        skip = time.monotonic() - t_page           # carregamento, cortado do vídeo
        caps = captions(lead["name"] or "your business")
        ms = await page.evaluate(_PAGE_SCRIPT, {"caps": caps, "holdTop": HOLD_TOP_S,
                                                "scroll": SCROLL_S, "holdEnd": HOLD_END_S})
        video = page.video
        await ctx.close()                          # só aqui a gravação é finalizada
        webm = tmp / "raw.webm"
        await video.save_as(str(webm))
        mp4 = site / "video.mp4"
        to_mp4(webm, mp4, skip_s=skip, duration_s=ms / 1000)
        poster(mp4, site / "video-poster.jpg")
        return mp4, ms / 1000
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def public_url(lead) -> str | None:
    """Link do vídeo depois de publicado, se o domínio dos sites estiver definido."""
    if not lead["hero_url"] or config.HERO_DOMAIN.startswith("SEUDOMINIO"):
        return None
    return lead["hero_url"].rstrip("/") + "/video.mp4"


def pending(con, lead_id: int | None = None, force: bool = False, limit: int | None = None):
    """Leads com site pronto e sem vídeo. Com force, também os que já têm."""
    q = "SELECT * FROM leads WHERE hero_path IS NOT NULL"
    args: list = []
    if lead_id:
        q += " AND id=?"; args.append(lead_id)
    elif not force:
        q += " AND video_done_at IS NULL AND (video_url IS NULL OR video_url = '')"
    q += " ORDER BY COALESCE(review_count,0) DESC, id"   # mesma ordem da fila de ligação
    if limit:
        q += " LIMIT ?"; args.append(limit)
    return con.execute(q, args).fetchall()


async def build(con, leads, force: bool = False, progress=None) -> dict:
    """Grava os vídeos em sequência. Um navegador, um contexto por lead."""
    from playwright.async_api import async_playwright
    from ..qualify.render_check import new_browser

    out = {"done": 0, "errors": 0, "skipped": 0}
    async with async_playwright() as pw:
        b = await new_browser(pw)
        try:
            for lead in leads:
                manual = lead["video_url"] and not (lead["video_url"] or "").endswith("/video.mp4")
                if manual and not force:
                    out["skipped"] += 1
                    if progress: progress(lead, None, "pulado: já tem vídeo gravado à mão")
                    continue
                try:
                    mp4, secs = await record(b, lead)
                    fields = {"video_path": str(mp4), "video_done_at": db.now_iso()}
                    url = public_url(lead)
                    if url:
                        fields["video_url"] = url
                    db.update_lead(con, lead["id"], **fields)
                    out["done"] += 1
                    if progress: progress(lead, mp4, f"{secs:.0f}s, {mp4.stat().st_size // 1024} KB")
                except Exception as e:
                    out["errors"] += 1
                    if progress: progress(lead, None, f"erro: {type(e).__name__}: {e}")
        finally:
            await b.close()
    return out
