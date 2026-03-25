from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import BIGINT, INTEGER, NUMERIC, TEXT, TIMESTAMP, Column, MetaData, Table, create_engine, delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from src.application.dto.matched_date_record import MatchedDateRecord
from src.application.ports.notifications_repository import NotificationsRepository


metadata = MetaData()

notifications_table = Table(
    "notifications",
    metadata,
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
    Column("notified_at", TIMESTAMP, nullable=True),
)


class _NotificationState(NamedTuple):
    last_notified_at: datetime
    last_notified_price_minor: int


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
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS notified_at TIMESTAMP"))
            conn.execute(text("DROP INDEX IF EXISTS uq_notifications_period"))
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_period
                    ON notifications(
                        guest_id, availability_period, period_label, category_name, group_id, tariff,
                        old_price_minor, new_price_minor, coalesce(offer_id, ''), coalesce(loyalty_status, ''),
                        coalesce(bank_status, ''), coalesce(notified_at, computed_at)
                    )
                    """
                )
            )

    def filter_new(self, rows: list[MatchedDateRecord], *, as_of_date: date, cooldown_days: int) -> list[MatchedDateRecord]:
        if not rows:
            self._prune_and_normalize_existing(as_of_date)
            return []

        grouped_input = self._aggregate_rows(rows)
        self._prune_and_normalize_existing(as_of_date)
        normalized_rows = [x for x in (self._normalize_row(r, as_of_date=as_of_date) for r in grouped_input) if x is not None]
        if not normalized_rows:
            return []

        existing_states: dict[tuple[str, str, str, str], _NotificationState] = {}
        with self._engine.connect() as conn:
            for row in conn.execute(select(notifications_table)).mappings():
                rec = self._from_db_row(row)
                logical_key = self._logical_key(rec)
                notified_at = rec.notified_at or rec.computed_at
                state = existing_states.get(logical_key)
                if state is None or notified_at > state.last_notified_at:
                    existing_states[logical_key] = _NotificationState(
                        last_notified_at=notified_at,
                        last_notified_price_minor=rec.new_price_minor,
                    )
                elif notified_at == state.last_notified_at and rec.new_price_minor < state.last_notified_price_minor:
                    existing_states[logical_key] = _NotificationState(
                        last_notified_at=state.last_notified_at,
                        last_notified_price_minor=rec.new_price_minor,
                    )

        rows_by_logical_key: dict[tuple[str, str, str, str], list[MatchedDateRecord]] = {}
        for row in normalized_rows:
            rows_by_logical_key.setdefault(self._logical_key(row), []).append(row)

        out: list[MatchedDateRecord] = []
        for logical_key, logical_rows in rows_by_logical_key.items():
            state = existing_states.get(logical_key)
            current_best_price = min(row.new_price_minor for row in logical_rows)
            best_rows = [
                row
                for row in logical_rows
                if row.new_price_minor == current_best_price
            ]
            if state is None:
                out.extend(best_rows)
                continue

            if current_best_price < state.last_notified_price_minor:
                out.extend(best_rows)
                continue

            if self._cooldown_elapsed(
                as_of_date=as_of_date,
                last_notified_at=state.last_notified_at,
                cooldown_days=cooldown_days,
            ):
                out.extend(best_rows)

        return out

    def mark_sent(self, rows: list[MatchedDateRecord], *, run_id: str) -> None:
        if not rows:
            return
        notified_at = datetime.now()
        values = [self._to_row(run_id, row, notified_at=notified_at) for row in rows]
        stmt = insert(notifications_table).values(values).on_conflict_do_nothing()
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def get_run_rows(self, run_id: str, *, guest_id: str | None = None) -> list[MatchedDateRecord]:
        stmt = select(notifications_table).where(notifications_table.c.run_id == run_id)
        if guest_id is not None:
            stmt = stmt.where(notifications_table.c.guest_id == guest_id)

        out: list[MatchedDateRecord] = []
        with self._engine.connect() as conn:
            for row in conn.execute(stmt).mappings():
                out.append(self._from_db_row(row))
        return out

    def _prune_and_normalize_existing(self, as_of_date: date) -> None:
        with self._engine.begin() as conn:
            existing = list(conn.execute(select(notifications_table)).mappings())
            conn.execute(delete(notifications_table))

            rows_to_keep: list[tuple[str, MatchedDateRecord]] = []
            for row in existing:
                rec = self._from_db_row(row)
                normalized = self._normalize_row(rec, as_of_date=as_of_date)
                if normalized is None:
                    continue
                rows_to_keep.append((row["run_id"], normalized))

            rows_serialized: list[dict] = []
            for run_id, rec in rows_to_keep:
                rows_serialized.append(self._to_row(run_id, rec, notified_at=rec.notified_at))

            if rows_serialized:
                stmt = insert(notifications_table).values(rows_serialized).on_conflict_do_nothing()
                conn.execute(stmt)

    @staticmethod
    def _normalize_row(row: MatchedDateRecord, *, as_of_date: date) -> MatchedDateRecord | None:
        period_start = row.date
        period_end = row.period_end or row.date
        avail_start = row.availability_start
        avail_end_inclusive = row.availability_end - timedelta(days=1)

        if period_end < as_of_date or avail_end_inclusive < as_of_date:
            return None

        new_period_start = max(period_start, as_of_date)
        new_avail_start = max(avail_start, as_of_date)

        return MatchedDateRecord(
            guest_id=row.guest_id,
            date=new_period_start,
            category_name=row.category_name,
            group_id=row.group_id,
            tariff=row.tariff,
            old_price_minor=row.old_price_minor,
            new_price_minor=row.new_price_minor,
            offer_id=row.offer_id,
            offer_title=row.offer_title,
            offer_repr=row.offer_repr,
            offer_min_nights=row.offer_min_nights,
            loyalty_status=row.loyalty_status,
            loyalty_percent=row.loyalty_percent,
            bank_status=row.bank_status,
            bank_percent=row.bank_percent,
            availability_start=new_avail_start,
            availability_end=avail_end_inclusive + timedelta(days=1),
            computed_at=row.computed_at,
            period_end=period_end,
            notified_at=row.notified_at,
        )

    @staticmethod
    def _to_row(run_id: str, row: MatchedDateRecord, *, notified_at: datetime | None) -> dict:
        period_end = row.period_end or row.date
        period_label = f"{row.date.isoformat()} - {period_end.isoformat()}"
        availability_end_inclusive = row.availability_end - timedelta(days=1)
        availability_period = f"{row.availability_start.isoformat()} - {availability_end_inclusive.isoformat()}"
        return {
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
            "notified_at": notified_at,
        }

    @staticmethod
    def _parse_period(value: str) -> tuple[date, date]:
        left, right = [x.strip() for x in value.split(" - ", 1)]
        return date.fromisoformat(left), date.fromisoformat(right)

    @classmethod
    def _from_db_row(cls, row) -> MatchedDateRecord:
        period_start, period_end = cls._parse_period(row["period_label"])
        avail_start, avail_end_inclusive = cls._parse_period(row["availability_period"])
        return MatchedDateRecord(
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
            availability_start=avail_start,
            availability_end=avail_end_inclusive + timedelta(days=1),
            computed_at=row["computed_at"],
            period_end=period_end,
            notified_at=row.get("notified_at"),
        )

    @staticmethod
    def _logical_key(row: MatchedDateRecord) -> tuple[str, str, str, str]:
        return (
            row.guest_id,
            row.category_name,
            row.group_id,
            row.tariff.strip().lower(),
        )

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
        current_end = ordered[0].period_end or ordered[0].date
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
                    notified_at=current_base.notified_at,
                )
            )

        for row in ordered[1:]:
            row_key = cls._group_key(row)
            row_end = row.period_end or row.date
            if row_key == current_key and row.date <= current_end + timedelta(days=1):
                if row_end > current_end:
                    current_end = row_end
                continue
            flush()
            current_base = row
            current_key = row_key
            current_start = row.date
            current_end = row_end

        flush()
        return out

    @staticmethod
    def _cooldown_elapsed(*, as_of_date: date, last_notified_at: datetime, cooldown_days: int) -> bool:
        if cooldown_days <= 0:
            return True
        return (as_of_date - last_notified_at.date()).days >= cooldown_days
