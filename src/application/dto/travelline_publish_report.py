from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class TravellinePublishAdultsSummary:
    adults_count: int
    expected_requests_count: int
    attempted_count: int
    success_count: int
    fail_count: int
    collected_final_rows_count: int
    status: str


@dataclass(frozen=True, slots=True)
class TravellinePublishDateStat:
    stay_date: date
    rows_count: int


@dataclass(frozen=True, slots=True)
class TravellinePublishRunReport:
    run_id: str
    created_at: datetime
    completed_at: datetime
    mode: str
    validation_status: str
    validation_failure_reasons: tuple[str, ...]
    fallback_used: bool
    expected_dates_count: int
    actual_dates_count: int
    dates_with_no_categories_count: int
    total_final_rows_count: int
    tariff_pairing_anomalies_count: int
    unmapped_categories_count: int
    adults_summaries: tuple[TravellinePublishAdultsSummary, ...]
    empty_dates: tuple[date, ...]
    per_date_rows: tuple[TravellinePublishDateStat, ...]
