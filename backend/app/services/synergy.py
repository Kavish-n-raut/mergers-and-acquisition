from __future__ import annotations

from typing import Any

from app.schemas import SynergyAssumptions


class SynergyCalculationError(ValueError):
    pass


def calculate_synergies(assumptions: SynergyAssumptions) -> dict[str, Any]:
    annual_cost_savings = assumptions.company_b_opex * assumptions.cost_reduction_pct
    combined_base_revenue = assumptions.company_a_revenue + assumptions.company_b_revenue
    annual_revenue_bump = combined_base_revenue * assumptions.cross_sell_pct
    total_annual_synergy = annual_cost_savings + annual_revenue_bump

    weighted_market_score = (assumptions.market_compatibility_score / 10.0) * 0.60
    weighted_tech_score = (assumptions.tech_stack_compatibility / 10.0) * 0.40
    fit_percentage = (weighted_market_score + weighted_tech_score) * 100.0

    if not 0.0 <= fit_percentage <= 100.0:
        raise SynergyCalculationError("Computed fit score is outside expected bounds.")

    if fit_percentage >= 80.0:
        recommendation = (
            "High strategic fit - highly complementary products and cost elimination potential."
        )
    elif fit_percentage >= 60.0:
        recommendation = "Moderate strategic fit - integration risks exist, proceed with diligence."
    else:
        recommendation = "Low strategic fit - high integration risk and limited overlap."

    return {
        "assumptions": assumptions.model_dump(),
        "financial_synergies": {
            "annual_cost_savings": round(annual_cost_savings, 2),
            "annual_revenue_bump": round(annual_revenue_bump, 2),
            "total_annual_synergy": round(total_annual_synergy, 2),
        },
        "strategic_fit": {
            "fit_score_percentage": round(fit_percentage, 2),
            "recommendation": recommendation,
            "component_weights": {
                "market_compatibility_weight": 0.60,
                "tech_stack_compatibility_weight": 0.40,
            },
        },
    }

