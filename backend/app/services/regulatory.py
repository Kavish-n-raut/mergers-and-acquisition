"""Module 7 — The Close: Regulatory Horizon Engine (E5), CFIUS screening, and
closing-checklist generation (PRD v3.0 §4.7 / §5.5).

Deterministic, MVP mode. Antitrust filing thresholds are stored as USD-equivalent
approximations (documented) rather than pulled live. Second-request / Phase II
probability uses a fixed logistic model over combined market share, product
overlaps, transaction size, sector sensitivity, and PE-vs-strategic — the same
feature set the PRD specifies, with fixed coefficients instead of a trained fit.
"""

from __future__ import annotations

import math
from typing import Any

from app.schemas import CFIUSInput, ClosingChecklistInput, RegulatoryHorizonInput

# jurisdiction -> (regulator, USD-equivalent filing threshold, base review weeks, Phase II extra weeks)
JURISDICTIONS: dict[str, dict[str, Any]] = {
    "US_HSR": {"regulator": "DOJ / FTC (HSR Act)", "threshold_usd": 119_500_000, "base_weeks": 4, "phase2_weeks": 20, "filing_type": "HSR notification"},
    "EU_EC": {"regulator": "European Commission", "threshold_usd": 5_500_000_000, "base_weeks": 5, "phase2_weeks": 13, "filing_type": "EUMR notification"},
    "UK_CMA": {"regulator": "Competition & Markets Authority", "threshold_usd": 90_000_000, "base_weeks": 6, "phase2_weeks": 24, "filing_type": "CMA merger notice"},
    "IN_CCI": {"regulator": "Competition Commission of India", "threshold_usd": 720_000_000, "base_weeks": 4, "phase2_weeks": 12, "filing_type": "CCI Form I/II"},
    "CN_SAMR": {"regulator": "SAMR", "threshold_usd": 1_400_000_000, "base_weeks": 6, "phase2_weeks": 20, "filing_type": "SAMR notification"},
    "DE_BKA": {"regulator": "Bundeskartellamt", "threshold_usd": 550_000_000, "base_weeks": 4, "phase2_weeks": 16, "filing_type": "German merger notification"},
    "AU_ACCC": {"regulator": "ACCC", "threshold_usd": 0, "base_weeks": 8, "phase2_weeks": 12, "filing_type": "ACCC informal review"},
}

# Sectors with structurally higher investigation rates.
SECTOR_SENSITIVITY = {
    "telecom": 0.30, "telecommunications": 0.30, "media": 0.30, "healthcare": 0.25,
    "pharma": 0.25, "pharmaceuticals": 0.25, "defense": 0.40, "defence": 0.40,
    "technology": 0.15, "financial": 0.20, "energy": 0.20,
}


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def _phase2_probability(inp: RegulatoryHorizonInput) -> float:
    sector_risk = SECTOR_SENSITIVITY.get(inp.sector.strip().lower(), 0.10)
    size_ratio = math.log10(max(inp.deal_ev, 1.0) / 1e8)  # ~0 at $100M, grows with size
    z = (
        -2.6
        + 4.0 * inp.combined_market_share
        + 0.25 * inp.product_overlaps
        + 0.35 * max(0.0, size_ratio)
        + 3.0 * sector_risk
        - (1.0 if inp.is_private_equity else 0.0)
    )
    return round(_sigmoid(z), 4)


def regulatory_horizon(inp: RegulatoryHorizonInput) -> dict[str, Any]:
    p2 = _phase2_probability(inp)
    results: list[dict[str, Any]] = []

    for entry in inp.jurisdictions:
        meta = JURISDICTIONS[entry.jurisdiction]
        threshold = meta["threshold_usd"]
        filing_required = entry.combined_turnover_usd >= threshold or threshold == 0

        expected_weeks = meta["base_weeks"] + (meta["phase2_weeks"] * p2 if filing_required else 0)
        # Divestiture risk rises with market share and Phase II probability.
        divestiture_probability = round(min(0.9, inp.combined_market_share * p2 * 1.5), 4) if filing_required else 0.0
        divestiture_cost_estimate = round(inp.deal_ev * divestiture_probability * 0.15, 2)

        results.append({
            "jurisdiction": entry.jurisdiction,
            "regulator": meta["regulator"],
            "filing_type": meta["filing_type"],
            "filing_threshold_usd": threshold,
            "combined_turnover_usd": entry.combined_turnover_usd,
            "filing_required": filing_required,
            "phase2_probability": p2 if filing_required else 0.0,
            "expected_review_weeks": round(expected_weeks, 1),
            "divestiture_probability": divestiture_probability,
            "divestiture_cost_estimate_usd": divestiture_cost_estimate,
        })

    required = [r for r in results if r["filing_required"]]
    critical_path = max(required, key=lambda r: r["expected_review_weeks"]) if required else None

    return {
        "jurisdictions": results,
        "filings_required": len(required),
        "phase2_probability_model": p2,
        "critical_path": {
            "jurisdiction": critical_path["jurisdiction"],
            "expected_review_weeks": critical_path["expected_review_weeks"],
        } if critical_path else None,
        "total_estimated_divestiture_cost_usd": round(sum(r["divestiture_cost_estimate_usd"] for r in results), 2),
        "note": "Thresholds are USD-equivalent approximations; Phase II probability uses fixed logistic coefficients (MVP).",
    }


def cfius_screening(inp: CFIUSInput) -> dict[str, Any]:
    if not inp.us_business or not inp.foreign_acquirer:
        return {
            "risk_tier": "Low",
            "blocking": False,
            "rationale": ["CFIUS is not implicated: transaction does not involve a foreign acquirer of a US business."],
            "estimated_timeline_days": 0,
            "estimated_legal_cost_usd": 0,
        }

    rationale: list[str] = []
    sensitive_factors = 0
    if inp.critical_technology:
        sensitive_factors += 1
        rationale.append("Target holds critical/export-controlled technology (TID US Business).")
    if inp.critical_infrastructure:
        sensitive_factors += 1
        rationale.append("Target operates critical infrastructure.")
    if inp.sensitive_personal_data:
        sensitive_factors += 1
        rationale.append("Target holds sensitive personal data of US persons.")
    if inp.proximity_to_military:
        sensitive_factors += 1
        rationale.append("Target property is in proximity to sensitive US government/military sites.")
    if inp.acquirer_country_of_concern:
        rationale.append("Acquirer is from a country subject to heightened CFIUS scrutiny.")

    mandatory_declaration = inp.critical_technology and inp.acquirer_country_of_concern
    if sensitive_factors >= 2 or (mandatory_declaration and sensitive_factors >= 2):
        tier, blocking, timeline, cost = "Mandatory Full Notice", True, 45, (500_000, 1_000_000)
    elif mandatory_declaration:
        tier, blocking, timeline, cost = "Mandatory Declaration", True, 30, (100_000, 300_000)
    elif sensitive_factors == 1:
        tier, blocking, timeline, cost = "Voluntary Filing Recommended", False, 30, (75_000, 200_000)
    else:
        tier, blocking, timeline, cost = "Low", False, 0, (0, 0)
        rationale.append("Foreign acquisition of a US business, but no TID sensitivity factors identified.")

    return {
        "risk_tier": tier,
        "blocking": blocking,
        "sensitive_factor_count": sensitive_factors,
        "rationale": rationale,
        "estimated_timeline_days": timeline,
        "estimated_legal_cost_usd_range": {"low": cost[0], "high": cost[1]},
    }


def closing_checklist(inp: ClosingChecklistInput) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    def add(item: str, category: str) -> None:
        items.append({"item": item, "category": category, "status": "Not Started", "assignee": None})

    for jur in inp.required_jurisdictions:
        add(f"Regulatory clearance — {jur}", "Regulatory")
    if inp.acquirer_board_approval:
        add("Board approval — Acquirer", "Corporate")
    if inp.target_board_approval:
        add("Board approval — Target", "Corporate")
    if inp.shareholder_approval_required:
        add("Shareholder approval", "Corporate")
    if inp.financing_required:
        add("Financing commitment letter (debt)", "Financing")
    add("No Material Adverse Change certificate", "Legal")
    add("Representations & warranties bring-down", "Legal")
    for i in range(inp.change_of_control_consents):
        add(f"Third-party change-of-control consent #{i + 1}", "Consents")
    add("Disclosure schedules finalized", "Closing Deliverables")
    add("Legal opinions delivered", "Closing Deliverables")
    add("Officer certificates executed", "Closing Deliverables")
    add("Pay-off letters for existing debt", "Closing Deliverables")

    by_category: dict[str, int] = {}
    for it in items:
        by_category[it["category"]] = by_category.get(it["category"], 0) + 1

    return {
        "items": items,
        "total_items": len(items),
        "by_category": by_category,
        "status_legend": ["Not Started", "In Progress", "Complete", "Blocked"],
    }
