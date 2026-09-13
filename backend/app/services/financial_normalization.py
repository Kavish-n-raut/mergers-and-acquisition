"""Module 2 — The Approach: three-year financial normalization (PRD v3.0 §4.2.2).

Deterministic. Maps raw yearly figures onto a standard M&A chart of accounts,
applies line-itemized normalization add-backs (owner comp, non-recurring items,
etc.), presents as-reported vs normalized EBITDA side by side, tags the three
most recent years as LTM / PY-1 / PY-2, and raises anomaly flags.
"""

from __future__ import annotations

from statistics import mean, pstdev
from typing import Any

from app.schemas import FinancialNormalizationInput, YearlyFinancials

PERIOD_LABELS = ["LTM", "PY-1", "PY-2"]


def _safe_div(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _normalize_year(year: YearlyFinancials, period_label: str) -> dict[str, Any]:
    gross_profit = year.revenue - year.cogs
    opex = year.sga + year.rnd
    reported_ebitda = gross_profit - opex

    adjustments = [{"label": a.label, "amount": a.amount} for a in year.adjustments]
    adjustments_total = sum(a.amount for a in year.adjustments)
    normalized_ebitda = reported_ebitda + adjustments_total

    def _below_ebitda(ebitda: float) -> dict[str, Any]:
        ebit = ebitda - year.depreciation_amortization
        ebt = ebit - year.interest_expense
        tax = max(0.0, ebt) * year.tax_rate
        net_income = ebt - tax
        return {
            "ebit": round(ebit, 2),
            "ebt": round(ebt, 2),
            "tax": round(tax, 2),
            "net_income": round(net_income, 2),
        }

    return {
        "period": period_label,
        "year": year.year,
        "net_revenue": round(year.revenue, 2),
        "cogs": round(year.cogs, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin": _round_opt(_safe_div(gross_profit, year.revenue)),
        "sga": round(year.sga, 2),
        "rnd": round(year.rnd, 2),
        "d_and_a": round(year.depreciation_amortization, 2),
        "reported_ebitda": round(reported_ebitda, 2),
        "reported_ebitda_margin": _round_opt(_safe_div(reported_ebitda, year.revenue)),
        "adjustments": adjustments,
        "adjustments_total": round(adjustments_total, 2),
        "normalized_ebitda": round(normalized_ebitda, 2),
        "normalized_ebitda_margin": _round_opt(_safe_div(normalized_ebitda, year.revenue)),
        "reported_below_ebitda": _below_ebitda(reported_ebitda),
        "normalized_below_ebitda": _below_ebitda(normalized_ebitda),
    }


def _round_opt(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None else None


def _detect_anomalies(rows: list[dict[str, Any]], inp: FinancialNormalizationInput) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []

    # 1) Normalized EBITDA margin above the sector 95th percentile.
    if inp.sector_ebitda_margin_95th is not None:
        for row in rows:
            margin = row["normalized_ebitda_margin"]
            if margin is not None and margin > inp.sector_ebitda_margin_95th:
                anomalies.append({
                    "type": "ebitda_margin_outlier",
                    "period": row["period"],
                    "detail": f"Normalized EBITDA margin {margin:.1%} exceeds the sector 95th percentile {inp.sector_ebitda_margin_95th:.1%}.",
                })

    # 2) Year-over-year revenue growth outliers (>3 std from the mean YoY, needs >= 3 years).
    ordered = sorted(rows, key=lambda r: r["year"])
    growths: list[tuple[int, float]] = []
    for prev, curr in zip(ordered, ordered[1:]):
        if prev["net_revenue"]:
            growths.append((curr["year"], (curr["net_revenue"] - prev["net_revenue"]) / prev["net_revenue"]))
    if len(growths) >= 2:
        values = [g for _, g in growths]
        mu, sigma = mean(values), pstdev(values)
        for yr, g in growths:
            if sigma > 0 and abs(g - mu) > 3 * sigma:
                anomalies.append({
                    "type": "revenue_growth_outlier",
                    "period": str(yr),
                    "detail": f"{yr} revenue growth {g:.1%} is more than 3 standard deviations from the mean.",
                })
    # Heuristic fallback when there is too little history to compute a distribution.
    for yr, g in growths:
        if g > 0.5:
            anomalies.append({
                "type": "revenue_growth_high",
                "period": str(yr),
                "detail": f"{yr} revenue growth of {g:.1%} is unusually high and should be diligence-verified.",
            })

    return anomalies


def normalize_financials(inp: FinancialNormalizationInput) -> dict[str, Any]:
    # Most recent year first, tagged LTM / PY-1 / PY-2 / (year) beyond three.
    ordered = sorted(inp.years, key=lambda y: y.year, reverse=True)
    rows = [
        _normalize_year(year, PERIOD_LABELS[i] if i < len(PERIOD_LABELS) else f"PY-{i}")
        for i, year in enumerate(ordered)
    ]

    anomalies = _detect_anomalies(rows, inp)
    total_adjustments = round(sum(r["adjustments_total"] for r in rows), 2)

    return {
        "periods": rows,
        "chart_of_accounts": [
            "Net Revenue", "COGS", "Gross Profit", "Gross Margin %", "SG&A", "R&D",
            "EBITDA (reported)", "Normalization Adjustments", "EBITDA (normalized)",
            "D&A", "EBIT", "Interest", "EBT", "Tax", "Net Income",
        ],
        "total_normalization_adjustments": total_adjustments,
        "anomalies": anomalies,
        "requires_analyst_signoff": bool(anomalies),
        "note": "EBITDA excludes D&A. Add-backs are positive amounts that increase normalized EBITDA.",
    }
