import pytest
from datetime import date
from decimal import Decimal

from src.domain.entities.rate import DailyRate, DailyRateError
from src.domain.value_objects.money import Money


def d(y, m, day):
    return date(y, m, day)


def test_create_daily_rate_ok_defaults():
    r = DailyRate(
        date=d(2026, 2, 10),
        category_id="deluxe",
        tariff_code="breakfast",
        price=Money.rub("12345.67"),
    )
    assert r.is_available is True
    assert r.is_last_room is False
    assert r.price.amount == Decimal("12345.67")


def test_invalid_date_type_raises():
    with pytest.raises(DailyRateError):
        DailyRate(  # type: ignore
            date="2026-02-10",
            category_id="deluxe",
            tariff_code="breakfast",
            price=Money.rub("100"),
        )


def test_empty_category_id_raises():
    with pytest.raises(DailyRateError):
        DailyRate(
            date=d(2026, 2, 10),
            category_id="   ",
            tariff_code="breakfast",
            price=Money.rub("100"),
        )


def test_empty_tariff_code_raises():
    with pytest.raises(DailyRateError):
        DailyRate(
            date=d(2026, 2, 10),
            category_id="deluxe",
            tariff_code="",
            price=Money.rub("100"),
        )


def test_price_must_be_money():
    with pytest.raises(DailyRateError):
        DailyRate(
            date=d(2026, 2, 10),
            category_id="deluxe",
            tariff_code="breakfast",
            price=12345,  # type: ignore
        )


def test_flags_must_be_bool():
    with pytest.raises(DailyRateError):
        DailyRate(
            date=d(2026, 2, 10),
            category_id="deluxe",
            tariff_code="breakfast",
            price=Money.rub("100"),
            is_available="yes",  # type: ignore
        )

    with pytest.raises(DailyRateError):
        DailyRate(
            date=d(2026, 2, 10),
            category_id="deluxe",
            tariff_code="breakfast",
            price=Money.rub("100"),
            is_last_room=1,  # type: ignore
        )