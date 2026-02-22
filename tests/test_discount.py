from decimal import Decimal

from src.domain.value_objects.discount import FixedOff, PayXGetY, PercentOff
from src.domain.value_objects.money import Money


def test_percent_off_per_night_multiplier():
    assert PercentOff(Decimal("0.15")).per_night_multiplier() == Decimal("0.85")


def test_pay_x_get_y_per_night_multiplier():
    assert PayXGetY(3, 4).per_night_multiplier() == Decimal("0.75")


def test_fixed_off_per_night_multiplier_not_supported():
    assert FixedOff(Money.rub("10.00")).per_night_multiplier() is None

