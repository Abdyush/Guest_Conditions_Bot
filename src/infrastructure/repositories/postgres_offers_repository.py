from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

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

    def replace_all(self, offers: list[Offer]) -> None:
        with self._engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE special_offers"))
            if not offers:
                return
            rows = []
            for offer in offers:
                discount_type, discount_value = _serialize_discount(offer)
                rows.append(
                    {
                        "id": offer.id,
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

    def get_offers(self, today: date) -> list[Offer]:
        _ = today
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
