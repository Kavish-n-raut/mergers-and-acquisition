from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.schemas import HistoricalTransactionInput
from app.services.deal_genome import (
    create_or_update_transaction,
    import_transactions_csv,
    seed_sample_transactions,
    summarize_deal_genome,
)


def _make_db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)()


def test_seed_sample_transactions_reports_actual_count():
    db = _make_db()

    summary = seed_sample_transactions(db)

    assert summary.total_transactions == 3
    assert summary.by_source_type["sample_seed"] == 3
    assert summary.database_claim == "3 transactions loaded"
    assert "Do not market it as 50,000+" in summary.note


def test_create_or_update_transaction_dedupes_same_buyer_target_date():
    db = _make_db()
    payload = HistoricalTransactionInput(
        buyer_name="Apex Holdings",
        target_name="Vector Analytics",
        announcement_date="2026-08-19",
        deal_value=100000000.0,
        sector="Software",
        buyer_country="United States",
        target_country="Canada",
        payment_type="Cash",
        deal_status="announced",
        source_type="manual",
    )

    first = create_or_update_transaction(db, payload)
    second = create_or_update_transaction(db, payload.model_copy(update={"deal_value": 125000000.0}))
    summary = summarize_deal_genome(db)

    assert first.id == second.id
    assert second.deal_value == 125000000.0
    assert summary.total_transactions == 1


def test_import_transactions_csv_validates_rows():
    db = _make_db()
    csv_payload = (
        "buyer_name,target_name,announcement_date,deal_value,sector,buyer_country,target_country,payment_type,deal_status,source_type\n"
        "Apex Holdings,Vector Analytics,2026-08-19,100000000,Software,United States,Canada,Cash,announced,manual\n"
        "Broken Row,,2026-08-20,not-a-number,Software,United States,Canada,Cash,announced,manual\n"
    ).encode("utf-8")

    result = import_transactions_csv(db, csv_payload)

    assert result["imported"] == 1
    assert result["error_count"] >= 1
    assert result["summary"]["total_transactions"] == 1
