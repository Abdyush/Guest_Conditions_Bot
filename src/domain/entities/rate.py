from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.domain.value_objects.money import Money


class DailyRateError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DailyRate:
    """
    Цена за 1 ночь (дата ночёвки).
    date: дата ночёвки (например, 2026-02-10 — ночь с 10 на 11)
    """
    date: date
    category_id: str
    tariff_code: str
    price: Money
    is_available: bool = True
    is_last_room: bool = False

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