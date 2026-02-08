import pytest
from datetime import date
from decimal import Decimal

from src.domain.entities.rate import DailyRate
from src.domain.services.period_builder import PeriodBuilder, PeriodBuilderError
from src.domain.value_objects.money import Money


def d(y, m, day):
    return date(y, m, day)


def r(dt, price="100.00", cat="deluxe", tariff="breakfast", avail=True, last=False):
    return DailyRate(
        date=dt,
        category_id=cat,
        tariff_code=tariff,
        price=Money.rub(price),
        is_available=avail,
        is_last_room=last,
    )


def test_empty_input_returns_empty():
    assert PeriodBuilder.build([]) == []


def test_single_night_period():
    periods = PeriodBuilder.build([r(d(2026, 2, 10))])
    assert len(periods) == 1
    p = periods[0]
    assert p.date_range.start == d(2026, 2, 10)
    assert p.date_range.end == d(2026, 2, 11)
    assert p.nights == 1
    assert len(p.rates) == 1


def test_build_two_periods_on_gap_in_dates():
    rates = [
        r(d(2026, 2, 10), "100"),
        r(d(2026, 2, 11), "110"),
        r(d(2026, 2, 13), "130"),
        r(d(2026, 2, 14), "140"),
    ]
    periods = PeriodBuilder.build(rates)
    assert len(periods) == 2

    p1, p2 = periods
    assert p1.date_range.start == d(2026, 2, 10)
    assert p1.date_range.end == d(2026, 2, 12)
    assert p1.nights == 2
    assert [x.date for x in p1.rates] == [d(2026, 2, 10), d(2026, 2, 11)]

    assert p2.date_range.start == d(2026, 2, 13)
    assert p2.date_range.end == d(2026, 2, 15)
    assert p2.nights == 2
    assert [x.date for x in p2.rates] == [d(2026, 2, 13), d(2026, 2, 14)]


def test_unavailable_breaks_period():
    rates = [
        r(d(2026, 2, 10), "100", avail=True),
        r(d(2026, 2, 11), "110", avail=False),
        r(d(2026, 2, 12), "120", avail=True),
    ]
    periods = PeriodBuilder.build(rates)
    assert len(periods) == 2

    assert periods[0].date_range.start == d(2026, 2, 10)
    assert periods[0].date_range.end == d(2026, 2, 11)
    assert periods[0].nights == 1

    assert periods[1].date_range.start == d(2026, 2, 12)
    assert periods[1].date_range.end == d(2026, 2, 13)
    assert periods[1].nights == 1


def test_input_can_be_unsorted_builder_sorts():
    rates = [
        r(d(2026, 2, 12), "120"),
        r(d(2026, 2, 10), "100"),
        r(d(2026, 2, 11), "110"),
    ]
    periods = PeriodBuilder.build(rates)
    assert len(periods) == 1
    assert [x.date for x in periods[0].rates] == [d(2026, 2, 10), d(2026, 2, 11), d(2026, 2, 12)]


def test_mixed_category_or_tariff_raises():
    rates = [
        r(d(2026, 2, 10), cat="deluxe", tariff="breakfast"),
        r(d(2026, 2, 11), cat="family", tariff="breakfast"),
    ]
    with pytest.raises(PeriodBuilderError):
        PeriodBuilder.build(rates)

    rates2 = [
        r(d(2026, 2, 10), cat="deluxe", tariff="breakfast"),
        r(d(2026, 2, 11), cat="deluxe", tariff="full"),
    ]
    with pytest.raises(PeriodBuilderError):
        PeriodBuilder.build(rates2)


def test_rates_preserve_prices():
    rates = [
        r(d(2026, 2, 10), "100.10"),
        r(d(2026, 2, 11), "200.20"),
    ]
    periods = PeriodBuilder.build(rates)
    assert len(periods) == 1
    amounts = [x.price.amount for x in periods[0].rates]
    assert amounts == [Decimal("100.10"), Decimal("200.20")]