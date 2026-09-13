import pytest

from app.schemas import LBOInput
from app.services.deal_financing import LBOFinancingError, _irr, calculate_lbo


def test_irr_matches_known_simple_case():
    # -100 now, +121 in two years => IRR = 10%.
    irr = _irr([-100.0, 0.0, 121.0])
    assert irr is not None
    assert abs(irr - 0.10) < 1e-4


def test_irr_returns_none_without_sign_change():
    assert _irr([-100.0, -10.0, -5.0]) is None


def test_calculate_lbo_base_case_structure_and_returns():
    inputs = LBOInput(
        enterprise_value=500.0,
        ebitda=100.0,
        senior_leverage_x=3.0,
        mezzanine_leverage_x=1.0,
        ebitda_growth_rate=0.05,
        projection_years=5,
    )
    result = calculate_lbo(inputs)

    # Entry multiple = 500 / 100 = 5.0x
    assert result["entry_multiple"] == pytest.approx(5.0)
    # Exit defaults to entry multiple when not supplied.
    assert result["exit_multiple"] == pytest.approx(5.0)

    su = result["sources_and_uses"]
    # Sources must reconcile to uses: senior + mezz + rollover + equity == uses_total.
    reconciled = (
        su["sources_senior_debt"]
        + su["sources_mezzanine_debt"]
        + su["sources_seller_rollover"]
        + su["sources_sponsor_equity"]
    )
    assert reconciled == pytest.approx(su["uses_total"], rel=1e-6)

    # Debt is paid down over the hold: ending debt < starting debt.
    assert result["exit"]["exit_net_debt"] < result["total_debt"]

    # Schedule has one row per projection year.
    assert len(result["debt_schedule"]) == 5

    # Sensitivity grid is 5x5.
    matrix = result["sensitivity"]["equity_irr_matrix"]
    assert len(matrix) == 5 and all(len(row) == 5 for row in matrix)

    # A growing, deleveraging LBO should produce a positive IRR and MOIC > 1.
    assert result["returns"]["equity_irr"] is not None
    assert result["returns"]["moic"] > 1.0


def test_calculate_lbo_rejects_over_leverage_with_zero_equity():
    # Debt (4x + 2x = 6x * 100 = 600) exceeds uses (~510) => non-positive equity.
    inputs = LBOInput(
        enterprise_value=500.0,
        ebitda=100.0,
        senior_leverage_x=4.0,
        mezzanine_leverage_x=2.0,
    )
    with pytest.raises(LBOFinancingError):
        calculate_lbo(inputs)


def test_calculate_lbo_flags_covenant_breach_on_thin_coverage():
    # High leverage + high rates + no growth => thin DSCR, should breach a strict covenant.
    inputs = LBOInput(
        enterprise_value=800.0,
        ebitda=100.0,
        senior_leverage_x=4.0,
        mezzanine_leverage_x=1.0,
        senior_rate=0.10,
        mezzanine_rate=0.15,
        ebitda_growth_rate=0.0,
        min_dscr_covenant=3.0,
    )
    result = calculate_lbo(inputs)
    assert result["covenants"]["covenant_breach"] is True
    assert any("DSCR" in w for w in result["warnings"])
