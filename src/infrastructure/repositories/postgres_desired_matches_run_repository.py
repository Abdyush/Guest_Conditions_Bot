from __future__ import annotations

import os
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import BIGINT, INTEGER, NUMERIC, TEXT, TIMESTAMP, Column, MetaData, Table, create_engine, select, text
from sqlalchemy.engine import Engine

from src.application.dto.matched_date_record import MatchedDateRecord
from src.application.ports.matches_run_repository import MatchesRunRepository


metadata = MetaData()

desired_matches_run_table = Table(
    "desired_matches_run",
    metadata,
    Column("snapshot_id", TEXT, nullable=True),
    Column("run_id", TEXT, nullable=False),
    Column("guest_id", TEXT, nullable=False),
    Column("availability_period", TEXT, nullable=False),
    Column("period_label", TEXT, nullable=True),
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
    Column("computed_at", TIMESTAMP, nullable=False),
)

active_snapshots_table = Table(
    "active_snapshots",
    metadata,
    Column("dataset", TEXT, primary_key=True),
    Column("snapshot_id", TEXT, nullable=False),
)

DATASET_KEY = "desired_matches_run"
logger = logging.getLogger(__name__)


class PostgresDesiredMatchesRunRepository(MatchesRunRepository):
    def __init__(self, database_url: str | None = None):
        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL is required for PostgresDesiredMatchesRunRepository")
        self._engine = create_engine(url, future=True)
        self._init_schema(self._engine)

    @staticmethod
    def _init_schema(engine: Engine) -> None:
        metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE desired_matches_run ADD COLUMN IF NOT EXISTS snapshot_id TEXT"))
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
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_desired_matches_run_guest_period ON desired_matches_run(guest_id, period_label);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_desired_matches_run_snapshot ON desired_matches_run(snapshot_id);"))

    def replace_run(self, run_id: str, rows: list[MatchedDateRecord]) -> None:
        snapshot_id = run_id
        logger.info("desired_matches_snapshot_start snapshot_id=%s rows=%s", snapshot_id, len(rows))
        with self._engine.begin() as conn:
            grouped_rows = self._aggregate_rows(rows)
            if grouped_rows:
                conn.execute(
                    desired_matches_run_table.insert(),
                    [self._to_row(run_id, snapshot_id, row) for row in grouped_rows],
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
        logger.info("desired_matches_snapshot_published snapshot_id=%s", snapshot_id)

    def get_run_rows(self, run_id: str) -> list[MatchedDateRecord]:
        stmt = select(desired_matches_run_table).where(desired_matches_run_table.c.run_id == run_id)
        out: list[MatchedDateRecord] = []
        with self._engine.connect() as conn:
            for row in conn.execute(stmt).mappings():
                period_start, period_end_inclusive = self._parse_period_label(row["period_label"])
                availability_start, availability_end_inclusive = self._parse_period_label(row["availability_period"])
                out.append(
                    MatchedDateRecord(
                        guest_id=row["guest_id"],
                        date=period_start,
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
                        availability_start=availability_start,
                        availability_end=availability_end_inclusive + timedelta(days=1),
                        computed_at=row["computed_at"],
                        period_end=period_end_inclusive,
                    )
                )
        return out

    def get_latest_run_id(self) -> str | None:
        with self._engine.connect() as conn:
            active_snapshot_id = self._get_active_snapshot_id(conn)
            if active_snapshot_id:
                return active_snapshot_id
        stmt = select(desired_matches_run_table.c.run_id).order_by(desired_matches_run_table.c.computed_at.desc()).limit(1)
        with self._engine.connect() as conn:
            row = conn.execute(stmt).first()
            if row is None:
                return None
            return str(row.run_id)

    @staticmethod
    def _to_row(run_id: str, snapshot_id: str, row: MatchedDateRecord) -> dict:
        period_start = row.date
        period_end = row.period_end or row.date
        period_label = f"{period_start.isoformat()} - {period_end.isoformat()}"
        availability_end_inclusive = row.availability_end - timedelta(days=1)
        availability_period = f"{row.availability_start.isoformat()} - {availability_end_inclusive.isoformat()}"
        return {
            "snapshot_id": snapshot_id,
            "run_id": run_id,
            "guest_id": row.guest_id,
            "availability_period": availability_period,
            "period_label": period_label,
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
            "computed_at": row.computed_at,
        }

    @staticmethod
    def _get_active_snapshot_id(conn) -> str | None:
        row = conn.execute(
            select(active_snapshots_table.c.snapshot_id).where(active_snapshots_table.c.dataset == DATASET_KEY)
        ).first()
        if row is None:
            return None
        return str(row.snapshot_id)

    @staticmethod
    def _group_key(row: MatchedDateRecord) -> tuple:
        return (
            row.guest_id,
            row.category_name,
            row.group_id,
            row.tariff,
            row.old_price_minor,
            row.new_price_minor,
            row.offer_id or "",
            row.offer_title or "",
            row.offer_repr or "",
            row.offer_min_nights or 0,
            row.loyalty_status or "",
            row.loyalty_percent or 0,
            row.bank_status or "",
            row.bank_percent or 0,
            row.availability_start,
            row.availability_end,
        )

    @classmethod
    def _aggregate_rows(cls, rows: list[MatchedDateRecord]) -> list[MatchedDateRecord]:
        if not rows:
            return []

        ordered = sorted(rows, key=lambda r: (*cls._group_key(r), r.date))
        out: list[MatchedDateRecord] = []

        current_start = ordered[0].date
        current_end = ordered[0].date
        current_base = ordered[0]
        current_key = cls._group_key(current_base)

        def flush() -> None:
            out.append(
                MatchedDateRecord(
                    guest_id=current_base.guest_id,
                    date=current_start,
                    category_name=current_base.category_name,
                    group_id=current_base.group_id,
                    tariff=current_base.tariff,
                    old_price_minor=current_base.old_price_minor,
                    new_price_minor=current_base.new_price_minor,
                    offer_id=current_base.offer_id,
                    offer_title=current_base.offer_title,
                    offer_repr=current_base.offer_repr,
                    offer_min_nights=current_base.offer_min_nights,
                    loyalty_status=current_base.loyalty_status,
                    loyalty_percent=current_base.loyalty_percent,
                    bank_status=current_base.bank_status,
                    bank_percent=current_base.bank_percent,
                    availability_start=current_base.availability_start,
                    availability_end=current_base.availability_end,
                    computed_at=current_base.computed_at,
                    period_end=current_end,
                )
            )

        for row in ordered[1:]:
            row_key = cls._group_key(row)
            if row_key == current_key and row.date == current_end + timedelta(days=1):
                current_end = row.date
                continue

            flush()
            current_base = row
            current_key = row_key
            current_start = row.date
            current_end = row.date

        flush()
        return out

    @staticmethod
    def _parse_period_label(value: str) -> tuple[date, date]:
        left, right = [x.strip() for x in value.split(" - ", 1)]
        return date.fromisoformat(left), date.fromisoformat(right)
