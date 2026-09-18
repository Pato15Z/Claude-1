"""Rascunhos dos 4 toques, com campos preenchidos. Envio é manual: você copia,
cola e registra com `lp touch log`. Inglês, curto, sem link no toque 1 do
email? Não: o link do hero É a mensagem. Ajuste o texto aqui."""
from __future__ import annotations

TEMPLATES = {
    1: {
        "channel": "email",
        "subject": "I built {name} a new homepage (30-sec video)",
        "body": """Hi {first_name},

I was looking for {vertical} companies in {city} and found {name} on Google — {rating_line}but {site_line}.

So I went ahead and built you a homepage using your own photos and reviews. Here it is:
{hero_url}

Here's a 30-second screen recording of it on a phone: {video_url}

If you like it, it's yours: $1,000 to launch it on your own domain, and $99/month to keep it fast, updated and ranking. If not, no worries — I'll take it down in a few weeks.

Reply "yes" and I'll send the next steps.

{sender_name}
{sender_phone}""",
    },
    2: {
        "channel": "facebook_page",
        "subject": "",
        "body": """Hi! I'm {sender_name}. I built {name} a homepage with your own photos — here it is on a phone: {hero_url}
Sent you an email about it on {touch1_date}, in case it went to spam. Happy to walk you through it in 5 minutes.""",
    },
    3: {
        "channel": "ligacao",
        "subject": "Roteiro de ligação",
        "body": """"Hi, is this {first_name}? This is {sender_name}. I'm the one who built the homepage for {name} — did you get a chance to see it?"
(se não) "It's at {hero_url} — it's your photos, your reviews, your number, ready to go."
(se sim) "What did you think? ... The launch is $1,000 and $99 a month. Want me to put it on your domain this week?"
Objeções: 'já tenho site' → 'This one is built for phones — that's where 80% of your customers find you now.'
'caro' → 'One roof job pays for it.'""",
    },
    4: {
        "channel": "email",
        "subject": "Taking down {name}'s homepage next week",
        "body": """Hi {first_name},

Quick last note — the homepage I built for {name} ({hero_url}) comes down next week.

If you want it, just reply "keep it" and I'll move it to your domain. If not, thanks for your time and good luck with the season.

{sender_name}""",
    },
}

import os as _os
# Preencha uma vez: LEADPIPE_SENDER_NAME, LEADPIPE_SENDER_PHONE, LEADPIPE_VIDEO_URL
SENDER = {"sender_name": _os.environ.get("LEADPIPE_SENDER_NAME", "SEU NOME"),
          "sender_phone": _os.environ.get("LEADPIPE_SENDER_PHONE", "SEU TELEFONE"),
          "video_url": _os.environ.get("LEADPIPE_VIDEO_URL", "LINK DO VIDEO")}


def render(touch_number: int, lead, touch1_date: str | None = None, sender: dict | None = None) -> dict:
    t = TEMPLATES[touch_number]
    s = {**SENDER, **(sender or {})}
    first = (lead["name"] or "").split()[0] if lead["name"] else "there"
    if first.lower() in ("the", "a", "all", "pro", "top", "best", "elite", "premier", "quality") or len(first) < 3 or "'" in first:
        first = "there"
    rating_line = f"{lead['rating']:.1f} stars from {lead['review_count']} reviews, " if lead["rating"] and lead["review_count"] else ""
    site_line = {"SEM_SITE": "you don't have a website yet", "SITE_QUEBRADO": "your website doesn't load well on a phone",
                 "SITE_ANTIGO": "your website looks a few years old on a phone"}.get(lead["site_status"] or "", "your website could work harder for you")
    ctx = {
        "name": lead["name"], "first_name": first, "city": lead["city"] or "your area", "vertical": lead["vertical"],
        "hero_url": lead["hero_url"] or "[HERO URL — rode lp hero build]", "rating_line": rating_line, "site_line": site_line,
        "touch1_date": touch1_date or "Monday", **s,
    }
    return {"channel": t["channel"], "subject": t["subject"].format(**ctx), "body": t["body"].format(**ctx)}
