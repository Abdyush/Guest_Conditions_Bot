from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.application.dto.admin_dashboard import AdminReport
from src.application.ports.admin_events_repository import AdminEventsRepository


@dataclass(frozen=True, slots=True)
class GetAdminReports:
    events_repo: AdminEventsRepository

    def execute(self, *, now: datetime) -> dict[str, AdminReport]:
        since = now - timedelta(days=7)
        return {
            "parser_rates": self._build_report(
                title="Отчеты парсера цен за последнюю неделю",
                since=since,
                event_types={"parser_rates_run"},
            ),
            "parser_offers": self._build_report(
                title="Отчеты парсера офферов за последнюю неделю",
                since=since,
                event_types={"parser_offers_run"},
            ),
            "recalculation": self._build_report(
                title="Отчеты пересчета цен за последнюю неделю",
                since=since,
                event_types={"recalculation_run"},
            ),
            "user_errors": self._build_report(
                title="Логи ошибок пользователей за последнюю неделю",
                since=since,
                event_types={"telegram_user_error"},
            ),
        }

    def _build_report(self, *, title: str, since: datetime, event_types: set[str]) -> AdminReport:
        entries = self.events_repo.list_since(since=since, event_types=event_types)
        entries_sorted = sorted(entries, key=lambda item: item.created_at, reverse=True)
        total = len(entries_sorted)
        success = sum(1 for item in entries_sorted if item.status == "success")
        error = sum(1 for item in entries_sorted if item.status == "error")
        busy = sum(1 for item in entries_sorted if item.status == "busy")
        last_run_at = entries_sorted[0].created_at if entries_sorted else None
        return AdminReport(
            title=title,
            total_runs=total,
            success_runs=success,
            error_runs=error,
            busy_runs=busy,
            last_run_at=last_run_at,
            recent_entries=entries_sorted[:10],
        )
