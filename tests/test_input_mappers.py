from datetime import date
from decimal import Decimal

import pytest

from src.infrastructure.contracts.daily_rate_input import DailyRateInput
from src.infrastructure.contracts.offer_input import OfferInput, DateRangeInput
from src.infrastructure.mappers.to_domain import map_daily_rates, map_offers, InputValidationError
from src.domain.value_objects.date_range import DateRange


def d(y, m, day):
    return date(y, m, day)


def test_map_daily_rates_ok():
    dr = DailyRateInput(
        date=d(2026, 2, 10),
        category_id="deluxe",
        tariff_code="breakfast",
        amount_minor=12345,  # 123.45 RUB
        currency="RUB",
        is_last_room=True,
    )
    out = map_daily_rates([dr])
    assert out[0].price.amount_minor == 12345
    assert out[0].category_id == "deluxe"
    assert out[0].tariff_code == "breakfast"


def test_map_offers_percent_ok():
    o = OfferInput(
        offer_id="o2",
        title="-30% от 5 ночей",
        loyalty_compatible=True,
        min_nights=5,
        booking_period=DateRangeInput(d(2026, 2, 1), d(2026, 2, 28)),
        stay_periods=[DateRangeInput(d(2026, 2, 1), d(2026, 6, 30))],
        discount_type="PERCENT_OFF",
        percent=Decimal("0.30"),
    )
    out = map_offers([o])
    assert out[0].min_nights == 5


def test_map_offers_invalid_percent_raises():
    o = OfferInput(
        offer_id="bad",
        title="bad",
        loyalty_compatible=True,
        min_nights=5,
        booking_period=None,
        stay_periods=[DateRangeInput(d(2026, 2, 1), d(2026, 6, 30))],
        discount_type="PERCENT_OFF",
        percent=Decimal("30"),
    )
    with pytest.raises(InputValidationError):
        map_offers([o])


def test_map_offers_allowed_categories_blocks_other_categories():
    o = OfferInput(
        offer_id="villa_only",
        title="Villa only",
        loyalty_compatible=True,
        min_nights=1,
        booking_period=DateRangeInput(d(2026, 2, 19), d(2026, 3, 28)),
        stay_periods=[DateRangeInput(d(2026, 2, 19), d(2026, 3, 29))],
        discount_type="PERCENT_OFF",
        percent=Decimal("0.30"),
        allowed_categories=["Villa Deluxe"],
    )
    offer = map_offers([o])[0]

    assert offer.allowed_categories == {"Villa Deluxe"}
    assert offer.is_applicable(
        DateRange(d(2026, 2, 20), d(2026, 2, 21)),
        booking_date=d(2026, 2, 20),
        category_id="Deluxe Mountain",
        group_id="DELUXE",
        tariff_code="breakfast",
    ) is False
    assert offer.is_applicable(
        DateRange(d(2026, 2, 20), d(2026, 2, 21)),
        booking_date=d(2026, 2, 20),
        category_id="Villa Deluxe",
        group_id="SOME_OTHER_GROUP",
        tariff_code="breakfast",
    ) is True
