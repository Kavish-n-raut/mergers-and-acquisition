from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models import HistoricalTransaction
from app.schemas import (
    DealGenomeSummaryResponse,
    HistoricalTransactionInput,
    HistoricalTransactionResponse,
)


class DealGenomeError(ValueError):
    pass


SAMPLE_TRANSACTIONS: list[dict[str, Any]] = [
    {
        "buyer_name": "Aster Capital Technologies",
        "target_name": "Northstar Process Automation",
        "announcement_date": "2026-01-15",
        "close_date": "2026-03-31",
        "deal_value": 87500000.0,
        "enterprise_value": 87500000.0,
        "revenue": 34000000.0,
        "ebitda": 6800000.0,
        "sector": "Industrial software",
        "buyer_country": "United States",
        "target_country": "India",
        "payment_type": "Cash",
        "premium_pct": 18.0,
        "deal_status": "closed",
        "source_url": "sample_data/merger_pdf_pack",
        "source_type": "sample_seed",
    },
    {
        "buyer_name": "Northbridge Systems",
        "target_name": "Meridian Workflow Cloud",
        "announcement_date": "2025-09-08",
        "close_date": "2025-12-19",
        "deal_value": 142000000.0,
        "enterprise_value": 150000000.0,
        "revenue": 52000000.0,
        "ebitda": 9100000.0,
        "sector": "SaaS",
        "buyer_country": "United States",
        "target_country": "United Kingdom",
        "payment_type": "Cash + earn-out",
        "premium_pct": 22.5,
        "deal_status": "closed",
        "source_url": "local-demo",
        "source_type": "sample_seed",
    },
    {
        "buyer_name": "Atlas Manufacturing Group",
        "target_name": "Keystone Robotics",
        "announcement_date": "2025-06-18",
        "close_date": "2025-10-02",
        "deal_value": 238000000.0,
        "enterprise_value": 255000000.0,
        "revenue": 88000000.0,
        "ebitda": 17600000.0,
        "sector": "Automation",
        "buyer_country": "Germany",
        "target_country": "United States",
        "payment_type": "Cash",
        "premium_pct": 15.0,
        "deal_status": "closed",
        "source_url": "local-demo",
        "source_type": "sample_seed",
    },
]


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _serialize(row: HistoricalTransaction) -> HistoricalTransactionResponse:
    return HistoricalTransactionResponse(
        id=row.id,
        buyer_name=row.buyer_name,
        target_name=row.target_name,
        announcement_date=row.announcement_date,
        close_date=row.close_date,
        deal_value=row.deal_value,
        enterprise_value=row.enterprise_value,
        revenue=row.revenue,
        ebitda=row.ebitda,
        sector=row.sector,
        buyer_country=row.buyer_country,
        target_country=row.target_country,
        payment_type=row.payment_type,
        premium_pct=row.premium_pct,
        deal_status=row.deal_status,
        source_url=row.source_url,
        source_type=row.source_type,
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _dedupe_query(db: Session, payload: HistoricalTransactionInput):
    query = db.query(HistoricalTransaction).filter(
        func.lower(HistoricalTransaction.buyer_name) == payload.buyer_name.lower(),
        func.lower(HistoricalTransaction.target_name) == payload.target_name.lower(),
        HistoricalTransaction.announcement_date == payload.announcement_date,
    )
    if payload.source_url:
        query = query.filter(
            or_(
                HistoricalTransaction.source_url == payload.source_url,
                HistoricalTransaction.source_url == "",
            )
        )
    return query


def create_or_update_transaction(db: Session, payload: HistoricalTransactionInput) -> HistoricalTransactionResponse:
    existing = _dedupe_query(db, payload).first()
    if existing is None:
        row = HistoricalTransaction(**payload.model_dump())
        db.add(row)
    else:
        row = existing
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return _serialize(row)


def list_transactions(
    db: Session,
    *,
    q: str | None = None,
    sector: str | None = None,
    country: str | None = None,
    limit: int = 100,
) -> list[HistoricalTransactionResponse]:
    query = db.query(HistoricalTransaction)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            or_(
                func.lower(HistoricalTransaction.buyer_name).like(like),
                func.lower(HistoricalTransaction.target_name).like(like),
                func.lower(HistoricalTransaction.sector).like(like),
            )
        )
    if sector:
        query = query.filter(func.lower(HistoricalTransaction.sector).like(f"%{sector.lower()}%"))
    if country:
        country_like = f"%{country.lower()}%"
        query = query.filter(
            or_(
                func.lower(HistoricalTransaction.buyer_country).like(country_like),
                func.lower(HistoricalTransaction.target_country).like(country_like),
            )
        )
    rows = query.order_by(HistoricalTransaction.announcement_date.desc()).limit(limit).all()
    return [_serialize(row) for row in rows]


def summarize_deal_genome(db: Session) -> DealGenomeSummaryResponse:
    total = int(db.query(HistoricalTransaction).count())

    def grouped(column) -> dict[str, int]:
        rows = db.query(column, func.count(HistoricalTransaction.id)).group_by(column).all()
        return {str(key or "Unknown"): int(count) for key, count in rows}

    claim = f"{total:,} transactions loaded"
    if total >= 50_000:
        claim = f"{total:,}+ historical transactions loaded"

    return DealGenomeSummaryResponse(
        total_transactions=total,
        by_source_type=grouped(HistoricalTransaction.source_type),
        by_status=grouped(HistoricalTransaction.deal_status),
        by_sector=grouped(HistoricalTransaction.sector),
        database_claim=claim,
        note="This endpoint reports the actual database count. Do not market it as 50,000+ until the count is truly above 50,000.",
    )


def seed_sample_transactions(db: Session) -> DealGenomeSummaryResponse:
    for item in SAMPLE_TRANSACTIONS:
        create_or_update_transaction(db, HistoricalTransactionInput.model_validate(item))
    return summarize_deal_genome(db)


def import_transactions_csv(db: Session, file_bytes: bytes) -> dict[str, Any]:
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DealGenomeError("CSV must be UTF-8 encoded.") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise DealGenomeError("CSV has no header row.")

    imported = 0
    errors: list[dict[str, Any]] = []
    for row_number, row in enumerate(reader, start=2):
        cleaned = {key: (value.strip() if isinstance(value, str) else value) for key, value in row.items() if key}
        for numeric_key in ["deal_value", "enterprise_value", "revenue", "ebitda", "premium_pct"]:
            if cleaned.get(numeric_key) == "":
                cleaned[numeric_key] = None
            elif cleaned.get(numeric_key) is not None:
                try:
                    cleaned[numeric_key] = float(cleaned[numeric_key])
                except (TypeError, ValueError):
                    errors.append({"row": row_number, "error": f"{numeric_key} must be numeric."})
                    cleaned[numeric_key] = None
        try:
            payload = HistoricalTransactionInput.model_validate(cleaned)
            create_or_update_transaction(db, payload)
            imported += 1
        except ValidationError as exc:
            errors.append({"row": row_number, "error": str(exc)})

    return {
        "imported": imported,
        "errors": errors[:50],
        "error_count": len(errors),
        "summary": summarize_deal_genome(db).model_dump(),
    }
