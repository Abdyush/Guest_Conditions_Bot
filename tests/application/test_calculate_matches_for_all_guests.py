from datetime import date
from decimal import Decimal

from src.application.use_cases.calculate_matches_for_all_guests import CalculateMatchesForAllGuests
from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.entities.offer import Offer
from src.domain.entities.rate import DailyRate
from src.domain.services.category_capacity import Occupancy
from src.domain.services.child_supplement_policy import ChildSupplementPolicy
from src.domain.services.date_price_selector import DatePriceSelector
from src.domain.services.period_builder import PeriodBuilder
from src.domain.services.pricing_service import PricingService
from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.category_rule import CategoryRule, PricingMode
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.discount import PercentOff
from src.domain.value_objects.loyalty import LoyaltyPolicy, LoyaltyStatus
from src.domain.value_objects.money import Money


def d(y, m, day):
    return date(y, m, day)


class InMemoryRatesRepo:
    def __init__(self, rates: list[DailyRate]):
        self._rates = rates

    def get_daily_rates(self, date_from: date, date_to: date) -> list[DailyRate]:
        return [r for r in self._rates if date_from <= r.date <= date_to]


class InMemoryOffersRepo:
    def __init__(self, offers: list[Offer]):
        self._offers = offers

    def get_offers(self, today: date) -> list[Offer]:
        _ = today
        return list(self._offers)


class InMemoryGuestsRepo:
    def __init__(self, guests: list[GuestPreferences]):
        self._guests = guests

    def get_active_guests(self) -> list[GuestPreferences]:
        return list(self._guests)


class InMemoryRulesRepo:
    def __init__(self, group_rules: dict[str, CategoryRule]):
        self._group_rules = group_rules

    def get_group_rules(self) -> dict[str, CategoryRule]:
        return self._group_rules

    def get_child_policies(self) -> dict[str, ChildSupplementPolicy]:
        return {}

    def get_category_to_group(self) -> dict[str, str]:
        return {"Deluxe": "DELUXE"}


def _rate(day: date, price: str) -> DailyRate:
    return DailyRate(
        date=day,
        category_id="Deluxe",
        group_id="DELUXE",
        tariff_code="breakfast",
        adults_count=2,
        price=Money.rub(price),
        is_available=True,
        is_last_room=False,
    )


def _build_use_case(*, rates, offers, guests):
    group_rules = {
        "DELUXE": CategoryRule(
            group_id="DELUXE",
            capacity_adults=2,
            free_infants=0,
            pricing_mode=PricingMode.FLAT,
        )
    }
    rules_repo = InMemoryRulesRepo(group_rules)
    pricing_service = PricingService(
        loyalty_policy=LoyaltyPolicy(
            {
                LoyaltyStatus.GOLD: Decimal("0.10"),
                LoyaltyStatus.BRONZE: Decimal("0.07"),
            }
        ),
        group_rules=group_rules,
    )
    selector = DatePriceSelector(pricing_service)
    use_case = CalculateMatchesForAllGuests(
        rates_repo=InMemoryRatesRepo(rates),
        offers_repo=InMemoryOffersRepo(offers),
        guests_repo=InMemoryGuestsRepo(guests),
        rules_repo=rules_repo,
        pricing_service=pricing_service,
        period_builder=PeriodBuilder,
        selector=selector,
    )
    return use_case


def test_execute_returns_result_for_each_guest():
    rates = [_rate(d(2026, 2, 10), "100"), _rate(d(2026, 2, 11), "100")]
    offers = [
        Offer(
            id="off10",
            title="10%",
            description="",
            discount=PercentOff(Decimal("0.10")),
            stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
            booking_period=DateRange(d(2026, 2, 1), d(2026, 2, 28)),
            min_nights=1,
            loyalty_compatible=True,
        )
    ]
    guests = [
        GuestPreferences(
            desired_price_per_night=Money.rub("95"),
            loyalty_status=LoyaltyStatus.GOLD,
            allowed_groups={"DELUXE"},
            occupancy=Occupancy(adults=2, children_4_13=0, infants=0),
            guest_id="g1",
            guest_name="Guest 1",
        ),
        GuestPreferences(
            desired_price_per_night=Money.rub("50"),
            loyalty_status=LoyaltyStatus.BRONZE,
            allowed_groups={"DELUXE"},
            occupancy=Occupancy(adults=2, children_4_13=0, infants=0),
            guest_id="g2",
            guest_name="Guest 2",
        ),
    ]

    use_case = _build_use_case(rates=rates, offers=offers, guests=guests)
    results = use_case.execute(date_from=d(2026, 2, 10), date_to=d(2026, 2, 12), booking_date=d(2026, 2, 5))

    assert len(results) == 2
    assert results[0].guest_id == "g1"
    assert len(results[0].matched_lines) == 2
    assert results[1].guest_id == "g2"
    assert results[1].matched_lines == []


def test_bank_status_overrides_loyalty_in_use_case():
    rates = [_rate(d(2026, 2, 10), "100")]
    guests = [
        GuestPreferences(
            desired_price_per_night=Money.rub("100"),
            loyalty_status=LoyaltyStatus.GOLD,
            bank_status=BankStatus.SBER_PREMIER,
            allowed_groups={"DELUXE"},
            occupancy=Occupancy(adults=2, children_4_13=0, infants=0),
            guest_id="g_bank",
        )
    ]

    use_case = _build_use_case(rates=rates, offers=[], guests=guests)
    results = use_case.execute(date_from=d(2026, 2, 10), date_to=d(2026, 2, 11), booking_date=d(2026, 2, 5))

    assert len(results) == 1
    line = results[0].matched_lines[0]
    assert line.new_price.amount == Decimal("80.00")
    assert line.applied_bank_status == BankStatus.SBER_PREMIER
    assert line.applied_loyalty_status is None


def test_offer_applies_then_bank_after_offer_percent():
    rates = [_rate(d(2026, 2, 10), "100")]
    offers = [
        Offer(
            id="off15",
            title="15%",
            description="",
            discount=PercentOff(Decimal("0.15")),
            stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
            booking_period=DateRange(d(2026, 2, 1), d(2026, 2, 28)),
            min_nights=1,
            loyalty_compatible=False,
        )
    ]
    guests = [
        GuestPreferences(
            desired_price_per_night=Money.rub("100"),
            bank_status=BankStatus.SBER_FIRST,
            allowed_groups={"DELUXE"},
            occupancy=Occupancy(adults=2, children_4_13=0, infants=0),
            guest_id="g_after_offer",
        )
    ]

    use_case = _build_use_case(rates=rates, offers=offers, guests=guests)
    results = use_case.execute(date_from=d(2026, 2, 10), date_to=d(2026, 2, 11), booking_date=d(2026, 2, 5))

    line = results[0].matched_lines[0]
    assert line.new_price.amount == Decimal("72.25")
    assert line.applied_bank_percent == Decimal("0.15")
