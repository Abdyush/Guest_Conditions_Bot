from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.application.dto.admin_dashboard import AdminStatistics
from src.application.ports.admin_events_repository import AdminEventsRepository
from src.application.ports.admin_insights_repository import AdminInsightsRepository


@dataclass(frozen=True, slots=True)
class GetAdminStatistics:
    insights_repo: AdminInsightsRepository
    events_repo: AdminEventsRepository

    def execute(self, *, now: datetime) -> AdminStatistics:
        since = now - timedelta(days=7)
        blocked_events = self.events_repo.list_since(since=since, event_types={"telegram_blocked"})
        return AdminStatistics(
            total_users=self.insights_repo.total_users(),
            new_users_last_week=self.insights_repo.count_new_users_since(since=since),
            blocked_users_last_week=len(blocked_events),
            desired_price_by_group=self.insights_repo.desired_price_by_group(),
        )
