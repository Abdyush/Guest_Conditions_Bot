from __future__ import annotations

from datetime import date
from typing import Protocol

from src.application.dto.matched_date_record import MatchedDateRecord


class NotificationsRepository(Protocol):
    def filter_new(self, rows: list[MatchedDateRecord], *, as_of_date: date, cooldown_days: int) -> list[MatchedDateRecord]:
        ...

    def mark_sent(self, rows: list[MatchedDateRecord], *, run_id: str) -> None:
        ...

    def get_run_rows(self, run_id: str, *, guest_id: str | None = None) -> list[MatchedDateRecord]:
        ...
