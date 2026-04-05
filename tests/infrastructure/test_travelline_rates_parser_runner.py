from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.domain.entities.rate import DailyRate
from src.domain.value_objects.money import Money
from src.infrastructure.parsers.travelline_rates_parser_runner import TravellineRatesParserRunner
from src.infrastructure.travelline.models import TravellineRatesTransformResult


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

    def collect_window(self, *, date_from: date, date_to: date, adults_counts: tuple[int, ...]):
        self.calls.append((date_from, date_to, adults_counts))
        return self.transform_result


@dataclass
class _FakeRatesRepo:
    rows: list[DailyRate]

    def get_daily_rates(self, date_from: date, date_to: date) -> list[DailyRate]:
        return list(self.rows)


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
    assert summary_path.exists()
    assert diff_path.exists()

    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_payload["exact_price_matches"] == 1
    assert summary_payload["diff_path"].endswith("travelline_vs_selenium_diff.csv")
    diff_text = diff_path.read_text(encoding="utf-8")
    assert "travelline_only" in diff_text
