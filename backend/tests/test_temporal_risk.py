from app.schemas import RiskFlag
from app.services.temporal_risk import map_temporal_risks


def _risk(category: str, severity: str, text: str, explanation: str = "See extracted clause for detail.") -> RiskFlag:
    return RiskFlag(risk_category=category, severity=severity, quoted_text=text, ai_explanation=explanation)


def test_temporal_tiers_classified_by_keyword():
    risks = [
        _risk("Standstill", "Medium", "The target is subject to a standstill obligation upon execution of the LOI."),
        _risk("Change of Control", "High", "This contract terminates upon a change of control at closing."),
        _risk("Earn-out", "Low", "An earn-out is payable post-closing over the retention period."),
        _risk("Litigation", "High", "There is pending litigation with an unresolved outcome."),
    ]
    result = map_temporal_risks(risks)
    tiers = {f["risk_category"]: f["temporal_tier"] for f in result["findings"]}
    assert tiers["Standstill"] == "At Signing"
    assert tiers["Change of Control"] == "At Close"
    assert tiers["Earn-out"] == "Post-Close (Year 1)"
    assert tiers["Litigation"] == "Indeterminate"


def test_urgency_multiplier_reprioritises_equal_severity():
    # Two High findings: an At-Signing standstill should outrank an Indeterminate litigation.
    risks = [
        _risk("Litigation", "High", "Pending litigation, outcome unresolved."),
        _risk("Standstill", "High", "Standstill triggered upon signing of the letter of intent."),
    ]
    result = map_temporal_risks(risks)
    top = result["top_priority"]
    assert top["risk_category"] == "Standstill"
    # High base = 9.0; At Signing urgency 0.5 => 13.5; Indeterminate => 9.0.
    assert top["adjusted_score"] == 13.5
    assert result["findings"][-1]["adjusted_score"] == 9.0


def test_unmatched_finding_defaults_to_at_close():
    result = map_temporal_risks([_risk("Misc", "Low", "Some generic operational note with no timeline cue.")])
    assert result["findings"][0]["temporal_tier"] == "At Close"


def test_empty_input_is_handled():
    result = map_temporal_risks([])
    assert result["total_findings"] == 0
    assert result["top_priority"] is None
    assert result["findings"] == []
