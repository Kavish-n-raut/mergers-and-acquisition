from __future__ import annotations

import io
import math
from typing import Any

import pandas as pd

from app.schemas import DCFAssumptions, DCFDriverAssumptions

REQUIRED_COLUMNS = ("Year", "Revenue", "COGS", "Operating_Expenses")
NUMERIC_COLUMNS = ("Revenue", "COGS", "Operating_Expenses")


class FinancialDataError(ValueError):
    pass


class ValuationError(ValueError):
    pass


def load_financial_csv(file_bytes: bytes, file_label: str) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    try:
        frame = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as exc:
        raise FinancialDataError(f"{file_label}: unable to parse CSV ({exc}).") from exc

    if frame.empty:
        raise FinancialDataError(f"{file_label}: CSV contains no data rows.")

    frame.columns = [str(column).strip() for column in frame.columns]
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise FinancialDataError(
            f"{file_label}: missing required columns {missing_columns}. Expected {list(REQUIRED_COLUMNS)}."
        )

    cleaned = frame.loc[:, list(REQUIRED_COLUMNS)].copy()
    cleaned["Year"] = pd.to_numeric(cleaned["Year"], errors="coerce")
    invalid_years = int(cleaned["Year"].isna().sum())
    if invalid_years > 0:
        warnings.append(f"{file_label}: dropped {invalid_years} rows with invalid Year.")
        cleaned = cleaned.dropna(subset=["Year"])
    if cleaned.empty:
        raise FinancialDataError(f"{file_label}: no valid rows remain after Year normalization.")

    cleaned["Year"] = cleaned["Year"].astype(int)
    cleaned = cleaned.sort_values("Year")

    duplicates = int(cleaned.duplicated(subset=["Year"]).sum())
    if duplicates > 0:
        warnings.append(f"{file_label}: removed {duplicates} duplicate year rows.")
        cleaned = cleaned.drop_duplicates(subset=["Year"], keep="last")

    for column in NUMERIC_COLUMNS:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
        missing = int(cleaned[column].isna().sum())
        if missing > 0:
            cleaned[column] = cleaned[column].interpolate(method="linear", limit_direction="both")
            if cleaned[column].isna().any():
                fallback = cleaned[column].median(skipna=True)
                if pd.isna(fallback):
                    raise FinancialDataError(
                        f"{file_label}: {column} cannot be imputed because all values are missing."
                    )
                cleaned[column] = cleaned[column].fillna(float(fallback))
            warnings.append(f"{file_label}: imputed {missing} values in {column}.")

    return cleaned.reset_index(drop=True), warnings


def calculate_financial_ratios(financials: pd.DataFrame) -> pd.DataFrame:
    result = financials.copy()
    safe_revenue = result["Revenue"].where(result["Revenue"] > 0)
    result["Revenue_Growth"] = result["Revenue"].pct_change()
    result["Gross_Margin"] = (result["Revenue"] - result["COGS"]) / safe_revenue
    result["EBITDA_Margin"] = (
        result["Revenue"] - result["COGS"] - result["Operating_Expenses"]
    ) / safe_revenue
    result = result.replace([float("inf"), float("-inf")], pd.NA)
    return result


def dataframe_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records = frame.to_dict(orient="records")

    def _sanitize(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return None
            return value
        if pd.isna(value):
            return None
        return value

    return [{key: _sanitize(value) for key, value in row.items()} for row in records]


def calculate_dcf(assumptions: DCFAssumptions) -> dict[str, Any]:
    wacc = assumptions.wacc
    growth = assumptions.terminal_growth_rate
    fcfs = assumptions.free_cash_flows

    if growth >= wacc:
        raise ValuationError("terminal_growth_rate must be lower than wacc.")

    discount_base = 1.0 + wacc
    discounted: list[dict[str, float | int]] = []
    pv_sum = 0.0

    for year_index, cash_flow in enumerate(fcfs, start=1):
        factor = discount_base**year_index
        pv = cash_flow / factor
        pv_sum += pv
        discounted.append(
            {
                "year_index": year_index,
                "free_cash_flow": cash_flow,
                "discount_factor": factor,
                "present_value": pv,
            }
        )

    terminal_year_cash_flow = fcfs[-1] * (1.0 + growth)
    terminal_value = terminal_year_cash_flow / (wacc - growth)
    pv_terminal = terminal_value / (discount_base ** len(fcfs))
    enterprise_value = pv_sum + pv_terminal

    return {
        "assumptions": assumptions.model_dump(),
        "discounted_cash_flows": discounted,
        "pv_cash_flow_sum": pv_sum,
        "terminal_year_cash_flow": terminal_year_cash_flow,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal,
        "enterprise_value": enterprise_value,
        "formula_reference": {
            "pv_fcf": "FCF_t / (1 + WACC)^t",
            "terminal_value": "FCF_(n+1) / (WACC - g)",
            "enterprise_value": "Sum(PV(FCF_t)) + PV(Terminal Value)",
        },
    }


def _project_unlevered_fcfs(drivers: DCFDriverAssumptions, growth_rate: float) -> list[dict[str, float]]:
    """Build the year-by-year unlevered free-cash-flow schedule from drivers."""
    rows: list[dict[str, float]] = []
    prev_revenue = drivers.base_revenue
    for year in range(1, drivers.projection_years + 1):
        revenue = drivers.base_revenue * ((1.0 + growth_rate) ** year)
        ebitda = revenue * drivers.ebitda_margin
        da = revenue * drivers.da_pct_of_revenue
        ebit = ebitda - da
        nopat = ebit * (1.0 - drivers.tax_rate)
        capex = revenue * drivers.capex_pct_of_revenue
        delta_revenue = revenue - prev_revenue
        delta_nwc = delta_revenue * drivers.nwc_pct_of_revenue_change
        ufcf = nopat + da - capex - delta_nwc
        rows.append(
            {
                "year": year,
                "revenue": round(revenue, 4),
                "ebitda": round(ebitda, 4),
                "ebit": round(ebit, 4),
                "nopat": round(nopat, 4),
                "d_and_a": round(da, 4),
                "capex": round(capex, 4),
                "change_in_nwc": round(delta_nwc, 4),
                "unlevered_fcf": round(ufcf, 4),
            }
        )
        prev_revenue = revenue
    return rows


def _dcf_case(drivers: DCFDriverAssumptions, growth_rate: float) -> dict[str, Any]:
    schedule = _project_unlevered_fcfs(drivers, growth_rate)
    fcfs = [row["unlevered_fcf"] for row in schedule]
    valuation = calculate_dcf(
        DCFAssumptions(
            wacc=drivers.wacc,
            terminal_growth_rate=drivers.terminal_growth_rate,
            free_cash_flows=fcfs,
        )
    )
    enterprise_value = valuation["enterprise_value"]
    return {
        "growth_rate": round(growth_rate, 6),
        "schedule": schedule,
        "enterprise_value": enterprise_value,
        "equity_value": enterprise_value - drivers.net_debt,
        "terminal_value": valuation["terminal_value"],
        "pv_terminal_value": valuation["pv_terminal_value"],
        "pv_cash_flow_sum": valuation["pv_cash_flow_sum"],
    }


def calculate_dcf_from_drivers(drivers: DCFDriverAssumptions) -> dict[str, Any]:
    """Driver-based DCF with Base/Bull/Bear scenarios (PRD §4.3.2)."""
    base_g = drivers.revenue_growth_rate
    bull_g = base_g * (1.0 + drivers.scenario_delta)
    bear_g = base_g * (1.0 - drivers.scenario_delta)

    base = _dcf_case(drivers, base_g)
    bull = _dcf_case(drivers, bull_g)
    bear = _dcf_case(drivers, bear_g)

    return {
        "assumptions": drivers.model_dump(),
        "base_case": base,
        "bull_case": bull,
        "bear_case": bear,
        "enterprise_value_range": {
            "bear": bear["enterprise_value"],
            "base": base["enterprise_value"],
            "bull": bull["enterprise_value"],
        },
        "equity_value_range": {
            "bear": bear["equity_value"],
            "base": base["equity_value"],
            "bull": bull["equity_value"],
        },
        "formula_reference": {
            "revenue": "base_revenue * (1 + g)^t",
            "unlevered_fcf": "EBIT*(1-tax) + D&A - Capex - dNWC",
            "bull_bear": "growth_rate shocked by +/- scenario_delta (relative)",
        },
    }
