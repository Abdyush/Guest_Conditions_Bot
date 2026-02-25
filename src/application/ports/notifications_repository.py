from __future__ import annotations

from datetime import date
from typing import Protocol

from src.application.dto.matched_date_record import MatchedDateRecord


class NotificationsRepository(Protocol):
    def filter_new(self, rows: list[MatchedDateRecord], *, as_of_date: date) -> list[MatchedDateRecord]:
        ...

    def mark_sent(self, rows: list[MatchedDateRecord], *, run_id: str) -> None:
        ...
