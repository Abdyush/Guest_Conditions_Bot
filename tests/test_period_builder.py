import pytest
from datetime import date

from src.domain.entities.rate import DailyRate
from src.domain.services.period_builder import PeriodBuilder, BuiltPeriod
from src.domain.value_objects.money import Money


def d(y, m, day):
    return date(y, m, day)


def r(day: date, *, cat="deluxe", tariff="breakfast", price="100.00", available=True) -> DailyRate:
    return DailyRate(
        day,
        cat,
        tariff,
        Money.rub(price),
        available,
        False,
    )


def key(p: BuiltPeriod) -> tuple[str, str]:
    return (p.rates[0].category_id, p.rates[0].tariff_code)


def test_empty_input_returns_empty():
    assert PeriodBuilder.build([]) == []


def test_single_night_creates_one_period():
    periods = PeriodBuilder.build([r(d(2026, 2, 10))])
    assert len(periods) == 1
    assert periods[0].nights == 1
    assert periods[0].date_range.start == d(2026, 2, 10)
    assert periods[0].date_range.end == d(2026, 2, 11)


def test_contiguous_nights_create_one_period():
    rates = [r(d(2026, 2, 10)), r(d(2026, 2, 11)), r(d(2026, 2, 12))]
    periods = PeriodBuilder.build(rates)

    assert len(periods) == 1
    p = periods[0]
    assert p.nights == 3
    assert [x.date for x in p.rates] == [d(2026, 2, 10), d(2026, 2, 11), d(2026, 2, 12)]
    assert p.date_range.start == d(2026, 2, 10)
    assert p.date_range.end == d(2026, 2, 13)


def test_gap_splits_periods():
    rates = [r(d(2026, 2, 10)), r(d(2026, 2, 11)), r(d(2026, 2, 13))]
    periods = PeriodBuilder.build(rates)

    assert len(periods) == 2
    assert periods[0].date_range.start == d(2026, 2, 10)
    assert periods[0].date_range.end == d(2026, 2, 12)  # 10,11
    assert periods[1].date_range.start == d(2026, 2, 13)
    assert periods[1].date_range.end == d(2026, 2, 14)


def test_is_available_false_splits_periods():
    rates = [
        r(d(2026, 2, 10)),
        r(d(2026, 2, 11), available=False),
        r(d(2026, 2, 12)),
    ]
    periods = PeriodBuilder.build(rates)

    assert len(periods) == 2
    assert [x.date for x in periods[0].rates] == [d(2026, 2, 10)]
    assert [x.date for x in periods[1].rates] == [d(2026, 2, 12)]


def test_unsorted_input_is_sorted_inside_builder():
    rates = [r(d(2026, 2, 12)), r(d(2026, 2, 10)), r(d(2026, 2, 11))]
    periods = PeriodBuilder.build(rates)

    assert len(periods) == 1
    assert [x.date for x in periods[0].rates] == [d(2026, 2, 10), d(2026, 2, 11), d(2026, 2, 12)]


def test_mixed_category_or_tariff_is_grouped_not_mixed():
    rates = [
        r(d(2026, 2, 10), cat="deluxe", tariff="breakfast"),
        r(d(2026, 2, 11), cat="family", tariff="breakfast"),
        r(d(2026, 2, 12), cat="deluxe", tariff="full"),
    ]
    periods = PeriodBuilder.build(rates)

    keys = {key(p) for p in periods}
    assert keys == {("deluxe", "breakfast"), ("family", "breakfast"), ("deluxe", "full")}

    # каждый период однороден
    for p in periods:
        k = key(p)
        assert all((x.category_id, x.tariff_code) == k for x in p.rates)


def test_builder_returns_stable_order_by_key_and_start():
    rates = [
        r(d(2026, 2, 11), cat="b", tariff="t"),
        r(d(2026, 2, 10), cat="a", tariff="t"),
        r(d(2026, 2, 12), cat="a", tariff="t"),
    ]
    periods = PeriodBuilder.build(rates)

    # ожидаем сортировку по (category_id, tariff_code, start_date)
    assert [(p.rates[0].category_id, p.rates[0].tariff_code, p.date_range.start) for p in periods] == [
        ("a", "t", d(2026, 2, 10)),
        ("a", "t", d(2026, 2, 12)),
        ("b", "t", d(2026, 2, 11)),
    ]


def test_adults_count_is_part_of_grouping_key():
    rates = [
        DailyRate(d(2026, 2, 10), "deluxe", "breakfast", Money.rub("100"), True, False, adults_count=2),
        DailyRate(d(2026, 2, 11), "deluxe", "breakfast", Money.rub("100"), True, False, adults_count=3),
    ]
    periods = PeriodBuilder.build(rates)
    assert len(periods) == 2
    assert {p.adults_count for p in periods} == {2, 3}
