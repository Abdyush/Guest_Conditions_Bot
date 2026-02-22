from __future__ import annotations

from dataclasses import dataclass

from src.domain.value_objects.category_rule import CategoryRule


@dataclass(frozen=True, slots=True)
class Occupancy:
    adults: int
    children_4_13: int = 0
    infants: int = 0


def can_fit(rule: CategoryRule, occupancy: Occupancy) -> bool:
    non_infant = occupancy.adults + occupancy.children_4_13
    return non_infant <= rule.capacity_adults and occupancy.infants <= rule.free_infants
