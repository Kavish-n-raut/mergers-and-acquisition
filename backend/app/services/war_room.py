from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import WarRoomMessage
from app.schemas import WarRoomMessageIn, WarRoomMessageOut


def save_war_room_message(
    db: Session,
    deal_id: str,
    sender_role: str,
    payload: WarRoomMessageIn,
) -> WarRoomMessageOut:
    row = WarRoomMessage(
        deal_id=deal_id,
        sender_role=sender_role,
        sender_name=payload.sender_name,
        content=payload.content,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return WarRoomMessageOut(
        deal_id=row.deal_id,
        sender_role=row.sender_role,
        sender_name=row.sender_name,
        content=row.content,
        created_at=row.created_at.replace(tzinfo=timezone.utc).isoformat(),
    )


def get_war_room_messages(db: Session, deal_id: str, limit: int = 100) -> list[WarRoomMessageOut]:
    rows = (
        db.query(WarRoomMessage)
        .filter(WarRoomMessage.deal_id == deal_id)
        .order_by(WarRoomMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [
        WarRoomMessageOut(
            deal_id=r.deal_id,
            sender_role=r.sender_role,
            sender_name=r.sender_name,
            content=r.content,
            created_at=r.created_at.replace(tzinfo=timezone.utc).isoformat(),
        )
        for r in rows
    ]

