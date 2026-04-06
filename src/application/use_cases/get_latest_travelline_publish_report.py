from __future__ import annotations

from dataclasses import dataclass

from src.application.dto.travelline_publish_report import TravellinePublishRunReport
from src.application.ports.travelline_publish_report_repository import TravellinePublishReportRepository


@dataclass(frozen=True, slots=True)
class GetLatestTravellinePublishReport:
    repo: TravellinePublishReportRepository

    def execute(self) -> TravellinePublishRunReport | None:
        return self.repo.get_latest_run_report()
