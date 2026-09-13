"""Patent-velocity signal (Sentiment Radar / E2 R&D momentum).

Primary source: **Google Patents** free JSON endpoint — no API key, reachable,
reliable. We count granted patents by assignee per priority year to gauge R&D
momentum (accelerating filings = tech momentum; sustained decline = R&D distress).

Fallback: USPTO PatentsView (search.patentsview.org) when PATENTSVIEW_API_KEY is
set — kept because PatentsView is the "official" source, but its host has been
flaky and its key is not self-serve, so Google Patents is the default.

Note on recency: patents publish ~12-18 months after filing, so the most recent
year is always undercounted — the trend across years is the useful signal, not
the absolute latest-year value.
"""

from __future__ import annotations

import json
import time
from datetime import date
from typing import Any

import requests

from app.core.config import get_settings

GOOGLE_PATENTS_URL = "https://patents.google.com/xhr/query"
PATENTSVIEW_URL = "https://search.patentsview.org/api/v1/patent/"
USPTO_ODP_URL = "https://api.uspto.gov/api/v1/patent/applications/search"
REQUEST_TIMEOUT = 25
# Google Patents' JSON endpoint requires a browser-like User-Agent.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


class PatentsError(ValueError):
    pass


class PatentsConfigurationError(PatentsError):
    pass


def is_configured() -> bool:
    # Google Patents needs no key, so the feature is always available.
    return True


def patentsview_configured() -> bool:
    key = get_settings().patentsview_api_key
    return bool(key and key.strip() and not key.strip().lower().startswith("your_"))


def uspto_configured() -> bool:
    key = get_settings().uspto_api_key
    return bool(key and key.strip() and not key.strip().lower().startswith("your_"))


def _signal_from_counts(counts: list[int]) -> str:
    if len(counts) < 2:
        return "Insufficient data"
    prior = counts[:-1]
    prior_mean = sum(prior) / len(prior)
    latest = counts[-1]
    if prior_mean <= 0:
        return "Insufficient data"
    change = (latest - prior_mean) / prior_mean
    if change <= -0.40:
        return "R&D distress (filing rate down >40% vs baseline)"
    if change >= 0.40:
        return "Technology momentum (filing rate up >40% vs baseline)"
    return "Stable filing rate"


# --- Google Patents (keyless, default) ----------------------------------------

def _gp_count(assignee: str, year: int) -> int:
    inner = (
        f'q=assignee:"{assignee}"'
        f"&before=priority:{year + 1}0101"
        f"&after=priority:{year}0101"
        f"&type=PATENT"
    )
    try:
        resp = requests.get(
            GOOGLE_PATENTS_URL,
            params={"url": inner, "exp": ""},
            headers={"User-Agent": _BROWSER_UA},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise PatentsError(f"Google Patents request failed: {exc}") from exc
    # Google returns 429/503 or an HTML "Sorry..." page when it throttles automated queries.
    if resp.status_code in (429, 503) or resp.text[:60].lower().find("sorry") != -1:
        raise PatentsError(
            "Google Patents temporarily rate-limited this network (it throttles automated queries). "
            "Retry in a few minutes, or configure PATENTSVIEW_API_KEY / USPTO ODP for heavier use."
        )
    if resp.status_code >= 400:
        raise PatentsError(f"Google Patents request failed ({resp.status_code}).")
    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        raise PatentsError(f"Google Patents returned non-JSON payload: {exc}") from exc
    return int((data.get("results", {}) or {}).get("total_num_results", 0) or 0)


def get_patent_velocity_google(company: str, years: int = 4) -> dict[str, Any]:
    current = date.today().year
    year_list = list(range(current - years + 1, current + 1))
    by_year: dict[str, int] = {}
    for i, y in enumerate(year_list):
        if i:
            time.sleep(0.4)  # be polite to Google Patents between per-year queries
        by_year[str(y)] = _gp_count(company, y)
    counts = [by_year[str(y)] for y in year_list]
    return {
        "company": company,
        "total_patents": sum(counts),
        "filings_by_year": by_year,
        "signal": _signal_from_counts(counts),
        "source": "Google Patents",
        "note": "Counts by priority year; the most recent year(s) are undercounted due to the ~12-18 month publication lag.",
    }


# --- USPTO PatentsView (optional, needs key) ----------------------------------

def _get_patent_velocity_patentsview(company: str, max_records: int = 1000) -> dict[str, Any]:
    from collections import Counter

    q = {"_text_any": {"assignees.assignee_organization": company}}
    fields = ["patent_id", "patent_date"]
    options = {"size": max(1, min(max_records, 1000))}
    params = {"q": json.dumps(q), "f": json.dumps(fields), "o": json.dumps(options)}
    headers = {"X-Api-Key": get_settings().patentsview_api_key.strip(), "Accept": "application/json"}
    try:
        resp = requests.get(PATENTSVIEW_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise PatentsError(f"PatentsView request failed: {exc}") from exc
    if resp.status_code in (401, 403):
        raise PatentsConfigurationError("PatentsView rejected the API key. Check PATENTSVIEW_API_KEY.")
    if resp.status_code >= 400:
        raise PatentsError(f"PatentsView request failed ({resp.status_code}).")
    patents = (resp.json() or {}).get("patents", []) or []
    by_year: Counter[str] = Counter()
    for p in patents:
        d = p.get("patent_date") or ""
        if len(d) >= 4:
            by_year[d[:4]] += 1
    counts = [by_year[y] for y in sorted(by_year)]
    return {
        "company": company,
        "total_patents": len(patents),
        "filings_by_year": dict(sorted(by_year.items())),
        "signal": _signal_from_counts(counts),
        "source": "USPTO PatentsView",
    }


# --- USPTO Open Data Portal (official, throttle-proof, needs self-serve key) ---

def _odp_count(company: str, year: int) -> int:
    body = {
        "q": (
            f'applicationMetaData.firstApplicantName:"{company}" '
            f"AND applicationMetaData.filingDate:[{year}-01-01 TO {year}-12-31]"
        ),
        "pagination": {"offset": 0, "limit": 1},
    }
    headers = {"X-API-KEY": get_settings().uspto_api_key.strip(), "Content-Type": "application/json"}
    try:
        resp = requests.post(USPTO_ODP_URL, json=body, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise PatentsError(f"USPTO ODP request failed: {exc}") from exc
    if resp.status_code in (401, 403):
        raise PatentsConfigurationError("USPTO ODP rejected the API key. Check USPTO_API_KEY.")
    if resp.status_code == 429:
        raise PatentsError("USPTO ODP rate limit hit (429).")
    if resp.status_code >= 400:
        raise PatentsError(f"USPTO ODP request failed ({resp.status_code}): {resp.text[:200]}")
    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        raise PatentsError(f"USPTO ODP returned non-JSON payload: {exc}") from exc
    # ODP returns a total match count (field name has varied: count / totalCount).
    for key in ("count", "totalCount", "total"):
        if isinstance(data.get(key), int):
            return data[key]
    bag = data.get("patentFileWrapperDataBag") or data.get("results") or []
    return len(bag)


def get_patent_velocity_uspto(company: str, years: int = 5) -> dict[str, Any]:
    current = date.today().year
    year_list = list(range(current - years + 1, current + 1))
    by_year: dict[str, int] = {str(y): _odp_count(company, y) for y in year_list}
    counts = [by_year[str(y)] for y in year_list]
    return {
        "company": company,
        "total_patents": sum(counts),
        "filings_by_year": by_year,
        "signal": _signal_from_counts(counts),
        "source": "USPTO Open Data Portal",
        "note": "Counts by filing year (applicant name match); official USPTO source, no scraping throttle.",
    }


def get_patent_velocity(company: str) -> dict[str, Any]:
    """Preference: USPTO ODP (official, key) > Google Patents (keyless) > PatentsView (key)."""
    if uspto_configured():
        return get_patent_velocity_uspto(company)
    try:
        return get_patent_velocity_google(company)
    except PatentsError:
        if patentsview_configured():
            return _get_patent_velocity_patentsview(company)
        raise
