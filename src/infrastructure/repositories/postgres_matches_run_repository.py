from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import BIGINT, DATE, INTEGER, NUMERIC, TEXT, TIMESTAMP, Column, MetaData, Table, create_engine, delete, select, text
from sqlalchemy.engine import Engine

from src.application.dto.matched_date_record import MatchedDateRecord
from src.application.ports.matches_run_repository import MatchesRunRepository


metadata = MetaData()

matches_run_table = Table(
    "matches_run",
    metadata,
    Column("run_id", TEXT, nullable=False),
    Column("guest_id", TEXT, nullable=False),
    Column("date", DATE, nullable=False),
    Column("category_name", TEXT, nullable=False),
    Column("group_id", TEXT, nullable=False),
    Column("tariff", TEXT, nullable=False),
    Column("old_price_minor", BIGINT, nullable=False),
    Column("new_price_minor", BIGINT, nullable=False),
    Column("offer_id", TEXT, nullable=True),
    Column("offer_title", TEXT, nullable=True),
    Column("offer_repr", TEXT, nullable=True),
    Column("offer_min_nights", INTEGER, nullable=True),
    Column("loyalty_status", TEXT, nullable=True),
    Column("loyalty_percent", NUMERIC(5, 4), nullable=True),
    Column("bank_status", TEXT, nullable=True),
    Column("bank_percent", NUMERIC(5, 4), nullable=True),
    Column("availability_start", DATE, nullable=False),
    Column("availability_end", DATE, nullable=False),
    Column("computed_at", TIMESTAMP, nullable=False),
)


class PostgresMatchesRunRepository(MatchesRunRepository):
    def __init__(self, database_url: str | None = None):
        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL is required for PostgresMatchesRunRepository")
        self._engine = create_engine(url, future=True)
        self._init_schema(self._engine)

    @staticmethod
    def _init_schema(engine: Engine) -> None:
        metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_matches_run_guest_date ON matches_run(guest_id, date);"))

    def replace_run(self, run_id: str, rows: list[MatchedDateRecord]) -> None:
        with self._engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE matches_run"))
            if not rows:
                return
            conn.execute(
                matches_run_table.insert(),
                [self._to_row(run_id, row) for row in rows],
            )

    def get_run_rows(self, run_id: str) -> list[MatchedDateRecord]:
        stmt = select(matches_run_table).where(matches_run_table.c.run_id == run_id)
        out: list[MatchedDateRecord] = []
        with self._engine.connect() as conn:
            for row in conn.execute(stmt).mappings():
                out.append(
                    MatchedDateRecord(
                        guest_id=row["guest_id"],
                        date=row["date"],
                        category_name=row["category_name"],
                        group_id=row["group_id"],
                        tariff=row["tariff"],
                        old_price_minor=row["old_price_minor"],
                        new_price_minor=row["new_price_minor"],
                        offer_id=row["offer_id"],
                        offer_title=row["offer_title"],
                        offer_repr=row["offer_repr"],
                        offer_min_nights=row["offer_min_nights"],
                        loyalty_status=row["loyalty_status"],
                        loyalty_percent=row["loyalty_percent"],
                        bank_status=row["bank_status"],
                        bank_percent=row["bank_percent"],
                        availability_start=row["availability_start"],
                        availability_end=row["availability_end"],
                        computed_at=row["computed_at"],
                    )
                )
        return out

    @staticmethod
    def _to_row(run_id: str, row: MatchedDateRecord) -> dict:
        return {
            "run_id": run_id,
            "guest_id": row.guest_id,
            "date": row.date,
            "category_name": row.category_name,
            "group_id": row.group_id,
            "tariff": row.tariff,
            "old_price_minor": row.old_price_minor,
            "new_price_minor": row.new_price_minor,
            "offer_id": row.offer_id,
            "offer_title": row.offer_title,
            "offer_repr": row.offer_repr,
            "offer_min_nights": row.offer_min_nights,
            "loyalty_status": row.loyalty_status,
            "loyalty_percent": row.loyalty_percent,
            "bank_status": row.bank_status,
            "bank_percent": row.bank_percent,
            "availability_start": row.availability_start,
            "availability_end": row.availability_end,
            "computed_at": row.computed_at,
        }
