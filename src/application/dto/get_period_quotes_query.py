from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class GetPeriodQuotesQuery:
    guest_id: str
    period_start: date
    period_end: date
    group_ids: set[str] | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.guest_id, str) or not self.guest_id.strip():
            raise ValueError("guest_id must be non-empty str")
        if not isinstance(self.period_start, date) or not isinstance(self.period_end, date):
            raise ValueError("period_start and period_end must be date")
        if self.period_end < self.period_start:
            raise ValueError("period_end must be >= period_start")
        if self.group_ids is not None:
            if not isinstance(self.group_ids, set):
                raise ValueError("group_ids must be set[str] or None")
            if any((not isinstance(x, str) or not x.strip()) for x in self.group_ids):
                raise ValueError("group_ids must contain non-empty strings")
