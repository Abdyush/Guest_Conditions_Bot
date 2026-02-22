from datetime import date
from decimal import Decimal

from src.domain.entities.offer import Offer
from src.domain.entities.rate import DailyRate
from src.domain.services.date_price_selector import DatePriceSelector
from src.domain.services.period_builder import PeriodBuilder
from src.domain.services.pricing_service import PricingContext, PricingService
from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.discount import PayXGetY, PercentOff
from src.domain.value_objects.loyalty import LoyaltyPolicy, LoyaltyStatus
from src.domain.value_objects.money import Money


def d(y, m, day):
    return date(y, m, day)


def make_rates(start: date, prices: list[str], cat="deluxe", group="DELUXE", tariff="breakfast", adults=2) -> list[DailyRate]:
    rates = []
    for i, p in enumerate(prices):
        day = start.fromordinal(start.toordinal() + i)
        rates.append(
            DailyRate(
                date=day,
                category_id=cat,
                group_id=group,
                tariff_code=tariff,
                adults_count=adults,
                price=Money.rub(p),
                is_available=True,
                is_last_room=False,
            )
        )
    return rates


def loyalty_policy():
    return LoyaltyPolicy({LoyaltyStatus.GOLD: Decimal("0.10")})


def k(day: date, cat: str = "deluxe", tariff: str = "breakfast", adults: int = 2):
    return (day, cat, tariff, adults)


def test_loyalty_only_per_date_when_no_offers():
    service = PricingService(loyalty_policy())
    selector = DatePriceSelector(service)

    rates = make_rates(d(2026, 2, 10), ["110", "90", "100"])
    periods = PeriodBuilder.build(rates)

    ctx = PricingContext(booking_date=d(2026, 2, 5), loyalty_status=LoyaltyStatus.GOLD)
    best = selector.best_prices_by_date(daily_rates=rates, periods=periods, offers=[], ctx=ctx)

    assert best[k(d(2026, 2, 10))].new_price.amount == Decimal("99.00")
    assert best[k(d(2026, 2, 11))].new_price.amount == Decimal("81.00")
    assert best[k(d(2026, 2, 12))].new_price.amount == Decimal("90.00")
    assert best[k(d(2026, 2, 10))].offer_id is None


def test_offer_not_applied_when_period_shorter_than_min_nights():
    service = PricingService(loyalty_policy())
    selector = DatePriceSelector(service)

    rates = make_rates(d(2026, 2, 10), ["100", "100", "100"])
    periods = PeriodBuilder.build(rates)

    offer = Offer(
        id="o1",
        title="4=3",
        description="",
        discount=PayXGetY(3, 4),
        stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
        booking_period=DateRange(d(2026, 2, 1), d(2026, 2, 28)),
        min_nights=4,
        loyalty_compatible=True,
    )

    ctx = PricingContext(booking_date=d(2026, 2, 5), loyalty_status=LoyaltyStatus.GOLD)
    best = selector.best_prices_by_date(daily_rates=rates, periods=periods, offers=[offer], ctx=ctx)

    for day in [d(2026, 2, 10), d(2026, 2, 11), d(2026, 2, 12)]:
        assert best[k(day)].new_price.amount == Decimal("90.00")
        assert best[k(day)].offer_id is None


def test_offer_applied_per_night_when_period_is_eligible():
    service = PricingService(loyalty_policy())
    selector = DatePriceSelector(service)

    rates = make_rates(d(2026, 2, 10), ["100", "120", "80", "160"])
    periods = PeriodBuilder.build(rates)

    offer = Offer(
        id="o2",
        title="4=3",
        description="",
        discount=PayXGetY(3, 4),
        stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
        booking_period=DateRange(d(2026, 2, 1), d(2026, 2, 28)),
        min_nights=4,
        loyalty_compatible=False,
    )

    ctx = PricingContext(booking_date=d(2026, 2, 5), loyalty_status=None)
    best = selector.best_prices_by_date(daily_rates=rates, periods=periods, offers=[offer], ctx=ctx)

    assert best[k(d(2026, 2, 10))].new_price.amount == Decimal("75.00")
    assert best[k(d(2026, 2, 11))].new_price.amount == Decimal("90.00")
    assert best[k(d(2026, 2, 12))].new_price.amount == Decimal("60.00")
    assert best[k(d(2026, 2, 13))].new_price.amount == Decimal("120.00")
    assert best[k(d(2026, 2, 10))].condition == "от 4 ночей"


def test_pay_x_get_y_multiplier_is_0_75_for_3_4():
    m = PayXGetY(3, 4).per_night_multiplier()
    assert m == Decimal("0.75")


def test_loyalty_not_applied_when_offer_not_compatible():
    service = PricingService(loyalty_policy())
    selector = DatePriceSelector(service)

    rates = make_rates(d(2026, 2, 10), ["100", "100", "100", "100"])
    periods = PeriodBuilder.build(rates)

    offer = Offer(
        id="o3",
        title="15% off",
        description="",
        discount=PercentOff(Decimal("0.15")),
        stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
        booking_period=DateRange(d(2026, 2, 1), d(2026, 2, 28)),
        min_nights=4,
        loyalty_compatible=False,
    )

    ctx = PricingContext(booking_date=d(2026, 2, 5), loyalty_status=LoyaltyStatus.GOLD)
    best = selector.best_prices_by_date(daily_rates=rates, periods=periods, offers=[offer], ctx=ctx)

    for day in [d(2026, 2, 10), d(2026, 2, 11), d(2026, 2, 12), d(2026, 2, 13)]:
        assert best[k(day)].new_price.amount == Decimal("85.00")
        assert best[k(day)].offer_id == "o3"


def test_bank_overrides_loyalty_when_both_set():
    service = PricingService(loyalty_policy())
    selector = DatePriceSelector(service)
    rates = make_rates(d(2026, 2, 10), ["100"])
    periods = PeriodBuilder.build(rates)

    ctx = PricingContext(
        booking_date=d(2026, 2, 5),
        loyalty_status=LoyaltyStatus.GOLD,
        bank_status=BankStatus.SBER_PREMIER,
    )
    best = selector.best_prices_by_date(daily_rates=rates, periods=periods, offers=[], ctx=ctx)

    cand = best[k(d(2026, 2, 10))]
    assert cand.new_price.amount == Decimal("80.00")
    assert cand.applied_bank_status == BankStatus.SBER_PREMIER
    assert cand.applied_bank_percent == Decimal("0.20")
    assert cand.loyalty_status is None
    assert cand.loyalty_percent is None


def test_bank_after_offer_percent_when_offer_applied():
    service = PricingService(loyalty_policy())
    selector = DatePriceSelector(service)
    rates = make_rates(d(2026, 2, 10), ["100", "100", "100", "100"])
    periods = PeriodBuilder.build(rates)
    offer = Offer(
        id="o4",
        title="15% off",
        description="",
        discount=PercentOff(Decimal("0.15")),
        stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
        booking_period=DateRange(d(2026, 2, 1), d(2026, 2, 28)),
        min_nights=4,
        loyalty_compatible=False,
    )

    ctx = PricingContext(booking_date=d(2026, 2, 5), bank_status=BankStatus.SBER_FIRST)
    best = selector.best_prices_by_date(daily_rates=rates, periods=periods, offers=[offer], ctx=ctx)

    cand = best[k(d(2026, 2, 10))]
    assert cand.new_price.amount == Decimal("72.25")
    assert cand.applied_bank_percent == Decimal("0.15")


def test_bank_open_percent_when_offer_not_applied():
    service = PricingService(loyalty_policy())
    selector = DatePriceSelector(service)
    rates = make_rates(d(2026, 2, 10), ["100", "100", "100"])
    periods = PeriodBuilder.build(rates)
    offer = Offer(
        id="o5",
        title="4=3",
        description="",
        discount=PayXGetY(3, 4),
        stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
        booking_period=DateRange(d(2026, 2, 1), d(2026, 2, 28)),
        min_nights=4,
        loyalty_compatible=True,
    )

    ctx = PricingContext(booking_date=d(2026, 2, 5), bank_status=BankStatus.SBER_PRIVATE)
    best = selector.best_prices_by_date(daily_rates=rates, periods=periods, offers=[offer], ctx=ctx)

    cand = best[k(d(2026, 2, 10))]
    assert cand.new_price.amount == Decimal("70.00")
    assert cand.applied_bank_percent == Decimal("0.30")


def test_bank_stacks_with_offer_even_if_offer_not_loyalty_compatible():
    service = PricingService(loyalty_policy())
    selector = DatePriceSelector(service)
    rates = make_rates(d(2026, 2, 10), ["100", "100", "100", "100"])
    periods = PeriodBuilder.build(rates)
    offer = Offer(
        id="o6",
        title="15% off",
        description="",
        discount=PercentOff(Decimal("0.15")),
        stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
        booking_period=DateRange(d(2026, 2, 1), d(2026, 2, 28)),
        min_nights=4,
        loyalty_compatible=False,
    )

    ctx = PricingContext(
        booking_date=d(2026, 2, 5),
        loyalty_status=LoyaltyStatus.GOLD,
        bank_status=BankStatus.SBER_PREMIER,
    )
    best = selector.best_prices_by_date(daily_rates=rates, periods=periods, offers=[offer], ctx=ctx)

    cand = best[k(d(2026, 2, 10))]
    assert cand.new_price.amount == Decimal("76.50")
    assert cand.applied_bank_status == BankStatus.SBER_PREMIER
    assert cand.loyalty_status is None


def test_best_offer_selection_considers_bank_final_price():
    service = PricingService(loyalty_policy())
    selector = DatePriceSelector(service)
    rates = make_rates(d(2026, 2, 10), ["100", "100"])
    periods = PeriodBuilder.build(rates)
    offers = [
        Offer(
            id="o7",
            title="10%",
            description="",
            discount=PercentOff(Decimal("0.10")),
            stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
            booking_period=DateRange(d(2026, 2, 1), d(2026, 2, 28)),
            min_nights=1,
            loyalty_compatible=False,
        ),
        Offer(
            id="o8",
            title="15%",
            description="",
            discount=PercentOff(Decimal("0.15")),
            stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
            booking_period=DateRange(d(2026, 2, 1), d(2026, 2, 28)),
            min_nights=1,
            loyalty_compatible=False,
        ),
    ]

    ctx = PricingContext(booking_date=d(2026, 2, 5), bank_status=BankStatus.SBER_FIRST)
    best = selector.best_prices_by_date(daily_rates=rates, periods=periods, offers=offers, ctx=ctx)
    cand = best[k(d(2026, 2, 10))]

    assert cand.offer_id == "o8"
    assert cand.new_price.amount == Decimal("72.25")

