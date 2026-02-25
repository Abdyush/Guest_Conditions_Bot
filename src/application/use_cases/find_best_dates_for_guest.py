from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

from src.application.dto.best_date import BestDate
from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.entities.offer import Offer
from src.domain.entities.rate import DailyRate
from src.domain.services.category_capacity import can_fit
from src.domain.services.date_price_selector import DatePriceSelector
from src.domain.services.period_builder import PeriodBuilder
from src.domain.services.pricing_service import PricingContext
from src.domain.value_objects.category_rule import CategoryRule


class FindBestDatesForGuest:
    def __init__(
        self,
        selector: DatePriceSelector,
        group_rules: Optional[dict[str, CategoryRule]] = None,
        category_rules: Optional[dict[str, CategoryRule]] = None,
    ):
        self._selector = selector
        self._group_rules = group_rules or category_rules or {}

    def execute(
        self,
        *,
        preferences: GuestPreferences,
        daily_rates: Iterable[DailyRate],
        offers: Iterable[Offer],
        booking_date: date,
    ) -> list[BestDate]:
        rates = list(daily_rates)
        allowed_groups = preferences.effective_allowed_groups
        if allowed_groups is not None:
            rates = [r for r in rates if r.group_id in allowed_groups]

        filtered_rates: list[DailyRate] = []
        for rate in rates:
            if rate.adults_count != preferences.occupancy.adults:
                continue
            rule = self._group_rules.get(rate.group_id)
            if rule is not None and not can_fit(rule, preferences.occupancy):
                continue
            filtered_rates.append(rate)

        periods = PeriodBuilder.build(filtered_rates)

        ctx = PricingContext(
            booking_date=booking_date,
            loyalty_status=preferences.loyalty_status,
            bank_status=preferences.bank_status,
            children_4_13=preferences.occupancy.children_4_13,
        )

        best_map = self._selector.best_prices_by_date(
            daily_rates=filtered_rates,
            periods=periods,
            offers=offers,
            ctx=ctx,
        )

        result: list[BestDate] = []
        for cand in best_map.values():
            if cand.new_price <= preferences.desired_price_per_night:
                result.append(
                    BestDate(
                        date=cand.day,
                        category_name=cand.category_id,
                        group_id=cand.group_id,
                        availability_period=cand.availability_period,
                        tariff_code=cand.tariff_code,
                        old_price=cand.old_price,
                        new_price=cand.new_price,
                        offer_title=cand.offer_title,
                        offer_repr=cand.offer_repr,
                        offer_min_nights=cand.offer_min_nights,
                        loyalty_status=cand.loyalty_status,
                        loyalty_percent=cand.loyalty_percent,
                        offer_id=cand.offer_id,
                        applied_bank_status=cand.applied_bank_status,
                        applied_bank_percent=cand.applied_bank_percent,
                    )
                )

        result.sort(key=lambda x: (x.date, x.category_name, x.tariff_code))
        return result
