from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import uuid

from src.application.dto.travelline_publish_report import (
    TravellinePublishAdultsSummary,
    TravellinePublishDateStat,
    TravellinePublishRunReport,
)
from src.infrastructure.repositories.postgres_travelline_publish_report_repository import (
    PostgresTravellinePublishReportRepository,
)


def _database_url() -> str:
    path = Path(".tmp_tests") / f"travelline_publish_reports_{uuid.uuid4().hex}.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{path.resolve().as_posix()}"


def test_repository_persists_run_summary_adults_empty_dates_and_per_date_rows() -> None:
    database_url = _database_url()
    repo = PostgresTravellinePublishReportRepository(database_url=database_url)
    report = TravellinePublishRunReport(
        run_id="tlpub_1",
        created_at=datetime(2026, 4, 6, 10, 0, 0),
        completed_at=datetime(2026, 4, 6, 10, 5, 0),
        mode="travelline_publish",
        validation_status="passed",
        validation_failure_reasons=tuple(),
        fallback_used=False,
        expected_dates_count=3,
        actual_dates_count=2,
        dates_with_no_categories_count=1,
        total_final_rows_count=8,
        tariff_pairing_anomalies_count=0,
        unmapped_categories_count=0,
        adults_summaries=(
            TravellinePublishAdultsSummary(
                adults_count=1,
                expected_requests_count=3,
                attempted_count=3,
                success_count=3,
                fail_count=0,
                collected_final_rows_count=4,
                status="completed_with_rows",
            ),
            TravellinePublishAdultsSummary(
                adults_count=6,
                expected_requests_count=3,
                attempted_count=3,
                success_count=3,
                fail_count=0,
                collected_final_rows_count=0,
                status="completed_zero_rows",
            ),
        ),
        empty_dates=(date(2026, 4, 7),),
        per_date_rows=(
            TravellinePublishDateStat(stay_date=date(2026, 4, 6), rows_count=4),
            TravellinePublishDateStat(stay_date=date(2026, 4, 8), rows_count=4),
        ),
    )

    repo.save_run_report(report=report)

    loaded = repo.get_latest_run_report()

    assert loaded == report


def test_repository_marks_fallback_used_for_existing_run() -> None:
    database_url = _database_url()
    repo = PostgresTravellinePublishReportRepository(database_url=database_url)
    report = TravellinePublishRunReport(
        run_id="tlpub_2",
        created_at=datetime(2026, 4, 6, 11, 0, 0),
        completed_at=datetime(2026, 4, 6, 11, 5, 0),
        mode="travelline_publish",
        validation_status="failed",
        validation_failure_reasons=("adults_6:attempt_failed",),
        fallback_used=False,
        expected_dates_count=3,
        actual_dates_count=0,
        dates_with_no_categories_count=3,
        total_final_rows_count=0,
        tariff_pairing_anomalies_count=0,
        unmapped_categories_count=0,
        adults_summaries=tuple(),
        empty_dates=(date(2026, 4, 6), date(2026, 4, 7), date(2026, 4, 8)),
        per_date_rows=tuple(),
    )

    repo.save_run_report(report=report)
    repo.mark_fallback_used(run_id="tlpub_2")

    loaded = repo.get_latest_run_report()

    assert loaded is not None
    assert loaded.fallback_used is True
