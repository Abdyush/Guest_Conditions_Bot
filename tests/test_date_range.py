import pytest
from datetime import date

from src.domain.value_objects.date_range import DateRange, DateRangeError


def d(y, m, day):
    return date(y, m, day)


def test_invalid_equal_dates_raises():
    with pytest.raises(DateRangeError):
        DateRange(d(2026, 2, 1), d(2026, 2, 1))


def test_invalid_end_before_start_raises():
    with pytest.raises(DateRangeError):
        DateRange(d(2026, 2, 2), d(2026, 2, 1))


def test_nights_count():
    r = DateRange(d(2026, 2, 1), d(2026, 2, 5))
    assert r.nights == 4


def test_contains_start_included_end_excluded():
    r = DateRange(d(2026, 2, 1), d(2026, 2, 5))
    assert r.contains(d(2026, 2, 1)) is True
    assert r.contains(d(2026, 2, 4)) is True
    assert r.contains(d(2026, 2, 5)) is False


def test_overlaps_true():
    a = DateRange(d(2026, 2, 1), d(2026, 2, 5))
    b = DateRange(d(2026, 2, 4), d(2026, 2, 10))
    assert a.overlaps(b) is True
    assert b.overlaps(a) is True


def test_overlaps_false_when_touching_border():
    a = DateRange(d(2026, 2, 1), d(2026, 2, 5))
    b = DateRange(d(2026, 2, 5), d(2026, 2, 8))
    assert a.overlaps(b) is False
    assert b.overlaps(a) is False


def test_intersection_none_when_no_overlap():
    a = DateRange(d(2026, 2, 1), d(2026, 2, 5))
    b = DateRange(d(2026, 2, 5), d(2026, 2, 8))
    assert a.intersection(b) is None


def test_intersection_returns_common_range():
    a = DateRange(d(2026, 2, 1), d(2026, 2, 10))
    b = DateRange(d(2026, 2, 5), d(2026, 2, 12))
    inter = a.intersection(b)
    assert inter == DateRange(d(2026, 2, 5), d(2026, 2, 10))
    assert inter.nights == 5


def test_iter_nights():
    r = DateRange(d(2026, 2, 1), d(2026, 2, 4))
    assert r.iter_nights() == [d(2026, 2, 1), d(2026, 2, 2), d(2026, 2, 3)]