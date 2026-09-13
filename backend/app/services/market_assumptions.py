from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas import MarketAssumptionsResponse, PublicDataSeriesResponse
from app.services.public_data import PublicDataError, get_fred_series, get_treasury_yields

FALLBACK_RISK_FREE_RATE = 0.0421
FALLBACK_EQUITY_RISK_PREMIUM = 0.0433
DEFAULT_TERMINAL_GROWTH_RATE = 0.025


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_percent(value: Any) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if parsed > 1.0:
        parsed = parsed / 100.0
    if 0.0 <= parsed < 1.0:
        return parsed
    return None


def _latest_numeric_observation(series: PublicDataSeriesResponse) -> tuple[float, str] | None:
    for row in reversed(series.observations):
        parsed = _safe_percent(row.get("value"))
        if parsed is not None:
            return parsed, row.get("date", "")
    return None


def _risk_free_rate_from_public_sources() -> tuple[float, dict[str, str], bool]:
    try:
        fred = get_fred_series("DGS10", limit=30)
        latest = _latest_numeric_observation(fred)
        if latest is not None:
            value, date = latest
            return value, {
                "name": "FRED DGS10",
                "url": "https://fred.stlouisfed.org/series/DGS10",
                "value": f"{value:.4%}",
                "date": date,
            }, True
    except PublicDataError:
        pass

    try:
        treasury = get_treasury_yields(limit=30)
        latest = _latest_numeric_observation(treasury)
        if latest is not None:
            value, date = latest
            return value, {
                "name": "US Treasury FiscalData average interest rates",
                "url": "https://fiscaldata.treasury.gov/datasets/average-interest-rates-treasury-securities/average-interest-rates",
                "value": f"{value:.4%}",
                "date": date,
            }, True
    except PublicDataError:
        pass

    return FALLBACK_RISK_FREE_RATE, {
        "name": "Sample fallback risk-free rate",
        "url": "local-demo",
        "value": f"{FALLBACK_RISK_FREE_RATE:.4%}",
        "date": "sample",
    }, False


def calculate_market_assumptions(
    *,
    beta: float = 1.10,
    equity_risk_premium: float = FALLBACK_EQUITY_RISK_PREMIUM,
    debt_spread: float = 0.0200,
    tax_rate: float = 0.21,
    equity_weight: float = 0.75,
    terminal_growth_rate: float = DEFAULT_TERMINAL_GROWTH_RATE,
) -> MarketAssumptionsResponse:
    if not 0.0 <= equity_weight <= 1.0:
        raise ValueError("equity_weight must be between 0 and 1.")
    if not 0.0 <= tax_rate < 1.0:
        raise ValueError("tax_rate must be between 0 and 1.")
    if beta <= 0.0:
        raise ValueError("beta must be greater than 0.")

    risk_free_rate, risk_free_source, live_risk_free = _risk_free_rate_from_public_sources()
    debt_weight = 1.0 - equity_weight
    pre_tax_cost_of_debt = risk_free_rate + debt_spread
    cost_of_equity = risk_free_rate + (beta * equity_risk_premium)
    after_tax_cost_of_debt = pre_tax_cost_of_debt * (1.0 - tax_rate)
    wacc = (equity_weight * cost_of_equity) + (debt_weight * after_tax_cost_of_debt)

    sources = [
        risk_free_source,
        {
            "name": "Damodaran ERP manual input",
            "url": "https://pages.stern.nyu.edu/~adamodar/",
            "value": f"{equity_risk_premium:.4%}",
            "date": "configurable assumption",
        },
        {
            "name": "Local capital structure inputs",
            "url": "local-assumptions",
            "value": f"beta={beta:.2f}; equity_weight={equity_weight:.1%}; debt_spread={debt_spread:.1%}; tax_rate={tax_rate:.1%}",
            "date": "request",
        },
    ]

    source_mode = "mixed" if live_risk_free else "sample"
    note = (
        "Risk-free rate refreshed from a public source; ERP, beta, capital structure, debt spread, "
        "and tax rate remain editable assumptions."
        if live_risk_free
        else "Public rate source unavailable, so WACC uses clearly labeled sample assumptions."
    )

    return MarketAssumptionsResponse(
        risk_free_rate=float(round(risk_free_rate, 6)),
        equity_risk_premium=float(round(equity_risk_premium, 6)),
        beta=float(round(beta, 4)),
        pre_tax_cost_of_debt=float(round(pre_tax_cost_of_debt, 6)),
        tax_rate=float(round(tax_rate, 6)),
        equity_weight=float(round(equity_weight, 6)),
        debt_weight=float(round(debt_weight, 6)),
        cost_of_equity=float(round(cost_of_equity, 6)),
        after_tax_cost_of_debt=float(round(after_tax_cost_of_debt, 6)),
        wacc=float(round(wacc, 6)),
        terminal_growth_rate=float(round(terminal_growth_rate, 6)),
        source_mode=source_mode,
        sources=sources,
        last_updated=_utc_now(),
        note=note,
    )
