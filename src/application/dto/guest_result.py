from __future__ import annotations

from dataclasses import dataclass

from src.application.dto.date_line import DateLineDTO
from src.application.dto.period_pick import PeriodPickDTO
from src.domain.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class GuestResult:
    guest_id: str
    guest_name: str | None
    matched_lines: list[DateLineDTO]
    best_periods: dict[str, list[PeriodPickDTO]]
    desired_price_per_night: Money
