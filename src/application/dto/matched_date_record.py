from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class MatchedDateRecord:
    guest_id: str
    date: date
    category_name: str
    group_id: str
    tariff: str
    old_price_minor: int
    new_price_minor: int
    offer_id: str | None
    offer_title: str | None
    offer_repr: str | None
    offer_min_nights: int | None
    loyalty_status: str | None
    loyalty_percent: Decimal | None
    bank_status: str | None
    bank_percent: Decimal | None
    availability_start: date
    availability_end: date
    computed_at: datetime
    period_end: date | None = None
    notified_at: datetime | None = None
