from __future__ import annotations

import os
import logging
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import BOOLEAN, INTEGER, TEXT, Column, MetaData, Table, create_engine, select, text
from sqlalchemy.engine import Engine

from src.application.ports.offers_repository import OffersRepository
from src.domain.entities.offer import Offer
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.discount import PayXGetY, PercentOff


metadata = MetaData()

offers_table = Table(
    "special_offers",
    metadata,
    Column("snapshot_id", TEXT, nullable=True),
    Column("id", TEXT, primary_key=True),
    Column("title", TEXT, nullable=False),
    Column("description", TEXT, nullable=False),
    Column("discount_type", TEXT, nullable=False),
    Column("discount_value", TEXT, nullable=False),
    Column("min_nights", INTEGER, nullable=False),
    Column("stay_periods", TEXT, nullable=False),
    Column("booking_period", TEXT, nullable=True),
    Column("allowed_groups", TEXT, nullable=True),
    Column("allowed_categories", TEXT, nullable=True),
    Column("tariffs", TEXT, nullable=True),
    Column("loyalty_compatible", BOOLEAN, nullable=False),
)

active_snapshots_table = Table(
    "active_snapshots",
    metadata,
    Column("dataset", TEXT, primary_key=True),
    Column("snapshot_id", TEXT, nullable=False),
)

DATASET_KEY = "special_offers"
logger = logging.getLogger(__name__)


def _date_range_to_text(value: DateRange) -> str:
    return f"{value.start.isoformat()}..{value.end.isoformat()}"


def _parse_date_range(raw: str) -> DateRange:
    left, right = raw.split("..", 1)
    return DateRange(date.fromisoformat(left.strip()), date.fromisoformat(right.strip()))


def _parse_set(raw: str | None, *, separator: str) -> set[str] | None:
    text_value = (raw or "").strip()
    if not text_value:
        return None
    items = {part.strip() for part in text_value.split(separator) if part.strip()}
    return items or None


def _serialize_set(values: set[str] | None, *, separator: str) -> str | None:
    if not values:
        return None
    return separator.join(sorted(values))


def _serialize_discount(offer: Offer) -> tuple[str, str]:
    if isinstance(offer.discount, PercentOff):
        return "PERCENT", str(offer.discount.percent)
    if isinstance(offer.discount, PayXGetY):
        return "PAY_X_GET_Y", f"{offer.discount.pay_nights}/{offer.discount.get_nights}"
    raise ValueError(f"Unsupported discount type: {offer.discount.__class__.__name__}")


def _parse_discount(discount_type: str, discount_value: str):
    kind = discount_type.strip().upper()
    value = discount_value.strip()
    if kind == "PERCENT":
        return PercentOff(Decimal(value))
    if kind == "PAY_X_GET_Y":
        pay_raw, get_raw = value.split("/", 1)
        return PayXGetY(int(pay_raw.strip()), int(get_raw.strip()))
    raise ValueError(f"Unsupported discount_type: {discount_type}")


class PostgresOffersRepository(OffersRepository):
    def __init__(self, database_url: str | None = None):
        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL is required for PostgresOffersRepository")
        self._engine = create_engine(url, future=True)
        self._init_schema(self._engine)

    @staticmethod
    def _init_schema(engine: Engine) -> None:
        metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE special_offers ADD COLUMN IF NOT EXISTS snapshot_id TEXT"))
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
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_special_offers_snapshot ON special_offers(snapshot_id);"))

    def replace_all(self, offers: list[Offer]) -> None:
        if not offers:
            logger.warning("special_offers_publish_skip reason=empty_rows")
            return
        snapshot_id = f"of_{uuid4().hex}"
        logger.info("special_offers_snapshot_start snapshot_id=%s rows=%s", snapshot_id, len(offers))
        with self._engine.begin() as conn:
            rows = []
            for offer in offers:
                discount_type, discount_value = _serialize_discount(offer)
                rows.append(
                    {
                        "snapshot_id": snapshot_id,
                        "id": f"{snapshot_id}|{offer.id}",
                        "title": offer.title,
                        "description": offer.description,
                        "discount_type": discount_type,
                        "discount_value": discount_value,
                        "min_nights": offer.min_nights or 1,
                        "stay_periods": "|".join(_date_range_to_text(p) for p in offer.stay_periods),
                        "booking_period": _date_range_to_text(offer.booking_period) if offer.booking_period else None,
                        "allowed_groups": _serialize_set(offer.allowed_groups, separator=","),
                        "allowed_categories": _serialize_set(offer.allowed_categories, separator="|"),
                        "tariffs": _serialize_set(offer.tariffs, separator=","),
                        "loyalty_compatible": bool(offer.loyalty_compatible),
                    }
                )
            conn.execute(offers_table.insert(), rows)
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
        logger.info("special_offers_snapshot_published snapshot_id=%s", snapshot_id)

    def get_offers(self, today: date) -> list[Offer]:
        _ = today
        with self._engine.connect() as conn:
            active_snapshot_id = self._get_active_snapshot_id(conn)
        if active_snapshot_id:
            stmt = select(offers_table).where(offers_table.c.snapshot_id == active_snapshot_id)
        else:
            # Backward compatibility for legacy unversioned rows.
            stmt = select(offers_table)
        out: list[Offer] = []
        with self._engine.connect() as conn:
            for row in conn.execute(stmt).mappings():
                stay_periods = [_parse_date_range(chunk) for chunk in row["stay_periods"].split("|") if chunk.strip()]
                booking_period = _parse_date_range(row["booking_period"]) if row["booking_period"] else None
                out.append(
                    Offer(
                        id=row["id"],
                        title=row["title"],
                        description=row["description"],
                        discount=_parse_discount(row["discount_type"], row["discount_value"]),
                        stay_periods=stay_periods,
                        booking_period=booking_period,
                        min_nights=row["min_nights"],
                        allowed_groups=_parse_set(row["allowed_groups"], separator=","),
                        allowed_categories=_parse_set(row["allowed_categories"], separator="|"),
                        tariffs=_parse_set(row["tariffs"], separator=","),
                        loyalty_compatible=bool(row["loyalty_compatible"]),
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
