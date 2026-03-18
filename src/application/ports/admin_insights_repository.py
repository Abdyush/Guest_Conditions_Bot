from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.application.dto.admin_dashboard import DesiredPriceByGroupStat


class AdminInsightsRepository(Protocol):
    def total_users(self) -> int:
        ...

    def count_new_users_since(self, *, since: datetime) -> int | None:
        ...

    def desired_price_by_group(self) -> list[DesiredPriceByGroupStat]:
        ...
