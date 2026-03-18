from __future__ import annotations

from dataclasses import dataclass

from src.application.dto.matched_date_record import MatchedDateRecord


@dataclass(frozen=True, slots=True)
class GuestNotificationBatch:
    run_id: str
    guest_id: str
    guest_name: str
    telegram_user_ids: list[int]
    rows: list[MatchedDateRecord]
    category_groups: list[tuple[str, str]]
