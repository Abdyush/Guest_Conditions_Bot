from datetime import date
from decimal import Decimal

from src.application.services.best_dates_service import BestDatesService
from src.application.use_cases.find_best_dates_for_guest import FindBestDatesForGuest
from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.services.date_price_selector import DatePriceSelector
from src.domain.services.pricing_service import PricingService
from src.domain.value_objects.loyalty import LoyaltyPolicy, LoyaltyStatus
from src.domain.value_objects.money import Money
from src.infrastructure.contracts.daily_rate_input import DailyRateInput
from src.infrastructure.contracts.offer_input import DateRangeInput, OfferInput


def d(y, m, day):
    return date(y, m, day)


def test_best_dates_service_pipeline_from_inputs():
    loyalty_policy = LoyaltyPolicy({LoyaltyStatus.GOLD: Decimal("0.10")})
    pricing = PricingService(loyalty_policy)
    selector = DatePriceSelector(pricing)
    use_case = FindBestDatesForGuest(selector)
    service = BestDatesService(use_case)

    prefs = GuestPreferences(
        desired_price_per_night=Money.rub("100"),
        loyalty_status=LoyaltyStatus.GOLD,
        allowed_categories={"deluxe"},
    )

    daily_rate_inputs = [
        DailyRateInput(date=d(2026, 2, 10), category_name="deluxe", group_id="deluxe", tariff_code="breakfast", adults_count=2, amount_minor=11000, currency="RUB", is_last_room=False),
        DailyRateInput(date=d(2026, 2, 11), category_name="deluxe", group_id="deluxe", tariff_code="breakfast", adults_count=2, amount_minor=11000, currency="RUB", is_last_room=False),
        DailyRateInput(date=d(2026, 2, 12), category_name="deluxe", group_id="deluxe", tariff_code="breakfast", adults_count=2, amount_minor=11000, currency="RUB", is_last_room=False),
        DailyRateInput(date=d(2026, 2, 13), category_name="deluxe", group_id="deluxe", tariff_code="breakfast", adults_count=2, amount_minor=11000, currency="RUB", is_last_room=False),
    ]

    offer_inputs = [
        OfferInput(
            offer_id="o1",
            title="4=3",
            loyalty_compatible=True,
            min_nights=4,
            booking_period=DateRangeInput(d(2026, 2, 1), d(2026, 2, 28)),
            stay_periods=[DateRangeInput(d(2026, 2, 1), d(2026, 3, 1))],
            discount_type="PAY_X_GET_Y",
            x=3,
            y=4,
        )
    ]

    result = service.find_best_dates_from_inputs(
        preferences=prefs,
        daily_rate_inputs=daily_rate_inputs,
        offer_inputs=offer_inputs,
        booking_date=d(2026, 2, 5),
    )

    assert len(result) == 4
    assert all(item.offer_id == "o1" for item in result)
    assert all(item.offer_min_nights == 4 for item in result)
