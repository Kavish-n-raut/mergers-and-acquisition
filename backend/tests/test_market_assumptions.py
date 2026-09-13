from __future__ import annotations

from app.services import market_assumptions


def test_calculate_market_assumptions_uses_public_rate_when_available(monkeypatch):
    monkeypatch.setattr(
        market_assumptions,
        "_risk_free_rate_from_public_sources",
        lambda: (
            0.04,
            {
                "name": "Test public rate",
                "url": "https://example.test/rate",
                "value": "4.0000%",
                "date": "2026-08-19",
            },
            True,
        ),
    )

    result = market_assumptions.calculate_market_assumptions(
        beta=1.0,
        equity_risk_premium=0.05,
        debt_spread=0.02,
        tax_rate=0.25,
        equity_weight=0.8,
        terminal_growth_rate=0.025,
    )

    assert result.source_mode == "mixed"
    assert result.risk_free_rate == 0.04
    assert result.cost_of_equity == 0.09
    assert result.after_tax_cost_of_debt == 0.045
    assert result.wacc == 0.081
    assert result.terminal_growth_rate == 0.025


def test_calculate_market_assumptions_fallback_is_labeled(monkeypatch):
    monkeypatch.setattr(
        market_assumptions,
        "_risk_free_rate_from_public_sources",
        lambda: (
            0.0421,
            {
                "name": "Sample fallback risk-free rate",
                "url": "local-demo",
                "value": "4.2100%",
                "date": "sample",
            },
            False,
        ),
    )

    result = market_assumptions.calculate_market_assumptions()

    assert result.source_mode == "sample"
    assert "sample assumptions" in result.note
    assert result.wacc > 0
