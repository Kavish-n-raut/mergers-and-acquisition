from app.schemas import NegotiationInput
from app.services.negotiator import calculate_walk_away_price


def test_walk_away_price_bound():
    bound = calculate_walk_away_price(target_ev=10_000_000, annual_synergy=1_000_000, npv_multiple=5.0)
    assert bound == 15_000_000


def test_negotiation_input_schema():
    payload = NegotiationInput(
        target_enterprise_value=10_000_000.0,
        total_annual_synergy=1_200_000.0,
        risk_flags=[],
        recommended_structure="All Cash",
    )
    assert payload.recommended_structure == "All Cash"

