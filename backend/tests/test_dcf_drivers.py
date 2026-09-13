import pytest

from app.schemas import DCFDriverAssumptions
from app.services.financial_engine import calculate_dcf_from_drivers


def _drivers(**overrides):
    base = dict(
        base_revenue=1000.0,
        revenue_growth_rate=0.10,
        projection_years=5,
        ebitda_margin=0.25,
        wacc=0.10,
        terminal_growth_rate=0.025,
        net_debt=200.0,
    )
    base.update(overrides)
    return DCFDriverAssumptions(**base)


def test_driver_dcf_scenarios_are_ordered():
    result = calculate_dcf_from_drivers(_drivers())
    ev = result["enterprise_value_range"]
    # Higher growth (bull) must produce a higher EV than base, base higher than bear.
    assert ev["bull"] > ev["base"] > ev["bear"]


def test_driver_dcf_bridges_to_equity_with_net_debt():
    result = calculate_dcf_from_drivers(_drivers(net_debt=200.0))
    base = result["base_case"]
    assert base["equity_value"] == pytest.approx(base["enterprise_value"] - 200.0)


def test_driver_dcf_schedule_length_and_growth():
    result = calculate_dcf_from_drivers(_drivers(projection_years=7, revenue_growth_rate=0.10))
    schedule = result["base_case"]["schedule"]
    assert len(schedule) == 7
    # Year-1 revenue = 1000 * 1.10 = 1100.
    assert schedule[0]["revenue"] == pytest.approx(1100.0)
    # Revenue grows each year.
    revenues = [row["revenue"] for row in schedule]
    assert revenues == sorted(revenues)


def test_driver_dcf_produces_positive_enterprise_value():
    result = calculate_dcf_from_drivers(_drivers())
    assert result["base_case"]["enterprise_value"] > 0
