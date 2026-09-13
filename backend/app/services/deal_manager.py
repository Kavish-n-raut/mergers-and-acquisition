from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import DealRecord
from app.schemas import DealCreateRequest, DealStageLiteral, DealStageUpdateRequest

DEAL_STAGE_ORDER: list[DealStageLiteral] = [
    "m1_hunt",
    "m2_approach",
    "m3_handshake",
    "m4_deep_dive",
    "m5_war_room",
    "m6_check",
    "m7_close",
    "m8_reality",
]


class DealLifecycleError(ValueError):
    pass


def create_deal(db: Session, payload: DealCreateRequest) -> DealRecord:
    deal = DealRecord(
        deal_name=payload.deal_name,
        stage="m1_hunt",
        status="in_progress",
        status_log=["Deal created at m1_hunt"],
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def _stage_index(stage: str) -> int:
    if stage not in DEAL_STAGE_ORDER:
        raise DealLifecycleError(f"Unknown stage: {stage}")
    return DEAL_STAGE_ORDER.index(stage)  # type: ignore[arg-type]


def update_deal_stage(db: Session, deal: DealRecord, payload: DealStageUpdateRequest) -> DealRecord:
    current_idx = _stage_index(deal.stage)
    target_idx = _stage_index(payload.stage)

    if target_idx < current_idx:
        raise DealLifecycleError(
            f"Invalid transition from {deal.stage} to {payload.stage}. "
            "Backward stage transitions are not allowed."
        )

    if target_idx > current_idx + 1:
        raise DealLifecycleError(
            f"Invalid transition from {deal.stage} to {payload.stage}. "
            "Only sequential next-stage transitions are allowed."
        )

    deal.stage = payload.stage
    deal.status = payload.status
    new_log = list(deal.status_log or [])
    new_log.append(
        f"{datetime.now(timezone.utc).isoformat()} stage_update -> {payload.stage} ({payload.status})"
    )
    deal.status_log = new_log
    db.commit()
    db.refresh(deal)
    return deal
