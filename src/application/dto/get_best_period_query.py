from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class GetBestPeriodQuery:
    guest_id: str
    group_id: str
    date_from: date
    date_to: date
    booking_date: date
    top_k: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.guest_id, str) or not self.guest_id.strip():
            raise ValueError("guest_id must be non-empty str")
        if not isinstance(self.group_id, str) or not self.group_id.strip():
            raise ValueError("group_id must be non-empty str")
        if not isinstance(self.date_from, date) or not isinstance(self.date_to, date) or not isinstance(self.booking_date, date):
            raise ValueError("date_from/date_to/booking_date must be date")
        if self.date_to < self.date_from:
            raise ValueError("date_to must be >= date_from")
        if not isinstance(self.top_k, int) or self.top_k <= 0:
            raise ValueError("top_k must be int > 0")
