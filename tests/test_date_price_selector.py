import pytest
from datetime import date
from decimal import Decimal

from src.domain.entities.offer import Offer
from src.domain.entities.rate import DailyRate
from src.domain.services.date_price_selector import DatePriceSelector
from src.domain.services.period_builder import BuiltPeriod
from src.domain.services.pricing_service import PricingService, PricingContext
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.discount import PayXGetY
from src.domain.value_objects.loyalty import LoyaltyPolicy, LoyaltyStatus
from src.domain.value_objects.money import Money


def d(y, m, day):
    return date(y, m, day)


def make_rates(start: date, prices: list[str], cat="deluxe", tariff="breakfast") -> list[DailyRate]:
    rates = []
    for i, p in enumerate(prices):
        day = start.fromordinal(start.toordinal() + i)
        rates.append(DailyRate(day, cat, tariff, Money.rub(p), True, False))
    return rates


def make_period_from_rates(rates: list[DailyRate]) -> BuiltPeriod:
    dr = DateRange(rates[0].date, rates[-1].date.fromordinal(rates[-1].date.toordinal() + 1))
    return BuiltPeriod(date_range=dr, rates=rates)


def loyalty_policy():
    return LoyaltyPolicy({LoyaltyStatus.GOLD: Decimal("0.10")})  # -10%


def test_loyalty_only_per_date_is_min_when_no_offers():
    service = PricingService(loyalty_policy())
    selector = DatePriceSelector(service)

    rates = make_rates(d(2026, 2, 10), ["110", "90", "100"])
    periods = [make_period_from_rates(rates)]  # не важно, офферов нет
    offers = []

    ctx = PricingContext(booking_date=d(2026, 2, 5), loyalty_status=LoyaltyStatus.GOLD)

    best = selector.best_prices_by_date(
        daily_rates=rates,
        periods=periods,
        offers=offers,
        ctx=ctx,
    )

    assert best[d(2026, 2, 10)].price_per_night.amount == Decimal("99.00")   # 110 -10%
    assert best[d(2026, 2, 11)].price_per_night.amount == Decimal("81.00")   # 90  -10%
    assert best[d(2026, 2, 12)].price_per_night.amount == Decimal("90.00")   # 100 -10%
    assert best[d(2026, 2, 10)].offer_id is None


def test_offer_ignored_if_not_bookable_today_booking_period_miss():
    service = PricingService(loyalty_policy())
    selector = DatePriceSelector(service)

    rates = make_rates(d(2026, 2, 10), ["110", "110", "110", "110"])
    periods = [make_period_from_rates(rates)]

    offer = Offer(
        id="o1",
        title="4=3",
        description="",
        discount=PayXGetY(3, 4),
        stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
        booking_period=DateRange(d(2026, 1, 1), d(2026, 1, 10)),  # оффер уже нельзя забронировать
        min_nights=4,
        loyalty_compatible=True,
    )

    ctx = PricingContext(booking_date=d(2026, 2, 5), loyalty_status=LoyaltyStatus.GOLD)
    best = selector.best_prices_by_date(
        daily_rates=rates,
        periods=periods,
        offers=[offer],
        ctx=ctx,
    )

    # Должны остаться только loyalty-only: 110 -> 99
    for day in [d(2026, 2, 10), d(2026, 2, 11), d(2026, 2, 12), d(2026, 2, 13)]:
        assert best[day].price_per_night.amount == Decimal("99.00")
        assert best[day].offer_id is None


def test_offer_effective_per_night_can_win_over_loyalty_only():
    service = PricingService(loyalty_policy())
    selector = DatePriceSelector(service)

    # 4 ночи по 110: total_before=440
    # offer 4=3: скидка 110 => total_after_offer=330
    # loyalty -10% от 330 => 297
    # effective_per_night = 297/4 = 74.25
    rates = make_rates(d(2026, 2, 10), ["110", "110", "110", "110"])
    periods = [make_period_from_rates(rates)]

    offer = Offer(
        id="o2",
        title="4=3",
        description="",
        discount=PayXGetY(3, 4),
        stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
        booking_period=DateRange(d(2026, 2, 1), d(2026, 2, 28)),  # сегодня можно
        min_nights=4,
        loyalty_compatible=True,
    )

    ctx = PricingContext(booking_date=d(2026, 2, 5), loyalty_status=LoyaltyStatus.GOLD)
    best = selector.best_prices_by_date(
        daily_rates=rates,
        periods=periods,
        offers=[offer],
        ctx=ctx,
    )

    # loyalty-only было бы 99.00, оффер даёт 74.25 -> должен победить
    for day in [d(2026, 2, 10), d(2026, 2, 11), d(2026, 2, 12), d(2026, 2, 13)]:
        assert best[day].price_per_night.amount == Decimal("74.25")
        assert best[day].offer_id == "o2"
        assert best[day].window_start == d(2026, 2, 10)
        assert best[day].window_end == d(2026, 2, 14)


def test_best_price_for_day_is_min_across_overlapping_windows():
    service = PricingService(loyalty_policy())
    selector = DatePriceSelector(service)

    # 5 ночей: 50, 200, 200, 200, 200
    # Окна по 4 ночи:
    #  - окно 0-4: содержит 50 + 200+200+200 => offer скидка = 50 (cheapest), total=650-50=600, loyalty -10% => 540, eff=135
    #  - окно 1-5: 200*4 => offer скидка = 200, total=800-200=600, loyalty -10% => 540, eff=135
    # Тут одинаково. Сделаем различие:
    # заменим первую цену 10 вместо 50:
    # окно 0-4: скидка 10 => total_after_offer=610, loyalty => 549, eff=137.25
    # окно 1-5: скидка 200 => total_after_offer=600, loyalty => 540, eff=135.00
    # Дата 2026-02-11 входит в оба окна, должна выбрать 135.00.
    rates = make_rates(d(2026, 2, 10), ["10", "200", "200", "200", "200"])
    periods = [make_period_from_rates(rates)]

    offer = Offer(
        id="o3",
        title="4=3",
        description="",
        discount=PayXGetY(3, 4),
        stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
        booking_period=DateRange(d(2026, 2, 1), d(2026, 2, 28)),
        min_nights=4,
        loyalty_compatible=True,
    )

    ctx = PricingContext(booking_date=d(2026, 2, 5), loyalty_status=LoyaltyStatus.GOLD)
    best = selector.best_prices_by_date(
        daily_rates=rates,
        periods=periods,
        offers=[offer],
        ctx=ctx,
    )

    # День 2026-02-11 (второй) входит в оба окна. Должен выбрать 135.00, а не loyalty-only (180.00)
    assert best[d(2026, 2, 11)].price_per_night.amount == Decimal("135.00")
    assert best[d(2026, 2, 11)].offer_id == "o3"