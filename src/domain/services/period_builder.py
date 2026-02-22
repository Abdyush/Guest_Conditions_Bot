from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from src.domain.entities.rate import DailyRate
from src.domain.value_objects.date_range import DateRange


class PeriodBuilderError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BuiltPeriod:
    date_range: DateRange
    rates: list[DailyRate]

    @property
    def nights(self) -> int:
        return self.date_range.nights

    @property
    def category_id(self) -> str:
        return self.rates[0].category_id

    @property
    def group_id(self) -> str:
        return self.rates[0].group_id

    @property
    def tariff_code(self) -> str:
        return self.rates[0].tariff_code

    @property
    def adults_count(self) -> int:
        return self.rates[0].adults_count


class PeriodBuilder:
    @staticmethod
    def build(rates: Iterable[DailyRate]) -> list[BuiltPeriod]:
        rates_list = list(rates)
        if not rates_list:
            return []

        groups: dict[tuple[str, str, int], list[DailyRate]] = {}
        for r in rates_list:
            groups.setdefault((r.category_id, r.tariff_code, r.adults_count), []).append(r)

        periods: list[BuiltPeriod] = []
        for group_rates in groups.values():
            periods.extend(PeriodBuilder._build_one_key(group_rates))

        periods.sort(key=lambda p: (p.category_id, p.tariff_code, p.adults_count, p.date_range.start))
        return periods

    @staticmethod
    def _build_one_key(rates: list[DailyRate]) -> list[BuiltPeriod]:
        if not rates:
            return []

        rates.sort(key=lambda x: x.date)

        periods: list[BuiltPeriod] = []
        cur_rates: list[DailyRate] = []

        def flush() -> None:
            nonlocal cur_rates
            if not cur_rates:
                return
            start = cur_rates[0].date
            end = cur_rates[-1].date + timedelta(days=1)
            periods.append(BuiltPeriod(DateRange(start, end), cur_rates))
            cur_rates = []

        prev_date = None
        for r in rates:
            if not r.is_available:
                flush()
                prev_date = None
                continue

            if prev_date is None:
                cur_rates = [r]
                prev_date = r.date
                continue

            if r.date == prev_date + timedelta(days=1):
                cur_rates.append(r)
                prev_date = r.date
            else:
                flush()
                cur_rates = [r]
                prev_date = r.date

        flush()
        return periods
