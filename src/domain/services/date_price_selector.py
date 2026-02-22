from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from src.domain.entities.offer import Offer
from src.domain.entities.rate import DailyRate
from src.domain.services.period_builder import BuiltPeriod
from src.domain.services.pricing_service import PricingContext, PricingService
from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.discount import PayXGetY, PercentOff
from src.domain.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class DatePriceCandidate:
    day: date
    category_id: str
    group_id: str
    tariff_code: str
    adults_count: int
    availability_period: DateRange
    old_price: Money
    new_price: Money
    reason: str
    offer_id: Optional[str]
    offer_title: Optional[str]
    offer_repr: Optional[str]
    offer_min_nights: Optional[int]
    condition: Optional[str]
    loyalty_status: Optional[str]
    loyalty_percent: Optional[str]
    applied_bank_status: Optional[BankStatus]
    applied_bank_percent: Optional[Decimal]


class DatePriceSelector:
    def __init__(self, pricing: PricingService):
        self._pricing = pricing

    def best_prices_by_date(
        self,
        *,
        daily_rates: Iterable[DailyRate],
        periods: Iterable[BuiltPeriod],
        offers: Iterable[Offer],
        ctx: PricingContext,
    ) -> dict[tuple[date, str, str, int], DatePriceCandidate]:
        _ = list(daily_rates)
        offers_list = list(offers)
        best: dict[tuple[date, str, str, int], DatePriceCandidate] = {}

        loyalty_percent = self._pricing.loyalty_percent(ctx.loyalty_status)
        loyalty_status = ctx.loyalty_status.value if ctx.loyalty_status is not None else None
        loyalty_percent_label = self._format_percent(loyalty_percent)
        bank_discount = self._pricing.bank_discount(ctx.bank_status)

        for period in periods:
            nights = period.nights
            for rate in period.rates:
                if not rate.is_available:
                    continue

                old = rate.price
                if bank_discount is not None and ctx.bank_status is not None:
                    base_price = old.percent_off(bank_discount.open_percent)
                    base_loyalty_status = None
                    base_loyalty_percent = None
                    base_bank_status = ctx.bank_status
                    base_bank_percent = bank_discount.open_percent
                    base_reason = "bank_only"
                else:
                    base_price = old if loyalty_percent is None else old.percent_off(loyalty_percent)
                    base_loyalty_status = loyalty_status
                    base_loyalty_percent = loyalty_percent_label
                    base_bank_status = None
                    base_bank_percent = None
                    base_reason = "loyalty_only"

                best_candidate = DatePriceCandidate(
                    day=rate.date,
                    category_id=rate.category_id,
                    group_id=rate.group_id,
                    tariff_code=rate.tariff_code,
                    adults_count=rate.adults_count,
                    availability_period=period.date_range,
                    old_price=old,
                    new_price=base_price,
                    reason=base_reason,
                    offer_id=None,
                    offer_title=None,
                    offer_repr=None,
                    offer_min_nights=None,
                    condition=None,
                    loyalty_status=base_loyalty_status,
                    loyalty_percent=base_loyalty_percent,
                    applied_bank_status=base_bank_status,
                    applied_bank_percent=base_bank_percent,
                )

                for offer in offers_list:
                    if not offer.is_eligible_by_period_length(nights):
                        continue

                    if not offer.is_applicable(
                        stay_range=period.date_range,
                        booking_date=ctx.booking_date,
                        category_id=rate.category_id,
                        group_id=rate.group_id,
                        tariff_code=rate.tariff_code,
                    ):
                        continue

                    multiplier = offer.discount.per_night_multiplier()
                    if multiplier is None:
                        continue

                    after_offer = old * multiplier
                    if bank_discount is not None and ctx.bank_status is not None:
                        after = after_offer.percent_off(bank_discount.after_offer_percent)
                        cand_loyalty_status = None
                        cand_loyalty_percent = None
                        cand_bank_status = ctx.bank_status
                        cand_bank_percent = bank_discount.after_offer_percent
                    else:
                        after = after_offer
                        cand_loyalty_status = None
                        cand_loyalty_percent = None
                        cand_bank_status = None
                        cand_bank_percent = None
                        if loyalty_percent is not None and offer.loyalty_compatible:
                            after = after_offer.percent_off(loyalty_percent)
                            cand_loyalty_status = loyalty_status
                            cand_loyalty_percent = loyalty_percent_label

                    if after < best_candidate.new_price:
                        best_candidate = DatePriceCandidate(
                            day=rate.date,
                            category_id=rate.category_id,
                            group_id=rate.group_id,
                            tariff_code=rate.tariff_code,
                            adults_count=rate.adults_count,
                            availability_period=period.date_range,
                            old_price=old,
                            new_price=after,
                            reason="offer_applied",
                            offer_id=offer.id,
                            offer_title=offer.title,
                            offer_repr=self._offer_repr(offer),
                            offer_min_nights=offer.min_nights,
                            condition=DatePriceSelector._offer_condition(offer.min_nights),
                            loyalty_status=cand_loyalty_status,
                            loyalty_percent=cand_loyalty_percent,
                            applied_bank_status=cand_bank_status,
                            applied_bank_percent=cand_bank_percent,
                        )

                self._put_min(best, best_candidate)

        return best

    @staticmethod
    def _offer_condition(min_nights: Optional[int]) -> str:
        nights = min_nights if min_nights is not None else 1
        return f"от {nights} ночей"

    @staticmethod
    def _format_percent(p: Optional[Decimal]) -> Optional[str]:
        if p is None:
            return None
        value = (p * Decimal("100")).quantize(Decimal("1"))
        return f"{value}%"

    @staticmethod
    def _offer_repr(offer: Offer) -> str:
        discount = offer.discount
        if isinstance(discount, PercentOff):
            value = (discount.percent * Decimal("100")).quantize(Decimal("1"))
            return f"{value}%"
        if isinstance(discount, PayXGetY):
            return f"{discount.get_nights}={discount.pay_nights}"
        return discount.__class__.__name__

    @staticmethod
    def _key(cand: DatePriceCandidate) -> tuple[date, str, str, int]:
        return (cand.day, cand.category_id, cand.tariff_code, cand.adults_count)

    @staticmethod
    def _put_min(
        best: dict[tuple[date, str, str, int], DatePriceCandidate],
        cand: DatePriceCandidate,
    ) -> None:
        key = DatePriceSelector._key(cand)
        cur = best.get(key)
        if cur is None or cand.new_price < cur.new_price:
            best[key] = cand

