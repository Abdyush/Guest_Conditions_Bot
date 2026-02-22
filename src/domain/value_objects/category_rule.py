from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PricingMode(str, Enum):
    PER_ADULT = "PER_ADULT"
    FLAT = "FLAT"


@dataclass(frozen=True, slots=True)
class CategoryRule:
    group_id: str
    capacity_adults: int
    free_infants: int
    pricing_mode: PricingMode
