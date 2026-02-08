from __future__ import annotations

from datetime import timedelta

from src.domain.services.period_builder import BuiltPeriod
from src.domain.value_objects.date_range import DateRange


class WindowGenerator:
    """
    Делает "окна" фиксированной длины из одного длинного периода доступности.

    Важно:
    - period должен быть уже "чистым": одна категория + один тариф, только доступные ночи,
      и rates внутри отсортированы по датам (это гарантирует PeriodBuilder).
    - window_size = min_nights оффера (по твоему правилу).
    - шаг = 1 ночь (скользящее окно).
    """

    @staticmethod
    def windows(period: BuiltPeriod, window_size: int) -> list[BuiltPeriod]:
        if window_size <= 0:
            raise ValueError("window_size must be > 0")

        nights = period.nights
        if nights < window_size:
            return []

        rates = period.rates
        res: list[BuiltPeriod] = []

        # i = индекс начала окна
        for i in range(0, len(rates) - window_size + 1):
            window_rates = rates[i : i + window_size]
            start = window_rates[0].date
            end = window_rates[-1].date + timedelta(days=1)
            res.append(BuiltPeriod(date_range=DateRange(start, end), rates=window_rates))

        return res
