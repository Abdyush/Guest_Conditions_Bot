from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AdminEventEntry:
    event_type: str
    status: str
    trigger: str | None
    message: str | None
    user_id: int | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AdminReport:
    title: str
    total_runs: int
    success_runs: int
    error_runs: int
    busy_runs: int
    last_run_at: datetime | None
    recent_entries: list[AdminEventEntry]


@dataclass(frozen=True, slots=True)
class DesiredPriceByGroupStat:
    group_id: str
    users_count: int
    avg_price_minor: int
    min_price_minor: int
    max_price_minor: int


@dataclass(frozen=True, slots=True)
class AdminStatistics:
    total_users: int
    new_users_last_week: int | None
    blocked_users_last_week: int | None
    desired_price_by_group: list[DesiredPriceByGroupStat]
