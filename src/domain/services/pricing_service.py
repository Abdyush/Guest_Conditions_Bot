from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain.entities.offer import Offer
from src.domain.entities.quote import Quote
from src.domain.services.period_builder import BuiltPeriod
from src.domain.value_objects.loyalty import LoyaltyPolicy, LoyaltyStatus
from src.domain.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class PricingContext:
    booking_date: date
    loyalty_status: Optional[LoyaltyStatus] = None


class PricingService:
    """
    Считает цену по ОКНУ проживания (BuiltPeriod):
    1) total_before = сумма цен ночей
    2) если offer применим сегодня (booking_date) и к этому stay — применяем offer.discount
    3) затем лояльность (B) от суммы после оффера, если:
       - loyalty_status задан
       - и (оффера нет или offer.loyalty_compatible=True)
    """
    def __init__(self, loyalty_policy: LoyaltyPolicy):
        self._loyalty_policy = loyalty_policy

    def loyalty_percent(self, loyalty_status: Optional[LoyaltyStatus]) -> Optional[Decimal]:
        """
        Нужно селекторам/юзкейсам для расчёта "только лояльность" по каждой ночи отдельно.
        """
        if loyalty_status is None:
            return None
        return self._loyalty_policy.percent_for(loyalty_status)

    def price_night_loyalty_only(self, price: Money, *, ctx: PricingContext) -> Money:
        """
        Цена одной ночи только с лояльностью (без офферов).
        """
        p = self.loyalty_percent(ctx.loyalty_status)
        return price if p is None else price.percent_off(p)

    def price_period(
        self,
        period: BuiltPeriod,
        *,
        offer: Optional[Offer],
        ctx: PricingContext,
    ) -> Quote:
        nightly = [r.price for r in period.rates]
        total_before = self._sum(nightly)

        # Offer
        offer_discount = Money.zero()
        total_after_offer = total_before
        offer_applied = False

        if offer is not None:
            applicable = offer.is_applicable(
                period.date_range,
                booking_date=ctx.booking_date,
                category_id=period.rates[0].category_id,
                tariff_code=period.rates[0].tariff_code,
            )
            if applicable:
                res = offer.discount.apply(nightly)
                total_after_offer = res.total_after
                offer_discount = res.discount_amount
                offer_applied = True

        # Loyalty (после оффера)
        loyalty_discount = Money.zero()
        total_after = total_after_offer

        if ctx.loyalty_status is not None:
            can_stack = (offer is None) or offer.loyalty_compatible
            if can_stack:
                p = self._loyalty_policy.percent_for(ctx.loyalty_status)
                total_after = total_after_offer.percent_off(p)
                loyalty_discount = total_after_offer - total_after

        return Quote(
            category_id=period.rates[0].category_id,
            tariff_code=period.rates[0].tariff_code,
            date_range=period.date_range,
            nights=period.nights,
            total_before=total_before,
            offer_discount=offer_discount,
            loyalty_discount=loyalty_discount,
            total_after=total_after,
        )

    @staticmethod
    def _sum(values: list[Money]) -> Money:
        total = Money.zero()
        for m in values:
            total = total + m
        return total