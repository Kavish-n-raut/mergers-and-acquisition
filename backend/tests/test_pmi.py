from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.schemas import PMIDNAInput, SynergyRealizationEntryInput
from app.services.pmi import (
    add_realization_entry,
    calculate_pmi_dna_score,
    synergy_realization_dashboard,
)


def _make_db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)()


def test_pmi_dna_score_weighted_composite():
    # All components 80 => composite 80 (weights sum to 1.0).
    result = calculate_pmi_dna_score(
        PMIDNAInput(
            culture_compatibility=80.0,
            org_structure_compatibility=80.0,
            leadership_profile_match=80.0,
            compensation_overlap=80.0,
            technology_stack_compatibility=80.0,
        )
    )
    assert result["composite_score"] == 80.0
    assert len(result["friction_heatmap"]) == 6


def test_pmi_dna_low_tech_score_drives_high_it_friction():
    result = calculate_pmi_dna_score(
        PMIDNAInput(
            culture_compatibility=90.0,
            org_structure_compatibility=90.0,
            leadership_profile_match=90.0,
            compensation_overlap=90.0,
            technology_stack_compatibility=20.0,
        )
    )
    it = next(row for row in result["friction_heatmap"] if row["workstream"] == "IT")
    assert it["friction_level"] == "High"
    assert it["friction_score"] == 80.0


def test_synergy_realization_dashboard_variance_and_rollup():
    db = _make_db()
    add_realization_entry(db, "deal1", SynergyRealizationEntryInput(category="Headcount", period_month=1, predicted_amount=100.0, realized_amount=90.0))
    add_realization_entry(db, "deal1", SynergyRealizationEntryInput(category="Headcount", period_month=2, predicted_amount=100.0, realized_amount=110.0))

    dash = synergy_realization_dashboard(db, "deal1")
    cat = dash["categories"][0]
    assert cat["cumulative_predicted"] == 200.0
    assert cat["cumulative_realized"] == 200.0
    assert cat["variance_abs"] == 0.0
    assert dash["totals"]["realization_rate"] == 1.0


def test_synergy_realization_upsert_and_root_cause_flag():
    db = _make_db()
    # Two consecutive months trailing prediction by > 15% => root-cause flag.
    add_realization_entry(db, "deal2", SynergyRealizationEntryInput(category="Cross-Sell", period_month=1, predicted_amount=100.0, realized_amount=50.0))
    add_realization_entry(db, "deal2", SynergyRealizationEntryInput(category="Cross-Sell", period_month=2, predicted_amount=100.0, realized_amount=60.0))
    # Upsert month 1 (should not create a duplicate row).
    add_realization_entry(db, "deal2", SynergyRealizationEntryInput(category="Cross-Sell", period_month=1, predicted_amount=100.0, realized_amount=55.0))

    dash = synergy_realization_dashboard(db, "deal2")
    cat = dash["categories"][0]
    assert cat["months_tracked"] == 2
    assert cat["root_cause_review_required"] is True
