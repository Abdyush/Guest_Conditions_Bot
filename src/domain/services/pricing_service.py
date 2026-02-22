from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain.entities.offer import Offer
from src.domain.entities.quote import Quote
from src.domain.services.child_supplement_policy import ChildSupplementPolicy
from src.domain.value_objects.bank import BankPolicy, BankStatus
from src.domain.services.period_builder import BuiltPeriod
from src.domain.value_objects.category_rule import CategoryRule, PricingMode
from src.domain.value_objects.loyalty import LoyaltyPolicy, LoyaltyStatus
from src.domain.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class PricingContext:
    booking_date: date
    loyalty_status: Optional[LoyaltyStatus] = None
    bank_status: Optional[BankStatus] = None
    children_4_13: int = 0


class PricingService:
    def __init__(
        self,
        loyalty_policy: LoyaltyPolicy,
        bank_policy: Optional[BankPolicy] = None,
        group_rules: Optional[dict[str, CategoryRule]] = None,
        child_policy_by_group: Optional[dict[str, ChildSupplementPolicy]] = None,
        category_rules: Optional[dict[str, CategoryRule]] = None,
        child_policies: Optional[dict[str, ChildSupplementPolicy]] = None,
    ):
        self._loyalty_policy = loyalty_policy
        self._bank_policy = bank_policy or BankPolicy.default()
        self._group_rules = group_rules or category_rules or {}
        self._child_policy_by_group = child_policy_by_group or child_policies or {}

    def loyalty_percent(self, loyalty_status: Optional[LoyaltyStatus]) -> Optional[Decimal]:
        if loyalty_status is None:
            return None
        return self._loyalty_policy.percent_for(loyalty_status)

    def bank_discount(self, bank_status: Optional[BankStatus]):
        if bank_status is None:
            return None
        return self._bank_policy.discount_for(bank_status)

    def price_night_loyalty_only(
        self,
        price: Money,
        *,
        ctx: PricingContext,
        group_id: Optional[str] = None,
        category_id: Optional[str] = None,
        stay_date: Optional[date] = None,
    ) -> Money:
        nightly_total = self._nightly_total(
            base_price=price,
            group_id=group_id or category_id,
            stay_date=stay_date,
            children_4_13=ctx.children_4_13,
        )
        p = self.loyalty_percent(ctx.loyalty_status)
        return nightly_total if p is None else nightly_total.percent_off(p)

    def price_period(
        self,
        period: BuiltPeriod,
        *,
        offer: Optional[Offer],
        ctx: PricingContext,
    ) -> Quote:
        nightly = [
            self._nightly_total(
                base_price=r.price,
                group_id=r.group_id,
                stay_date=r.date,
                children_4_13=ctx.children_4_13,
            )
            for r in period.rates
        ]
        total_before = self._sum(nightly)

        offer_discount = Money.zero()
        total_after_offer = total_before

        if offer is not None:
            applicable = offer.is_applicable(
                period.date_range,
                booking_date=ctx.booking_date,
                category_id=period.rates[0].category_id,
                group_id=period.rates[0].group_id,
                tariff_code=period.rates[0].tariff_code,
            )
            if applicable:
                res = offer.discount.apply(nightly)
                total_after_offer = res.total_after
                offer_discount = res.discount_amount

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

    def _nightly_total(
        self,
        *,
        base_price: Money,
        group_id: Optional[str],
        stay_date: Optional[date],
        children_4_13: int,
    ) -> Money:
        if group_id is None or stay_date is None or children_4_13 <= 0:
            return base_price

        rule = self._group_rules.get(group_id)
        if rule is None or rule.pricing_mode != PricingMode.PER_ADULT:
            return base_price

        policy = self._child_policy_by_group.get(group_id)
        if policy is None:
            return base_price

        child_amount = policy.amount_for(stay_date) * children_4_13
        return base_price + child_amount

    @staticmethod
    def _sum(values: list[Money]) -> Money:
        total = Money.zero()
        for m in values:
            total = total + m
        return total
