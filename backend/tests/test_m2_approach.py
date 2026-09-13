import pytest

from app.schemas import (
    AdvisorGraphInput,
    DealParticipant,
    FinancialNormalizationInput,
    NormalizationAdjustment,
    YearlyFinancials,
)
from app.services.advisor_graph import build_advisor_conflict_graph
from app.services.financial_normalization import normalize_financials


# --- Financial normalization --------------------------------------------------

def test_normalization_periods_and_addbacks():
    inp = FinancialNormalizationInput(years=[
        YearlyFinancials(year=2023, revenue=100.0, cogs=40.0, sga=20.0, rnd=5.0,
                         adjustments=[NormalizationAdjustment(label="Owner comp addback", amount=8.0)]),
        YearlyFinancials(year=2024, revenue=120.0, cogs=48.0, sga=22.0, rnd=6.0),
        YearlyFinancials(year=2025, revenue=140.0, cogs=54.0, sga=24.0, rnd=7.0),
    ])
    result = normalize_financials(inp)
    periods = result["periods"]
    # Most recent year is LTM.
    assert periods[0]["period"] == "LTM" and periods[0]["year"] == 2025
    assert periods[1]["period"] == "PY-1"
    assert periods[2]["period"] == "PY-2"

    # 2023 reported EBITDA = 100 - 40 - 20 - 5 = 35; +8 addback => 43 normalized.
    y2023 = next(p for p in periods if p["year"] == 2023)
    assert y2023["reported_ebitda"] == 35.0
    assert y2023["normalized_ebitda"] == 43.0
    assert result["total_normalization_adjustments"] == 8.0


def test_normalization_flags_margin_anomaly_and_requires_signoff():
    inp = FinancialNormalizationInput(
        years=[YearlyFinancials(year=2025, revenue=100.0, cogs=10.0, sga=5.0, rnd=0.0)],  # 85% EBITDA margin
        sector_ebitda_margin_95th=0.40,
    )
    result = normalize_financials(inp)
    assert result["requires_analyst_signoff"] is True
    assert any(a["type"] == "ebitda_margin_outlier" for a in result["anomalies"])


def test_normalization_below_ebitda_bridge():
    inp = FinancialNormalizationInput(years=[
        YearlyFinancials(year=2025, revenue=100.0, cogs=40.0, sga=20.0, rnd=0.0,
                         depreciation_amortization=10.0, interest_expense=5.0, tax_rate=0.20),
    ])
    row = normalize_financials(inp)["periods"][0]
    # reported EBITDA 40; EBIT 30; EBT 25; tax 5; NI 20.
    below = row["reported_below_ebitda"]
    assert below["ebit"] == 30.0
    assert below["ebt"] == 25.0
    assert below["tax"] == 5.0
    assert below["net_income"] == 20.0


# --- Advisor conflict graph ---------------------------------------------------

def test_advisor_graph_detects_cross_side_conflict():
    inp = AdvisorGraphInput(participants=[
        DealParticipant(name="Buyer Bank", role="financing_bank", side="buyer", affiliations=["Goldman Sachs"]),
        DealParticipant(name="Target CFO", role="management", side="target", affiliations=["Goldman Sachs"]),
    ])
    graph = build_advisor_conflict_graph(inp)
    assert graph["summary"]["conflicts"] == 1
    assert graph["conflict_flags"][0]["affiliation"] == "Goldman Sachs"


def test_advisor_graph_detects_leverage_relationship():
    inp = AdvisorGraphInput(participants=[
        DealParticipant(name="Buyer VP", role="management", side="buyer", affiliations=["Stanford GSB"]),
        DealParticipant(name="Target CEO", role="board", side="target", affiliations=["Stanford GSB"]),
    ])
    graph = build_advisor_conflict_graph(inp)
    assert graph["summary"]["conflicts"] == 0
    assert graph["summary"]["leverage_opportunities"] == 1


def test_advisor_graph_ignores_same_side_overlap():
    inp = AdvisorGraphInput(participants=[
        DealParticipant(name="Buyer Advisor A", role="advisor", side="buyer", affiliations=["Firm X"]),
        DealParticipant(name="Buyer Advisor B", role="advisor", side="buyer", affiliations=["Firm X"]),
    ])
    graph = build_advisor_conflict_graph(inp)
    assert graph["summary"]["conflicts"] == 0
    assert graph["summary"]["leverage_opportunities"] == 0
