"""Module 6 — The Check: leveraged-acquisition finance (LBO) engine.

Deterministic financing model per PRD v3.0 §4.6. Computes the capital stack,
a year-by-year debt-paydown / covenant schedule, exit equity value, levered
equity IRR and MOIC, plus a 5x5 entry/exit multiple IRR sensitivity grid.

MVP mode: no live debt-market feed (Debt Market Pulse). Leverage levels and
rates are explicit analyst assumptions. Math is deterministic; no LLM is used
for any number (consistent with the platform's "no LLM math authority" rule).
"""

from __future__ import annotations

from typing import Any

from app.schemas import LBOInput


class LBOFinancingError(ValueError):
    pass


def _irr(cash_flows: list[float], *, lower: float = -0.9999, upper: float = 10.0, tol: float = 1e-7) -> float | None:
    """Solve for the internal rate of return via bisection.

    Returns None when the cash-flow vector has no sign change (no real IRR) or
    the root cannot be bracketed in the search range.
    """

    def npv(rate: float) -> float:
        return sum(cf / ((1.0 + rate) ** t) for t, cf in enumerate(cash_flows))

    # An IRR requires at least one sign change in the cash-flow stream.
    signs = {cf > 0 for cf in cash_flows if cf != 0}
    if len(signs) < 2:
        return None

    f_lower = npv(lower)
    f_upper = npv(upper)
    if f_lower == 0.0:
        return lower
    if f_upper == 0.0:
        return upper
    if (f_lower > 0) == (f_upper > 0):
        # Root not bracketed in the search window.
        return None

    for _ in range(200):
        mid = (lower + upper) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) < tol:
            return mid
        if (f_mid > 0) == (f_lower > 0):
            lower = mid
            f_lower = f_mid
        else:
            upper = mid
    return (lower + upper) / 2.0


def _project_schedule(
    *,
    ebitda: float,
    beginning_senior: float,
    beginning_mezz: float,
    inputs: LBOInput,
) -> tuple[list[dict[str, Any]], float, float, float | None]:
    """Run the annual EBITDA / interest / tax / capex / cash-sweep schedule.

    Returns (rows, ending_senior, ending_mezz, min_dscr).
    """
    senior = beginning_senior
    mezz = beginning_mezz
    rows: list[dict[str, Any]] = []
    min_dscr: float | None = None
    # Scheduled (mandatory) senior amortisation is a fixed fraction of the ORIGINAL
    # senior principal each year. DSCR is measured against this scheduled service,
    # not the discretionary excess-cash sweep, so the covenant test is meaningful.
    mandatory_amort_annual = beginning_senior * inputs.mandatory_amortization_pct

    for year in range(1, inputs.projection_years + 1):
        ebitda_t = ebitda * ((1.0 + inputs.ebitda_growth_rate) ** year)
        da_t = ebitda_t * inputs.da_pct_ebitda
        capex_t = ebitda_t * inputs.capex_pct_ebitda

        cash_interest = senior * inputs.senior_rate + mezz * inputs.mezzanine_rate
        ebit_t = ebitda_t - da_t
        ebt_t = ebit_t - cash_interest
        taxes_t = max(0.0, ebt_t) * inputs.tax_rate

        cfads = ebitda_t - capex_t - taxes_t

        # DSCR: coverage of scheduled debt service (interest + mandatory amortisation).
        scheduled_amort = min(senior, mandatory_amort_annual)
        scheduled_service = cash_interest + scheduled_amort
        dscr = (cfads / scheduled_service) if scheduled_service > 0 else None
        if dscr is not None:
            min_dscr = dscr if min_dscr is None else min(min_dscr, dscr)

        # Actual paydown: 100% excess-cash sweep (mandatory amort is a subset of it),
        # applied senior first, then mezzanine.
        sweep = max(0.0, cfads - cash_interest)
        senior_repaid = min(senior, sweep)
        mezz_repaid = min(mezz, sweep - senior_repaid)
        principal_repaid = senior_repaid + mezz_repaid
        senior -= senior_repaid
        mezz -= mezz_repaid

        ending_debt = senior + mezz
        rows.append(
            {
                "year": year,
                "ebitda": round(ebitda_t, 4),
                "d_and_a": round(da_t, 4),
                "cash_interest": round(cash_interest, 4),
                "taxes": round(taxes_t, 4),
                "capex": round(capex_t, 4),
                "cfads": round(cfads, 4),
                "principal_repaid": round(principal_repaid, 4),
                "ending_senior_debt": round(senior, 4),
                "ending_mezzanine_debt": round(mezz, 4),
                "ending_total_debt": round(ending_debt, 4),
                "net_leverage_x": round(ending_debt / ebitda_t, 4) if ebitda_t > 0 else None,
                "dscr": round(dscr, 4) if dscr is not None else None,
            }
        )

    return rows, senior, mezz, min_dscr


def _case_irr(*, entry_multiple: float, exit_multiple: float, inputs: LBOInput) -> float | None:
    """Recompute equity IRR for a single (entry, exit) multiple pair (sensitivity)."""
    entry_ev = entry_multiple * inputs.ebitda
    senior_debt = inputs.senior_leverage_x * inputs.ebitda
    mezz_debt = inputs.mezzanine_leverage_x * inputs.ebitda
    total_debt = senior_debt + mezz_debt
    uses = entry_ev * (1.0 + inputs.transaction_fees_pct)
    equity = uses - total_debt - inputs.seller_rollover
    if equity <= 0:
        return None

    _, end_senior, end_mezz, _ = _project_schedule(
        ebitda=inputs.ebitda,
        beginning_senior=senior_debt,
        beginning_mezz=mezz_debt,
        inputs=inputs,
    )
    exit_ebitda = inputs.ebitda * ((1.0 + inputs.ebitda_growth_rate) ** inputs.projection_years)
    exit_equity = exit_multiple * exit_ebitda - (end_senior + end_mezz)

    flows = [-equity] + [0.0] * (inputs.projection_years - 1) + [exit_equity]
    return _irr(flows)


def _sensitivity_grid(*, entry_multiple: float, exit_multiple: float, inputs: LBOInput) -> dict[str, Any]:
    """Build a 5x5 equity-IRR grid across entry and exit EV/EBITDA multiples."""
    steps = [-1.0, -0.5, 0.0, 0.5, 1.0]
    entry_axis = [round(max(0.5, entry_multiple + s), 2) for s in steps]
    exit_axis = [round(max(0.5, exit_multiple + s), 2) for s in steps]

    matrix: list[list[float | None]] = []
    for ex in exit_axis:
        row: list[float | None] = []
        for en in entry_axis:
            irr = _case_irr(entry_multiple=en, exit_multiple=ex, inputs=inputs)
            row.append(round(irr, 4) if irr is not None else None)
        matrix.append(row)

    return {
        "entry_multiples": entry_axis,
        "exit_multiples": exit_axis,
        "equity_irr_matrix": matrix,
        "hurdle_irr": inputs.board_hurdle_irr,
        "axis_note": "Rows = exit EV/EBITDA, columns = entry EV/EBITDA. Cells below hurdle_irr fail the Board return test.",
    }


def calculate_lbo(inputs: LBOInput) -> dict[str, Any]:
    """Full deterministic LBO / acquisition-finance analysis (PRD §4.6)."""
    entry_multiple = inputs.enterprise_value / inputs.ebitda
    exit_multiple = inputs.exit_multiple if inputs.exit_multiple is not None else entry_multiple

    senior_debt = inputs.senior_leverage_x * inputs.ebitda
    mezz_debt = inputs.mezzanine_leverage_x * inputs.ebitda
    total_debt = senior_debt + mezz_debt

    fees = inputs.enterprise_value * inputs.transaction_fees_pct
    uses = inputs.enterprise_value + fees
    equity_contribution = uses - total_debt - inputs.seller_rollover

    warnings: list[str] = []
    debt_capacity_warning = total_debt > inputs.enterprise_value
    if debt_capacity_warning:
        warnings.append(
            "Total debt raised exceeds the enterprise value — leverage assumptions are not achievable for this purchase price."
        )
    if equity_contribution <= 0:
        raise LBOFinancingError(
            "Computed sponsor equity is zero or negative: debt + seller rollover already exceed the uses of funds. "
            "Reduce leverage multiples, rollover, or increase the purchase price."
        )

    schedule, end_senior, end_mezz, min_dscr = _project_schedule(
        ebitda=inputs.ebitda,
        beginning_senior=senior_debt,
        beginning_mezz=mezz_debt,
        inputs=inputs,
    )
    exit_ending_debt = end_senior + end_mezz

    exit_ebitda = inputs.ebitda * ((1.0 + inputs.ebitda_growth_rate) ** inputs.projection_years)
    exit_ev = exit_multiple * exit_ebitda
    exit_equity_value = exit_ev - exit_ending_debt

    equity_flows = [-equity_contribution] + [0.0] * (inputs.projection_years - 1) + [exit_equity_value]
    equity_irr = _irr(equity_flows)
    moic = exit_equity_value / equity_contribution if equity_contribution > 0 else None

    meets_hurdle = equity_irr is not None and equity_irr >= inputs.board_hurdle_irr
    covenant_breach = min_dscr is not None and min_dscr < inputs.min_dscr_covenant
    if covenant_breach:
        warnings.append(
            f"Minimum DSCR of {min_dscr:.2f}x breaches the {inputs.min_dscr_covenant:.2f}x covenant threshold."
        )

    capital_stack = [
        {
            "tranche": "Senior Secured Debt",
            "amount": round(senior_debt, 4),
            "pct_of_capital": round(senior_debt / uses, 4) if uses > 0 else 0.0,
            "rate": inputs.senior_rate,
            "leverage_x": inputs.senior_leverage_x,
        },
        {
            "tranche": "Mezzanine / Unitranche",
            "amount": round(mezz_debt, 4),
            "pct_of_capital": round(mezz_debt / uses, 4) if uses > 0 else 0.0,
            "rate": inputs.mezzanine_rate,
            "leverage_x": inputs.mezzanine_leverage_x,
        },
        {
            "tranche": "Seller Rollover Equity",
            "amount": round(inputs.seller_rollover, 4),
            "pct_of_capital": round(inputs.seller_rollover / uses, 4) if uses > 0 else 0.0,
            "rate": 0.0,
            "leverage_x": round(inputs.seller_rollover / inputs.ebitda, 4) if inputs.ebitda > 0 else 0.0,
        },
        {
            "tranche": "Sponsor Common Equity",
            "amount": round(equity_contribution, 4),
            "pct_of_capital": round(equity_contribution / uses, 4) if uses > 0 else 0.0,
            "rate": 0.0,
            "leverage_x": 0.0,
        },
    ]

    return {
        "inputs": inputs.model_dump(),
        "entry_multiple": round(entry_multiple, 4),
        "exit_multiple": round(exit_multiple, 4),
        "sources_and_uses": {
            "uses_enterprise_value": round(inputs.enterprise_value, 4),
            "uses_transaction_fees": round(fees, 4),
            "uses_total": round(uses, 4),
            "sources_senior_debt": round(senior_debt, 4),
            "sources_mezzanine_debt": round(mezz_debt, 4),
            "sources_seller_rollover": round(inputs.seller_rollover, 4),
            "sources_sponsor_equity": round(equity_contribution, 4),
            "entry_leverage_x": round(total_debt / inputs.ebitda, 4) if inputs.ebitda > 0 else None,
        },
        "capital_stack": capital_stack,
        "total_debt": round(total_debt, 4),
        "equity_contribution": round(equity_contribution, 4),
        "debt_schedule": schedule,
        "exit": {
            "exit_year": inputs.projection_years,
            "exit_ebitda": round(exit_ebitda, 4),
            "exit_enterprise_value": round(exit_ev, 4),
            "exit_net_debt": round(exit_ending_debt, 4),
            "exit_equity_value": round(exit_equity_value, 4),
        },
        "returns": {
            "equity_irr": round(equity_irr, 4) if equity_irr is not None else None,
            "moic": round(moic, 4) if moic is not None else None,
            "board_hurdle_irr": inputs.board_hurdle_irr,
            "meets_hurdle": meets_hurdle,
        },
        "covenants": {
            "min_dscr": round(min_dscr, 4) if min_dscr is not None else None,
            "min_dscr_covenant": inputs.min_dscr_covenant,
            "covenant_breach": covenant_breach,
        },
        "sensitivity": _sensitivity_grid(entry_multiple=entry_multiple, exit_multiple=exit_multiple, inputs=inputs),
        "debt_capacity_warning": debt_capacity_warning,
        "warnings": warnings,
        "formula_reference": {
            "sponsor_equity": "EV * (1 + fees%) - senior_debt - mezz_debt - seller_rollover",
            "cash_sweep": "principal_repaid = min(debt, EBITDA - capex - taxes - cash_interest)",
            "exit_equity": "exit_multiple * exit_EBITDA - ending_net_debt",
            "equity_irr": "IRR([-equity, 0, ..., exit_equity])",
            "moic": "exit_equity_value / sponsor_equity",
        },
    }
