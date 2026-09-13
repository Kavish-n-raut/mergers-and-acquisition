import math

import pandas as pd

from app.schemas import DCFAssumptions
from app.services.financial_engine import (
    calculate_dcf,
    calculate_financial_ratios,
    dataframe_to_records,
)


def test_calculate_dcf_returns_positive_enterprise_value():
    assumptions = DCFAssumptions(
        wacc=0.1,
        terminal_growth_rate=0.02,
        free_cash_flows=[100.0, 120.0, 140.0, 160.0, 180.0],
    )
    result = calculate_dcf(assumptions)
    assert result["enterprise_value"] > 0
    assert len(result["discounted_cash_flows"]) == 5


def test_dataframe_to_records_sanitizes_nan_and_inf():
    frame = pd.DataFrame(
        [
            {"Year": 2024, "Revenue": 100.0, "COGS": 40.0, "Operating_Expenses": 30.0},
            {"Year": 2025, "Revenue": 120.0, "COGS": 50.0, "Operating_Expenses": 35.0},
        ]
    )
    ratios = calculate_financial_ratios(frame)
    records = dataframe_to_records(ratios)

    assert records[0]["Revenue_Growth"] is None
    assert records[1]["Revenue_Growth"] is not None
    assert not any(
        isinstance(value, float) and (math.isnan(value) or math.isinf(value))
        for row in records
        for value in row.values()
    )
