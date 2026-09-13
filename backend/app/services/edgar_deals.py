"""SEC EDGAR M&A deal-history ingestion (free, no API key).

Uses EDGAR's full-text search API (efts.sec.gov) to find real merger filings
(8-K Item 1.01/2.01 deal announcements, DEFM14A merger proxies) and turns them
into real records for the Deal Genome (E1) — replacing purely synthetic history.

Verified live (Sept 2026): GET https://efts.sec.gov/LATEST/search-index
  ?q="merger agreement"&forms=8-K&startdt=YYYY-MM-DD&enddt=YYYY-MM-DD
Returns Elasticsearch JSON: hits.hits[]._source {ciks, display_names, form,
file_date, adsh, sics, biz_locations, items}. Requires a User-Agent header;
max 10 requests/second.
"""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from sqlalchemy.orm import Session

from app.schemas import HistoricalTransactionInput
from app.services.deal_genome import create_or_update_transaction

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
REQUEST_TIMEOUT = 25
# Enrichment fetches the filing document; keep each fetch short so a large
# enrich batch can't block the (single-worker) server long enough to look dead.
ENRICH_TIMEOUT = 10
# SEC requires a descriptive User-Agent on all automated requests.
USER_AGENT = "QuantumBlack-MADealOS/1.0 contact:compliance@qb.local"

# 2-digit SIC prefix -> coarse sector label (enough for Deal Genome matching).
_SIC_SECTOR = {
    "01": "Agriculture", "10": "Mining", "13": "Oil & Gas", "15": "Construction",
    "20": "Food", "28": "Pharma/Chemicals", "35": "Industrial/Tech Hardware",
    "36": "Electronics", "37": "Transportation Equipment", "48": "Telecom",
    "49": "Utilities", "50": "Wholesale", "52": "Retail", "60": "Banking",
    "61": "Credit", "62": "Securities", "63": "Insurance", "67": "Holding/Investment",
    "73": "Software/IT Services", "80": "Healthcare Services", "87": "Professional Services",
}


class EdgarError(ValueError):
    pass


def _clean_company(display_name: str) -> str:
    # "APPLE INC.  (AAPL)  (CIK 0000320193)" -> "APPLE INC."
    return display_name.split("  (")[0].strip() if display_name else display_name


def _sector_from_sics(sics: list[str]) -> str:
    for sic in sics or []:
        prefix = str(sic)[:2]
        if prefix in _SIC_SECTOR:
            return _SIC_SECTOR[prefix]
    return "Unknown"


def _filing_url(cik: str, adsh: str) -> str:
    cik_num = str(cik).lstrip("0") or "0"
    adsh_nodash = adsh.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{adsh_nodash}/{adsh}-index.htm"


def search_ma_filings(
    query: str = '"merger agreement"',
    forms: str = "8-K",
    start: str | None = None,
    end: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"q": query, "forms": forms}
    if start and end:
        params.update({"dateRange": "custom", "startdt": start, "enddt": end})
    try:
        resp = requests.get(EFTS_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise EdgarError(f"EDGAR request failed: {exc}") from exc
    if resp.status_code >= 400:
        raise EdgarError(f"EDGAR request failed ({resp.status_code}): {resp.text[:200]}")
    try:
        payload = resp.json()
    except json.JSONDecodeError as exc:
        raise EdgarError(f"EDGAR returned non-JSON payload: {exc}") from exc

    hits = (payload.get("hits", {}) or {}).get("hits", []) or []
    results: list[dict[str, Any]] = []
    for hit in hits[: max(1, limit)]:
        src = hit.get("_source", {})
        names = src.get("display_names", []) or []
        cik = (src.get("ciks") or [""])[0]
        adsh = src.get("adsh", "")
        results.append({
            "company": _clean_company(names[0]) if names else "Unknown",
            "cik": cik,
            "form": src.get("form", ""),
            "filed_date": src.get("file_date", ""),
            "sector": _sector_from_sics(src.get("sics", [])),
            "location": (src.get("biz_locations") or [""])[0],
            "items": src.get("items", []),
            "accession": adsh,
            "url": _filing_url(cik, adsh) if cik and adsh else "",
        })
    return results


# --- Deal-value enrichment (best-effort parse of the filing text) -------------
_CONSIDERATION_KEYWORDS = (
    "aggregate", "purchase price", "total consideration", "merger consideration",
    "enterprise value", "equity value", "transaction value", "per share",
)
# $1,234.5 million / $2 billion / $500,000,000
_MONEY_RE = re.compile(
    r"\$\s?([\d,]+(?:\.\d+)?)\s?(billion|million|bn|mm|m|b)?", re.IGNORECASE
)


def _to_usd(number: str, unit: str | None) -> float | None:
    try:
        value = float(number.replace(",", ""))
    except ValueError:
        return None
    unit = (unit or "").lower()
    if unit in ("billion", "bn", "b"):
        value *= 1_000_000_000
    elif unit in ("million", "mm", "m"):
        value *= 1_000_000
    return value


def _extract_deal_value(text: str) -> float | None:
    """Best-effort: the largest dollar amount appearing near consideration wording.

    Heuristic, not exact — the PRD's precise multiples need structured data. This
    gives a real 'near estimate' from the actual filing instead of a blank."""
    lowered = text.lower()
    candidates: list[float] = []
    for match in _MONEY_RE.finditer(text):
        start = match.start()
        window = lowered[max(0, start - 120): start + 40]
        if any(kw in window for kw in _CONSIDERATION_KEYWORDS):
            usd = _to_usd(match.group(1), match.group(2))
            # Ignore tiny/per-share-only numbers and absurd parses.
            if usd is not None and 1_000_000 <= usd <= 5_000_000_000_000:
                candidates.append(usd)
    return max(candidates) if candidates else None


def _fetch_primary_document_text(cik: str, adsh: str) -> str | None:
    """Fetch the primary filing document and return its plain text (HTML stripped)."""
    cik_num = str(cik).lstrip("0") or "0"
    adsh_nodash = adsh.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{adsh_nodash}"
    headers = {"User-Agent": USER_AGENT}
    try:
        idx = requests.get(f"{base}/index.json", headers=headers, timeout=ENRICH_TIMEOUT)
        if idx.status_code >= 400:
            return None
        items = (idx.json().get("directory", {}) or {}).get("item", []) or []
        # Prefer the largest .htm that is not the index page.
        docs = [it for it in items if str(it.get("name", "")).lower().endswith((".htm", ".html")) and "index" not in str(it.get("name", "")).lower()]
        if not docs:
            return None
        docs.sort(key=lambda it: int(it.get("size", 0) or 0), reverse=True)
        primary = docs[0]["name"]
        doc = requests.get(f"{base}/{primary}", headers=headers, timeout=ENRICH_TIMEOUT)
        if doc.status_code >= 400:
            return None
        raw = doc.text
        # Strip tags/entities to plain text.
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"&[a-zA-Z#0-9]+;", " ", text)
        return re.sub(r"\s+", " ", text)
    except (requests.RequestException, ValueError, KeyError):
        return None


def enrich_deal_value(cik: str, adsh: str) -> float | None:
    text = _fetch_primary_document_text(cik, adsh)
    return _extract_deal_value(text) if text else None


def import_ma_filings_to_genome(
    db: Session,
    query: str = '"merger agreement"',
    forms: str = "8-K",
    start: str | None = None,
    end: str | None = None,
    limit: int = 20,
    enrich: bool = False,
) -> dict[str, Any]:
    """Write EDGAR filings into the Deal Genome as real records.

    Seeds real acquirer names, sectors, dates, and source URLs. With enrich=True,
    also fetches each filing's primary document and extracts a best-effort deal
    value (largest dollar amount near consideration wording) — slower (one extra
    fetch per filing) but populates real dollar figures instead of blanks.
    """
    filings = search_ma_filings(query, forms=forms, start=start, end=end, limit=limit)
    imported = 0
    valued = 0
    errors: list[str] = []
    for f in filings:
        if f["company"] == "Unknown":
            continue
        deal_value: float | None = None
        if enrich and f.get("cik") and f.get("accession"):
            deal_value = enrich_deal_value(f["cik"], f["accession"])
            if deal_value is not None:
                valued += 1
        try:
            create_or_update_transaction(
                db,
                HistoricalTransactionInput(
                    buyer_name=f["company"][:255],
                    target_name="(see filing)",
                    announcement_date=f["filed_date"] or "",
                    deal_value=deal_value,
                    enterprise_value=deal_value,
                    sector=(f["sector"] or "Unknown")[:160],
                    buyer_country="United States",
                    target_country="Unknown",
                    payment_type="Unknown",
                    deal_status="announced",
                    source_url=f["url"][:1200],
                    source_type="sec_edgar",
                ),
            )
            imported += 1
        except Exception as exc:  # keep importing the rest
            errors.append(f"{f['company']}: {exc}")

    return {
        "searched": len(filings),
        "imported": imported,
        "deal_values_extracted": valued,
        "enriched": enrich,
        "error_count": len(errors),
        "errors": errors[:10],
    }
