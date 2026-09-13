"""E4 — Temporal Risk Mapper (PRD v3.0 §4.4.2 / §5.4).

Scores every diligence finding not only by severity but by *when* it
crystallises relative to the deal timeline. A temporal urgency multiplier is
applied to each finding's base severity score:

    adjusted_score = base_severity_score * (1 + urgency_factor)

so two findings with identical severity can rank very differently depending on
proximity to signing/close. The adjusted, ranked findings are the intended
input to the Module 5 Tactics Engine / Negotiation Playbook.

Deterministic and keyword-driven (MVP mode) — no LLM is required.
"""

from __future__ import annotations

from typing import Any

from app.schemas import RiskFlag

# Base severity score on a 0-10 scale.
_BASE_SEVERITY_SCORE = {"High": 9.0, "Medium": 5.0, "Low": 2.0}

# Temporal tiers and their urgency multipliers (PRD §4.4.2).
_URGENCY_FACTOR = {
    "At Signing": 0.5,
    "At Close": 0.3,
    "Post-Close (Year 1)": 0.1,
    "Post-Close (Year 2+)": 0.05,
    "Indeterminate": 0.0,
}

# Keyword rules, evaluated in priority order. First matching tier wins.
_TIER_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("At Signing", ("standstill", "exclusivity", "no-shop", "no shop", "letter of intent", "loi", "upon execution", "on signing", "upon signing")),
    ("Indeterminate", ("litigation", "pending", "threatened", "investigation", "dispute", "unresolved", "environmental", "remediation", "regulatory proceeding")),
    ("Post-Close (Year 2+)", ("year 2", "year two", "36 month", "36-month", "three-year", "long-term", "survival period")),
    ("Post-Close (Year 1)", ("earn-out", "earnout", "non-compete", "noncompete", "non-solicit", "indemn", "escrow", "deferred", "retention", "post-closing", "post-close", "holdback")),
    ("At Close", ("change of control", "change-of-control", "change in control", "consent", "assignment", "anti-assignment", "termination", "closing", "upon completion", "completion of the transaction")),
]

# Findings that match no keyword default to At Close — most diligence risks
# (consents, change-of-control triggers) fire at transaction completion.
_DEFAULT_TIER = "At Close"


def _classify_tier(risk: RiskFlag) -> tuple[str, str | None]:
    """Return (temporal_tier, matched_keyword) for a single finding."""
    haystack = " ".join([risk.risk_category, risk.quoted_text, risk.ai_explanation]).lower()
    for tier, keywords in _TIER_KEYWORDS:
        for kw in keywords:
            if kw in haystack:
                return tier, kw
    return _DEFAULT_TIER, None


def map_temporal_risks(risks: list[RiskFlag]) -> dict[str, Any]:
    """Classify and time-adjust a list of diligence findings."""
    findings: list[dict[str, Any]] = []
    tier_counts: dict[str, int] = {tier: 0 for tier in _URGENCY_FACTOR}

    for risk in risks:
        tier, matched = _classify_tier(risk)
        base = _BASE_SEVERITY_SCORE[risk.severity]
        urgency = _URGENCY_FACTOR[tier]
        adjusted = base * (1.0 + urgency)
        tier_counts[tier] += 1
        findings.append(
            {
                "risk_category": risk.risk_category,
                "severity": risk.severity,
                "quoted_text": risk.quoted_text,
                "ai_explanation": risk.ai_explanation,
                "temporal_tier": tier,
                "matched_keyword": matched,
                "base_severity_score": round(base, 4),
                "urgency_factor": urgency,
                "adjusted_score": round(adjusted, 4),
            }
        )

    # Rank by time-adjusted score — this is the negotiation-prioritisation order.
    ranked = sorted(findings, key=lambda f: f["adjusted_score"], reverse=True)
    for position, finding in enumerate(ranked, start=1):
        finding["priority_rank"] = position

    return {
        "total_findings": len(findings),
        "tier_counts": tier_counts,
        "findings": ranked,
        "top_priority": ranked[0] if ranked else None,
        "methodology": {
            "base_severity_score": _BASE_SEVERITY_SCORE,
            "urgency_factor": _URGENCY_FACTOR,
            "formula": "adjusted_score = base_severity_score * (1 + urgency_factor)",
            "default_tier": _DEFAULT_TIER,
        },
    }
