"""Finnhub free market-data client (https://finnhub.io).

A free alternative to Bloomberg/CapIQ for the platform's live-market-anchoring
needs. Free tier: 60 calls/minute. Set FINNHUB_API_KEY to enable; without a key
the endpoints report a clear "not configured" status rather than failing hard.

Verified endpoint contract (Sept 2026):
- Quote:        GET /quote?symbol=SYM&token=KEY  -> {c,d,dp,h,l,o,pc,t}
- Profile:      GET /stock/profile2?symbol=SYM&token=KEY
- Financials:   GET /stock/metric?symbol=SYM&metric=all&token=KEY -> {metric:{...}, series:{...}}
- Company news: GET /company-news?symbol=SYM&from=YYYY-MM-DD&to=YYYY-MM-DD&token=KEY -> [{headline,summary,source,url,datetime,...}]
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import requests

from app.core.config import get_settings

BASE_URL = "https://finnhub.io/api/v1"
REQUEST_TIMEOUT = 20


class FinnhubError(ValueError):
    pass


class FinnhubConfigurationError(FinnhubError):
    pass


def is_configured() -> bool:
    key = get_settings().finnhub_api_key
    return bool(key and key.strip() and not key.strip().lower().startswith("your_"))


def _get(path: str, params: dict[str, Any]) -> Any:
    if not is_configured():
        raise FinnhubConfigurationError(
            "FINNHUB_API_KEY is not set. Get a free key at https://finnhub.io and add it to backend/.env."
        )
    params = {**params, "token": get_settings().finnhub_api_key.strip()}
    try:
        resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise FinnhubError(f"Finnhub request failed: {exc}") from exc
    if resp.status_code == 401:
        raise FinnhubConfigurationError("Finnhub rejected the API key (401). Check FINNHUB_API_KEY.")
    if resp.status_code == 429:
        raise FinnhubError("Finnhub rate limit hit (429). Free tier allows 60 calls/minute.")
    if resp.status_code >= 400:
        raise FinnhubError(f"Finnhub request failed ({resp.status_code}): {resp.text[:200]}")
    try:
        return resp.json()
    except json.JSONDecodeError as exc:
        raise FinnhubError(f"Finnhub returned non-JSON payload: {exc}") from exc


def get_quote(symbol: str) -> dict[str, Any]:
    data = _get("/quote", {"symbol": symbol.upper()})
    return {
        "symbol": symbol.upper(),
        "current_price": data.get("c"),
        "change": data.get("d"),
        "percent_change": data.get("dp"),
        "high": data.get("h"),
        "low": data.get("l"),
        "open": data.get("o"),
        "previous_close": data.get("pc"),
        "timestamp": data.get("t"),
        "source": "Finnhub",
    }


def get_company_profile(symbol: str) -> dict[str, Any]:
    data = _get("/stock/profile2", {"symbol": symbol.upper()})
    return {"symbol": symbol.upper(), "profile": data, "source": "Finnhub"}


def get_basic_financials(symbol: str) -> dict[str, Any]:
    data = _get("/stock/metric", {"symbol": symbol.upper(), "metric": "all"})
    metric = data.get("metric", {}) if isinstance(data, dict) else {}
    # Surface the multiples the valuation engines care about, when present.
    highlights = {
        "market_cap": metric.get("marketCapitalization"),
        "pe_ttm": metric.get("peTTM"),
        "ev_ebitda": metric.get("currentEv/freeCashFlowTTM") or metric.get("enterpriseValueOverEBITDA"),
        "ev_revenue": metric.get("enterpriseValueOverRevenue"),
        "revenue_growth_ttm": metric.get("revenueGrowthTTMYoy"),
        "ebitda_margin_ttm": metric.get("ebitdaMargin") or metric.get("netMarginTTM"),
        "net_debt_ebitda": metric.get("netDebtToEBITDA"),
    }
    return {"symbol": symbol.upper(), "highlights": highlights, "metric": metric, "source": "Finnhub"}


def get_company_news(symbol: str, days: int = 30, limit: int = 20) -> dict[str, Any]:
    today = date.today()
    frm = today - timedelta(days=max(1, days))
    data = _get(
        "/company-news",
        {"symbol": symbol.upper(), "from": frm.isoformat(), "to": today.isoformat()},
    )
    items = data if isinstance(data, list) else []
    articles = [
        {
            "headline": a.get("headline", ""),
            "summary": a.get("summary", ""),
            "source": a.get("source", ""),
            "url": a.get("url", ""),
            "datetime": a.get("datetime"),
        }
        for a in items[: max(1, limit)]
    ]
    return {"symbol": symbol.upper(), "count": len(articles), "articles": articles, "source": "Finnhub"}
