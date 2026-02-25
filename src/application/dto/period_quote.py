from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class PeriodQuote:
    category_name: str
    group_id: str
    tariff: str
    from_date: date
    to_date: date
    applied_from: date
    applied_to: date
    nights: int
    total_old_minor: int
    total_new_minor: int
    offer_id: str | None
    offer_title: str | None
    offer_repr: str | None
    loyalty_status: str | None
    loyalty_percent: str | None
    bank_status: str | None
    bank_percent: str | None
