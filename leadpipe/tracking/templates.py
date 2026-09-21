"""Rascunhos dos 4 toques (vídeo primeiro). Envio é manual: você copia,
cola e marca o checkmark no app. Inglês, curto: o vídeo e a página são a
mensagem. Ajuste o texto aqui ou nas Configurações do app (nome, telefone,
link padrão do vídeo)."""
from __future__ import annotations

import os as _os

TEMPLATES = {
    1: {
        "channel": "email",
        "subject": "30-sec video: a new homepage for {name}",
        "body": """Hi {first_name},

I found {name} on Google ({rating_line}) and noticed {site_line}. So I built you a homepage from your own photos and reviews.

30-second video of it on a phone: {video_url}
Live page: {hero_url}

If you like it, it's yours: $1,000 to launch it on your domain and $99/month to keep it fast and updated. If not, no worries, it comes down in a few weeks.

Reply "yes" and I'll send the next steps.

{sender_name}
{sender_phone}""",
    },
    2: {
        "channel": "facebook_page",
        "subject": "",
        "body": """Hi! I'm {sender_name}. I built {name} a homepage from your Google photos and reviews. 30-sec video: {video_url}
Live page: {hero_url}
I emailed you on {touch1_date} too, in case it landed in spam. Happy to walk you through it in 5 minutes.""",
    },
    3: {
        "channel": "instagram",
        "subject": "",
        "body": """Hey {name}! Built you a homepage from your own photos, here's a 30-sec video: {video_url}
Page: {hero_url}
If you want it live on your domain, just reply here. — {sender_name}""",
    },
    4: {
        "channel": "email",
        "subject": "Taking down {name}'s homepage next week",
        "body": """Hi {first_name},

Quick last note. The homepage I built for {name} comes down next week:
{hero_url}

If you want to keep it, reply "keep it" and I'll move it to your domain this week. If not, thanks for your time and good luck with the season.

{sender_name}""",
    },
}

# Preencha nas Configurações do app (ou LEADPIPE_SENDER_NAME, LEADPIPE_SENDER_PHONE, LEADPIPE_VIDEO_URL)
SENDER = {"sender_name": _os.environ.get("LEADPIPE_SENDER_NAME", "SEU NOME"),
          "sender_phone": _os.environ.get("LEADPIPE_SENDER_PHONE", "SEU TELEFONE"),
          "video_url": _os.environ.get("LEADPIPE_VIDEO_URL", "LINK DO VIDEO")}


def render(touch_number: int, lead, touch1_date: str | None = None, sender: dict | None = None) -> dict:
    t = TEMPLATES[touch_number]
    s = {**SENDER, **{k: v for k, v in (sender or {}).items() if v}}
    first = (lead["name"] or "").split()[0] if lead["name"] else "there"
    if first.lower() in ("the", "a", "all", "pro", "top", "best", "elite", "premier", "quality") or len(first) < 3 or "'" in first:
        first = "there"
    rating_line = f"{lead['rating']:.1f} stars from {lead['review_count']} reviews" if lead["rating"] and lead["review_count"] else "nice reviews"
    site_line = {"SEM_SITE": "you don't have a website yet", "SITE_QUEBRADO": "your website doesn't load well on a phone",
                 "SITE_ANTIGO": "your website looks a few years old on a phone"}.get(lead["site_status"] or "", "your website could work harder for you")
    keys = lead.keys() if hasattr(lead, "keys") else []
    video = (lead["video_url"] if "video_url" in keys and lead["video_url"] else None) or s["video_url"]
    ctx = {
        "name": lead["name"], "first_name": first, "city": lead["city"] or "your area", "vertical": lead["vertical"],
        "hero_url": lead["hero_url"] or "[HERO URL: gere o site primeiro]", "rating_line": rating_line, "site_line": site_line,
        "touch1_date": touch1_date or "Monday", **s, "video_url": video,
    }
    return {"channel": t["channel"], "subject": t["subject"].format(**ctx), "body": t["body"].format(**ctx)}
