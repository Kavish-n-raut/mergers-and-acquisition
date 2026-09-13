"""GDELT news retrieval (free, no API key) — a free alternative to NewsAPI.

GDELT monitors global news; its DOC 2.0 API returns matching articles as JSON.
Pair the returned headlines with FinBERT (services/finbert.py) to produce the
Sentiment Radar (E2) distress/momentum signals with no paid data.

Verified contract (Sept 2026):
  GET https://api.gdeltproject.org/api/v2/doc/doc
    ?query=<q>&mode=artlist&format=json&maxrecords=<n>&timespan=<e.g. 3m>
  -> {"articles": [{"url","title","seendate","domain","language","sourcecountry"}]}

Note: GDELT throttles to ~1 request / 5 seconds per IP and returns a plain-text
"Please limit requests..." notice when exceeded — handled explicitly below.
"""

from __future__ import annotations

import json
from typing import Any

import requests

BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
REQUEST_TIMEOUT = 25
USER_AGENT = "QuantumBlack-MADealOS/1.0 contact:compliance@qb.local"


class GdeltError(ValueError):
    pass


class GdeltRateLimitError(GdeltError):
    pass


def get_news(query: str, max_records: int = 25, timespan: str = "3m") -> dict[str, Any]:
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": max(1, min(max_records, 250)),
        "timespan": timespan,
        "sort": "datedesc",
    }
    try:
        resp = requests.get(BASE_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise GdeltError(f"GDELT request failed: {exc}") from exc
    if resp.status_code >= 400:
        raise GdeltError(f"GDELT request failed ({resp.status_code}): {resp.text[:200]}")

    text = resp.text.strip()
    # GDELT returns a plain-text notice (not JSON) when rate-limited.
    if text.lower().startswith("please limit requests"):
        raise GdeltRateLimitError("GDELT rate limit: max ~1 request every 5 seconds per IP. Retry shortly.")
    try:
        payload = json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise GdeltError(f"GDELT returned non-JSON payload: {text[:150]}") from exc

    articles = [
        {
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "domain": a.get("domain", ""),
            "seendate": a.get("seendate", ""),
            "language": a.get("language", ""),
            "sourcecountry": a.get("sourcecountry", ""),
        }
        for a in (payload.get("articles", []) or [])
    ]
    return {"query": query, "count": len(articles), "articles": articles, "source": "GDELT"}
