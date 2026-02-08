from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class Quote:
    category_id: str
    tariff_code: str
    date_range: DateRange
    nights: int

    total_before: Money
    offer_discount: Money
    loyalty_discount: Money
    total_after: Money

    @property
    def effective_per_night(self) -> Money:
        if self.nights <= 0:
            return Money.zero()
        return self.total_after * (Decimal("1") / Decimal(self.nights))