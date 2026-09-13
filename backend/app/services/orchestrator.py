from __future__ import annotations

from app.schemas import (
    DealStructureInput,
    FullAnalysisRequest,
    MasterDiligenceReport,
    NegotiationInput,
    RiskFlag,
    SynergyAssumptions,
)
from app.services.deal_structuring import generate_deal_structure
from app.services.document_scanner import process_and_scan_pdf
from app.services.financial_engine import (
    calculate_dcf,
    calculate_financial_ratios,
    dataframe_to_records,
    load_financial_csv,
)
from app.services.negotiator import generate_negotiation_strategy
from app.services.synergy import calculate_synergies


def run_full_analysis(
    deal_id: str,
    company_a_bytes: bytes,
    company_b_bytes: bytes,
    payload: FullAnalysisRequest,
    legal_pdf_bytes: bytes | None = None,
    legal_pdf_name: str | None = None,
) -> MasterDiligenceReport:
    status_log: list[str] = []
    company_a_financials: dict = {}
    company_b_financials: dict = {}
    valuation: dict | None = None
    synergies: dict = {}
    legal_risks: dict | None = None
    deal_structure: dict | None = None
    negotiation_strategy: dict | None = None

    cleaned_company_a = None
    cleaned_company_b = None
    target_enterprise_value: float | None = None
    risk_flags_for_strategy: list[RiskFlag] = []

    # Stage 1: Financials + Valuation
    try:
        cleaned_company_a, warnings_a = load_financial_csv(company_a_bytes, "Company A")
        cleaned_company_b, warnings_b = load_financial_csv(company_b_bytes, "Company B")
        ratios_a = calculate_financial_ratios(cleaned_company_a)
        ratios_b = calculate_financial_ratios(cleaned_company_b)

        latest_a = cleaned_company_a.sort_values("Year").iloc[-1]
        latest_b = cleaned_company_b.sort_values("Year").iloc[-1]
        latest_a_ebitda = float(
            latest_a["Revenue"] - latest_a["COGS"] - latest_a["Operating_Expenses"]
        )
        latest_b_ebitda = float(
            latest_b["Revenue"] - latest_b["COGS"] - latest_b["Operating_Expenses"]
        )

        company_a_financials = {
            "row_count": int(len(cleaned_company_a)),
            "warnings": warnings_a,
            "latest_year": int(latest_a["Year"]),
            "latest_revenue": float(latest_a["Revenue"]),
            "latest_ebitda": latest_a_ebitda,
            "ratios": dataframe_to_records(ratios_a),
        }
        company_b_financials = {
            "row_count": int(len(cleaned_company_b)),
            "warnings": warnings_b,
            "latest_year": int(latest_b["Year"]),
            "latest_revenue": float(latest_b["Revenue"]),
            "latest_ebitda": latest_b_ebitda,
            "ratios": dataframe_to_records(ratios_b),
        }

        valuation = calculate_dcf(payload.dcf_assumptions)
        raw_ev = valuation.get("enterprise_value") if isinstance(valuation, dict) else None
        if isinstance(raw_ev, (int, float)):
            target_enterprise_value = float(raw_ev)
        status_log.append("Financial + Valuation Engine: Success")
    except Exception as exc:
        status_log.append(
            f"Financial + Valuation Engine: Failed ({exc}). Continuing with partial pipeline."
        )

    # Stage 2: Legal scanner
    if legal_pdf_bytes is None:
        status_log.append("Legal Scanner: Skipped (no PDF uploaded).")
    else:
        try:
            legal_scan = process_and_scan_pdf(legal_pdf_bytes, legal_pdf_name or "uploaded.pdf")
            legal_risks = legal_scan.model_dump()
            risk_flags_for_strategy = legal_scan.risks
            status_log.append("Legal Scanner: Success")
        except Exception as exc:
            legal_risks = None
            risk_flags_for_strategy = []
            status_log.append(f"Legal Scanner: Failed ({exc}). Bypassing legal context.")

    # Stage 3: Synergy
    try:
        if payload.synergy_assumptions is not None:
            synergy_input = payload.synergy_assumptions
        else:
            if cleaned_company_a is None or cleaned_company_b is None:
                raise ValueError("Cannot derive synergy assumptions without clean financials.")
            latest_a = cleaned_company_a.sort_values("Year").iloc[-1]
            latest_b = cleaned_company_b.sort_values("Year").iloc[-1]
            synergy_input = SynergyAssumptions(
                company_a_revenue=float(latest_a["Revenue"]),
                company_b_revenue=float(latest_b["Revenue"]),
                company_b_opex=float(latest_b["Operating_Expenses"]),
                cost_reduction_pct=0.10,
                cross_sell_pct=0.05,
                market_compatibility_score=6,
                tech_stack_compatibility=5,
            )
            status_log.append("Synergy Engine: Derived assumptions from financials.")

        synergies = calculate_synergies(synergy_input)
        status_log.append("Synergy Engine: Success")
    except Exception as exc:
        synergies = {}
        status_log.append(f"Synergy Engine: Failed ({exc}). Continuing.")

    # Stage 4: Structuring
    try:
        if target_enterprise_value is None:
            fallback_ev = company_b_financials.get("latest_revenue")
            if isinstance(fallback_ev, (int, float)):
                target_enterprise_value = float(fallback_ev)
                status_log.append("Deal Structuring: using target revenue as EV fallback.")
        if target_enterprise_value is None:
            raise ValueError("No EV available for structuring.")

        latest_ebitda = company_b_financials.get("latest_ebitda")
        structuring_input = DealStructureInput(
            acquirer_market_cap=payload.acquirer_market_cap,
            valuation_data={
                "enterprise_value": target_enterprise_value,
                "ebitda": float(latest_ebitda) if isinstance(latest_ebitda, (int, float)) else None,
            },
            risk_flags=risk_flags_for_strategy,
        )
        structuring = generate_deal_structure(structuring_input)
        deal_structure = structuring.model_dump()
        status_log.append("Deal Structuring Engine: Success")
    except Exception as exc:
        deal_structure = None
        status_log.append(f"Deal Structuring Engine: Failed ({exc}). Continuing.")

    # Stage 5: Negotiation
    try:
        if deal_structure is None or target_enterprise_value is None:
            raise ValueError("Missing structuring output or target EV.")
        total_synergy = synergies.get("financial_synergies", {}).get("total_annual_synergy", 0.0)
        total_synergy = float(total_synergy) if isinstance(total_synergy, (int, float)) else 0.0

        negotiation = generate_negotiation_strategy(
            NegotiationInput(
                target_enterprise_value=float(target_enterprise_value),
                total_annual_synergy=total_synergy,
                risk_flags=risk_flags_for_strategy,
                recommended_structure=deal_structure["recommended_structure"],
            )
        )
        negotiation_strategy = negotiation.model_dump()
        status_log.append("Negotiation Engine: Success")
    except Exception as exc:
        negotiation_strategy = None
        status_log.append(f"Negotiation Engine: Failed ({exc}). Continuing.")

    return MasterDiligenceReport(
        deal_id=deal_id,
        company_a_financials=company_a_financials,
        company_b_financials=company_b_financials,
        valuation=valuation,
        synergies=synergies,
        legal_risks=legal_risks,
        deal_structure=deal_structure,
        negotiation_strategy=negotiation_strategy,
        status_log=status_log,
    )

