from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.application.dto.admin_dashboard import AdminEventEntry


class AdminEventsRepository(Protocol):
    def log_event(
        self,
        *,
        event_type: str,
        status: str,
        created_at: datetime,
        trigger: str | None = None,
        message: str | None = None,
        user_id: int | None = None,
    ) -> None:
        ...

    def list_since(self, *, since: datetime, event_types: set[str] | None = None) -> list[AdminEventEntry]:
        ...
