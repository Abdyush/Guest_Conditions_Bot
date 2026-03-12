from __future__ import annotations

import os
import logging
from datetime import date
from uuid import uuid4

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
    Column("snapshot_id", TEXT, nullable=True),
    Column("date", DATE, nullable=False),
    Column("category_name", TEXT, nullable=False),
    Column("group_id", TEXT, nullable=False),
    Column("tariff_code", TEXT, nullable=False),
    Column("adults_count", INTEGER, nullable=False),
    Column("amount_minor", BIGINT, nullable=False),
    Column("currency", TEXT, nullable=False),
    Column("is_last_room", BOOLEAN, nullable=False),
)

active_snapshots_table = Table(
    "active_snapshots",
    metadata,
    Column("dataset", TEXT, primary_key=True),
    Column("snapshot_id", TEXT, nullable=False),
)

DATASET_KEY = "daily_rates"
logger = logging.getLogger(__name__)


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
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE daily_rates ADD COLUMN IF NOT EXISTS snapshot_id TEXT"))
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS active_snapshots(
                        dataset TEXT PRIMARY KEY,
                        snapshot_id TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_daily_rates_snapshot ON daily_rates(snapshot_id);"))

    def replace_all(self, rows: list[DailyRate]) -> None:
        if not rows:
            logger.warning("daily_rates_publish_skip reason=empty_rows")
            return
        snapshot_id = f"dr_{uuid4().hex}"
        logger.info("daily_rates_snapshot_start snapshot_id=%s rows=%s", snapshot_id, len(rows))
        with self._engine.begin() as conn:
            conn.execute(
                daily_rates_table.insert(),
                [
                    {
                        "snapshot_id": snapshot_id,
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
            conn.execute(
                text(
                    """
                    INSERT INTO active_snapshots(dataset, snapshot_id)
                    VALUES (:dataset, :snapshot_id)
                    ON CONFLICT (dataset) DO UPDATE SET snapshot_id = EXCLUDED.snapshot_id
                    """
                ),
                {"dataset": DATASET_KEY, "snapshot_id": snapshot_id},
            )
        logger.info("daily_rates_snapshot_published snapshot_id=%s", snapshot_id)

    def get_daily_rates(self, date_from: date, date_to: date) -> list[DailyRate]:
        with self._engine.connect() as conn:
            active_snapshot_id = self._get_active_snapshot_id(conn)
        if active_snapshot_id:
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
                .where(daily_rates_table.c.snapshot_id == active_snapshot_id)
                .where(daily_rates_table.c.date >= date_from)
                .where(daily_rates_table.c.date <= date_to)
            )
        else:
            # Backward compatibility for legacy unversioned rows.
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

    @staticmethod
    def _get_active_snapshot_id(conn) -> str | None:
        row = conn.execute(
            select(active_snapshots_table.c.snapshot_id).where(active_snapshots_table.c.dataset == DATASET_KEY)
        ).first()
        if row is None:
            return None
        return str(row.snapshot_id)
