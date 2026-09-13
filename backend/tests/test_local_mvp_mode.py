from __future__ import annotations

import importlib

from fastapi.testclient import TestClient

from app.schemas import DealStructureInput, NegotiationInput, ValuationData
from app.services import deal_structuring, document_scanner, negotiator


def _build_local_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("AI_PROVIDER", "local")
    monkeypatch.setenv("USE_ANTHROPIC", "false")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from app.core.config import get_settings

    get_settings.cache_clear()
    import app.main as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_app_starts_without_anthropic_key(monkeypatch):
    client = _build_local_client(monkeypatch)
    response = client.get("/")
    assert response.status_code == 200
    assert "API is running" in response.json()["message"]


def test_health_llm_local_mode_without_key(monkeypatch):
    client = _build_local_client(monkeypatch)
    response = client.get("/api/v1/health/llm")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "local"
    assert payload["status"] == "ok"


def test_document_scanner_local_mode_does_not_call_anthropic(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "local")
    monkeypatch.setenv("USE_ANTHROPIC", "false")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def _raise_if_called(*args, **kwargs):
        raise AssertionError("Anthropic structured output should not be called in local mode.")

    monkeypatch.setattr(document_scanner, "generate_structured_output", _raise_if_called)
    monkeypatch.setattr(document_scanner, "_import_pdf_reader", lambda: object())
    monkeypatch.setattr(
        document_scanner,
        "_extract_documents",
        lambda *_: [
            {
                "page": 1,
                "text": (
                    "The agreement includes a change of control restriction and lender consent "
                    "for additional indebtedness."
                ),
            }
        ],
    )

    result = document_scanner.process_and_scan_pdf(b"not-used", "sample.pdf")
    assert result.total_risks_found >= 1
    assert any(r.risk_category in {"Change of Control", "Debt Covenant"} for r in result.risks)


def test_deal_structuring_local_mode_does_not_call_anthropic(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "local")
    monkeypatch.setenv("USE_ANTHROPIC", "false")

    def _raise_if_called(*args, **kwargs):
        raise AssertionError("Anthropic structured output should not be called in local mode.")

    monkeypatch.setattr(deal_structuring, "generate_structured_output", _raise_if_called)

    output = deal_structuring.generate_deal_structure(
        DealStructureInput(
            acquirer_market_cap=200_000_000.0,
            valuation_data=ValuationData(enterprise_value=60_000_000.0, ebitda=8_000_000.0),
            risk_flags=[],
        )
    )
    assert output.recommended_structure in {"All Cash", "Stock Swap", "LBO", "Cash + Earn-out", "Hybrid"}
    assert output.estimated_dilution_pct >= 0


def test_negotiation_local_mode_does_not_call_anthropic(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "local")
    monkeypatch.setenv("USE_ANTHROPIC", "false")

    def _raise_if_called(*args, **kwargs):
        raise AssertionError("Anthropic structured output should not be called in local mode.")

    monkeypatch.setattr(negotiator, "generate_structured_output", _raise_if_called)

    output = negotiator.generate_negotiation_strategy(
        NegotiationInput(
            target_enterprise_value=50_000_000.0,
            total_annual_synergy=5_000_000.0,
            risk_flags=[],
            recommended_structure="All Cash",
        )
    )
    assert output.walk_away_price == 75_000_000.0
    assert len(output.tactical_moves) == 3

