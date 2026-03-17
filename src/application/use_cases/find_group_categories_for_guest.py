from __future__ import annotations

from typing import Iterable

from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.entities.rate import DailyRate
from src.domain.services.category_capacity import can_fit
from src.domain.value_objects.category_rule import CategoryRule


def find_group_categories_for_guest(
    *,
    daily_rates: Iterable[DailyRate],
    group_rules: dict[str, CategoryRule],
    guest: GuestPreferences,
    group_id: str,
) -> list[str]:
    normalized_group_id = group_id.strip().upper()
    allowed_groups = guest.effective_allowed_groups
    categories: set[str] = set()

    for rate in daily_rates:
        if rate.group_id.strip().upper() != normalized_group_id:
            continue
        if allowed_groups is not None and rate.group_id not in allowed_groups:
            continue
        if rate.adults_count != guest.occupancy.adults:
            continue
        rule = group_rules.get(rate.group_id)
        if rule is not None and not can_fit(rule, guest.occupancy):
            continue
        if not rate.is_available:
            continue
        categories.add(rate.category_id)

    return sorted(categories)
