from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.domain.value_objects.money import Money


class DailyRateError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DailyRate:
    date: date
    category_id: str  # Full category name
    tariff_code: str
    price: Money
    is_available: bool = True
    is_last_room: bool = False
    group_id: Optional[str] = None
    adults_count: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.date, date):
            raise DailyRateError("date must be datetime.date")

        if not isinstance(self.category_id, str) or not self.category_id.strip():
            raise DailyRateError("category_id must be non-empty str")

        if not isinstance(self.tariff_code, str) or not self.tariff_code.strip():
            raise DailyRateError("tariff_code must be non-empty str")

        if not isinstance(self.price, Money):
            raise DailyRateError("price must be Money")

        if not isinstance(self.is_available, bool):
            raise DailyRateError("is_available must be bool")

        if not isinstance(self.is_last_room, bool):
            raise DailyRateError("is_last_room must be bool")

        if self.group_id is None:
            object.__setattr__(self, "group_id", self.category_id)
        elif not isinstance(self.group_id, str) or not self.group_id.strip():
            raise DailyRateError("group_id must be non-empty str")

        if not isinstance(self.adults_count, int) or self.adults_count <= 0:
            raise DailyRateError("adults_count must be int > 0")
