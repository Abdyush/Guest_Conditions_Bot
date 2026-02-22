from __future__ import annotations

from datetime import date
from typing import Protocol

from src.domain.entities.rate import DailyRate


class RatesRepository(Protocol):
    def get_daily_rates(self, date_from: date, date_to: date) -> list[DailyRate]:
        ...
