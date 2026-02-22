from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.application.dto.matched_date_record import MatchedDateRecord


class NotificationsRepository(Protocol):
    def filter_new(self, rows: list[MatchedDateRecord]) -> list[MatchedDateRecord]:
        ...

    def mark_sent(self, rows: list[MatchedDateRecord], *, sent_at: datetime) -> None:
        ...
