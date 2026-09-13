import types

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
import app.services.gdelt as gdelt
import app.services.patents as patents
import app.services.edgar_deals as edgar


class _FakeResp:
    def __init__(self, *, text="", data=None, status=200):
        self._data = data
        self.text = text if text else (str(data) if data is not None else "")
        self.status_code = status

    def json(self):
        if self._data is None:
            import json
            return json.loads(self.text)
        return self._data


def _make_db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)()


# --- GDELT --------------------------------------------------------------------

def test_gdelt_parses_articles(monkeypatch):
    import json as _json
    payload = {"articles": [
        {"title": "Acme beats earnings", "url": "http://a", "domain": "reuters.com", "seendate": "20260101T000000Z", "language": "English", "sourcecountry": "US"},
        {"title": "Acme expands", "url": "http://b", "domain": "ap.com"},
    ]}
    # gdelt.get_news reads resp.text and json.loads() it, so provide JSON as text.
    monkeypatch.setattr(gdelt.requests, "get", lambda url, params=None, headers=None, timeout=None: _FakeResp(text=_json.dumps(payload)))
    result = gdelt.get_news("Acme Corp")
    assert result["count"] == 2
    assert result["articles"][0]["title"] == "Acme beats earnings"


def test_gdelt_rate_limit_detected(monkeypatch):
    monkeypatch.setattr(
        gdelt.requests, "get",
        lambda url, params=None, headers=None, timeout=None: _FakeResp(text="Please limit requests to one every 5 seconds"),
    )
    with pytest.raises(gdelt.GdeltRateLimitError):
        gdelt.get_news("Acme")


# --- USPTO PatentsView --------------------------------------------------------

def test_patents_keyless_by_default():
    # Google Patents needs no key, so the feature is always "configured".
    assert patents.is_configured() is True


def test_patents_google_velocity_signal(monkeypatch):
    # Mock the per-year Google Patents count: rising then a sharp drop.
    counts = iter([100, 110, 120, 40])
    monkeypatch.setattr(patents, "_gp_count", lambda assignee, year: next(counts))
    result = patents.get_patent_velocity_google("Acme", years=4)
    assert result["source"] == "Google Patents"
    assert result["total_patents"] == 370
    assert len(result["filings_by_year"]) == 4
    assert "distress" in result["signal"].lower()  # latest 40 vs prior mean 110 => big drop


def test_patents_google_momentum_signal(monkeypatch):
    counts = iter([50, 60, 70, 200])
    monkeypatch.setattr(patents, "_gp_count", lambda assignee, year: next(counts))
    result = patents.get_patent_velocity_google("Acme", years=4)
    assert "momentum" in result["signal"].lower()


def test_uspto_odp_count_parsing(monkeypatch):
    monkeypatch.setattr(patents, "get_settings", lambda: types.SimpleNamespace(uspto_api_key="k"))
    monkeypatch.setattr(patents.requests, "post", lambda url, json=None, headers=None, timeout=None: _FakeResp(data={"count": 123, "patentFileWrapperDataBag": []}))
    assert patents._odp_count("Acme", 2023) == 123


def test_get_patent_velocity_prefers_uspto_when_configured(monkeypatch):
    monkeypatch.setattr(patents, "uspto_configured", lambda: True)
    monkeypatch.setattr(patents, "_odp_count", lambda company, year: 42)
    def _fail(*a, **k):
        raise AssertionError("should not call Google when USPTO ODP is configured")
    monkeypatch.setattr(patents, "_gp_count", _fail)
    result = patents.get_patent_velocity("Acme")
    assert result["source"] == "USPTO Open Data Portal"
    assert result["total_patents"] == 42 * len(result["filings_by_year"])


# --- SEC EDGAR ----------------------------------------------------------------

_EDGAR_SAMPLE = {
    "hits": {"hits": [
        {"_source": {
            "display_names": ["APEX HOLDINGS INC.  (APX)  (CIK 0001234567)"],
            "ciks": ["0001234567"], "adsh": "0001193125-26-000123", "form": "8-K",
            "file_date": "2026-05-01", "sics": ["7372"], "biz_locations": ["San Jose, CA"],
            "items": ["1.01", "2.01"],
        }},
        {"_source": {
            "display_names": ["NORTHSTAR AUTOMATION CORP  (NAC)  (CIK 0007654321)"],
            "ciks": ["0007654321"], "adsh": "0001193125-26-000456", "form": "8-K",
            "file_date": "2026-04-15", "sics": ["3559"], "biz_locations": ["Chicago, IL"],
            "items": ["1.01"],
        }},
    ]}
}


def test_edgar_search_parsing(monkeypatch):
    monkeypatch.setattr(edgar.requests, "get", lambda url, params=None, headers=None, timeout=None: _FakeResp(data=_EDGAR_SAMPLE))
    filings = edgar.search_ma_filings(limit=10)
    assert len(filings) == 2
    assert filings[0]["company"] == "APEX HOLDINGS INC."
    assert filings[0]["sector"] == "Software/IT Services"  # SIC 7372
    assert filings[0]["url"].startswith("https://www.sec.gov/Archives/edgar/data/1234567/")


def test_edgar_extract_deal_value():
    text = (
        "On May 1, 2026, the Company entered into a merger agreement. "
        "The aggregate purchase price is approximately $2.4 billion in cash, "
        "or $45.00 per share. Legal fees of $3 million are excluded."
    )
    value = edgar._extract_deal_value(text)
    assert value == 2_400_000_000.0  # picks the consideration figure, not the $3M fees


def test_edgar_extract_deal_value_none_when_no_consideration():
    assert edgar._extract_deal_value("The cafeteria budget is $2 million this year.") is None


def test_edgar_import_into_deal_genome(monkeypatch):
    monkeypatch.setattr(edgar.requests, "get", lambda url, params=None, headers=None, timeout=None: _FakeResp(data=_EDGAR_SAMPLE))
    db = _make_db()
    result = edgar.import_ma_filings_to_genome(db, limit=10)
    assert result["imported"] == 2
    from app.services.deal_genome import summarize_deal_genome
    summary = summarize_deal_genome(db)
    assert summary.total_transactions == 2
    assert summary.by_source_type.get("sec_edgar") == 2
