from __future__ import annotations

import sys
import types
from datetime import date

from src.domain.entities.rate import DailyRate
from src.domain.value_objects.money import Money
from src.infrastructure.parsers.selenium_rates_parser_runner import (
    SeleniumRatesParserRunner,
    build_rates_segments,
)
from src.infrastructure.selenium.rates_parallel_runner import RatesParallelRunConfig, SeleniumRatesParallelRunner


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


def test_build_rates_segments_splits_90_days_into_three_segments_of_30():
    segments = build_rates_segments(
        start_date=date(2026, 4, 1),
        days_to_collect=90,
        segment_size_days=30,
    )

    assert [(segment.start_date, segment.days_to_collect) for segment in segments] == [
        (date(2026, 4, 1), 30),
        (date(2026, 5, 1), 30),
        (date(2026, 5, 31), 30),
    ]
    assert [(segment.start_day_number, segment.end_day_number) for segment in segments] == [
        (1, 30),
        (31, 60),
        (61, 90),
    ]


def test_build_rates_segments_keeps_last_partial_segment():
    segments = build_rates_segments(
        start_date=date(2026, 4, 1),
        days_to_collect=65,
        segment_size_days=30,
    )

    assert [(segment.start_date, segment.days_to_collect) for segment in segments] == [
        (date(2026, 4, 1), 30),
        (date(2026, 5, 1), 30),
        (date(2026, 5, 31), 5),
    ]
    assert [(segment.start_day_number, segment.end_day_number) for segment in segments] == [
        (1, 30),
        (31, 60),
        (61, 65),
    ]


def test_parallel_runner_uses_old_profile_single_executor_for_all_adults(monkeypatch):
    monkeypatch.setitem(sys.modules, "selenium", types.SimpleNamespace(webdriver=object()))

    calls: list[tuple[int, tuple[date, ...]]] = []

    def fake_run_single_parser(self, *, webdriver, category_to_group, adults_count, stay_dates):
        calls.append((adults_count, tuple(stay_dates)))
        return types.SimpleNamespace(
            adults_count=adults_count,
            rates=tuple(_rate(stay_date=stay_date, adults_count=adults_count) for stay_date in stay_dates),
            total_found=len(stay_dates),
            total_collected=len(stay_dates),
            failed_fn=None,
            elapsed_seconds=1.0,
        )

    monkeypatch.setattr(SeleniumRatesParallelRunner, "_run_single_parser", fake_run_single_parser)

    runner = SeleniumRatesParallelRunner(
        RatesParallelRunConfig(
            category_to_group={"Category": "DELUXE"},
            adults_counts=(1, 2, 3, 4, 5, 6),
            days_to_collect=30,
        )
    )

    out = runner.run(start_date=date(2026, 4, 1))

    assert len(calls) == 6
    assert {adults_count for adults_count, _ in calls} == {1, 2, 3, 4, 5, 6}
    assert all(len(stay_dates) == 30 for _, stay_dates in calls)
    assert len(out) == 180


def test_parser_runner_runs_three_segments_and_publishes_once(monkeypatch):
    import src.infrastructure.parsers.selenium_rates_parser_runner as parser_module

    captured: dict[str, object] = {"run_calls": [], "replace_calls": []}

    class FakeRulesRepo:
        def get_category_to_group(self):
            return {"Category": "DELUXE"}

    class FakeParallelRunner:
        def __init__(self, config):
            captured.setdefault("configs", []).append(config)

        def run(self, *, start_date):
            captured["run_calls"].append(start_date)
            return [_rate(stay_date=start_date, adults_count=1)]

    class FakeDailyRatesRepo:
        def replace_all(self, rows):
            captured["replace_calls"].append(rows)

    monkeypatch.setattr(parser_module, "SeleniumRatesParallelRunner", FakeParallelRunner)
    monkeypatch.setattr(parser_module, "PostgresDailyRatesRepository", FakeDailyRatesRepo)
    monkeypatch.setattr(parser_module, "sleep", lambda *_args: None)

    runner = SeleniumRatesParserRunner(
        rules_repo=FakeRulesRepo(),
        headless=False,
        wait_seconds=11,
        segment_size_days=30,
        segment_pause_seconds=5.0,
    )

    count = runner.run(
        start_date=date(2026, 4, 1),
        days_to_collect=90,
        adults_counts=(1, 2, 3, 4, 5, 6),
    )

    assert count == 3
    assert captured["run_calls"] == [date(2026, 4, 1), date(2026, 5, 1), date(2026, 5, 31)]
    assert [config.days_to_collect for config in captured["configs"]] == [30, 30, 30]
    assert all(config.adults_counts == (1, 2, 3, 4, 5, 6) for config in captured["configs"])
    assert all(config.headless is False for config in captured["configs"])
    assert all(config.wait_seconds == 11 for config in captured["configs"])
    assert len(captured["replace_calls"]) == 1
    assert len(captured["replace_calls"][0]) == 3


def test_parser_runner_keeps_single_publish_for_partial_last_segment(monkeypatch):
    import src.infrastructure.parsers.selenium_rates_parser_runner as parser_module

    captured: dict[str, object] = {"configs": [], "replace_calls": []}

    class FakeRulesRepo:
        def get_category_to_group(self):
            return {"Category": "DELUXE"}

    class FakeParallelRunner:
        def __init__(self, config):
            captured["configs"].append(config)

        def run(self, *, start_date):
            return [_rate(stay_date=start_date, adults_count=2)]

    class FakeDailyRatesRepo:
        def replace_all(self, rows):
            captured["replace_calls"].append(rows)

    monkeypatch.setattr(parser_module, "SeleniumRatesParallelRunner", FakeParallelRunner)
    monkeypatch.setattr(parser_module, "PostgresDailyRatesRepository", FakeDailyRatesRepo)
    monkeypatch.setattr(parser_module, "sleep", lambda *_args: None)

    runner = SeleniumRatesParserRunner(
        rules_repo=FakeRulesRepo(),
        segment_size_days=30,
        segment_pause_seconds=0.0,
    )

    count = runner.run(
        start_date=date(2026, 4, 1),
        days_to_collect=65,
        adults_counts=(1, 2, 3, 4, 5, 6),
    )

    assert count == 3
    assert [config.days_to_collect for config in captured["configs"]] == [30, 30, 5]
    assert len(captured["replace_calls"]) == 1
    assert len(captured["replace_calls"][0]) == 3
