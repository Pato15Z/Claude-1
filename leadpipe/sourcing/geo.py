"""Cerca geográfica: um lead só entra se estiver dentro do estado pedido.

Por quê: o Google Maps usa a localização do navegador. Quem busca do Brasil
recebe, em buscas ambíguas, resultados perto de casa. Três defesas:
  1. geolocalização do navegador forçada para o centro do estado (Playwright)
  2. gl=us + hl=en na URL e "State, USA" na query
  3. este filtro: coordenada dentro da caixa do estado E telefone válido nos EUA
"""
from __future__ import annotations

import phonenumbers

# (lat_min, lat_max, lng_min, lng_max) aproximados, com folga de ~0.2°.
STATE_BBOX = {
    "AL": (30.1, 35.2, -88.7, -84.7), "AK": (51.0, 71.6, -179.5, -129.8), "AZ": (31.1, 37.2, -115.1, -108.8),
    "AR": (32.8, 36.7, -94.8, -89.4), "CA": (32.3, 42.2, -124.6, -113.9), "CO": (36.8, 41.2, -109.3, -101.8),
    "CT": (40.8, 42.3, -73.9, -71.6), "DE": (38.2, 40.0, -75.9, -74.8), "FL": (24.3, 31.2, -87.8, -79.8),
    "GA": (30.1, 35.2, -85.8, -80.6), "HI": (18.7, 22.5, -160.5, -154.6), "ID": (41.8, 49.2, -117.4, -110.8),
    "IL": (36.8, 42.7, -91.7, -87.3), "IN": (37.6, 41.9, -88.3, -84.6), "IA": (40.2, 43.7, -96.8, -90.0),
    "KS": (36.8, 40.2, -102.3, -94.4), "KY": (36.3, 39.4, -89.8, -81.8), "LA": (28.7, 33.2, -94.2, -88.6),
    "ME": (42.8, 47.7, -71.3, -66.7), "MD": (37.7, 39.9, -79.7, -74.8), "MA": (41.0, 43.0, -73.7, -69.7),
    "MI": (41.5, 48.5, -90.6, -82.2), "MN": (43.3, 49.6, -97.4, -89.3), "MS": (29.9, 35.2, -91.8, -87.9),
    "MO": (35.8, 40.8, -95.9, -88.9), "MT": (44.2, 49.2, -116.2, -103.8), "NE": (39.8, 43.2, -104.3, -95.1),
    "NV": (34.8, 42.2, -120.2, -113.8), "NH": (42.5, 45.5, -72.8, -70.4), "NJ": (38.7, 41.6, -75.8, -73.7),
    "NM": (31.1, 37.2, -109.3, -102.8), "NY": (40.3, 45.2, -80.0, -71.6), "NC": (33.6, 36.8, -84.5, -75.2),
    "ND": (45.7, 49.2, -104.3, -96.3), "OH": (38.2, 42.2, -85.0, -80.3), "OK": (33.4, 37.2, -103.2, -94.2),
    "OR": (41.8, 46.5, -124.8, -116.3), "PA": (39.5, 42.5, -80.7, -74.5), "RI": (41.0, 42.1, -72.0, -71.0),
    "SC": (31.8, 35.4, -83.6, -78.3), "SD": (42.3, 46.2, -104.3, -96.2), "TN": (34.8, 36.9, -90.5, -81.4),
    "TX": (25.6, 36.7, -106.9, -93.3), "UT": (36.8, 42.2, -114.3, -108.8), "VT": (42.5, 45.2, -73.6, -71.3),
    "VA": (36.3, 39.7, -83.9, -75.0), "WA": (45.3, 49.2, -124.9, -116.7), "WV": (37.0, 40.8, -82.9, -77.5),
    "WI": (42.3, 47.3, -93.1, -86.6), "WY": (40.8, 45.2, -111.3, -103.8), "DC": (38.7, 39.1, -77.2, -76.8),
}


def state_center(state: str) -> tuple[float, float]:
    b = STATE_BBOX[state.upper()]
    return ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2)


def in_state(lat: float | None, lng: float | None, state: str) -> bool | None:
    """True/False, ou None quando não há coordenada."""
    if lat is None or lng is None:
        return None
    b = STATE_BBOX.get(state.upper())
    if not b:
        return None
    return b[0] <= lat <= b[1] and b[2] <= lng <= b[3]


def is_us_phone(raw: str | None) -> bool | None:
    """True se é número VÁLIDO dos EUA (código de área existente), None sem telefone."""
    if not raw:
        return None
    try:
        n = phonenumbers.parse(raw, "US")
    except phonenumbers.NumberParseException:
        return False
    return phonenumbers.is_valid_number(n) and phonenumbers.region_code_for_number(n) in ("US", "PR", "VI", "GU")


def accept(lat, lng, phone_raw, state: str) -> tuple[bool, str]:
    """Regra: rejeita se a coordenada existe e está fora do estado, ou se o
    telefone existe e não é dos EUA. Sem nenhum dos dois, aceita (raro)."""
    geo = in_state(lat, lng, state)
    if geo is False:
        return False, "fora do estado"
    ph = is_us_phone(phone_raw)
    if ph is False:
        return False, "telefone não é dos EUA"
    return True, "ok"
