from __future__ import annotations

from datetime import date
from typing import Iterable

from src.application.dto.best_date import BestDate
from src.application.use_cases.find_best_dates_for_guest import FindBestDatesForGuest
from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.entities.offer import Offer
from src.domain.entities.rate import DailyRate
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.discount import PayXGetY, PercentOff
from src.domain.value_objects.money import Money


class BestDatesService:
    """
    Application-level pipeline for best date calculation.
    """

    def __init__(self, use_case: FindBestDatesForGuest):
        self._use_case = use_case

    def find_best_dates(
        self,
        *,
        preferences: GuestPreferences,
        daily_rates: Iterable[DailyRate],
        offers: Iterable[Offer],
        booking_date: date,
    ) -> list[BestDate]:
        return self._use_case.execute(
            preferences=preferences,
            daily_rates=daily_rates,
            offers=offers,
            booking_date=booking_date,
        )

    def find_best_dates_from_inputs(
        self,
        *,
        preferences: GuestPreferences,
        daily_rate_inputs: Iterable[object],
        offer_inputs: Iterable[object],
        booking_date: date,
    ) -> list[BestDate]:
        daily_rates = [self._to_daily_rate(x) for x in daily_rate_inputs]
        offers = [self._to_offer(x) for x in offer_inputs]
        return self.find_best_dates(
            preferences=preferences,
            daily_rates=daily_rates,
            offers=offers,
            booking_date=booking_date,
        )

    @staticmethod
    def _to_daily_rate(inp: object) -> DailyRate:
        category_name = getattr(inp, "category_name", None) or getattr(inp, "category_id", None)
        group_id = getattr(inp, "group_id", None) or category_name
        return DailyRate(
            date=getattr(inp, "date"),
            category_id=category_name,
            group_id=group_id,
            tariff_code=getattr(inp, "tariff_code"),
            adults_count=getattr(inp, "adults_count", 1),
            price=Money.from_minor(getattr(inp, "amount_minor"), currency=getattr(inp, "currency", "RUB")),
            is_available=True,
            is_last_room=bool(getattr(inp, "is_last_room", False)),
        )

    @staticmethod
    def _to_offer(inp: object) -> Offer:
        if getattr(inp, "discount_type") == "PERCENT_OFF":
            discount = PercentOff(getattr(inp, "percent"))
        elif getattr(inp, "discount_type") == "PAY_X_GET_Y":
            discount = PayXGetY(getattr(inp, "x"), getattr(inp, "y"))
        else:
            raise ValueError(f"Unknown discount_type: {getattr(inp, 'discount_type')}")

        booking_period = getattr(inp, "booking_period", None)
        mapped_booking = None
        if booking_period is not None:
            mapped_booking = DateRange(booking_period.start, booking_period.end)

        stay_periods = [DateRange(x.start, x.end) for x in getattr(inp, "stay_periods")]

        allowed_groups = getattr(inp, "allowed_groups", None)
        mapped_groups = set(allowed_groups) if allowed_groups else None

        allowed_categories = getattr(inp, "allowed_categories", None)
        mapped_categories = set(allowed_categories) if allowed_categories else None

        loyalty_compatible = bool(getattr(inp, "loyalty_compatible", True))
        min_nights = int(getattr(inp, "min_nights", 1))

        return Offer(
            id=getattr(inp, "offer_id"),
            title=getattr(inp, "title"),
            description=getattr(inp, "raw_text", "") or "",
            discount=discount,
            stay_periods=stay_periods,
            booking_period=mapped_booking,
            min_nights=min_nights,
            allowed_groups=mapped_groups,
            allowed_categories=mapped_categories,
            loyalty_compatible=loyalty_compatible,
        )
