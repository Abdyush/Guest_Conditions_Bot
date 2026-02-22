from datetime import date
from decimal import Decimal

from src.application.use_cases.find_best_dates_for_guest import FindBestDatesForGuest
from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.entities.offer import Offer
from src.domain.entities.rate import DailyRate
from src.domain.services.category_capacity import Occupancy
from src.domain.services.date_price_selector import DatePriceSelector
from src.domain.services.pricing_service import PricingService
from src.domain.value_objects.category_rule import CategoryRule, PricingMode
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.discount import PayXGetY
from src.domain.value_objects.loyalty import LoyaltyPolicy, LoyaltyStatus
from src.domain.value_objects.money import Money


def d(y, m, day):
    return date(y, m, day)


def make_rates(start, prices, category_name, group_id, tariff="breakfast"):
    rates = []
    for i, p in enumerate(prices):
        day = start.fromordinal(start.toordinal() + i)
        rates.append(
            DailyRate(
                date=day,
                category_id=category_name,
                group_id=group_id,
                tariff_code=tariff,
                adults_count=2,
                price=Money.rub(p),
                is_available=True,
                is_last_room=False,
            )
        )
    return rates


def test_find_best_dates_for_guest_end_to_end():
    loyalty_policy = LoyaltyPolicy({LoyaltyStatus.GOLD: Decimal("0.10")})
    pricing = PricingService(loyalty_policy)
    selector = DatePriceSelector(pricing)
    use_case = FindBestDatesForGuest(selector)

    prefs = GuestPreferences(
        desired_price_per_night=Money.rub("100"),
        loyalty_status=LoyaltyStatus.GOLD,
        allowed_groups={"DELUXE"},
    )

    deluxe_rates = make_rates(d(2026, 2, 10), ["110", "110", "110", "110"], "Deluxe Sea View", "DELUXE")
    other_rates = make_rates(d(2026, 2, 10), ["50", "50"], "Standard Room", "STANDARD")
    daily_rates = deluxe_rates + other_rates

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

    result = use_case.execute(
        preferences=prefs,
        daily_rates=daily_rates,
        offers=[offer],
        booking_date=d(2026, 2, 5),
    )

    assert len(result) == 4
    for item in result:
        assert item.new_price.amount == Decimal("74.25")
        assert item.offer_id == "o1"
        assert item.category_name == "Deluxe Sea View"
        assert item.group_id == "DELUXE"
        assert item.tariff_code == "breakfast"
        assert item.offer_min_nights == 4


def test_use_case_skips_category_when_occupancy_does_not_fit_rule():
    loyalty_policy = LoyaltyPolicy({LoyaltyStatus.GOLD: Decimal("0.10")})
    pricing = PricingService(loyalty_policy)
    selector = DatePriceSelector(pricing)
    use_case = FindBestDatesForGuest(
        selector,
        group_rules={
            "DELUXE": CategoryRule(
                group_id="DELUXE",
                capacity_adults=2,
                free_infants=0,
                pricing_mode=PricingMode.PER_ADULT,
            )
        },
    )

    prefs = GuestPreferences(
        desired_price_per_night=Money.rub("300"),
        loyalty_status=LoyaltyStatus.GOLD,
        allowed_groups={"DELUXE"},
        occupancy=Occupancy(adults=2, children_4_13=1, infants=0),
    )

    daily_rates = [
        DailyRate(
            date=d(2026, 2, 10),
            category_id="Deluxe Sea View",
            group_id="DELUXE",
            tariff_code="breakfast",
            adults_count=2,
            price=Money.rub("100"),
            is_available=True,
            is_last_room=False,
        ),
    ]

    result = use_case.execute(
        preferences=prefs,
        daily_rates=daily_rates,
        offers=[],
        booking_date=d(2026, 2, 5),
    )

    assert result == []


def test_two_categories_same_group_both_present_in_result_when_price_matches():
    loyalty_policy = LoyaltyPolicy({LoyaltyStatus.GOLD: Decimal("0.10")})
    pricing = PricingService(loyalty_policy)
    selector = DatePriceSelector(pricing)
    use_case = FindBestDatesForGuest(selector)

    prefs = GuestPreferences(
        desired_price_per_night=Money.rub("300"),
        loyalty_status=LoyaltyStatus.GOLD,
        allowed_groups={"DELUXE"},
    )

    daily_rates = [
        DailyRate(
            date=d(2026, 2, 10),
            category_id="Deluxe Mountain",
            group_id="DELUXE",
            tariff_code="breakfast",
            adults_count=2,
            price=Money.rub("100"),
            is_available=True,
            is_last_room=False,
        ),
        DailyRate(
            date=d(2026, 2, 10),
            category_id="Deluxe Garden",
            group_id="DELUXE",
            tariff_code="breakfast",
            adults_count=2,
            price=Money.rub("120"),
            is_available=True,
            is_last_room=False,
        ),
    ]

    result = use_case.execute(
        preferences=prefs,
        daily_rates=daily_rates,
        offers=[],
        booking_date=d(2026, 2, 5),
    )

    assert len(result) == 2
    keys = {(x.date, x.category_name, x.group_id, x.tariff_code) for x in result}
    assert keys == {
        (d(2026, 2, 10), "Deluxe Mountain", "DELUXE", "breakfast"),
        (d(2026, 2, 10), "Deluxe Garden", "DELUXE", "breakfast"),
    }

