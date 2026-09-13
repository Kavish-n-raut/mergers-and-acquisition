"""Module 8 — The Reality: PMI DNA Score (E6) and Synergy Realization Tracker.

Deterministic, MVP mode:
- PMI DNA Score is a weighted composite of analyst/diligence-derived component
  scores (PRD §4.8.2 weights: 25/20/20/20/15). Live Glassdoor/LinkedIn scraping
  is out of local scope, so components are supplied as inputs.
- The Synergy Realization Tracker is PostgreSQL/SQLite-backed and compares
  Module 3 predictions against monthly realised actuals, flagging categories
  that trail prediction by >15% for two consecutive months (root-cause trigger).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import SynergyRealizationEntry
from app.schemas import PMIDNAInput, SynergyRealizationEntryInput

# PRD §4.8.2 component weights (sum to 1.0).
_PMI_WEIGHTS = {
    "culture_compatibility": 0.25,
    "org_structure_compatibility": 0.20,
    "leadership_profile_match": 0.20,
    "compensation_overlap": 0.20,
    "technology_stack_compatibility": 0.15,
}

# Which component most drives friction in each integration workstream.
_WORKSTREAM_DRIVERS = {
    "IT": "technology_stack_compatibility",
    "Finance": "org_structure_compatibility",
    "HR": "compensation_overlap",
    "Sales": "leadership_profile_match",
    "Operations": "org_structure_compatibility",
    "Culture": "culture_compatibility",
}

# 15% trailing shortfall over 2 consecutive months triggers root-cause review.
_ROOT_CAUSE_THRESHOLD = 0.15


def calculate_pmi_dna_score(inputs: PMIDNAInput) -> dict[str, Any]:
    components = inputs.model_dump()
    composite = round(sum(components[k] * w for k, w in _PMI_WEIGHTS.items()), 2)

    # Friction heatmap: 0 = maximum friction, 100 = seamless. Friction = 100 - score.
    heatmap = []
    for workstream, driver in _WORKSTREAM_DRIVERS.items():
        score = components[driver]
        friction = round(100.0 - score, 2)
        if friction >= 60:
            level = "High"
        elif friction >= 35:
            level = "Medium"
        else:
            level = "Low"
        heatmap.append(
            {
                "workstream": workstream,
                "driver_component": driver,
                "compatibility_score": score,
                "friction_score": friction,
                "friction_level": level,
            }
        )

    if composite >= 70:
        band = "Low friction — integration likely to track plan."
    elif composite >= 50:
        band = "Moderate friction — pre-staff the high-friction workstreams before Day 1."
    else:
        band = "High friction — material integration risk; build retention and change plans pre-close."

    return {
        "composite_score": composite,
        "components": components,
        "weights": _PMI_WEIGHTS,
        "friction_heatmap": heatmap,
        "risk_narrative": band,
        "formula_reference": {
            "composite": "sum(component * weight)",
            "friction": "100 - compatibility_score",
        },
    }


def add_realization_entry(db: Session, deal_id: str, payload: SynergyRealizationEntryInput) -> dict[str, Any]:
    """Insert or update the actuals for a (deal, category, month)."""
    existing = (
        db.query(SynergyRealizationEntry)
        .filter(
            SynergyRealizationEntry.deal_id == deal_id,
            SynergyRealizationEntry.category == payload.category,
            SynergyRealizationEntry.period_month == payload.period_month,
        )
        .one_or_none()
    )
    if existing is None:
        entry = SynergyRealizationEntry(
            deal_id=deal_id,
            category=payload.category,
            period_month=payload.period_month,
            predicted_amount=payload.predicted_amount,
            realized_amount=payload.realized_amount,
            note=payload.note,
        )
        db.add(entry)
    else:
        existing.predicted_amount = payload.predicted_amount
        existing.realized_amount = payload.realized_amount
        existing.note = payload.note
        entry = existing
    db.commit()
    db.refresh(entry)
    return {
        "id": entry.id,
        "deal_id": entry.deal_id,
        "category": entry.category,
        "period_month": entry.period_month,
        "predicted_amount": entry.predicted_amount,
        "realized_amount": entry.realized_amount,
        "note": entry.note,
    }


def synergy_realization_dashboard(db: Session, deal_id: str) -> dict[str, Any]:
    """Aggregate realised-vs-predicted synergies by category with variance and alerts."""
    rows = (
        db.query(SynergyRealizationEntry)
        .filter(SynergyRealizationEntry.deal_id == deal_id)
        .order_by(SynergyRealizationEntry.category, SynergyRealizationEntry.period_month)
        .all()
    )

    by_category: dict[str, list[SynergyRealizationEntry]] = {}
    for row in rows:
        by_category.setdefault(row.category, []).append(row)

    categories: list[dict[str, Any]] = []
    total_predicted = 0.0
    total_realized = 0.0

    for category, entries in by_category.items():
        cum_predicted = sum(e.predicted_amount for e in entries)
        cum_realized = sum(e.realized_amount for e in entries)
        total_predicted += cum_predicted
        total_realized += cum_realized

        latest = entries[-1]
        run_rate_annualized = round(latest.realized_amount * 12.0, 2)
        variance_abs = round(cum_realized - cum_predicted, 2)
        variance_pct = round((cum_realized - cum_predicted) / cum_predicted, 4) if cum_predicted > 0 else None

        # Root-cause trigger: realised trails predicted by > threshold for 2 consecutive months.
        consecutive_shortfall = 0
        root_cause_flag = False
        for e in entries:
            if e.predicted_amount > 0 and (e.predicted_amount - e.realized_amount) / e.predicted_amount > _ROOT_CAUSE_THRESHOLD:
                consecutive_shortfall += 1
                if consecutive_shortfall >= 2:
                    root_cause_flag = True
            else:
                consecutive_shortfall = 0

        categories.append(
            {
                "category": category,
                "months_tracked": len(entries),
                "cumulative_predicted": round(cum_predicted, 2),
                "cumulative_realized": round(cum_realized, 2),
                "run_rate_annualized": run_rate_annualized,
                "variance_abs": variance_abs,
                "variance_pct": variance_pct,
                "root_cause_review_required": root_cause_flag,
            }
        )

    overall_variance_pct = (
        round((total_realized - total_predicted) / total_predicted, 4) if total_predicted > 0 else None
    )

    return {
        "deal_id": deal_id,
        "categories": categories,
        "totals": {
            "cumulative_predicted": round(total_predicted, 2),
            "cumulative_realized": round(total_realized, 2),
            "variance_abs": round(total_realized - total_predicted, 2),
            "variance_pct": overall_variance_pct,
            "realization_rate": round(total_realized / total_predicted, 4) if total_predicted > 0 else None,
        },
        "root_cause_threshold": _ROOT_CAUSE_THRESHOLD,
    }
