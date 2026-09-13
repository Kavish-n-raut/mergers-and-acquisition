from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any

import requests

from app.schemas import (
    CompanyMapMarker,
    CompanyMapResponse,
    CompanyProfileResponse,
    MarketDataCard,
    MarketDataSummaryResponse,
)

REQUEST_TIMEOUT = 8
DEFAULT_TTL = timedelta(minutes=30)


class _TTLCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[datetime, Any]] = {}

    def get(self, key: str) -> Any | None:
        value = self._data.get(key)
        if value is None:
            return None
        expires_at, payload = value
        if datetime.now(timezone.utc) > expires_at:
            self._data.pop(key, None)
            return None
        return payload

    def set(self, key: str, payload: Any, ttl: timedelta = DEFAULT_TTL) -> None:
        self._data[key] = (datetime.now(timezone.utc) + ttl, payload)


cache = _TTLCache()


COUNTRY_CENTROIDS = {
    "US": (39.8283, -98.5795),
    "USA": (39.8283, -98.5795),
    "United States": (39.8283, -98.5795),
    "GB": (54.0, -2.0),
    "GBR": (54.0, -2.0),
    "United Kingdom": (54.0, -2.0),
    "DE": (51.1657, 10.4515),
    "Germany": (51.1657, 10.4515),
    "FR": (46.2276, 2.2137),
    "France": (46.2276, 2.2137),
    "BE": (50.5039, 4.4699),
    "BEL": (50.5039, 4.4699),
    "Belgium": (50.5039, 4.4699),
    "CA": (56.1304, -106.3468),
    "Canada": (56.1304, -106.3468),
    "CH": (46.8182, 8.2275),
    "Switzerland": (46.8182, 8.2275),
    "DK": (56.2639, 9.5018),
    "DNK": (56.2639, 9.5018),
    "Denmark": (56.2639, 9.5018),
    "IN": (20.5937, 78.9629),
    "IND": (20.5937, 78.9629),
    "India": (20.5937, 78.9629),
    "IT": (41.8719, 12.5674),
    "ITA": (41.8719, 12.5674),
    "Italy": (41.8719, 12.5674),
    "NL": (52.1326, 5.2913),
    "NLD": (52.1326, 5.2913),
    "Netherlands": (52.1326, 5.2913),
    "SE": (60.1282, 18.6435),
    "SWE": (60.1282, 18.6435),
    "Sweden": (60.1282, 18.6435),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


SAMPLE_COMPANIES = [
    {
        "id": "sample-rockwell-automation",
        "name": "Rockwell Automation, Inc.",
        "headquarters": "Milwaukee, Wisconsin",
        "city": "Milwaukee, WI",
        "country": "United States",
        "sector": "Industrial Automation",
        "company_size": "Large cap public company",
        "public_private": "Public",
        "listed_exchange": "NYSE",
        "ticker": "ROK",
        "lei": None,
        "registration_number": None,
        "marker_role": "competitor",
        "lat": 43.0389,
        "lng": -87.9065,
        "mna_signal": "Low",
        "confidence": "Low",
        "distress_signal": "Insufficient public data",
        "signal_score": 18.0,
        "signal_explanation": "No direct public sale-process signal in the local dataset. Relevance is based on industrial automation sector overlap only.",
        "data_source": "Local sample fallback; verify with SEC EDGAR and company filings before use",
        "source_url": "https://www.sec.gov/edgar/search/",
        "last_updated": "2026-05-22T00:00:00+00:00",
        "source_mode": "sample",
    },
    {
        "id": "sample-emerson-electric",
        "name": "Emerson Electric Co.",
        "headquarters": "St. Louis, Missouri",
        "city": "St. Louis, MO",
        "country": "United States",
        "sector": "Industrial Technology",
        "company_size": "Large cap public company",
        "public_private": "Public",
        "listed_exchange": "NYSE",
        "ticker": "EMR",
        "lei": None,
        "registration_number": None,
        "marker_role": "competitor",
        "lat": 38.627,
        "lng": -90.1994,
        "mna_signal": "Low",
        "confidence": "Low",
        "distress_signal": "Insufficient public data",
        "signal_score": 20.0,
        "signal_explanation": "No direct public sale-process evidence in the local dataset. Flagged only as a sector-relevant public comparable.",
        "data_source": "Local sample fallback; verify with SEC EDGAR and company filings before use",
        "source_url": "https://www.sec.gov/edgar/search/",
        "last_updated": "2026-05-22T00:00:00+00:00",
        "source_mode": "sample",
    },
    {
        "id": "sample-siemens-ag",
        "name": "Siemens AG",
        "headquarters": "Munich, Germany",
        "city": "Munich",
        "country": "Germany",
        "sector": "Industrial Automation",
        "company_size": "Large cap public company",
        "public_private": "Public",
        "listed_exchange": "XETRA",
        "ticker": "SIE.DE",
        "lei": None,
        "registration_number": None,
        "marker_role": "competitor",
        "lat": 48.1351,
        "lng": 11.582,
        "mna_signal": "Insufficient public data",
        "confidence": "Insufficient public data",
        "distress_signal": "Insufficient public data",
        "signal_score": 0.0,
        "signal_explanation": "No direct public M&A process evidence is included in this local dataset.",
        "data_source": "Local sample fallback; verify with official filings and exchange data before use",
        "source_url": None,
        "last_updated": "2026-05-22T00:00:00+00:00",
        "source_mode": "sample",
    },
    {
        "id": "sample-abb-ltd",
        "name": "ABB Ltd",
        "headquarters": "Zurich, Switzerland",
        "city": "Zurich",
        "country": "Switzerland",
        "sector": "Electrification and Automation",
        "company_size": "Large cap public company",
        "public_private": "Public",
        "listed_exchange": "SIX Swiss Exchange",
        "ticker": "ABBN.SW",
        "lei": None,
        "registration_number": None,
        "marker_role": "competitor",
        "lat": 47.3769,
        "lng": 8.5417,
        "mna_signal": "Insufficient public data",
        "confidence": "Insufficient public data",
        "distress_signal": "Insufficient public data",
        "signal_score": 0.0,
        "signal_explanation": "No direct public M&A process evidence is included in this local dataset.",
        "data_source": "Local sample fallback; verify with official filings and exchange data before use",
        "source_url": None,
        "last_updated": "2026-05-22T00:00:00+00:00",
        "source_mode": "sample",
    },
    {
        "id": "sample-schneider-electric",
        "name": "Schneider Electric SE",
        "headquarters": "Rueil-Malmaison, France",
        "city": "Rueil-Malmaison",
        "country": "France",
        "sector": "Energy Management and Automation",
        "company_size": "Large cap public company",
        "public_private": "Public",
        "listed_exchange": "Euronext Paris",
        "ticker": "SU.PA",
        "lei": None,
        "registration_number": None,
        "marker_role": "competitor",
        "lat": 48.8765,
        "lng": 2.1813,
        "mna_signal": "Insufficient public data",
        "confidence": "Insufficient public data",
        "distress_signal": "Insufficient public data",
        "signal_score": 0.0,
        "signal_explanation": "No direct public M&A process evidence is included in this local dataset.",
        "data_source": "Local sample fallback; verify with official filings and exchange data before use",
        "source_url": None,
        "last_updated": "2026-05-22T00:00:00+00:00",
        "source_mode": "sample",
    },
    {
        "id": "sample-honeywell",
        "name": "Honeywell International Inc.",
        "headquarters": "Charlotte, North Carolina",
        "city": "Charlotte, NC",
        "country": "United States",
        "sector": "Industrial Technology",
        "company_size": "Large cap public company",
        "public_private": "Public",
        "listed_exchange": "NASDAQ",
        "ticker": "HON",
        "lei": None,
        "registration_number": None,
        "marker_role": "buyer",
        "lat": 35.2271,
        "lng": -80.8431,
        "mna_signal": "Low",
        "confidence": "Low",
        "distress_signal": "Insufficient public data",
        "signal_score": 22.0,
        "signal_explanation": "Strategic-buyer relevance is based on sector adjacency only; no sale-process signal is asserted.",
        "data_source": "Local sample fallback; verify with SEC EDGAR and company filings before use",
        "source_url": "https://www.sec.gov/edgar/search/",
        "last_updated": "2026-05-22T00:00:00+00:00",
        "source_mode": "sample",
    },
    {
        "id": "sample-ptc",
        "name": "PTC Inc.",
        "headquarters": "Boston, Massachusetts",
        "city": "Boston, MA",
        "country": "United States",
        "sector": "Industrial Software",
        "company_size": "Mid/Large cap public company",
        "public_private": "Public",
        "listed_exchange": "NASDAQ",
        "ticker": "PTC",
        "lei": None,
        "registration_number": None,
        "marker_role": "target",
        "lat": 42.3601,
        "lng": -71.0589,
        "mna_signal": "Low",
        "confidence": "Low",
        "distress_signal": "Insufficient public data",
        "signal_score": 24.0,
        "signal_explanation": "Product adjacency may be strategically relevant, but the local dataset contains no direct sale-process evidence.",
        "data_source": "Local sample fallback; verify with SEC EDGAR and company filings before use",
        "source_url": "https://www.sec.gov/edgar/search/",
        "last_updated": "2026-05-22T00:00:00+00:00",
        "source_mode": "sample",
    },
    {
        "id": "sample-ge-vernova",
        "name": "GE Vernova Inc.",
        "headquarters": "Cambridge, Massachusetts",
        "city": "Cambridge, MA",
        "country": "United States",
        "sector": "Energy Technology",
        "company_size": "Large cap public company",
        "public_private": "Public",
        "listed_exchange": "NYSE",
        "ticker": "GEV",
        "lei": None,
        "registration_number": None,
        "marker_role": "company",
        "lat": 42.3736,
        "lng": -71.1097,
        "mna_signal": "Insufficient public data",
        "confidence": "Insufficient public data",
        "distress_signal": "Insufficient public data",
        "signal_score": 0.0,
        "signal_explanation": "No direct public M&A process evidence is included in this local dataset.",
        "data_source": "Local sample fallback; verify with SEC EDGAR and company filings before use",
        "source_url": "https://www.sec.gov/edgar/search/",
        "last_updated": "2026-05-22T00:00:00+00:00",
        "source_mode": "sample",
    },
]


MARKET_DATA_CARDS = [
    {
        "label": "S&P 500",
        "value": "5,310.74",
        "change": "+0.61%",
        "status": "positive",
        "last_updated": "Sample as of local demo",
        "data_source": "Sample fallback; replace with Stooq or licensed market feed",
        "detail": "Broad US equity risk appetite proxy.",
    },
    {
        "label": "NASDAQ",
        "value": "16,920.8",
        "change": "+0.83%",
        "status": "positive",
        "last_updated": "Sample as of local demo",
        "data_source": "Sample fallback; replace with Stooq or licensed market feed",
        "detail": "Technology and growth equity sentiment proxy.",
    },
    {
        "label": "US10Y",
        "value": "4.21%",
        "change": "-2 bp",
        "status": "positive",
        "last_updated": "Sample as of local demo",
        "data_source": "Sample fallback; replace with Treasury/FRED",
        "detail": "Risk-free discount-rate benchmark for valuation.",
    },
    {
        "label": "DXY",
        "value": "103.88",
        "change": "+0.12%",
        "status": "neutral",
        "last_updated": "Sample as of local demo",
        "data_source": "Sample fallback; replace with public FX feed",
        "detail": "US dollar strength can affect cross-border deal economics.",
    },
    {
        "label": "WTI",
        "value": "$78.40",
        "change": "-0.45%",
        "status": "negative",
        "last_updated": "Sample as of local demo",
        "data_source": "Sample fallback; replace with FRED/EIA source",
        "detail": "Energy price marker relevant for industrial and transportation exposure.",
    },
    {
        "label": "Global M&A Activity",
        "value": "+12% QoQ",
        "change": "Improving",
        "status": "positive",
        "last_updated": "Sample as of local demo",
        "data_source": "Sample fallback; replace with licensed deal database",
        "detail": "Indicative activity pulse only; not a live transaction feed.",
    },
    {
        "label": "Private Credit Spread",
        "value": "Stable",
        "change": "Flat",
        "status": "neutral",
        "last_updated": "Sample as of local demo",
        "data_source": "Sample fallback; replace with lender or market data feed",
        "detail": "Financing climate indicator for leveraged transaction capacity.",
    },
]


def _marker(payload: dict[str, Any]) -> CompanyMapMarker:
    return CompanyMapMarker.model_validate(payload)


def _sample_markers() -> list[CompanyMapMarker]:
    return [_marker(item) for item in SAMPLE_COMPANIES]


def _matches(value: str | None, filter_value: str | None) -> bool:
    if not filter_value:
        return True
    return filter_value.lower() in (value or "").lower()


def _filter_companies(
    companies: list[CompanyMapMarker],
    *,
    q: str | None = None,
    country: str | None = None,
    sector: str | None = None,
    company_size: str | None = None,
    public_private: str | None = None,
    listed_exchange: str | None = None,
    mna_signal: str | None = None,
    distress_signal: str | None = None,
    ipo_public_company: bool | None = None,
    marker_role: str | None = None,
) -> list[CompanyMapMarker]:
    query = (q or "").lower().strip()
    output: list[CompanyMapMarker] = []
    for company in companies:
        query_match = True
        if query:
            fields = [
                company.name,
                company.city,
                company.country,
                company.sector,
                company.ticker or "",
                company.lei or "",
                company.registration_number or "",
            ]
            query_match = any(query in field.lower() for field in fields)
        if not query_match:
            continue
        if not _matches(company.country, country):
            continue
        if not _matches(company.sector, sector):
            continue
        if not _matches(company.company_size, company_size):
            continue
        if public_private and company.public_private.lower() != public_private.lower():
            continue
        if listed_exchange and not _matches(company.listed_exchange, listed_exchange):
            continue
        if mna_signal and company.mna_signal.lower() != mna_signal.lower():
            continue
        if distress_signal and company.distress_signal.lower() != distress_signal.lower():
            continue
        if ipo_public_company is not None and bool(company.ticker) != ipo_public_company:
            continue
        if marker_role and company.marker_role != marker_role:
            continue
        output.append(company)
    return output


def _within_viewport(company: CompanyMapMarker, north: float, south: float, east: float, west: float) -> bool:
    return south <= company.lat <= north and west <= company.lng <= east


def search_companies(
    *,
    q: str | None = None,
    country: str | None = None,
    sector: str | None = None,
    company_size: str | None = None,
    public_private: str | None = None,
    listed_exchange: str | None = None,
    mna_signal: str | None = None,
    distress_signal: str | None = None,
    ipo_public_company: bool | None = None,
    marker_role: str | None = None,
    limit: int = 100,
) -> CompanyMapResponse:
    cache_key = f"company-search:{q}:{country}:{sector}:{company_size}:{public_private}:{listed_exchange}:{mna_signal}:{distress_signal}:{ipo_public_company}:{marker_role}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    companies = _sample_markers()
    if q:
        companies.extend(_search_sec_company_tickers(q))
        companies.extend(_search_gleif(q))

    deduped: dict[str, CompanyMapMarker] = {}
    for company in companies:
        deduped[company.id] = company
    filtered = _filter_companies(
        list(deduped.values()),
        q=q,
        country=country,
        sector=sector,
        company_size=company_size,
        public_private=public_private,
        listed_exchange=listed_exchange,
        mna_signal=mna_signal,
        distress_signal=distress_signal,
        ipo_public_company=ipo_public_company,
        marker_role=marker_role,
    )[:limit]
    source_modes = {company.source_mode for company in filtered}
    response = CompanyMapResponse(
        companies=filtered,
        total=len(filtered),
        data_source="SEC EDGAR, GLEIF LEI API, OpenCorporates/Companies House-ready adapters, local sample fallback",
        source_mode="mixed" if len(source_modes) > 1 else (next(iter(source_modes)) if source_modes else "sample"),
        last_updated=_now_iso(),
        note="No record asserts a company is for sale. M&A signal is an evidence/confidence indicator only.",
    )
    cache.set(cache_key, response)
    return response


def viewport_companies(
    *,
    north: float,
    south: float,
    east: float,
    west: float,
    **filters: Any,
) -> CompanyMapResponse:
    response = search_companies(**filters)
    visible = [company for company in response.companies if _within_viewport(company, north, south, east, west)]
    return CompanyMapResponse(
        companies=visible,
        total=len(visible),
        data_source=response.data_source,
        source_mode=response.source_mode,
        last_updated=_now_iso(),
        note="Viewport loading returns only companies inside the requested bounds.",
    )


def get_company_profile(company_id: str) -> CompanyProfileResponse | None:
    companies = search_companies(limit=500).companies
    company = next((item for item in companies if item.id == company_id), None)
    if company is None:
        return None

    nearby = sorted(
        [candidate for candidate in companies if candidate.id != company.id],
        key=lambda candidate: _distance_km(company.lat, company.lng, candidate.lat, candidate.lng),
    )[:4]
    links = []
    if company.source_url:
        links.append({"label": company.data_source, "url": company.source_url})
    if company.ticker:
        links.append({"label": "SEC EDGAR search", "url": "https://www.sec.gov/edgar/search/"})
    if company.lei:
        links.append({"label": "GLEIF LEI search", "url": f"https://search.gleif.org/#/record/{company.lei}"})

    return CompanyProfileResponse(
        company=company,
        overview=f"{company.name} is shown as a {company.public_private.lower()} company in {company.sector}. This profile is for market-mapping workflow support and must be verified against source filings or registries.",
        filings_registry_links=links,
        competitors_nearby=nearby,
        mna_signal_explanation=company.signal_explanation,
        legal_regulatory_notes=[
            f"Verify registry standing and beneficial ownership requirements in {company.country}.",
            "Confirm competition, foreign investment, sanctions, and sector licensing considerations before outreach.",
            "Do not use this workflow output as legal/regulatory advice.",
        ],
        ipo_public_company_details={
            "public_private": company.public_private,
            "ticker": company.ticker or "Not available",
            "listed_exchange": company.listed_exchange or "Not available",
            "filings_note": "Use SEC EDGAR, exchange filings, Companies House, GLEIF, or official investor relations pages where available.",
        },
    )


def market_data_summary() -> MarketDataSummaryResponse:
    return MarketDataSummaryResponse(
        cards=[MarketDataCard.model_validate(item) for item in MARKET_DATA_CARDS],
        source_mode="sample",
        note="Sample market data for local/free MVP. Replace with Stooq, FRED, Treasury, EIA, or licensed feeds for production.",
    )


def _search_sec_company_tickers(query: str) -> list[CompanyMapMarker]:
    normalized = query.strip().lower()
    if len(normalized) < 2:
        return []
    cache_key = "sec-company-tickers"
    payload = cache.get(cache_key)
    if payload is None:
        try:
            response = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers={"User-Agent": "MADealOS local MVP contact@example.com"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            cache.set(cache_key, payload, timedelta(hours=6))
        except requests.RequestException:
            return []

    matches: list[CompanyMapMarker] = []
    for record in list(payload.values())[:12000]:
        title = str(record.get("title", ""))
        ticker = str(record.get("ticker", ""))
        if normalized not in title.lower() and normalized not in ticker.lower():
            continue
        sample_match = next((item for item in _sample_markers() if item.ticker and item.ticker.lower() == ticker.lower()), None)
        if sample_match:
            matches.append(sample_match.model_copy(update={"source_mode": "live", "data_source": "SEC EDGAR company_tickers.json + local HQ coordinates", "last_updated": _now_iso()}))
            continue
        matches.append(
            CompanyMapMarker(
                id=f"sec-{ticker.lower()}",
                name=title.title(),
                headquarters="United States headquarters not geocoded",
                city="United States centroid",
                country="United States",
                sector="Public company",
                company_size="Public company",
                public_private="Public",
                listed_exchange=None,
                ticker=ticker,
                marker_role="company",
                lat=39.8283,
                lng=-98.5795,
                mna_signal="Insufficient public data",
                confidence="Insufficient public data",
                signal_score=0.0,
                signal_explanation="SEC ticker match only. No M&A process signal is inferred from the ticker registry.",
                data_source="SEC EDGAR company_tickers.json; approximate country centroid used because HQ coordinates are unavailable",
                source_url="https://www.sec.gov/files/company_tickers.json",
                last_updated=_now_iso(),
                source_mode="live",
            )
        )
        if len(matches) >= 12:
            break
    return matches


def _search_gleif(query: str) -> list[CompanyMapMarker]:
    normalized = query.strip()
    if len(normalized) < 3:
        return []
    cache_key = f"gleif:{normalized.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        response = requests.get(
            "https://api.gleif.org/api/v1/lei-records",
            params={"filter[entity.legalName]": normalized, "page[size]": 5},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        rows = response.json().get("data", [])
    except requests.RequestException:
        return []

    markers: list[CompanyMapMarker] = []
    for row in rows:
        attributes = row.get("attributes", {})
        entity = attributes.get("entity", {})
        name = entity.get("legalName", {}).get("name") or row.get("id")
        address = entity.get("legalAddress", {}) or {}
        country = address.get("country") or "Unknown"
        city = address.get("city") or country
        coordinates = COUNTRY_CENTROIDS.get(country) or COUNTRY_CENTROIDS.get(country.upper())
        if coordinates is None:
            continue
        lat, lng = coordinates
        markers.append(
            CompanyMapMarker(
                id=f"gleif-{row.get('id')}",
                name=name,
                headquarters=", ".join(part for part in [city, country] if part),
                city=city,
                country=country,
                sector="Legal entity registry result",
                company_size="Unknown",
                public_private="Unknown",
                lei=row.get("id"),
                marker_role="company",
                lat=float(lat),
                lng=float(lng),
                mna_signal="Insufficient public data",
                confidence="Insufficient public data",
                signal_score=0.0,
                signal_explanation="GLEIF legal entity match only. No M&A process signal is inferred from LEI registration.",
                data_source="GLEIF LEI API; country centroid used where HQ coordinates are unavailable",
                source_url=f"https://api.gleif.org/api/v1/lei-records/{row.get('id')}",
                last_updated=_now_iso(),
                source_mode="live",
            )
        )
    cache.set(cache_key, markers)
    return markers


def _distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lng / 2) ** 2
    return 2 * radius * asin(sqrt(a))
