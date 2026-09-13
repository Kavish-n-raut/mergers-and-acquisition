from __future__ import annotations

import csv
import io
import json
from typing import Any

import requests

from app.schemas import PublicDataSeriesResponse

REQUEST_TIMEOUT = 20
DEFAULT_USER_AGENT = "QuantumBlack-MADealOS/1.0 contact:compliance@qb.local"


class PublicDataError(ValueError):
    pass


def _get_json(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    response = requests.get(url, headers=headers or {}, timeout=REQUEST_TIMEOUT)
    if response.status_code >= 400:
        raise PublicDataError(f"Public data request failed ({response.status_code}): {response.text[:300]}")
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise PublicDataError(f"Public data endpoint returned non-JSON payload: {exc}") from exc


def get_sec_companyfacts(cik: str) -> dict[str, Any]:
    normalized = "".join(ch for ch in cik if ch.isdigit()).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{normalized}.json"
    headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}
    payload = _get_json(url, headers=headers)
    return {
        "source": "SEC EDGAR",
        "identifier": normalized,
        "entity_name": payload.get("entityName", ""),
        "facts": payload.get("facts", {}),
    }


def get_fred_series(series_id: str, limit: int = 20) -> PublicDataSeriesResponse:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    if response.status_code >= 400:
        raise PublicDataError(f"FRED request failed ({response.status_code}): {response.text[:300]}")

    reader = csv.DictReader(io.StringIO(response.text))
    rows = [row for row in reader if row.get(series_id)]
    trimmed = rows[-limit:] if limit > 0 else rows
    observations = [
        {"date": row.get("DATE", ""), "value": row.get(series_id, "")}
        for row in trimmed
    ]
    return PublicDataSeriesResponse(
        source="FRED",
        identifier=series_id,
        observations=observations,
    )


def get_treasury_yields(limit: int = 20) -> PublicDataSeriesResponse:
    # U.S. Treasury Fiscal Data API (free public endpoint)
    url = (
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates"
        "?sort=-record_date&page[size]=200"
    )
    payload = _get_json(url)
    data = payload.get("data", [])
    filtered = [
        {"date": row.get("record_date", ""), "value": row.get("avg_interest_rate_amt", "")}
        for row in data[: max(1, limit)]
        if row.get("security_desc")
    ]
    return PublicDataSeriesResponse(
        source="US Treasury FiscalData",
        identifier="avg_interest_rates",
        observations=filtered,
    )


def get_stooq_prices(symbol: str, limit: int = 20) -> PublicDataSeriesResponse:
    normalized = symbol.strip().lower()
    if "." not in normalized:
        normalized = f"{normalized}.us"
    url = f"https://stooq.com/q/d/l/?s={normalized}&i=d"
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    if response.status_code >= 400:
        raise PublicDataError(f"Stooq request failed ({response.status_code}): {response.text[:300]}")

    reader = csv.DictReader(io.StringIO(response.text))
    rows = [row for row in reader if row.get("Close")]
    trimmed = rows[-limit:] if limit > 0 else rows
    observations = [
        {"date": row.get("Date", ""), "value": row.get("Close", "")}
        for row in trimmed
    ]
    return PublicDataSeriesResponse(
        source="Stooq",
        identifier=normalized.upper(),
        observations=observations,
    )


def get_reference_datasets() -> dict[str, list[dict[str, str]]]:
    return {
        "valuation_references": [
            {
                "name": "Damodaran Data Library",
                "url": "https://pages.stern.nyu.edu/~adamodar/",
                "notes": "Industry multiples, implied ERP, and valuation support tables.",
            }
        ],
        "diligence_corpora": [
            {
                "name": "CUAD",
                "url": "https://www.atticusprojectai.org/cuad",
                "notes": "Clause-level legal contract dataset for diligence testing.",
            },
            {
                "name": "SEC Material Contracts",
                "url": "https://www.sec.gov/edgar/search-and-access",
                "notes": "Public exhibits and filed agreements for realistic scenario generation.",
            },
        ],
        "regulatory_sources": [
            {"name": "FTC", "url": "https://www.ftc.gov"},
            {"name": "European Commission Competition", "url": "https://competition-policy.ec.europa.eu"},
            {"name": "UK CMA", "url": "https://www.gov.uk/government/organisations/competition-and-markets-authority"},
            {"name": "CFIUS Treasury", "url": "https://home.treasury.gov/policy-issues/international/the-committee-on-foreign-investment-in-the-united-states-cfius"},
        ],
    }

