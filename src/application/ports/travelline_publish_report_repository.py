from __future__ import annotations

from typing import Protocol

from src.application.dto.travelline_publish_report import TravellinePublishRunReport


class TravellinePublishReportRepository(Protocol):
    def save_run_report(self, *, report: TravellinePublishRunReport) -> None:
        ...

    def mark_fallback_used(self, *, run_id: str) -> None:
        ...

    def get_latest_run_report(self) -> TravellinePublishRunReport | None:
        ...
