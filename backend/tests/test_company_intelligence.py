from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_market_data_summary_returns_professional_cards():
    response = client.get("/api/v1/market-data/summary")
    assert response.status_code == 200

    payload = response.json()
    labels = {card["label"] for card in payload["cards"]}
    assert {"S&P 500", "NASDAQ", "US10Y", "DXY", "WTI"}.issubset(labels)
    assert payload["source_mode"] == "sample"


def test_company_map_search_and_viewport_use_safe_signal_language():
    search_response = client.get("/api/v1/company-map/search", params={"limit": 20})
    assert search_response.status_code == 200
    search_payload = search_response.json()
    assert search_payload["companies"]
    assert "No record asserts a company is for sale" in search_payload["note"]

    viewport_response = client.get(
        "/api/v1/company-map/viewport",
        params={"north": 60, "south": 20, "east": -60, "west": -130, "limit": 20},
    )
    assert viewport_response.status_code == 200
    viewport_payload = viewport_response.json()
    assert viewport_payload["companies"]
    assert all(20 <= company["lat"] <= 60 for company in viewport_payload["companies"])
    assert all(-130 <= company["lng"] <= -60 for company in viewport_payload["companies"])


def test_company_profile_contains_registry_and_signal_context():
    response = client.get("/api/v1/company-map/company/sample-rockwell-automation")
    assert response.status_code == 200

    payload = response.json()
    assert payload["company"]["name"] == "Rockwell Automation, Inc."
    assert payload["filings_registry_links"]
    assert "No direct public sale-process signal" in payload["mna_signal_explanation"]
    assert payload["legal_regulatory_notes"]
