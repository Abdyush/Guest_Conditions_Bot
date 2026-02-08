import pytest
from datetime import date
from decimal import Decimal

from src.domain.entities.rate import DailyRate
from src.domain.services.period_builder import BuiltPeriod
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.money import Money
from src.domain.value_objects.discount import PercentOff, PayXGetY
from src.domain.entities.offer import Offer
from src.domain.value_objects.loyalty import LoyaltyPolicy, LoyaltyStatus
from src.domain.services.pricing_service import PricingService, PricingContext


def d(y, m, day):
    return date(y, m, day)


def make_period(prices: list[str], *, cat="deluxe", tariff="breakfast", start=date(2026, 2, 10)):
    rates = []
    for i, p in enumerate(prices):
        day = start.fromordinal(start.toordinal() + i)
        rates.append(DailyRate(day, cat, tariff, Money.rub(p), True, False))
    dr = DateRange(rates[0].date, rates[-1].date.fromordinal(rates[-1].date.toordinal() + 1))
    return BuiltPeriod(dr, rates)


def policy():
    return LoyaltyPolicy({LoyaltyStatus.GOLD: Decimal("0.10")})


def test_offer_blocked_by_booking_period():
    service = PricingService(policy())
    period = make_period(["100", "100", "100", "100"])

    offer = Offer(
        id="o1",
        title="4=3",
        description="",
        discount=PayXGetY(3, 4),
        stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
        booking_period=DateRange(d(2026, 1, 1), d(2026, 1, 10)),
        min_nights=4,
        loyalty_compatible=True,
    )

    # сегодня вне booking window => оффер не применится
    q = service.price_period(period, offer=offer, ctx=PricingContext(booking_date=d(2026, 2, 5), loyalty_status=LoyaltyStatus.GOLD))
    assert q.offer_discount.amount == Decimal("0.00")
    assert q.total_after.amount == Decimal("360.00")  # только лояльность 10% от 400


def test_offer_then_loyalty_when_compatible():
    service = PricingService(policy())
    period = make_period(["100", "100", "100", "100"])

    offer = Offer(
        id="o2",
        title="30% off",
        description="",
        discount=PercentOff(Decimal("0.30")),  # 400 -> 280
        stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
        booking_period=None,
        min_nights=1,
        loyalty_compatible=True,
    )

    q = service.price_period(period, offer=offer, ctx=PricingContext(booking_date=d(2026, 2, 5), loyalty_status=LoyaltyStatus.GOLD))
    assert q.total_before.amount == Decimal("400.00")
    assert q.total_after.amount == Decimal("252.00")  # 280 - 10%
    assert q.offer_discount.amount == Decimal("120.00")
    assert q.loyalty_discount.amount == Decimal("28.00")


def test_loyalty_not_applied_when_offer_not_compatible():
    service = PricingService(policy())
    period = make_period(["100", "100"])

    offer = Offer(
        id="o3",
        title="30% off",
        description="",
        discount=PercentOff(Decimal("0.30")),  # 200 -> 140
        stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
        min_nights=1,
        loyalty_compatible=False,
    )

    q = service.price_period(period, offer=offer, ctx=PricingContext(booking_date=d(2026, 2, 5), loyalty_status=LoyaltyStatus.GOLD))
    assert q.total_after.amount == Decimal("140.00")
    assert q.loyalty_discount.amount == Decimal("0.00")