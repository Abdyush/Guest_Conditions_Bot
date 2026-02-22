import pytest
from decimal import Decimal

from src.domain.value_objects.money import Money, MoneyError


def test_rub_from_int():
    m = Money.rub(123)
    assert m.amount == Decimal("123.00")
    assert m.currency == "RUB"


def test_rub_from_decimal_quantizes_to_kopeks():
    m = Money.rub(Decimal("123.4"))
    assert m.amount == Decimal("123.40")


def test_rub_from_str_dot():
    m = Money.rub("123.45")
    assert m.amount == Decimal("123.45")


def test_rub_from_str_comma():
    m = Money.rub("123,45")
    assert m.amount == Decimal("123.45")


def test_rub_from_str_spaces():
    m = Money.rub("  1 234,50 ")
    assert m.amount == Decimal("1234.50")


def test_reject_float_input():
    with pytest.raises(MoneyError):
        Money.rub(12.34)  # float запрещаем, чтобы не ловить бинарные хвосты


def test_addition_same_currency():
    a = Money.rub("10.00")
    b = Money.rub("2.30")
    assert (a + b).amount == Decimal("12.30")


def test_subtraction_same_currency():
    a = Money.rub("10.00")
    b = Money.rub("2.30")
    assert (a - b).amount == Decimal("7.70")


def test_currency_mismatch_raises_on_add():
    # если в твоём Money пока вообще запрещены валюты кроме RUB,
    # этот тест можно удалить. Он полезен, когда появится поддержка валют.
    a = Money(Decimal("10.00"), "RUB")
    with pytest.raises(MoneyError):
        _ = a + Money(Decimal("1.00"), "USD")


def test_negation():
    a = Money.rub("10.00")
    assert (-a).amount == Decimal("-10.00")


def test_mul_by_int():
    a = Money.rub("10.25")
    assert (a * 2).amount == Decimal("20.50")


def test_mul_by_decimal():
    a = Money.rub("10.00")
    assert (a * Decimal("0.75")).amount == Decimal("7.50")


def test_percent_off_30_percent():
    a = Money.rub("100.00")
    assert a.percent_off(Decimal("0.30")).amount == Decimal("70.00")


def test_percent_off_rounding_half_up():
    # 0.01 * 0.5 = 0.005 -> 0.01 при ROUND_HALF_UP
    a = Money.rub("0.01")
    assert a.percent_off(Decimal("0.50")).amount == Decimal("0.01")


def test_percent_off_bounds():
    a = Money.rub("100.00")
    with pytest.raises(MoneyError):
        a.percent_off(Decimal("-0.01"))
    with pytest.raises(MoneyError):
        a.percent_off(Decimal("1.01"))


def test_fixed_off_simple():
    a = Money.rub("100.00")
    d = Money.rub("15.25")
    assert a.fixed_off(d).amount == Decimal("84.75")


def test_fixed_off_floor_zero_default():
    a = Money.rub("10.00")
    d = Money.rub("15.00")
    assert a.fixed_off(d).amount == Decimal("0.00")


def test_fixed_off_can_go_negative_if_floor_zero_false():
    a = Money.rub("10.00")
    d = Money.rub("15.00")
    assert a.fixed_off(d, floor_zero=False).amount == Decimal("-5.00")


def test_comparisons():
    a = Money.rub("10.00")
    b = Money.rub("10.01")
    assert a < b
    assert a <= b
    assert b > a
    assert b >= a


def test_is_zero():
    assert Money.rub("0").is_zero() is True
    assert Money.rub("0.01").is_zero() is False


def test_str_format():
    assert str(Money.rub("1234.5")) == "1234.50 RUB"


def test_invalid_amount_nan_raises():
    with pytest.raises(MoneyError):
        Money(Decimal("NaN"), "RUB")


def test_invalid_amount_infinite_raises():
    with pytest.raises(MoneyError):
        Money(Decimal("Infinity"), "RUB")


def test_round_rubles_half_up_down():
    assert Money.rub("26000.40").round_rubles() == 26000


def test_round_rubles_half_up_up():
    assert Money.rub("25999.60").round_rubles() == 26000
