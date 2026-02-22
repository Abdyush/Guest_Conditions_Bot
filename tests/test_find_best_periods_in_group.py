from datetime import date
from decimal import Decimal

from src.application.use_cases.find_best_periods_in_group import find_best_periods_in_group
from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.entities.offer import Offer
from src.domain.entities.rate import DailyRate
from src.domain.services.category_capacity import Occupancy
from src.domain.services.pricing_service import PricingContext
from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.category_rule import CategoryRule, PricingMode
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.discount import PercentOff
from src.domain.value_objects.loyalty import LoyaltyStatus
from src.domain.value_objects.money import Money


def d(y: int, m: int, day: int) -> date:
    return date(y, m, day)


def rate(day: date, *, cat: str, group: str, tariff: str, price: str) -> DailyRate:
    return DailyRate(
        date=day,
        category_id=cat,
        group_id=group,
        tariff_code=tariff,
        adults_count=2,
        price=Money.rub(price),
        is_available=True,
        is_last_room=False,
    )


def test_merge_consecutive_days_into_single_period_6_nights():
    daily_rates: list[DailyRate] = []
    for day in range(20, 26):
        daily_rates.append(
            rate(
                d(2026, 7, day),
                cat="Deluxe Mountain",
                group="DELUXE",
                tariff="breakfast",
                price="26000.10",
            )
        )

    guest = GuestPreferences(
        desired_price_per_night=Money.rub("999999"),
        occupancy=Occupancy(adults=2, children_4_13=0, infants=0),
    )
    group_rules = {
        "DELUXE": CategoryRule(
            group_id="DELUXE",
            capacity_adults=2,
            free_infants=0,
            pricing_mode=PricingMode.FLAT,
        )
    }

    result = find_best_periods_in_group(
        daily_rates=daily_rates,
        offers=[],
        group_rules=group_rules,
        child_policies={},
        guest=guest,
        ctx=PricingContext(booking_date=d(2026, 7, 1)),
        group_id="DELUXE",
        date_from=d(2026, 7, 20),
        date_to=d(2026, 7, 31),
        top_k=5,
    )

    assert len(result) == 1
    pick = result[0]
    assert pick.start_date == d(2026, 7, 20)
    assert pick.end_date_inclusive == d(2026, 7, 25)
    assert pick.nights == 6


def test_sorting_prefers_longer_period():
    daily_rates: list[DailyRate] = []
    for day in range(20, 26):
        daily_rates.append(
            rate(
                d(2026, 7, day),
                cat="Deluxe Mountain",
                group="DELUXE",
                tariff="breakfast",
                price="26000.10",
            )
        )
    for day in range(22, 25):
        daily_rates.append(
            rate(
                d(2026, 7, day),
                cat="Deluxe Garden",
                group="DELUXE",
                tariff="breakfast",
                price="26000.20",
            )
        )

    guest = GuestPreferences(
        desired_price_per_night=Money.rub("999999"),
        occupancy=Occupancy(adults=2, children_4_13=0, infants=0),
    )
    group_rules = {
        "DELUXE": CategoryRule(
            group_id="DELUXE",
            capacity_adults=2,
            free_infants=0,
            pricing_mode=PricingMode.FLAT,
        )
    }

    result = find_best_periods_in_group(
        daily_rates=daily_rates,
        offers=[],
        group_rules=group_rules,
        child_policies={},
        guest=guest,
        ctx=PricingContext(booking_date=d(2026, 7, 1)),
        group_id="DELUXE",
        date_from=d(2026, 7, 20),
        date_to=d(2026, 7, 31),
        top_k=5,
    )

    assert len(result) == 2
    assert result[0].category_name == "Deluxe Mountain"
    assert result[0].nights == 6
    assert result[1].category_name == "Deluxe Garden"
    assert result[1].nights == 3


def test_rounding_is_used_only_for_grouping_candidates():
    daily_rates = [
        rate(d(2026, 7, 20), cat="Deluxe Garden", group="DELUXE", tariff="breakfast", price="25999.60"),
        rate(d(2026, 7, 21), cat="Deluxe Garden", group="DELUXE", tariff="breakfast", price="26000.40"),
    ]

    guest = GuestPreferences(
        desired_price_per_night=Money.rub("999999"),
        occupancy=Occupancy(adults=2, children_4_13=0, infants=0),
    )
    group_rules = {
        "DELUXE": CategoryRule(
            group_id="DELUXE",
            capacity_adults=2,
            free_infants=0,
            pricing_mode=PricingMode.FLAT,
        )
    }

    result = find_best_periods_in_group(
        daily_rates=daily_rates,
        offers=[],
        group_rules=group_rules,
        child_policies={},
        guest=guest,
        ctx=PricingContext(booking_date=d(2026, 7, 1)),
        group_id="DELUXE",
        date_from=d(2026, 7, 20),
        date_to=d(2026, 7, 31),
        top_k=5,
    )

    assert len(result) == 1
    assert result[0].nights == 2
    assert result[0].new_price_per_night.amount == Money.rub("25999.60").amount


def test_best_periods_bank_overrides_loyalty_and_changes_result():
    daily_rates = [
        rate(d(2026, 7, 20), cat="Deluxe Garden", group="DELUXE", tariff="breakfast", price="100.00"),
        rate(d(2026, 7, 21), cat="Deluxe Garden", group="DELUXE", tariff="breakfast", price="100.00"),
    ]
    group_rules = {
        "DELUXE": CategoryRule(
            group_id="DELUXE",
            capacity_adults=2,
            free_infants=0,
            pricing_mode=PricingMode.FLAT,
        )
    }
    guest = GuestPreferences(
        desired_price_per_night=Money.rub("999999"),
        loyalty_status=LoyaltyStatus.GOLD,
        occupancy=Occupancy(adults=2, children_4_13=0, infants=0),
    )

    no_bank = find_best_periods_in_group(
        daily_rates=daily_rates,
        offers=[],
        group_rules=group_rules,
        child_policies={},
        guest=guest,
        ctx=PricingContext(booking_date=d(2026, 7, 1), loyalty_status=LoyaltyStatus.GOLD),
        group_id="DELUXE",
        date_from=d(2026, 7, 20),
        date_to=d(2026, 7, 31),
        top_k=1,
    )
    with_bank = find_best_periods_in_group(
        daily_rates=daily_rates,
        offers=[],
        group_rules=group_rules,
        child_policies={},
        guest=GuestPreferences(
            desired_price_per_night=Money.rub("999999"),
            loyalty_status=LoyaltyStatus.GOLD,
            bank_status=BankStatus.SBER_PREMIER,
            occupancy=Occupancy(adults=2, children_4_13=0, infants=0),
        ),
        ctx=PricingContext(
            booking_date=d(2026, 7, 1),
            loyalty_status=LoyaltyStatus.GOLD,
            bank_status=BankStatus.SBER_PREMIER,
        ),
        group_id="DELUXE",
        date_from=d(2026, 7, 20),
        date_to=d(2026, 7, 31),
        top_k=1,
    )

    assert no_bank[0].new_price_per_night.amount == Money.rub("90.00").amount
    assert no_bank[0].applied_bank_status is None
    assert no_bank[0].applied_loyalty_status == "gold"
    assert with_bank[0].new_price_per_night.amount == Money.rub("80.00").amount
    assert with_bank[0].applied_bank_status == BankStatus.SBER_PREMIER
    assert with_bank[0].applied_loyalty_status is None


def test_best_offer_selection_considers_final_price_with_bank():
    daily_rates = [
        rate(d(2026, 7, 20), cat="Deluxe Garden", group="DELUXE", tariff="breakfast", price="100.00"),
        rate(d(2026, 7, 21), cat="Deluxe Garden", group="DELUXE", tariff="breakfast", price="100.00"),
    ]
    group_rules = {
        "DELUXE": CategoryRule(
            group_id="DELUXE",
            capacity_adults=2,
            free_infants=0,
            pricing_mode=PricingMode.FLAT,
        )
    }
    offers = [
        Offer(
            id="OFF10",
            title="10%",
            description="",
            discount=PercentOff(Decimal("0.10")),
            stay_periods=[DateRange(d(2026, 7, 1), d(2026, 8, 1))],
            booking_period=DateRange(d(2026, 7, 1), d(2026, 8, 1)),
            min_nights=1,
            loyalty_compatible=False,
        ),
        Offer(
            id="OFF15",
            title="15%",
            description="",
            discount=PercentOff(Decimal("0.15")),
            stay_periods=[DateRange(d(2026, 7, 1), d(2026, 8, 1))],
            booking_period=DateRange(d(2026, 7, 1), d(2026, 8, 1)),
            min_nights=1,
            loyalty_compatible=False,
        ),
    ]

    result = find_best_periods_in_group(
        daily_rates=daily_rates,
        offers=offers,
        group_rules=group_rules,
        child_policies={},
        guest=GuestPreferences(
            desired_price_per_night=Money.rub("999999"),
            bank_status=BankStatus.SBER_FIRST,
            occupancy=Occupancy(adults=2, children_4_13=0, infants=0),
        ),
        ctx=PricingContext(booking_date=d(2026, 7, 1), bank_status=BankStatus.SBER_FIRST),
        group_id="DELUXE",
        date_from=d(2026, 7, 20),
        date_to=d(2026, 7, 31),
        top_k=1,
    )

    assert result[0].offer_title == "15%"
    assert result[0].new_price_per_night.amount == Money.rub("72.25").amount
