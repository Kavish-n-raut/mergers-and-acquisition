from app.schemas import (
    CFIUSInput,
    ClosingChecklistInput,
    JurisdictionTurnover,
    RegulatoryHorizonInput,
)
from app.services.regulatory import cfius_screening, closing_checklist, regulatory_horizon


# --- Regulatory Horizon Engine ------------------------------------------------

def test_regulatory_filing_threshold_and_critical_path():
    inp = RegulatoryHorizonInput(
        deal_ev=2_000_000_000.0,
        combined_market_share=0.35,
        product_overlaps=4,
        sector="telecom",
        jurisdictions=[
            JurisdictionTurnover(jurisdiction="US_HSR", combined_turnover_usd=500_000_000.0),  # above threshold
            JurisdictionTurnover(jurisdiction="EU_EC", combined_turnover_usd=1_000_000_000.0),  # below EUR5B-equiv
        ],
    )
    result = regulatory_horizon(inp)
    by_jur = {r["jurisdiction"]: r for r in result["jurisdictions"]}
    assert by_jur["US_HSR"]["filing_required"] is True
    assert by_jur["EU_EC"]["filing_required"] is False
    assert result["filings_required"] == 1
    assert result["critical_path"]["jurisdiction"] == "US_HSR"


def test_regulatory_high_share_raises_phase2_probability():
    def prob(share, sector="general", pe=False):
        r = regulatory_horizon(RegulatoryHorizonInput(
            deal_ev=500_000_000.0, combined_market_share=share, product_overlaps=3, sector=sector,
            is_private_equity=pe,
            jurisdictions=[JurisdictionTurnover(jurisdiction="US_HSR", combined_turnover_usd=500_000_000.0)],
        ))
        return r["phase2_probability_model"]

    assert prob(0.6) > prob(0.1)
    # PE acquirers face a lower investigation rate than strategics, all else equal.
    assert prob(0.5, pe=True) < prob(0.5, pe=False)
    # Sensitive sectors raise the probability.
    assert prob(0.3, sector="defense") > prob(0.3, sector="general")


# --- CFIUS screening ----------------------------------------------------------

def test_cfius_not_implicated_for_domestic_deal():
    result = cfius_screening(CFIUSInput(us_business=True, foreign_acquirer=False))
    assert result["risk_tier"] == "Low"
    assert result["blocking"] is False


def test_cfius_mandatory_full_notice_on_multiple_factors():
    result = cfius_screening(CFIUSInput(
        us_business=True, foreign_acquirer=True, acquirer_country_of_concern=True,
        critical_technology=True, critical_infrastructure=True, sensitive_personal_data=True,
    ))
    assert result["risk_tier"] == "Mandatory Full Notice"
    assert result["blocking"] is True
    assert result["estimated_timeline_days"] == 45


def test_cfius_voluntary_on_single_factor():
    result = cfius_screening(CFIUSInput(
        us_business=True, foreign_acquirer=True, sensitive_personal_data=True,
    ))
    assert result["risk_tier"] == "Voluntary Filing Recommended"
    assert result["blocking"] is False


# --- Closing checklist --------------------------------------------------------

def test_closing_checklist_expands_by_inputs():
    result = closing_checklist(ClosingChecklistInput(
        required_jurisdictions=["US_HSR", "EU_EC"],
        shareholder_approval_required=True,
        change_of_control_consents=3,
    ))
    items = [i["item"] for i in result["items"]]
    assert "Regulatory clearance — US_HSR" in items
    assert "Regulatory clearance — EU_EC" in items
    assert "Shareholder approval" in items
    assert sum(1 for i in items if i.startswith("Third-party change-of-control consent")) == 3
    assert all(i["status"] == "Not Started" for i in result["items"])
