import pytest
from datetime import date

from src.domain.entities.rate import DailyRate
from src.domain.services.period_builder import BuiltPeriod
from src.domain.services.window_generator import WindowGenerator
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.money import Money


def d(y, m, day):
    return date(y, m, day)


def make_period(start: date, prices: list[str], cat="deluxe", tariff="breakfast") -> BuiltPeriod:
    rates = []
    for i, p in enumerate(prices):
        day = start.fromordinal(start.toordinal() + i)
        rates.append(DailyRate(day, cat, tariff, Money.rub(p), True, False))

    dr = DateRange(rates[0].date, rates[-1].date.fromordinal(rates[-1].date.toordinal() + 1))
    return BuiltPeriod(date_range=dr, rates=rates)


def test_windows_invalid_size_raises():
    period = make_period(d(2026, 2, 10), ["100", "100"])
    with pytest.raises(ValueError):
        WindowGenerator.windows(period, 0)


def test_windows_returns_empty_if_period_shorter_than_window():
    period = make_period(d(2026, 2, 10), ["100", "100", "100"])
    windows = WindowGenerator.windows(period, 4)
    assert windows == []


def test_windows_generates_sliding_windows_size_4_from_6():
    period = make_period(d(2026, 2, 10), ["100", "110", "120", "130", "140", "150"])
    windows = WindowGenerator.windows(period, 4)

    assert len(windows) == 3  # 6-4+1
    assert windows[0].date_range == DateRange(d(2026, 2, 10), d(2026, 2, 14))
    assert windows[1].date_range == DateRange(d(2026, 2, 11), d(2026, 2, 15))
    assert windows[2].date_range == DateRange(d(2026, 2, 12), d(2026, 2, 16))

    assert [r.date for r in windows[0].rates] == [d(2026, 2, 10), d(2026, 2, 11), d(2026, 2, 12), d(2026, 2, 13)]