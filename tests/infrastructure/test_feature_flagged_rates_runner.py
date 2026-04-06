from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from datetime import datetime

import pytest

from src.application.dto.travelline_publish_report import TravellinePublishRunReport
from src.infrastructure.parsers.feature_flagged_rates_runner import FeatureFlaggedRatesRunner
from src.infrastructure.parsers.travelline_rates_parser_runner import TravellinePublishValidationError


@dataclass
class _FakeSeleniumRunner:
    rows: int = 0
    calls: list[tuple[date, int, tuple[int, ...]]] = field(default_factory=list)

    def run(self, *, start_date: date, days_to_collect: int, adults_counts: tuple[int, ...]) -> int:
        self.calls.append((start_date, days_to_collect, adults_counts))
        return self.rows


@dataclass
class _FakeTravellineSummary:
    travelline_total_rows: int = 0
    price_mismatches: int = 0
    tariff_pairing_anomalies: int = 0


@dataclass
class _FakeTravellineCompareResult:
    summary: _FakeTravellineSummary


@dataclass
class _FakeTravellineRunner:
    publish_rows: int = 0
    compare_result: _FakeTravellineCompareResult = field(
        default_factory=lambda: _FakeTravellineCompareResult(summary=_FakeTravellineSummary())
    )
    publish_error: Exception | None = None
    compare_error: Exception | None = None
    run_calls: list[tuple[date, int, tuple[int, ...]]] = field(default_factory=list)
    compare_calls: list[tuple[date, date, tuple[int, ...]]] = field(default_factory=list)
    fallback_marked_run_ids: list[str] = field(default_factory=list)

    def run(self, *, start_date: date, days_to_collect: int, adults_counts: tuple[int, ...]) -> int:
        self.run_calls.append((start_date, days_to_collect, adults_counts))
        if self.publish_error is not None:
            raise self.publish_error
        return self.publish_rows

    def run_compare_only(self, *, date_from: date, date_to: date, adults_counts: tuple[int, ...]):
        self.compare_calls.append((date_from, date_to, adults_counts))
        if self.compare_error is not None:
            raise self.compare_error
        return self.compare_result

    def mark_fallback_used(self, *, report: TravellinePublishRunReport) -> None:
        self.fallback_marked_run_ids.append(report.run_id)


def test_default_config_uses_selenium_only() -> None:
    selenium_runner = _FakeSeleniumRunner(rows=9)
    travelline_runner = _FakeTravellineRunner(publish_rows=11)
    runner = FeatureFlaggedRatesRunner(
        selenium_runner=selenium_runner,
        travelline_runner=travelline_runner,
    )

    rows = runner.run(
        start_date=date(2026, 4, 5),
        days_to_collect=90,
        adults_counts=(1, 2, 3, 4, 5, 6),
    )

    assert rows == 9
    assert len(selenium_runner.calls) == 1
    assert travelline_runner.run_calls == []
    assert travelline_runner.compare_calls == []


def test_explicit_selenium_primary_rollback_mode_still_uses_selenium_only() -> None:
    selenium_runner = _FakeSeleniumRunner(rows=9)
    travelline_runner = _FakeTravellineRunner(publish_rows=42)
    runner = FeatureFlaggedRatesRunner(
        selenium_runner=selenium_runner,
        travelline_runner=travelline_runner,
        use_travelline_rates_source=False,
        travelline_enable_publish=False,
        travelline_compare_only=False,
        travelline_fallback_to_selenium=True,
    )

    rows = runner.run(
        start_date=date(2026, 4, 5),
        days_to_collect=90,
        adults_counts=(1, 2, 3, 4, 5, 6),
    )

    assert rows == 9
    assert len(selenium_runner.calls) == 1
    assert travelline_runner.run_calls == []
    assert travelline_runner.compare_calls == []


def test_travelline_publish_enabled_uses_travelline_publish_path() -> None:
    selenium_runner = _FakeSeleniumRunner(rows=9)
    travelline_runner = _FakeTravellineRunner(publish_rows=42)
    runner = FeatureFlaggedRatesRunner(
        selenium_runner=selenium_runner,
        travelline_runner=travelline_runner,
        use_travelline_rates_source=True,
        travelline_enable_publish=True,
    )

    rows = runner.run(
        start_date=date(2026, 4, 5),
        days_to_collect=90,
        adults_counts=(1, 2, 3, 4, 5, 6),
    )

    assert rows == 42
    assert selenium_runner.calls == []
    assert len(travelline_runner.run_calls) == 1


def test_travelline_compare_only_runs_without_publish() -> None:
    selenium_runner = _FakeSeleniumRunner(rows=9)
    travelline_runner = _FakeTravellineRunner(publish_rows=42)
    runner = FeatureFlaggedRatesRunner(
        selenium_runner=selenium_runner,
        travelline_runner=travelline_runner,
        use_travelline_rates_source=True,
        travelline_compare_only=True,
    )

    rows = runner.run(
        start_date=date(2026, 4, 5),
        days_to_collect=90,
        adults_counts=(1, 2, 3, 4, 5, 6),
    )

    assert rows == 9
    assert len(selenium_runner.calls) == 1
    assert travelline_runner.run_calls == []
    assert travelline_runner.compare_calls == [
        (date(2026, 4, 5), date(2026, 7, 3), (1, 2, 3, 4, 5, 6))
    ]


def test_travelline_failure_with_fallback_enabled_switches_to_selenium(caplog) -> None:
    selenium_runner = _FakeSeleniumRunner(rows=9)
    travelline_runner = _FakeTravellineRunner(
        publish_error=TravellinePublishValidationError(
            "travelline boom",
            report=TravellinePublishRunReport(
                run_id="tlpub_1",
                created_at=datetime(2026, 4, 6, 10, 0, 0),
                completed_at=datetime(2026, 4, 6, 10, 5, 0),
                mode="travelline_publish",
                validation_status="failed",
                validation_failure_reasons=("adults_6:attempt_failed",),
                fallback_used=False,
                expected_dates_count=90,
                actual_dates_count=88,
                dates_with_no_categories_count=2,
                total_final_rows_count=4400,
                tariff_pairing_anomalies_count=0,
                unmapped_categories_count=0,
                adults_summaries=tuple(),
                empty_dates=tuple(),
                per_date_rows=tuple(),
            ),
        )
    )
    runner = FeatureFlaggedRatesRunner(
        selenium_runner=selenium_runner,
        travelline_runner=travelline_runner,
        use_travelline_rates_source=True,
        travelline_enable_publish=True,
        travelline_fallback_to_selenium=True,
    )

    with caplog.at_level(logging.INFO):
        rows = runner.run(
            start_date=date(2026, 4, 5),
            days_to_collect=90,
            adults_counts=(1, 2, 3, 4, 5, 6),
        )

    assert rows == 9
    assert len(selenium_runner.calls) == 1
    assert "travelline_fallback_triggered=true" in caplog.text
    assert travelline_runner.fallback_marked_run_ids == ["tlpub_1"]


def test_travelline_failure_with_fallback_disabled_raises() -> None:
    selenium_runner = _FakeSeleniumRunner(rows=9)
    travelline_runner = _FakeTravellineRunner(publish_error=RuntimeError("travelline boom"))
    runner = FeatureFlaggedRatesRunner(
        selenium_runner=selenium_runner,
        travelline_runner=travelline_runner,
        use_travelline_rates_source=True,
        travelline_enable_publish=True,
        travelline_fallback_to_selenium=False,
    )

    with pytest.raises(RuntimeError, match="travelline boom"):
        runner.run(
            start_date=date(2026, 4, 5),
            days_to_collect=90,
            adults_counts=(1, 2, 3, 4, 5, 6),
        )

    assert selenium_runner.calls == []
