from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Iterable

from src.application.dto.period_pick import PeriodPickDTO
from src.domain.services.date_price_selector import DatePriceCandidate
from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.entities.offer import Offer
from src.domain.entities.rate import DailyRate
from src.domain.services.category_capacity import can_fit
from src.domain.services.child_supplement_policy import ChildSupplementPolicy
from src.domain.services.date_price_selector import DatePriceSelector
from src.domain.services.period_builder import PeriodBuilder
from src.domain.services.pricing_service import PricingContext
from src.application.use_cases.find_best_periods_in_group import DEFAULT_LOYALTY_POLICY
from src.domain.value_objects.category_rule import CategoryRule


def find_best_period_for_category(
    *,
    daily_rates: Iterable[DailyRate],
    offers: Iterable[Offer],
    group_rules: dict[str, CategoryRule],
    child_policies: dict[str, ChildSupplementPolicy],
    guest: GuestPreferences,
    ctx: PricingContext,
    group_id: str,
    category_name: str,
    date_from: date,
    date_to: date,
) -> PeriodPickDTO | None:
    normalized_group_id = group_id.strip().upper()
    normalized_category_name = category_name.strip()
    allowed_groups = guest.effective_allowed_groups

    category_rates = [
        rate
        for rate in daily_rates
        if rate.group_id.strip().upper() == normalized_group_id
        and rate.category_id == normalized_category_name
        and (allowed_groups is None or rate.group_id in allowed_groups)
        and rate.adults_count == guest.occupancy.adults
        and rate.is_available
        and (
            (rule := group_rules.get(rate.group_id)) is None
            or can_fit(rule, guest.occupancy)
        )
    ]
    if not category_rates:
        return None

    selector = DatePriceSelector(
        pricing=_build_pricing_service(group_rules=group_rules, child_policies=child_policies),
    )
    periods = PeriodBuilder.build(category_rates)
    best_map = selector.best_prices_by_date(
        daily_rates=category_rates,
        periods=periods,
        offers=offers,
        ctx=ctx,
    )

    lines = [
        line
        for line in best_map.values()
        if line.group_id.strip().upper() == normalized_group_id
        and line.category_id == normalized_category_name
        and date_from <= line.day <= date_to
    ]
    if not lines:
        return None

    min_round = min(line.new_price.round_rubles() for line in lines)
    candidates = [line for line in lines if line.new_price.round_rubles() == min_round]
    by_tariff: dict[str, list[DatePriceCandidate]] = defaultdict(list)
    for line in candidates:
        by_tariff[line.tariff_code].append(line)

    picks: list[PeriodPickDTO] = []
    for tariff_lines in by_tariff.values():
        tariff_lines.sort(key=lambda x: x.day)
        picks.extend(_build_period_picks(tariff_lines, group_id=normalized_group_id))

    if not picks:
        return None
    picks.sort(key=lambda x: (-x.nights, x.new_price_per_night.amount, x.start_date))
    return picks[0]


def _build_pricing_service(
    *,
    group_rules: dict[str, CategoryRule],
    child_policies: dict[str, ChildSupplementPolicy],
):
    from src.domain.services.pricing_service import PricingService

    return PricingService(
        loyalty_policy=DEFAULT_LOYALTY_POLICY,
        group_rules=group_rules,
        child_policy_by_group=child_policies,
    )


def _to_period_pick(lines, *, group_id: str) -> PeriodPickDTO:
    start_date = lines[0].day
    end_date = lines[-1].day
    nights = (end_date - start_date).days + 1
    selected = min(lines, key=lambda x: (x.new_price.amount, x.day))

    return PeriodPickDTO(
        category_name=selected.category_id,
        group_id=group_id,
        tariff_code=selected.tariff_code,
        start_date=start_date,
        end_date_inclusive=end_date,
        nights=nights,
        old_price_per_night=selected.old_price,
        new_price_per_night=selected.new_price,
        offer_title=selected.offer_title,
        offer_repr=selected.offer_repr,
        offer_min_nights=selected.offer_min_nights,
        applied_loyalty_status=selected.loyalty_status,
        applied_loyalty_percent=selected.loyalty_percent,
        applied_bank_status=selected.applied_bank_status,
        applied_bank_percent=selected.applied_bank_percent,
    )


def _build_period_picks(lines: list[DatePriceCandidate], *, group_id: str) -> list[PeriodPickDTO]:
    if not lines:
        return []

    out: list[PeriodPickDTO] = []
    current: list[DatePriceCandidate] = [lines[0]]

    for line in lines[1:]:
        if line.day == current[-1].day + timedelta(days=1):
            current.append(line)
            continue
        out.append(_to_period_pick(current, group_id=group_id))
        current = [line]

    out.append(_to_period_pick(current, group_id=group_id))
    return out
