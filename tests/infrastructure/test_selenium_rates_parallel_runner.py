from __future__ import annotations

import sys
import types
from datetime import date

from src.domain.entities.rate import DailyRate
from src.domain.value_objects.money import Money
from src.infrastructure.parsers.selenium_rates_parser_runner import SeleniumRatesParserRunner
from src.infrastructure.selenium.rates_parallel_runner import (
    ParserRunOutcome,
    RatesParallelRunConfig,
    SeleniumRatesParallelRunner,
)


def _rate(*, stay_date: date, adults_count: int) -> DailyRate:
    return DailyRate(
        date=stay_date,
        category_id=f"Category {adults_count}",
        group_id="DELUXE",
        tariff_code="breakfast",
        adults_count=adults_count,
        price=Money.rub("100"),
        is_available=True,
        is_last_room=False,
    )


def test_runner_processes_each_day_in_two_sequential_batches(monkeypatch):
    monkeypatch.setitem(sys.modules, "selenium", types.SimpleNamespace(webdriver=object()))

    calls: list[tuple[tuple[int, ...], tuple[date, ...], tuple[int, int] | None]] = []

    def fake_run_batch(self, *, webdriver, category_to_group, adults_counts, stay_dates, day_numbering=None):
        calls.append((adults_counts, tuple(stay_dates), day_numbering))
        return [
            ParserRunOutcome(
                adults_count=adults_count,
                rates=(_rate(stay_date=stay_dates[0], adults_count=adults_count),),
                total_found=1,
                total_collected=1,
                failed_fn=None,
                elapsed_seconds=1.0,
            )
            for adults_count in adults_counts
        ]

    monkeypatch.setattr(SeleniumRatesParallelRunner, "_run_batch", fake_run_batch)

    runner = SeleniumRatesParallelRunner(
        RatesParallelRunConfig(
            category_to_group={"Category": "DELUXE"},
            adults_counts=(1, 2, 3, 4, 5, 6),
            days_to_collect=2,
        )
    )

    start_date = date(2026, 4, 1)
    out = runner.run(start_date=start_date)

    assert calls == [
        ((1, 2), (date(2026, 4, 1),), (1, 2)),
        ((3, 4), (date(2026, 4, 1),), (1, 2)),
        ((5, 6), (date(2026, 4, 1),), (1, 2)),
        ((1, 2), (date(2026, 4, 2),), (2, 2)),
        ((3, 4), (date(2026, 4, 2),), (2, 2)),
        ((5, 6), (date(2026, 4, 2),), (2, 2)),
    ]
    assert len(out) == 12


def test_runner_sleeps_between_batches(monkeypatch):
    monkeypatch.setitem(sys.modules, "selenium", types.SimpleNamespace(webdriver=object()))

    sleeps: list[float] = []

    def fake_run_batch(self, *, webdriver, category_to_group, adults_counts, stay_dates, day_numbering=None):
        return [
            ParserRunOutcome(
                adults_count=adults_count,
                rates=(_rate(stay_date=stay_dates[0], adults_count=adults_count),),
                total_found=1,
                total_collected=1,
                failed_fn=None,
                elapsed_seconds=1.0,
            )
            for adults_count in adults_counts
        ]

    monkeypatch.setattr(SeleniumRatesParallelRunner, "_run_batch", fake_run_batch)
    monkeypatch.setattr("src.infrastructure.selenium.rates_parallel_runner.sleep", sleeps.append)

    runner = SeleniumRatesParallelRunner(
        RatesParallelRunConfig(
            category_to_group={"Category": "DELUXE"},
            adults_counts=(1, 2, 3, 4, 5, 6),
            days_to_collect=1,
            batch_pause_seconds=3.0,
        )
    )

    runner.run(start_date=date(2026, 4, 1))

    assert sleeps == [3.0, 3.0]


def test_parser_runner_publishes_snapshot_once_after_full_run(monkeypatch):
    import src.infrastructure.parsers.selenium_rates_parser_runner as parser_module

    captured: dict[str, object] = {}
    rates = [
        _rate(stay_date=date(2026, 4, 1), adults_count=1),
        _rate(stay_date=date(2026, 4, 2), adults_count=4),
    ]

    class FakeRulesRepo:
        def get_category_to_group(self):
            return {"Category": "DELUXE"}

    class FakeParallelRunner:
        def __init__(self, config):
            captured["config"] = config

        def run(self, *, start_date):
            captured["start_date"] = start_date
            return rates

    class FakeDailyRatesRepo:
        def replace_all(self, rows):
            captured.setdefault("replace_calls", []).append(rows)

    monkeypatch.setattr(parser_module, "SeleniumRatesParallelRunner", FakeParallelRunner)
    monkeypatch.setattr(parser_module, "PostgresDailyRatesRepository", FakeDailyRatesRepo)

    runner = SeleniumRatesParserRunner(
        rules_repo=FakeRulesRepo(),
        headless=False,
        wait_seconds=11,
    )

    count = runner.run(
        start_date=date(2026, 4, 1),
        days_to_collect=90,
        adults_counts=(1, 2, 3, 4, 5, 6),
    )

    assert count == 2
    assert captured["start_date"] == date(2026, 4, 1)
    assert isinstance(captured["config"], RatesParallelRunConfig)
    assert captured["config"].days_to_collect == 90
    assert captured["config"].adults_counts == (1, 2, 3, 4, 5, 6)
    assert captured["config"].batch_pause_seconds == 3.0
    assert captured["config"].retry_count == 1
    assert captured["config"].retry_pause_seconds == 1.0
    assert captured["replace_calls"] == [rates]


def test_aggregate_outcomes_tracks_partial_failures_by_day():
    runner = SeleniumRatesParallelRunner(
        RatesParallelRunConfig(
            category_to_group={"Category": "DELUXE"},
            adults_counts=(3,),
            days_to_collect=2,
        )
    )

    stats = runner._aggregate_outcomes_by_adults(
        [
            ParserRunOutcome(
                adults_count=3,
                rates=(_rate(stay_date=date(2026, 4, 1), adults_count=3),),
                stay_date=date(2026, 4, 1),
                total_found=5,
                total_collected=4,
                failed_fn=None,
                elapsed_seconds=10.0,
            ),
            ParserRunOutcome(
                adults_count=3,
                rates=tuple(),
                stay_date=date(2026, 4, 2),
                total_found=0,
                total_collected=0,
                failed_fn="_find_categories",
                elapsed_seconds=3.0,
            ),
        ]
    )

    assert len(stats) == 1
    stat = stats[0]
    assert stat.adults_count == 3
    assert stat.total_days == 2
    assert stat.success_days == 1
    assert stat.failed_days == 1
    assert stat.total_found == 5
    assert stat.total_collected == 4
    assert stat.total_elapsed_seconds == 13.0
    assert stat.errors == ((date(2026, 4, 2), "_find_categories"),)


def test_run_batch_retries_only_failed_worker_without_duplicate_rows(monkeypatch):
    attempts: dict[int, int] = {}
    sleeps: list[float] = []

    def fake_run_single_parser(self, *, webdriver, category_to_group, adults_count, stay_dates, day_numbering=None):
        attempts[adults_count] = attempts.get(adults_count, 0) + 1
        stay_date = stay_dates[0]
        if adults_count == 4 and attempts[adults_count] == 1:
            return ParserRunOutcome(
                adults_count=adults_count,
                rates=(_rate(stay_date=stay_date, adults_count=40),),
                stay_date=stay_date,
                total_found=1,
                total_collected=1,
                failed_fn="get_rates_for_date",
                elapsed_seconds=1.0,
            )
        return ParserRunOutcome(
            adults_count=adults_count,
            rates=(_rate(stay_date=stay_date, adults_count=adults_count),),
            stay_date=stay_date,
            total_found=1,
            total_collected=1,
            failed_fn=None,
            elapsed_seconds=1.0,
        )

    monkeypatch.setattr(SeleniumRatesParallelRunner, "_run_single_parser", fake_run_single_parser)
    monkeypatch.setattr("src.infrastructure.selenium.rates_parallel_runner.sleep", sleeps.append)

    runner = SeleniumRatesParallelRunner(
        RatesParallelRunConfig(
            category_to_group={"Category": "DELUXE"},
            adults_counts=(3, 4),
            days_to_collect=1,
            retry_count=1,
            retry_pause_seconds=1.5,
        )
    )

    outcomes = runner._run_batch(
        webdriver=object(),
        category_to_group={"Category": "DELUXE"},
        adults_counts=(3, 4),
        stay_dates=[date(2026, 4, 1)],
        day_numbering=(1, 1),
    )

    by_adults = {outcome.adults_count: outcome for outcome in outcomes}
    assert attempts == {3: 1, 4: 2}
    assert sleeps == [1.5]
    assert by_adults[3].failed_fn is None
    assert by_adults[4].failed_fn is None
    assert len(by_adults[4].rates) == 1
    assert by_adults[4].rates[0].adults_count == 4
