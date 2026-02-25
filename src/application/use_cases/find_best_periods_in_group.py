from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from src.application.dto.period_pick import PeriodPickDTO
from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.entities.offer import Offer
from src.domain.entities.rate import DailyRate
from src.domain.services.category_capacity import can_fit
from src.domain.services.child_supplement_policy import ChildSupplementPolicy
from src.domain.services.date_price_selector import DatePriceCandidate, DatePriceSelector
from src.domain.services.period_builder import PeriodBuilder
from src.domain.services.pricing_service import PricingContext, PricingService
from src.domain.value_objects.category_rule import CategoryRule
from src.domain.value_objects.loyalty import LoyaltyPolicy, LoyaltyStatus


DEFAULT_LOYALTY_POLICY = LoyaltyPolicy(
    {
        LoyaltyStatus.WHITE: Decimal("0.05"),
        LoyaltyStatus.BRONZE: Decimal("0.07"),
        LoyaltyStatus.SILVER: Decimal("0.08"),
        LoyaltyStatus.GOLD: Decimal("0.10"),
        LoyaltyStatus.PLATINUM: Decimal("0.12"),
        LoyaltyStatus.DIAMOND: Decimal("0.15"),
    }
)


def find_best_periods_in_group(
    *,
    daily_rates: Iterable[DailyRate],
    offers: Iterable[Offer],
    group_rules: dict[str, CategoryRule],
    child_policies: dict[str, ChildSupplementPolicy],
    guest: GuestPreferences,
    ctx: PricingContext,
    group_id: str,
    date_from: date,
    date_to: date,
    top_k: int = 5,
) -> list[PeriodPickDTO]:
    if top_k <= 0:
        return []

    filtered_rates: list[DailyRate] = []
    allowed_groups = guest.effective_allowed_groups

    for rate in daily_rates:
        if allowed_groups is not None and rate.group_id not in allowed_groups:
            continue
        if rate.adults_count != guest.occupancy.adults:
            continue
        rule = group_rules.get(rate.group_id)
        if rule is not None and not can_fit(rule, guest.occupancy):
            continue
        filtered_rates.append(rate)

    pricing = PricingService(
        loyalty_policy=DEFAULT_LOYALTY_POLICY,
        group_rules=group_rules,
        child_policy_by_group=child_policies,
    )
    selector = DatePriceSelector(pricing)
    periods = PeriodBuilder.build(filtered_rates)
    best_map = selector.best_prices_by_date(
        daily_rates=filtered_rates,
        periods=periods,
        offers=offers,
        ctx=ctx,
    )

    lines = [
        line
        for line in best_map.values()
        if line.group_id == group_id and date_from <= line.day <= date_to
    ]
    if not lines:
        return []

    min_round = min(line.new_price.round_rubles() for line in lines)
    candidates = [line for line in lines if line.new_price.round_rubles() == min_round]

    by_category_tariff: dict[tuple[str, str], list[DatePriceCandidate]] = defaultdict(list)
    for line in candidates:
        by_category_tariff[(line.category_id, line.tariff_code)].append(line)

    picks: list[PeriodPickDTO] = []
    for lines_by_key in by_category_tariff.values():
        lines_by_key.sort(key=lambda x: x.day)
        picks.extend(_build_period_picks(lines_by_key, group_id=group_id))

    picks.sort(key=lambda x: (-x.nights, x.new_price_per_night.amount, x.start_date))
    return picks[:top_k]


def _build_period_picks(lines: list[DatePriceCandidate], *, group_id: str) -> list[PeriodPickDTO]:
    if not lines:
        return []

    out: list[PeriodPickDTO] = []
    cur: list[DatePriceCandidate] = [lines[0]]

    for line in lines[1:]:
        if line.day == cur[-1].day + timedelta(days=1):
            cur.append(line)
            continue
        out.append(_to_period_pick(cur, group_id=group_id))
        cur = [line]

    out.append(_to_period_pick(cur, group_id=group_id))
    return out


def _to_period_pick(lines: list[DatePriceCandidate], *, group_id: str) -> PeriodPickDTO:
    start_date = lines[0].day
    end_date = lines[-1].day
    nights = (end_date - start_date).days + 1

    # If metadata differs inside one merged period, use the line with minimal real nightly price.
    selected = min(lines, key=lambda x: (x.new_price.amount, x.day))

    return PeriodPickDTO(
        category_name=selected.category_id,
        group_id=group_id,
        tariff_code=selected.tariff_code,
        start_date=start_date,
        end_date_inclusive=end_date,
        nights=nights,
        new_price_per_night=selected.new_price,
        offer_title=selected.offer_title,
        offer_repr=selected.offer_repr,
        offer_min_nights=selected.offer_min_nights,
        applied_loyalty_status=selected.loyalty_status,
        applied_loyalty_percent=selected.loyalty_percent,
        applied_bank_status=selected.applied_bank_status,
        applied_bank_percent=selected.applied_bank_percent,
    )
