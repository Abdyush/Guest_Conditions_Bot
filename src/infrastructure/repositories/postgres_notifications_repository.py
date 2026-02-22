from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import BIGINT, DATE, INTEGER, TEXT, TIMESTAMP, Column, MetaData, Table, and_, create_engine, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from src.application.dto.matched_date_record import MatchedDateRecord
from src.application.ports.notifications_repository import NotificationsRepository


metadata = MetaData()

notifications_table = Table(
    "notifications",
    metadata,
    Column("id", INTEGER, primary_key=True, autoincrement=True),
    Column("guest_id", TEXT, nullable=False),
    Column("date", DATE, nullable=False),
    Column("category_name", TEXT, nullable=False),
    Column("tariff", TEXT, nullable=False),
    Column("new_price_minor", BIGINT, nullable=False),
    Column("offer_id", TEXT, nullable=False, server_default=text("''")),
    Column("bank_status", TEXT, nullable=False, server_default=text("''")),
    Column("loyalty_status", TEXT, nullable=False, server_default=text("''")),
    Column("sent_at", TIMESTAMP, nullable=False),
)


class PostgresNotificationsRepository(NotificationsRepository):
    def __init__(self, database_url: str | None = None):
        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL is required for PostgresNotificationsRepository")
        self._engine = create_engine(url, future=True)
        self._init_schema(self._engine)

    @staticmethod
    def _init_schema(engine: Engine) -> None:
        metadata.create_all(engine)
        ddl = """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications
        ON notifications(guest_id, date, category_name, tariff, new_price_minor, offer_id, bank_status, loyalty_status);
        """
        with engine.begin() as conn:
            conn.execute(text(ddl))

    def filter_new(self, rows: list[MatchedDateRecord]) -> list[MatchedDateRecord]:
        if not rows:
            return []

        guest_ids = sorted({row.guest_id for row in rows})
        date_from = min(row.date for row in rows)
        date_to = max(row.date for row in rows)

        stmt = (
            select(
                notifications_table.c.guest_id,
                notifications_table.c.date,
                notifications_table.c.category_name,
                notifications_table.c.tariff,
                notifications_table.c.new_price_minor,
                notifications_table.c.offer_id,
                notifications_table.c.bank_status,
                notifications_table.c.loyalty_status,
            )
            .where(notifications_table.c.guest_id.in_(guest_ids))
            .where(and_(notifications_table.c.date >= date_from, notifications_table.c.date <= date_to))
        )

        existing: set[tuple[str, object, str, str, int, str, str, str]] = set()
        with self._engine.connect() as conn:
            for row in conn.execute(stmt):
                existing.add(
                    (
                        row.guest_id,
                        row.date,
                        row.category_name,
                        row.tariff,
                        row.new_price_minor,
                        row.offer_id,
                        row.bank_status,
                        row.loyalty_status,
                    )
                )

        return [row for row in rows if self._key(row) not in existing]

    def mark_sent(self, rows: list[MatchedDateRecord], *, sent_at: datetime) -> None:
        if not rows:
            return
        values = [
            {
                "guest_id": row.guest_id,
                "date": row.date,
                "category_name": row.category_name,
                "tariff": row.tariff,
                "new_price_minor": row.new_price_minor,
                "offer_id": row.offer_id or "",
                "bank_status": row.bank_status or "",
                "loyalty_status": row.loyalty_status or "",
                "sent_at": sent_at,
            }
            for row in rows
        ]
        stmt = insert(notifications_table).values(values).on_conflict_do_nothing()
        with self._engine.begin() as conn:
            conn.execute(stmt)

    @staticmethod
    def _key(row: MatchedDateRecord) -> tuple[str, object, str, str, int, str, str, str]:
        return (
            row.guest_id,
            row.date,
            row.category_name,
            row.tariff,
            row.new_price_minor,
            row.offer_id or "",
            row.bank_status or "",
            row.loyalty_status or "",
        )
