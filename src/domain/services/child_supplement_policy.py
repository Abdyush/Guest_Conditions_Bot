from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.domain.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class PeriodSupplement:
    start: date
    end: date
    amount: Money


class ChildSupplementPolicy:
    def __init__(self, period_rules: list[PeriodSupplement], default_amount: Money):
        self._period_rules = list(period_rules)
        self._default_amount = default_amount

    def amount_for(self, target_date: date) -> Money:
        for period in self._period_rules:
            if period.start <= target_date <= period.end:
                return period.amount
        return self._default_amount
