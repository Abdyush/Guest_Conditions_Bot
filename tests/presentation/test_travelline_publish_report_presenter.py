from __future__ import annotations

from datetime import date, datetime

from src.application.dto.travelline_publish_report import (
    TravellinePublishAdultsSummary,
    TravellinePublishDateStat,
    TravellinePublishRunReport,
)
from src.presentation.telegram.presenters.admin_menu_presenter import (
    build_travelline_publish_report_csv,
    render_travelline_publish_report_summary,
)


def _report() -> TravellinePublishRunReport:
    return TravellinePublishRunReport(
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
        total_final_rows_count=12,
        tariff_pairing_anomalies_count=0,
        unmapped_categories_count=0,
        adults_summaries=(
            TravellinePublishAdultsSummary(
                adults_count=1,
                expected_requests_count=3,
                attempted_count=3,
                success_count=3,
                fail_count=0,
                collected_final_rows_count=8,
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
            TravellinePublishDateStat(stay_date=date(2026, 4, 6), rows_count=8),
            TravellinePublishDateStat(stay_date=date(2026, 4, 8), rows_count=4),
        ),
    )


def test_render_travelline_publish_report_summary_includes_key_fields() -> None:
    text = render_travelline_publish_report_summary(_report())

    assert "Travelline publish run" in text
    assert "Rows: 12" in text
    assert "Expected dates: 3" in text
    assert "Actual dates: 2" in text
    assert "Dates with no categories: 1" in text
    assert "completed_with_rows=1" in text
    assert "completed_zero_rows=1" in text


def test_render_travelline_publish_report_summary_handles_missing_report() -> None:
    text = render_travelline_publish_report_summary(None)

    assert "отсутствует" in text.lower()


def test_build_travelline_publish_report_csv_contains_summary_adults_empty_dates_and_date_rows() -> None:
    csv_text = build_travelline_publish_report_csv(_report()).decode("utf-8")

    assert "row_type,run_id,validation_status" in csv_text
    assert "summary,tlpub_1,passed" in csv_text
    assert "adults,tlpub_1" in csv_text
    assert "empty_date,tlpub_1" in csv_text
    assert "date_rows,tlpub_1" in csv_text
    assert "2026-04-07" in csv_text
