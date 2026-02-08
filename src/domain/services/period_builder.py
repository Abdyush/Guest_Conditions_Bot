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
    """
    Период проживания + связанные с ним дневные цены.
    DateRange: [start, end)
    rates: список DailyRate в порядке дат, длина == nights
    """
    date_range: DateRange
    rates: list[DailyRate]

    @property
    def nights(self) -> int:
        return self.date_range.nights


class PeriodBuilder:
    """
    Строит подряд идущие периоды из DailyRate.

    ВАЖНО:
    - вход должен быть для одной пары (category_id, tariff_code)
      (это упрощает и исключает смешивание тарифов)
    - если попадутся чужие category/tariff — кидаем ошибку
    """

    @staticmethod
    def build(rates: Iterable[DailyRate]) -> list[BuiltPeriod]:
        rates_list = list(rates)
        if not rates_list:
            return []

        # проверяем единый ключ (category_id, tariff_code)
        key = (rates_list[0].category_id, rates_list[0].tariff_code)
        for r in rates_list:
            if (r.category_id, r.tariff_code) != key:
                raise PeriodBuilderError(
                    "All DailyRate items must have the same (category_id, tariff_code)"
                )

        # сортируем по дате (на вход можно подавать как угодно)
        rates_list.sort(key=lambda x: x.date)

        periods: list[BuiltPeriod] = []
        cur_rates: list[DailyRate] = []

        def flush() -> None:
            nonlocal cur_rates
            if not cur_rates:
                return
            start = cur_rates[0].date
            # end = last_date + 1 день
            end = cur_rates[-1].date + timedelta(days=1)
            periods.append(BuiltPeriod(DateRange(start, end), cur_rates))
            cur_rates = []

        prev_date = None
        for r in rates_list:
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