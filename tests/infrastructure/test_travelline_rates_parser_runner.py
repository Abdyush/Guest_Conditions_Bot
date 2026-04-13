from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pytest

from src.application.dto.travelline_publish_report import TravellinePublishRunReport
from src.domain.entities.rate import DailyRate
from src.domain.value_objects.money import Money
from src.infrastructure.parsers.travelline_rates_parser_runner import (
    TravellinePublishValidationError,
    TravellineRatesParserRunner,
)
from src.infrastructure.travelline.models import (
    TravellineAdultsProcessingSummary,
    CategoryMappingMismatch,
    TravellineCollectionDiagnostics,
    TravellineCollectionResult,
    TravellineDateRowsStat,
    TravellineRatesTransformResult,
    TariffPairingAnomaly,
)


def _rate(*, stay_date: date, adults: int, category: str, group_id: str, tariff: str, minor: int) -> DailyRate:
    return DailyRate(
        date=stay_date,
        category_id=category,
        group_id=group_id,
        tariff_code=tariff,
        adults_count=adults,
        price=Money.from_minor(minor, currency="RUB"),
        is_available=True,
        is_last_room=False,
    )


@dataclass
class _FakeSource:
    transform_result: TravellineRatesTransformResult
    calls: list[tuple[date, date, tuple[int, ...]]]
    diagnostics: TravellineCollectionDiagnostics | None = None

    def collect_window(self, *, date_from: date, date_to: date, adults_counts: tuple[int, ...]):
        self.calls.append((date_from, date_to, adults_counts))
        return self.transform_result

    def collect_window_with_diagnostics(self, *, date_from: date, date_to: date, adults_counts: tuple[int, ...], fail_fast: bool):
        self.calls.append((date_from, date_to, adults_counts))
        diagnostics = self.diagnostics or TravellineCollectionDiagnostics(
            expected_dates=(date_from,),
            adults_summaries=tuple(
                TravellineAdultsProcessingSummary(
                    adults_count=adults,
                    expected_requests_count=1,
                    attempted_count=1,
                    success_count=1,
                    fail_count=0,
                    collected_final_rows_count=sum(1 for rate in self.transform_result.daily_rates if rate.adults_count == adults),
                    status="completed_with_rows",
                )
                for adults in adults_counts
            ),
            empty_dates=tuple(),
            per_date_rows=(
                (TravellineDateRowsStat(stay_date=date_from, rows_count=len(self.transform_result.daily_rates)),)
                if self.transform_result.daily_rates
                else tuple()
            ),
            collection_failure_reasons=tuple(),
        )
        return TravellineCollectionResult(
            transform_result=self.transform_result,
            diagnostics=diagnostics,
        )


@dataclass
class _FakeRatesRepo:
    rows: list[DailyRate]
    replaced_rows: list[list[DailyRate]] | None = None

    def get_daily_rates(self, date_from: date, date_to: date) -> list[DailyRate]:
        return list(self.rows)

    def replace_all(self, rows: list[DailyRate]) -> None:
        if self.replaced_rows is None:
            self.replaced_rows = []
        self.replaced_rows.append(list(rows))


@dataclass
class _FakeReportRepo:
    saved_reports: list[TravellinePublishRunReport]
    marked_fallback_run_ids: list[str]

    def save_run_report(self, *, report: TravellinePublishRunReport) -> None:
        self.saved_reports.append(report)

    def mark_fallback_used(self, *, run_id: str) -> None:
        self.marked_fallback_run_ids.append(run_id)

    def get_latest_run_report(self) -> TravellinePublishRunReport | None:
        if not self.saved_reports:
            return None
        return self.saved_reports[-1]


def test_runner_compare_only_builds_artifacts_without_publish() -> None:
    tmp_path = Path(".tmp_tests") / "travelline_compare"
    tmp_path.mkdir(parents=True, exist_ok=True)
    selenium_rates = [
        _rate(
            stay_date=date(2026, 4, 10),
            adults=2,
            category="Deluxe Mountain View",
            group_id="DELUXE",
            tariff="breakfast",
            minor=1_200_000,
        )
    ]
    travelline_rates = [
        _rate(
            stay_date=date(2026, 4, 10),
            adults=2,
            category="Deluxe Mountain View",
            group_id="DELUXE",
            tariff="breakfast",
            minor=1_200_000,
        ),
        _rate(
            stay_date=date(2026, 4, 10),
            adults=2,
            category="Deluxe Mountain View",
            group_id="DELUXE",
            tariff="fullpansion",
            minor=1_500_000,
        ),
    ]
    source = _FakeSource(
        transform_result=TravellineRatesTransformResult(
            quotes=tuple(),
            daily_rate_inputs=tuple(),
            daily_rates=tuple(travelline_rates),
            duplicate_keys=("dup-1",),
            tariff_pairing_anomalies=tuple(),
            category_mapping_mismatches=tuple(),
        ),
        calls=[],
    )
    runner = TravellineRatesParserRunner(
        source=source,
        rates_repo=_FakeRatesRepo(rows=selenium_rates),
        artifacts_dir=tmp_path,
    )

    result = runner.run_compare_only(
        date_from=date(2026, 4, 10),
        date_to=date(2026, 4, 10),
        adults_counts=(2,),
    )

    assert source.calls == [(date(2026, 4, 10), date(2026, 4, 10), (2,))]
    assert result.summary.selenium_total_rows == 1
    assert result.summary.travelline_total_rows == 2
    assert result.summary.exact_price_matches == 1
    assert result.summary.travelline_only_rows == 1
    assert result.summary.duplicates_removed == 1

    summary_path = tmp_path / "travelline_vs_selenium_summary.json"
    diff_path = tmp_path / "travelline_vs_selenium_diff.csv"
    travelline_rates_path = tmp_path / "travelline_rates.csv"
    assert summary_path.exists()
    assert diff_path.exists()
    assert travelline_rates_path.exists()

    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_payload["exact_price_matches"] == 1
    assert summary_payload["diff_path"].endswith("travelline_vs_selenium_diff.csv")
    assert summary_payload["travelline_rates_path"].endswith("travelline_rates.csv")
    diff_text = diff_path.read_text(encoding="utf-8")
    assert "travelline_only" in diff_text
    travelline_rates_text = travelline_rates_path.read_text(encoding="utf-8")
    assert "fullpansion" in travelline_rates_text


def test_runner_publish_uses_replace_all_for_valid_travelline_result() -> None:
    travelline_rates = [
        _rate(
            stay_date=date(2026, 4, 10),
            adults=2,
            category="Deluxe Mountain View",
            group_id="DELUXE",
            tariff="breakfast",
            minor=1_200_000,
        ),
        _rate(
            stay_date=date(2026, 4, 10),
            adults=2,
            category="Deluxe Mountain View",
            group_id="DELUXE",
            tariff="fullpansion",
            minor=1_500_000,
        ),
    ]
    repo = _FakeRatesRepo(rows=[], replaced_rows=[])
    report_repo = _FakeReportRepo(saved_reports=[], marked_fallback_run_ids=[])
    source = _FakeSource(
        transform_result=TravellineRatesTransformResult(
            quotes=tuple(),
            daily_rate_inputs=tuple(),
            daily_rates=tuple(travelline_rates),
            duplicate_keys=tuple(),
            tariff_pairing_anomalies=tuple(),
            category_mapping_mismatches=tuple(),
        ),
        calls=[],
    )
    runner = TravellineRatesParserRunner(source=source, rates_repo=repo, report_repo=report_repo)

    rows = runner.run(
        start_date=date(2026, 4, 10),
        days_to_collect=1,
        adults_counts=(2,),
    )

    assert rows == 2
    assert repo.replaced_rows == [travelline_rates]
    assert len(report_repo.saved_reports) == 1
    report = report_repo.saved_reports[0]
    assert report.validation_status == "passed"
    assert report.total_final_rows_count == 2
    assert report.expected_dates_count == 1
    assert report.actual_dates_count == 1


def test_runner_publish_rejects_technically_incomplete_result_without_publish() -> None:
    repo = _FakeRatesRepo(rows=[], replaced_rows=[])
    report_repo = _FakeReportRepo(saved_reports=[], marked_fallback_run_ids=[])
    source = _FakeSource(
        transform_result=TravellineRatesTransformResult(
            quotes=tuple(),
            daily_rate_inputs=tuple(),
            daily_rates=tuple(),
            duplicate_keys=tuple(),
            tariff_pairing_anomalies=tuple(),
            category_mapping_mismatches=tuple(),
        ),
        diagnostics=TravellineCollectionDiagnostics(
            expected_dates=(date(2026, 4, 10),),
            adults_summaries=(
                TravellineAdultsProcessingSummary(
                    adults_count=2,
                    expected_requests_count=1,
                    attempted_count=1,
                    success_count=0,
                    fail_count=1,
                    collected_final_rows_count=0,
                    status="attempt_failed",
                ),
            ),
            empty_dates=(date(2026, 4, 10),),
            per_date_rows=tuple(),
            collection_failure_reasons=("availability_fetch_failed:date=2026-04-10:adults=2:TravellineClientError",),
        ),
        calls=[],
    )
    runner = TravellineRatesParserRunner(source=source, rates_repo=repo, report_repo=report_repo)

    try:
        runner.run(
            start_date=date(2026, 4, 10),
            days_to_collect=1,
            adults_counts=(2,),
        )
    except TravellinePublishValidationError as exc:
        assert "travelline_publish_validation_failed" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected TravellinePublishValidationError")

    assert repo.replaced_rows == []
    assert len(report_repo.saved_reports) == 1
    assert report_repo.saved_reports[0].validation_status == "failed"


def test_runner_publish_allows_completed_zero_rows_when_collection_is_technically_complete() -> None:
    repo = _FakeRatesRepo(rows=[], replaced_rows=[])
    report_repo = _FakeReportRepo(saved_reports=[], marked_fallback_run_ids=[])
    source = _FakeSource(
        transform_result=TravellineRatesTransformResult(
            quotes=tuple(),
            daily_rate_inputs=tuple(),
            daily_rates=tuple(),
            duplicate_keys=tuple(),
            tariff_pairing_anomalies=tuple(),
            category_mapping_mismatches=tuple(),
        ),
        diagnostics=TravellineCollectionDiagnostics(
            expected_dates=(date(2026, 4, 10),),
            adults_summaries=(
                TravellineAdultsProcessingSummary(
                    adults_count=1,
                    expected_requests_count=1,
                    attempted_count=1,
                    success_count=1,
                    fail_count=0,
                    collected_final_rows_count=0,
                    status="completed_zero_rows",
                ),
            ),
            empty_dates=(date(2026, 4, 10),),
            per_date_rows=tuple(),
            collection_failure_reasons=tuple(),
        ),
        calls=[],
    )
    runner = TravellineRatesParserRunner(source=source, rates_repo=repo, report_repo=report_repo)

    rows = runner.run(
        start_date=date(2026, 4, 10),
        days_to_collect=1,
        adults_counts=(1,),
    )

    assert rows == 0
    assert repo.replaced_rows == [[]]
    assert len(report_repo.saved_reports) == 1
    report = report_repo.saved_reports[0]
    assert report.validation_status == "passed"
    assert report.total_final_rows_count == 0
    assert report.dates_with_no_categories_count == 1
    assert report.empty_dates == (date(2026, 4, 10),)
    assert report.adults_summaries[0].status == "completed_zero_rows"


def test_runner_publish_fails_if_expected_adults_were_not_attempted() -> None:
    repo = _FakeRatesRepo(rows=[], replaced_rows=[])
    report_repo = _FakeReportRepo(saved_reports=[], marked_fallback_run_ids=[])
    source = _FakeSource(
        transform_result=TravellineRatesTransformResult(
            quotes=tuple(),
            daily_rate_inputs=tuple(),
            daily_rates=tuple(),
            duplicate_keys=tuple(),
            tariff_pairing_anomalies=tuple(),
            category_mapping_mismatches=tuple(),
        ),
        diagnostics=TravellineCollectionDiagnostics(
            expected_dates=(date(2026, 4, 10),),
            adults_summaries=(
                TravellineAdultsProcessingSummary(
                    adults_count=6,
                    expected_requests_count=1,
                    attempted_count=0,
                    success_count=0,
                    fail_count=0,
                    collected_final_rows_count=0,
                    status="not_attempted",
                ),
            ),
            empty_dates=(date(2026, 4, 10),),
            per_date_rows=tuple(),
            collection_failure_reasons=tuple(),
        ),
        calls=[],
    )
    runner = TravellineRatesParserRunner(source=source, rates_repo=repo, report_repo=report_repo)

    with pytest.raises(TravellinePublishValidationError, match="travelline_publish_validation_failed"):
        runner.run(
            start_date=date(2026, 4, 10),
            days_to_collect=1,
            adults_counts=(6,),
        )

    assert repo.replaced_rows == []
    assert len(report_repo.saved_reports) == 1
    assert report_repo.saved_reports[0].validation_status == "failed"
    assert "adults_6:not_attempted" in report_repo.saved_reports[0].validation_failure_reasons


def test_runner_publish_fails_if_adults_processing_is_partially_failed() -> None:
    repo = _FakeRatesRepo(rows=[], replaced_rows=[])
    report_repo = _FakeReportRepo(saved_reports=[], marked_fallback_run_ids=[])
    source = _FakeSource(
        transform_result=TravellineRatesTransformResult(
            quotes=tuple(),
            daily_rate_inputs=tuple(),
            daily_rates=tuple(),
            duplicate_keys=tuple(),
            tariff_pairing_anomalies=tuple(),
            category_mapping_mismatches=tuple(),
        ),
        diagnostics=TravellineCollectionDiagnostics(
            expected_dates=(date(2026, 4, 10), date(2026, 4, 11)),
            adults_summaries=(
                TravellineAdultsProcessingSummary(
                    adults_count=3,
                    expected_requests_count=2,
                    attempted_count=2,
                    success_count=1,
                    fail_count=1,
                    collected_final_rows_count=0,
                    status="attempt_failed",
                ),
            ),
            empty_dates=(date(2026, 4, 10), date(2026, 4, 11)),
            per_date_rows=tuple(),
            collection_failure_reasons=("availability_fetch_failed:date=2026-04-11:adults=3:TravellineClientError",),
        ),
        calls=[],
    )
    runner = TravellineRatesParserRunner(source=source, rates_repo=repo, report_repo=report_repo)

    with pytest.raises(TravellinePublishValidationError, match="travelline_publish_validation_failed"):
        runner.run(
            start_date=date(2026, 4, 10),
            days_to_collect=2,
            adults_counts=(3,),
        )

    assert repo.replaced_rows == []
    report = report_repo.saved_reports[-1]
    assert report.validation_status == "failed"
    assert "adults_3:attempt_failed" in report.validation_failure_reasons
    assert any(reason.startswith("availability_fetch_failed:") for reason in report.validation_failure_reasons)
    assert report.dates_with_no_categories_count == 2


def test_runner_publish_keeps_threshold_guards_for_anomalies_and_unmapped_categories() -> None:
    repo = _FakeRatesRepo(rows=[], replaced_rows=[])
    report_repo = _FakeReportRepo(saved_reports=[], marked_fallback_run_ids=[])
    source = _FakeSource(
        transform_result=TravellineRatesTransformResult(
            quotes=tuple(),
            daily_rate_inputs=tuple(),
            daily_rates=(
                _rate(
                    stay_date=date(2026, 4, 10),
                    adults=2,
                    category="Deluxe Mountain View",
                    group_id="DELUXE",
                    tariff="breakfast",
                    minor=1_200_000,
                ),
            ),
            duplicate_keys=tuple(),
            tariff_pairing_anomalies=(
                TariffPairingAnomaly(
                    stay_date=date(2026, 4, 10),
                    adults=2,
                    room_type_code="41073",
                    room_type_name="Deluxe Mountain View",
                    observed_prices=(10000.0, 31900.0, 37800.0, 47000.0),
                    quotes_count=4,
                    reason="unsupported_unique_prices",
                ),
            ),
            category_mapping_mismatches=(
                CategoryMappingMismatch(
                    room_type_code="41073",
                    room_type_name="Deluxe Mountain View",
                    fallback_category_id="Deluxe Mountain View",
                ),
            ),
        ),
        calls=[],
    )
    runner = TravellineRatesParserRunner(
        source=source,
        rates_repo=repo,
        report_repo=report_repo,
        max_tariff_pairing_anomalies=0,
        max_unmapped_categories=0,
    )

    with pytest.raises(TravellinePublishValidationError, match="travelline_publish_validation_failed"):
        runner.run(
            start_date=date(2026, 4, 10),
            days_to_collect=1,
            adults_counts=(2,),
        )

    report = report_repo.saved_reports[-1]
    assert "tariff_pairing_anomalies_exceeded:1>0" in report.validation_failure_reasons
    assert "unmapped_categories_exceeded:1>0" in report.validation_failure_reasons
    assert repo.replaced_rows == []


def test_runner_marks_fallback_used_in_report_repository() -> None:
    report_repo = _FakeReportRepo(saved_reports=[], marked_fallback_run_ids=[])
    runner = TravellineRatesParserRunner(
        source=_FakeSource(
            transform_result=TravellineRatesTransformResult(
                quotes=tuple(),
                daily_rate_inputs=tuple(),
                daily_rates=tuple(),
                duplicate_keys=tuple(),
                tariff_pairing_anomalies=tuple(),
                category_mapping_mismatches=tuple(),
            ),
            calls=[],
        ),
        rates_repo=_FakeRatesRepo(rows=[]),
        report_repo=report_repo,
    )
    report = TravellinePublishRunReport(
        run_id="run-1",
        created_at=datetime(2026, 4, 6, 12, 0, 0),
        completed_at=datetime(2026, 4, 6, 12, 5, 0),
        mode="travelline_publish",
        validation_status="failed",
        validation_failure_reasons=("adults_6:attempt_failed",),
        fallback_used=False,
        expected_dates_count=180,
        actual_dates_count=88,
        dates_with_no_categories_count=2,
        total_final_rows_count=4400,
        tariff_pairing_anomalies_count=0,
        unmapped_categories_count=0,
        adults_summaries=tuple(),
        empty_dates=tuple(),
        per_date_rows=tuple(),
    )

    runner.mark_fallback_used(report=report)

    assert report_repo.marked_fallback_run_ids == ["run-1"]
