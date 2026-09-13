from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Float, JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DealRecord(Base):
    __tablename__ = "deal_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_name: Mapped[str] = mapped_column(String(255), default="Unnamed Deal")
    stage: Mapped[str] = mapped_column(String(64), default="m1_hunt")
    status: Mapped[str] = mapped_column(String(32), default="in_progress")

    company_a_financials: Mapped[dict] = mapped_column(JSON, default=dict)
    company_b_financials: Mapped[dict] = mapped_column(JSON, default=dict)
    valuation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    synergies: Mapped[dict] = mapped_column(JSON, default=dict)
    legal_risks: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    deal_structure: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    negotiation_strategy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status_log: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id: Mapped[str] = mapped_column(String(36), index=True)
    actor_role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(128))
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WarRoomMessage(Base):
    __tablename__ = "war_room_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[str] = mapped_column(String(36), index=True)
    sender_role: Mapped[str] = mapped_column(String(32))
    sender_name: Mapped[str] = mapped_column(String(120), default="anonymous")
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DealModuleOutput(Base):
    """Persisted output of a module/engine for a deal, keyed by module name.

    Lets M1/M2/M6/M7 results (stateless compute) stick to a deal and flow between
    modules. One row per (deal_id, module_key); upserted on save.
    """

    __tablename__ = "deal_module_outputs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id: Mapped[str] = mapped_column(String(36), index=True)
    module_key: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SynergyRealizationEntry(Base):
    """Module 8 — monthly realised-vs-predicted synergy actuals, by category."""

    __tablename__ = "synergy_realization_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id: Mapped[str] = mapped_column(String(36), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    period_month: Mapped[int] = mapped_column(Integer, index=True)
    predicted_amount: Mapped[float] = mapped_column(Float, default=0.0)
    realized_amount: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class HistoricalTransaction(Base):
    __tablename__ = "historical_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    buyer_name: Mapped[str] = mapped_column(String(255), index=True)
    target_name: Mapped[str] = mapped_column(String(255), index=True)
    announcement_date: Mapped[str] = mapped_column(String(32), default="")
    close_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    deal_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    enterprise_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector: Mapped[str] = mapped_column(String(160), default="Unknown", index=True)
    buyer_country: Mapped[str] = mapped_column(String(120), default="Unknown")
    target_country: Mapped[str] = mapped_column(String(120), default="Unknown", index=True)
    payment_type: Mapped[str] = mapped_column(String(80), default="Unknown")
    premium_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    deal_status: Mapped[str] = mapped_column(String(80), default="announced", index=True)
    source_url: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(80), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
