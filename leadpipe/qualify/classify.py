"""Decisão final: um status de site por lead + motivo em texto.

Ordem:
  sem URL ou URL de agregador/rede social      → SEM_SITE
  não resolve / erro / 4xx / 5xx / timeout     → SITE_QUEBRADO
  render mobile quebrado                        → SITE_QUEBRADO
  ≥ OLD_SITE_MIN_SIGNALS sinais de antigo       → SITE_ANTIGO
  senão                                         → SITE_OK (descartar do funil)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import config
from .http_check import HttpResult, host_of
from .render_check import RenderResult
from .signals import SignalReport


@dataclass
class Verdict:
    site_status: str
    reason: str
    signals: dict = field(default_factory=dict)


def is_aggregator(url: str | None) -> str | None:
    if not url:
        return None
    h = host_of(url)
    for d in config.AGGREGATOR_DOMAINS:
        if h == d or h.endswith("." + d):
            return d
    return None


def classify_no_site(url: str | None) -> Verdict:
    if not url:
        return Verdict("SEM_SITE", "campo de site vazio")
    return Verdict("SEM_SITE", f"site aponta para {is_aggregator(url)}")


def classify(http: HttpResult, render: RenderResult | None, signals: SignalReport | None) -> Verdict:
    sig = {"http": {"error": http.error, "status": http.status, "elapsed_ms": http.elapsed_ms,
                    "final_url": http.final_url, "https": http.https, "bad_cert": http.bad_cert}}
    if render is not None:
        sig["render"] = {"error": render.error, "metrics": render.metrics, "broken": render.broken_reasons}
    if signals is not None:
        sig["old"] = signals.fired

    if not http.ok:
        labels = {"dns": "domínio não resolve", "timeout": f"timeout > {config.SITE_TIMEOUT_S:.0f}s",
                  "connect": "conexão recusada", "http_4xx": f"HTTP {http.status}",
                  "http_5xx": f"HTTP {http.status}", "bad_cert": "certificado inválido e sem fallback",
                  "invalid_url": "URL inválida"}
        return Verdict("SITE_QUEBRADO", labels.get(http.error or "", http.error or "erro"), sig)

    if render is not None:
        if render.error == "timeout":
            return Verdict("SITE_QUEBRADO", f"render mobile: timeout > {config.SITE_TIMEOUT_S:.0f}s", sig)
        if render.broken_reasons:
            return Verdict("SITE_QUEBRADO", "render mobile: " + "; ".join(render.broken_reasons), sig)

    if signals is not None and signals.count >= config.OLD_SITE_MIN_SIGNALS:
        parts = [f"{k} ({v})" for k, v in signals.fired.items()]
        return Verdict("SITE_ANTIGO", f"{signals.count} sinais: " + "; ".join(parts), sig)

    fired = (signals.fired if signals else {})
    note = f"1 sinal fraco: {next(iter(fired))}" if fired else "sem sinais"
    return Verdict("SITE_OK", f"responde em {http.elapsed_ms}ms, render ok, {note}", sig)
