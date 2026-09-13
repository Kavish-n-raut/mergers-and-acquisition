from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import DealRecord
from app.schemas import DealCreateRequest, DealStageUpdateRequest
from app.services.deal_manager import DealLifecycleError, create_deal, update_deal_stage


def _make_db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)()


def test_create_deal_default_stage():
    db = _make_db()
    deal = create_deal(db, DealCreateRequest(deal_name="Project Nova"))
    assert deal.stage == "m1_hunt"
    assert deal.status == "in_progress"


def test_stage_transition_sequential_only():
    db = _make_db()
    deal = create_deal(db, DealCreateRequest(deal_name="Project Atlas"))
    updated = update_deal_stage(
        db,
        deal,
        DealStageUpdateRequest(stage="m2_approach", status="in_progress"),
    )
    assert updated.stage == "m2_approach"

    record = db.get(DealRecord, updated.id)
    assert record is not None

    try:
        update_deal_stage(
            db,
            record,
            DealStageUpdateRequest(stage="m5_war_room", status="in_progress"),
        )
        assert False, "Expected DealLifecycleError for skipped stages"
    except DealLifecycleError:
        assert True


def test_stage_transition_disallows_backward_moves():
    db = _make_db()
    deal = create_deal(db, DealCreateRequest(deal_name="Project Orion"))
    step_2 = update_deal_stage(
        db,
        deal,
        DealStageUpdateRequest(stage="m2_approach", status="in_progress"),
    )
    step_3 = update_deal_stage(
        db,
        step_2,
        DealStageUpdateRequest(stage="m3_handshake", status="in_progress"),
    )

    try:
        update_deal_stage(
            db,
            step_3,
            DealStageUpdateRequest(stage="m2_approach", status="in_progress"),
        )
        assert False, "Expected DealLifecycleError for backward transition"
    except DealLifecycleError:
        assert True
