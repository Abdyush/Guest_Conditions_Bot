from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from time import sleep

from src.domain.entities.rate import DailyRate
from src.infrastructure.repositories.postgres_daily_rates_repository import PostgresDailyRatesRepository
from src.infrastructure.repositories.postgres_rules_repository import PostgresRulesRepository
from src.infrastructure.selenium.rates_parallel_runner import RatesParallelRunConfig, SeleniumRatesParallelRunner


@dataclass(frozen=True, slots=True)
class RatesSegment:
    index: int
    total: int
    start_date: date
    days_to_collect: int
    start_day_number: int
    end_day_number: int


def build_rates_segments(*, start_date: date, days_to_collect: int, segment_size_days: int) -> list[RatesSegment]:
    if days_to_collect <= 0:
        raise ValueError("days_to_collect must be > 0")
    if segment_size_days <= 0:
        raise ValueError("segment_size_days must be > 0")

    segments: list[RatesSegment] = []
    current_start = start_date
    remaining_days = days_to_collect
    segment_index = 1
    start_day_number = 1

    while remaining_days > 0:
        segment_days = min(segment_size_days, remaining_days)
        end_day_number = start_day_number + segment_days - 1
        segments.append(
            RatesSegment(
                index=segment_index,
                total=0,
                start_date=current_start,
                days_to_collect=segment_days,
                start_day_number=start_day_number,
                end_day_number=end_day_number,
            )
        )
        current_start = current_start + timedelta(days=segment_days)
        remaining_days -= segment_days
        start_day_number = end_day_number + 1
        segment_index += 1

    total_segments = len(segments)
    return [
        RatesSegment(
            index=segment.index,
            total=total_segments,
            start_date=segment.start_date,
            days_to_collect=segment.days_to_collect,
            start_day_number=segment.start_day_number,
            end_day_number=segment.end_day_number,
        )
        for segment in segments
    ]


@dataclass(frozen=True, slots=True)
class SeleniumRatesParserRunner:
    rules_repo: PostgresRulesRepository
    headless: bool = True
    wait_seconds: int = 20
    batch_pause_seconds: float = 3.0
    retry_count: int = 1
    retry_pause_seconds: float = 1.0
    segment_size_days: int = 30
    segment_pause_seconds: float = 5.0

    def run(self, *, start_date: date, days_to_collect: int, adults_counts: tuple[int, ...]) -> int:
        category_to_group = self.rules_repo.get_category_to_group()
        segments = build_rates_segments(
            start_date=start_date,
            days_to_collect=days_to_collect,
            segment_size_days=self.segment_size_days,
        )
        all_rates: list[DailyRate] = []

        for segment in segments:
            self._log_segment_start(segment=segment, days_total=days_to_collect)
            runner = SeleniumRatesParallelRunner(
                RatesParallelRunConfig(
                    category_to_group=category_to_group,
                    adults_counts=adults_counts,
                    days_to_collect=segment.days_to_collect,
                    headless=self.headless,
                    wait_seconds=self.wait_seconds,
                )
            )
            all_rates.extend(runner.run(start_date=segment.start_date))
            self._log_segment_finish(segment=segment)
            if segment.index < segment.total and self.segment_pause_seconds > 0:
                print(f"[СЕГМЕНТ {segment.index}/{segment.total}] пауза {self.segment_pause_seconds:.1f} сек.")
                sleep(self.segment_pause_seconds)

        repo = PostgresDailyRatesRepository()
        repo.replace_all(all_rates)
        return len(all_rates)

    @staticmethod
    def _log_segment_start(*, segment: RatesSegment, days_total: int) -> None:
        print(
            f"[СЕГМЕНТ {segment.index}/{segment.total}] старт — "
            f"дни {segment.start_day_number}-{segment.end_day_number} из {days_total}"
        )

    @staticmethod
    def _log_segment_finish(*, segment: RatesSegment) -> None:
        print(f"[СЕГМЕНТ {segment.index}/{segment.total}] завершён")
