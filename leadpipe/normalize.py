"""Normalização: telefone E.164, endereço, slug, fuso, datas relativas."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import phonenumbers
from slugify import slugify as _slugify

# --------------------------------------------------------------- telefone

def phone_e164(raw: str | None, region: str = "US") -> str | None:
    if not raw:
        return None
    try:
        n = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(n):
        return None
    return phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164)


# --------------------------------------------------------------- endereço

_ABBR = {
    "street": "st", "avenue": "ave", "boulevard": "blvd", "road": "rd", "drive": "dr",
    "lane": "ln", "court": "ct", "circle": "cir", "place": "pl", "parkway": "pkwy",
    "highway": "hwy", "north": "n", "south": "s", "east": "e", "west": "w",
    "northeast": "ne", "northwest": "nw", "southeast": "se", "southwest": "sw",
    "suite": "ste", "apartment": "apt", "trail": "trl", "terrace": "ter", "square": "sq",
}
_UNIT_RE = re.compile(r"\b(ste|suite|apt|unit|#)\s*[\w-]+\b")


def address_norm(addr: str | None) -> str | None:
    """Minúsculo, sem pontuação, abreviações padronizadas, sem sufixo de unidade,
    sem 'united states'. Mesmo endereço escrito de dois jeitos colide."""
    if not addr:
        return None
    s = addr.lower()
    s = re.sub(r"[.,]", " ", s)
    s = re.sub(r"\bunited states\b|\busa\b", " ", s)
    s = _UNIT_RE.sub(" ", s)
    toks = [_ABBR.get(t, t) for t in s.split()]
    s = " ".join(toks)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


_US_ADDR_RE = re.compile(
    r"^(?P<street>.*?),\s*(?P<city>[^,]+?),\s*(?P<state>[A-Z]{2})\s+(?P<zip>\d{5})(?:-\d{4})?"
    r"(?:,\s*(?:USA|United States))?\s*$"
)


def split_us_address(addr: str | None) -> dict[str, str | None]:
    """'123 Main St, Columbus, OH 43215, United States' → partes. Best-effort."""
    out: dict[str, str | None] = {"street": None, "city": None, "state": None, "zip": None}
    if not addr:
        return out
    m = _US_ADDR_RE.match(addr.strip())
    if m:
        out.update({k: m.group(k).strip() for k in out})
        return out
    # Sem rua: "Columbus, OH 43215" ou "Columbus, OH"
    m2 = re.match(r"^(?P<city>[^,]+?),\s*(?P<state>[A-Z]{2})(?:\s+(?P<zip>\d{5}))?", addr.strip())
    if m2:
        out["city"] = m2.group("city").strip()
        out["state"] = m2.group("state")
        out["zip"] = m2.group("zip")
    return out


# --------------------------------------------------------------- slug

def slug(name: str, city: str | None = None) -> str:
    base = _slugify(name, max_length=40, word_boundary=True)
    if city:
        base = f"{base}-{_slugify(city, max_length=15)}"
    return base or "site"


# --------------------------------------------------------------- fuso

_STATE_TZ = {
    # Estados de um fuso só (fallback quando não há coordenada).
    "CT": "America/New_York", "DE": "America/New_York", "GA": "America/New_York",
    "ME": "America/New_York", "MD": "America/New_York", "MA": "America/New_York",
    "NH": "America/New_York", "NJ": "America/New_York", "NY": "America/New_York",
    "NC": "America/New_York", "OH": "America/New_York", "PA": "America/New_York",
    "RI": "America/New_York", "SC": "America/New_York", "VT": "America/New_York",
    "VA": "America/New_York", "WV": "America/New_York", "DC": "America/New_York",
    "AL": "America/Chicago", "AR": "America/Chicago", "IL": "America/Chicago",
    "IA": "America/Chicago", "LA": "America/Chicago", "MN": "America/Chicago",
    "MS": "America/Chicago", "MO": "America/Chicago", "OK": "America/Chicago",
    "WI": "America/Chicago", "CO": "America/Denver", "MT": "America/Denver",
    "NM": "America/Denver", "UT": "America/Denver", "WY": "America/Denver",
    "AZ": "America/Phoenix", "CA": "America/Los_Angeles", "NV": "America/Los_Angeles",
    "WA": "America/Los_Angeles", "HI": "Pacific/Honolulu", "AK": "America/Anchorage",
    # Estados divididos: usa o fuso da maior parte da população.
    "FL": "America/New_York", "MI": "America/New_York", "IN": "America/New_York",
    "KY": "America/New_York", "TN": "America/Chicago", "TX": "America/Chicago",
    "KS": "America/Chicago", "NE": "America/Chicago", "ND": "America/Chicago",
    "SD": "America/Chicago", "ID": "America/Boise", "OR": "America/Los_Angeles",
}


@lru_cache(maxsize=1)
def _tzfinder():
    from timezonefinder import TimezoneFinder
    return TimezoneFinder(in_memory=True)


def timezone_for(lat: float | None, lng: float | None, state: str | None) -> str | None:
    """Coordenada → fuso exato. Sem coordenada → fuso majoritário do estado."""
    if lat is not None and lng is not None:
        try:
            tz = _tzfinder().timezone_at(lat=float(lat), lng=float(lng))
            if tz:
                return tz
        except Exception:
            pass
    if state:
        return _STATE_TZ.get(state.upper())
    return None


# --------------------------------------------------------------- datas

_REL_RE = re.compile(r"(?P<n>a|an|\d+)\s+(?P<unit>second|minute|hour|day|week|month|year)s?\s+ago", re.I)


def relative_date_to_iso(text: str | None, now: datetime | None = None) -> str | None:
    """'3 weeks ago' → data ISO aproximada. Google Maps só mostra datas assim."""
    if not text:
        return None
    m = _REL_RE.search(text)
    if not m:
        return None
    n = 1 if m.group("n").lower() in ("a", "an") else int(m.group("n"))
    unit = m.group("unit").lower()
    days = {"second": 0, "minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}[unit]
    now = now or datetime.now(timezone.utc)
    return (now - timedelta(days=n * days)).date().isoformat()


def parse_int(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def parse_float(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", text)
    return float(m.group(0).replace(",", ".")) if m else None
