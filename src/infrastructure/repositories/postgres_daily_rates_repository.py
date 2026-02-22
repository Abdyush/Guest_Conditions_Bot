from __future__ import annotations

import os
from datetime import date

from sqlalchemy import BIGINT, DATE, INTEGER, TEXT, BOOLEAN, Column, MetaData, Table, create_engine, select, text
from sqlalchemy.engine import Engine

from src.application.ports.daily_rates_snapshot_repository import DailyRatesSnapshotRepository
from src.application.ports.rates_repository import RatesRepository
from src.domain.entities.rate import DailyRate
from src.domain.value_objects.money import Money


metadata = MetaData()

daily_rates_table = Table(
    "daily_rates",
    metadata,
    Column("date", DATE, nullable=False),
    Column("category_name", TEXT, nullable=False),
    Column("group_id", TEXT, nullable=False),
    Column("tariff_code", TEXT, nullable=False),
    Column("adults_count", INTEGER, nullable=False),
    Column("amount_minor", BIGINT, nullable=False),
    Column("currency", TEXT, nullable=False),
    Column("is_last_room", BOOLEAN, nullable=False),
)


class PostgresDailyRatesRepository(DailyRatesSnapshotRepository, RatesRepository):
    def __init__(self, database_url: str | None = None):
        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL is required for PostgresDailyRatesRepository")
        self._engine = create_engine(url, future=True)
        self._init_schema(self._engine)

    @staticmethod
    def _init_schema(engine: Engine) -> None:
        metadata.create_all(engine)

    def replace_all(self, rows: list[DailyRate]) -> None:
        with self._engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE daily_rates"))
            if not rows:
                return
            conn.execute(
                daily_rates_table.insert(),
                [
                    {
                        "date": row.date,
                        "category_name": row.category_id,
                        "group_id": row.group_id,
                        "tariff_code": row.tariff_code,
                        "adults_count": row.adults_count,
                        "amount_minor": row.price.amount_minor,
                        "currency": row.price.currency,
                        "is_last_room": row.is_last_room,
                    }
                    for row in rows
                ],
            )

    def get_daily_rates(self, date_from: date, date_to: date) -> list[DailyRate]:
        stmt = (
            select(
                daily_rates_table.c.date,
                daily_rates_table.c.category_name,
                daily_rates_table.c.group_id,
                daily_rates_table.c.tariff_code,
                daily_rates_table.c.adults_count,
                daily_rates_table.c.amount_minor,
                daily_rates_table.c.currency,
                daily_rates_table.c.is_last_room,
            )
            .where(daily_rates_table.c.date >= date_from)
            .where(daily_rates_table.c.date <= date_to)
        )
        out: list[DailyRate] = []
        with self._engine.connect() as conn:
            for row in conn.execute(stmt):
                out.append(
                    DailyRate(
                        date=row.date,
                        category_id=row.category_name,
                        group_id=row.group_id,
                        tariff_code=row.tariff_code,
                        adults_count=row.adults_count,
                        price=Money.from_minor(row.amount_minor, currency=row.currency),
                        is_available=True,
                        is_last_room=bool(row.is_last_room),
                    )
                )
        return out
